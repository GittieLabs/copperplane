import inspect
import logging
import logging.handlers
import os
import platform
import sys
import json
import threading
import time
import uuid


def _default_log_dir() -> str:
    """A per-OS log directory, chosen without needing Rust to pass one in
    -- SPEC-107 §2 keeps this spec's Rust-side changes scoped to the macOS
    heartbeat signal, not a new config channel."""
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Logs")
    elif system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(base, "hardware-agent-studio")


def _configure_logging() -> None:
    """stderr is the log channel, unconditionally -- stdout is the
    JSON-RPC wire and must never carry a log line (CLAUDE.md's "stdout is
    sacred" norm). This runs before any bridge-module import below, so an
    import failure that would otherwise kill the daemon silently still
    reaches the log (SPEC-107 §2)."""
    handlers = [logging.StreamHandler(sys.stderr)]

    try:
        log_dir = _default_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, "daemon.log"), maxBytes=1_000_000, backupCount=3,
            )
        )
    except OSError:
        pass  # stderr alone is still a real log path; a read-only log dir isn't fatal.

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


_configure_logging()
logger = logging.getLogger("daemon")

try:
    import kicad_bridge
    from kicad_bridge import get_kicad_version
except Exception:
    logger.exception("kicad_bridge failed to import -- kicad.* routes will be unavailable")
    kicad_bridge = None
    get_kicad_version = None

try:
    import freecad_bridge
    from freecad_bridge import generate_enclosure
except Exception:
    logger.exception("freecad_bridge failed to import -- freecad.* routes will be unavailable")
    freecad_bridge = None
    generate_enclosure = None

# Env var Rust's spawn_daemon (CTX-106.1) sets non-secret config on --
# must match core/tauri-rust/src/config.rs's DAEMON_CONFIG_ENV_VAR. Applied
# once, at import time, before the read loop starts, so every route sees
# a fully-configured bridge module on its very first call.
_DAEMON_CONFIG_ENV_VAR = "HAS_DAEMON_CONFIG"

# In-memory config the daemon.configure route (below) fills in. Holds
# secrets Rust injects over stdin as the daemon's first-ever request --
# never written to disk, never logged (SPEC-106 §3).
CONFIG = {"secrets": {}}


def _apply_env_config() -> None:
    raw = os.environ.get(_DAEMON_CONFIG_ENV_VAR)
    if not raw:
        return

    try:
        env_config = json.loads(raw)
    except json.JSONDecodeError:
        return

    if freecad_bridge is not None:
        freecad_bridge.configure(
            path_override=env_config.get("freecadcmd_path_override"),
            output_dir=env_config.get("output_dir"),
        )
    if kicad_bridge is not None:
        kicad_bridge.configure(
            socket_path=env_config.get("kicad_socket_path"),
            timeout_ms=env_config.get("kicad_timeout_ms"),
        )


_apply_env_config()

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

def configure_daemon(secrets: dict = None) -> dict:
    """The daemon.configure route (SPEC-106 §2): merges secrets Rust hands
    over on the daemon's very first request into CONFIG. Ordinary route,
    dispatched through the normal ROUTES registry like anything else --
    Rust's spawn_daemon (CTX-106.1) is what guarantees this line reaches
    stdin before any other, not any special-casing here."""
    CONFIG["secrets"] = dict(secrets) if secrets else {}
    return {"configured": True}


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


def _build_routes() -> dict:
    """kicad.*/freecad.* are only registered if their bridge module
    actually imported (SPEC-107 §2) -- a broken kipy install shouldn't
    take down the daemon's ability to serve FreeCAD requests, or vice
    versa. A function (not a bare literal) so this registration logic is
    directly testable without needing to simulate a real import failure."""
    routes = {
        "kicad.generate_component": mock_generate_component,
        "job.cancel": cancel_job,
        "daemon.configure": configure_daemon,
    }
    if get_kicad_version is not None:
        routes["kicad.get_version"] = get_kicad_version
    if generate_enclosure is not None:
        routes["freecad.generate_enclosure"] = generate_enclosure
    return routes


# Route Registry mapping string methods to Python functions.
ROUTES = _build_routes()

# Methods that run off the read loop: a request for one of these returns
# {"job_id": ...} immediately, and the real result/failure/cancellation
# arrives later as a job.* notification (SPEC-105 §2).
ASYNC_ROUTES = {"freecad.generate_enclosure"} & ROUTES.keys()

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

# How often the heartbeat fires. Rust's macOS crash-signal path (CTX-107.1)
# treats a gap of roughly 2x this as evidence the daemon hard-crashed, not
# just that one heartbeat happened to be delayed.
_HEARTBEAT_INTERVAL_S = 5.0


def _detect_capabilities() -> dict:
    """Cheap, non-blocking checks only (SPEC-107 §3) -- SPEC-103/104 both
    connect to KiCad/FreeCAD lazily on first real use, and this probe must
    not itself pay for a slow handshake on every single startup."""
    kicad_available = False
    if kicad_bridge is not None:
        socket_path = kicad_bridge._socket_path_override or "/tmp/kicad/api.sock"
        kicad_available = os.path.exists(socket_path)

    freecad_available = False
    if freecad_bridge is not None:
        try:
            freecad_bridge.find_freecadcmd()
            freecad_available = True
        except Exception:
            freecad_available = False

    return {
        "kicad_available": kicad_available,
        "freecad_available": freecad_available,
        # SPEC-201 is the first spec with a real provider to report here.
        "llm_providers": [],
    }


def _emit_heartbeat() -> None:
    emit({"jsonrpc": "2.0", "method": "daemon.heartbeat", "params": {}})


def _heartbeat_loop() -> None:
    """Runs on its own thread, independent of request handling, so a
    long-running freecadcmd call in flight can never starve it and produce
    a false "crashed" signal on the Rust side (SPEC-107 §3)."""
    while True:
        time.sleep(_HEARTBEAT_INTERVAL_S)
        _emit_heartbeat()


def main():
    """
    The infinite event loop listening to standard input.
    """
    emit({"jsonrpc": "2.0", "method": "daemon.ready", "params": _detect_capabilities()})
    threading.Thread(target=_heartbeat_loop, daemon=True).start()

    for line in sys.stdin:
        if not line.strip():
            continue

        response = handle_request(line.strip())
        _write_line(response)

if __name__ == '__main__':
    main()
