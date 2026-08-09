import inspect
import sys
import json
import threading
import time
import uuid

from kicad_bridge import get_kicad_version
from freecad_bridge import generate_enclosure

def mock_generate_component(query):
    """
    Mock function to simulate generating a KiCad component.
    Sleeps for 1.5 seconds to simulate API/Processing delay.
    """
    time.sleep(1.5)
    return {
        "status": "success",
        "symbol_created": f"{query.upper()}_symbol.kicad_sym",
        "footprint_created": f"{query.upper()}_footprint.kicad_mod",
        "message": f"Successfully generated {query} and injected it into active KiCad schematic."
    }


class InvalidParamsError(Exception):
    """Raised when a request's params don't match the route's real signature."""


class JobNotFoundError(Exception):
    """Raised when job.cancel names a job_id that isn't (or is no longer) running."""


# Parameters a route function may declare for the daemon's own internal use
# (e.g. a per-job cancellation handle) that a client must never be able to
# supply directly over the wire.
_INTERNAL_ONLY_PARAMS = {"cancel_event"}

def cancel_job(job_id: str) -> dict:
    """Signals a running async job to cancel. Real cancellation (actually
    killing the underlying work, not just stopping its being reported on)
    is up to the route itself -- see SPEC-105 §3. This only sets the flag;
    _run_job's except branch is what turns that into a `job.cancelled`
    notification once the route's own code observes it."""
    entry = JOBS.get(job_id)
    if entry is None:
        raise JobNotFoundError(f"No such job: {job_id}")
    entry["cancel_event"].set()
    return {"job_id": job_id, "cancelling": True}


# Route Registry mapping string methods to Python functions
ROUTES = {
    "kicad.generate_component": mock_generate_component,
    "kicad.get_version": get_kicad_version,
    "freecad.generate_enclosure": generate_enclosure,
    "job.cancel": cancel_job,
}

# Methods that run off the read loop: a request for one of these returns
# {"job_id": ...} immediately, and the real result/failure/cancellation
# arrives later as a job.* notification (SPEC-105 §2).
ASYNC_ROUTES = {"freecad.generate_enclosure"}

# job_id -> {"cancel_event": threading.Event()} for every job currently
# in flight. Entries are removed once the job's worker thread finishes.
JOBS = {}

# Every stdout write (a request's response, or an async job's notification)
# must go through _write_line so two workers can never interleave partial
# writes onto the same line (SPEC-105 §3's stdout-atomicity constraint).
_stdout_lock = threading.Lock()


def _write_line(text: str) -> None:
    with _stdout_lock:
        sys.stdout.write(text + '\n')
        sys.stdout.flush()  # CRITICAL: Ensures Tauri receives the payload immediately


def emit(notification: dict) -> None:
    """Writes a JSON-RPC notification (no 'id') -- job.progress/completed/
    failed/cancelled -- through the same atomic path as a request's own
    response."""
    _write_line(json.dumps(notification))


def validate_params(method: str, params) -> None:
    """Checks `params` against the route function's real signature before
    dispatch, so a typo'd or missing key returns the JSON-RPC standard
    -32602 Invalid params instead of an opaque -32000 Server error raised
    from deep inside a TypeError (SPEC-105 §2)."""
    if not isinstance(params, dict):
        return

    sig = inspect.signature(ROUTES[method])
    accepted = set(sig.parameters.keys()) - _INTERNAL_ONLY_PARAMS
    required = {
        name for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty and name not in _INTERNAL_ONLY_PARAMS
    }

    unexpected = set(params.keys()) - accepted
    if unexpected:
        raise InvalidParamsError(f"Unexpected parameter(s): {', '.join(sorted(unexpected))}")

    missing = required - set(params.keys())
    if missing:
        raise InvalidParamsError(f"Missing required parameter(s): {', '.join(sorted(missing))}")


def _run_job(job_id: str, method: str, params: dict, cancel_event: threading.Event) -> None:
    """Runs an async route's real work on a worker thread, off the read
    loop, and reports the outcome as a job.* notification. Whether the
    underlying exception was actually a cancellation (vs. a genuine
    failure) is judged by cancel_event's own state, not by the specific
    exception type the route happened to raise -- this keeps daemon.py
    from needing to know about any one bridge module's exception classes."""
    emit({"jsonrpc": "2.0", "method": "job.progress", "params": {"job_id": job_id, "status": "running"}})

    func = ROUTES[method]
    kwargs = dict(params) if isinstance(params, dict) else {}
    if "cancel_event" in inspect.signature(func).parameters:
        kwargs["cancel_event"] = cancel_event

    try:
        result = func(**kwargs)
        emit({"jsonrpc": "2.0", "method": "job.completed", "params": {"job_id": job_id, "result": result}})
    except Exception as e:
        if cancel_event.is_set():
            emit({"jsonrpc": "2.0", "method": "job.cancelled", "params": {"job_id": job_id}})
        else:
            emit({"jsonrpc": "2.0", "method": "job.failed", "params": {"job_id": job_id, "error": str(e)}})
    finally:
        JOBS.pop(job_id, None)


def submit_job(method: str, params: dict) -> dict:
    """Starts an async route's work on a daemon worker thread and returns
    its job_id immediately -- the read loop never blocks on the route's
    actual work (SPEC-105 §2)."""
    job_id = str(uuid.uuid4())
    cancel_event = threading.Event()
    JOBS[job_id] = {"cancel_event": cancel_event}

    thread = threading.Thread(target=_run_job, args=(job_id, method, params, cancel_event), daemon=True)
    thread.start()

    return {"job_id": job_id}


def handle_request(line: str) -> str:
    """
    Parses a single JSON-RPC line, executes the routed function,
    and returns a JSON-RPC formatted response string.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        })

    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    # Validate Request Format
    if not method:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request: Missing 'method'"},
            "id": req_id
        })

    # Validate Route Exists
    if method not in ROUTES:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id
        })

    try:
        validate_params(method, params)
    except InvalidParamsError as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32602, "message": f"Invalid params: {e}"},
            "id": req_id
        })

    # Execute Route Handler
    try:
        if method in ASYNC_ROUTES:
            result = submit_job(method, params if isinstance(params, dict) else {})
        elif isinstance(params, dict):
            # Dynamically unpack params dictionary as kwargs
            result = ROUTES[method](**params)
        else:
            result = ROUTES[method]()

        return json.dumps({
            "jsonrpc": "2.0",
            "result": result,
            "id": req_id
        })

    except Exception as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": f"Server error: {str(e)}"},
            "id": req_id
        })

def main():
    """
    The infinite event loop listening to standard input.
    """
    for line in sys.stdin:
        if not line.strip():
            continue

        response = handle_request(line.strip())
        _write_line(response)

if __name__ == '__main__':
    main()
