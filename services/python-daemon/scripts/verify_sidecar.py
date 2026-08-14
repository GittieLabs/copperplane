#!/usr/bin/env python3
"""
SPEC-401/CTX-401.1: drives a real, already-frozen daemon binary over its
real JSON-RPC stdin/stdout wire -- the same protocol core/tauri-rust's
spawn_daemon speaks -- and checks it actually works, not just that
`pyinstaller` exited 0. Not a pytest suite: freezing takes real minutes,
and this is a manual/CI packaging-verification step, not a unit test.

Keeps stdin open for the whole run rather than writing all requests and
closing it immediately -- daemon.py's job threads are daemon=True, so
main() returning (which happens right after stdin hits EOF) does not wait
for an in-flight async job to finish; closing stdin too early silently
truncates the reply CTX-401.1's own real testing already hit once.

Usage: python3 verify_sidecar.py [path/to/frozen/binary]
Exits 0 if every check that could run passed; kicad.get_version is
skipped cleanly (not failed) when no live KiCad connection is available,
matching every other real-verification test in this repo.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time

_DEFAULT_BINARY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "dist", "hardware-agent-studio-daemon",
)


def _reader_thread(pipe, q):
    for line in iter(pipe.readline, ""):
        q.put(line)
    q.put(None)  # EOF sentinel


def _next_message(q, timeout_s):
    try:
        line = q.get(timeout=timeout_s)
    except queue.Empty:
        return None
    if line is None or not line.strip():
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        print(f"  (non-JSON line on stdout, ignoring: {line.strip()!r})")
        return None


def _wait_for(q, predicate, timeout_s, label):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        msg = _next_message(q, deadline - time.monotonic())
        if msg is None:
            continue
        if predicate(msg):
            return msg
    print(f"FAIL: timed out waiting for {label}")
    return None


def main():
    binary = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_BINARY
    if not os.path.isfile(binary):
        print(f"FAIL: no frozen binary at {binary} -- build it first (pyinstaller daemon.spec)")
        return 1

    proc = subprocess.Popen(
        [binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    out_q = queue.Queue()
    threading.Thread(target=_reader_thread, args=(proc.stdout, out_q), daemon=True).start()

    failures = 0
    try:
        ready = _wait_for(out_q, lambda m: m.get("method") == "daemon.ready", 20.0, "daemon.ready")
        if ready is None:
            failures += 1
        else:
            caps = ready["params"]
            print(f"PASS: daemon.ready -- python_version={caps['python_version']}, "
                  f"kicad_available={caps['kicad_available']}, freecad_available={caps['freecad_available']}")

        if ready is not None and ready["params"]["kicad_available"]:
            proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "method": "kicad.get_version", "params": {}, "id": 1},
            ) + "\n")
            proc.stdin.flush()
            resp = _wait_for(out_q, lambda m: m.get("id") == 1, 15.0, "kicad.get_version result")
            if resp is not None and "result" in resp:
                print(f"PASS: kicad.get_version -- {resp['result']['full_version']}")
            elif resp is not None:
                print(f"FAIL: kicad.get_version returned an error: {resp.get('error')}")
                failures += 1
            else:
                failures += 1
        elif ready is not None:
            print("SKIP: kicad.get_version -- no live KiCad connection available")

        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "method": "daemon.configure",
            "params": {"secrets": {"anthropic_api_key": "sk-fake-verification-key"}}, "id": 2,
        }) + "\n")
        proc.stdin.flush()
        _wait_for(out_q, lambda m: m.get("id") == 2, 5.0, "daemon.configure result")

        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "method": "llm.chat",
            "params": {"prompt": "hi", "provider": "anthropic"}, "id": 3,
        }) + "\n")
        proc.stdin.flush()
        submitted = _wait_for(out_q, lambda m: m.get("id") == 3, 5.0, "llm.chat job submission")
        if submitted is None:
            failures += 1
        else:
            job_id = submitted["result"]["job_id"]
            final = _wait_for(
                out_q,
                lambda m: m.get("method") in ("job.completed", "job.failed")
                and m["params"].get("job_id") == job_id,
                20.0, "llm.chat job completion",
            )
            # A real auth error proves the lazily-imported AnthropicProvider,
            # its transitive httpx/anthropic SDK imports, and real TLS/certifi
            # verification all survived the freeze intact -- that's the real
            # thing this check verifies, not whether the fake key is valid.
            if final is not None and final["method"] == "job.failed" and "401" in final["params"]["error"]:
                print("PASS: llm.chat -- real HTTPS call reached Anthropic's API and got a real 401 "
                      "(the fake key was correctly rejected; the SDK stack survived the freeze)")
            elif final is not None:
                print(f"FAIL: llm.chat did not fail with a real 401 as expected: {final}")
                failures += 1
            else:
                failures += 1
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    if failures:
        print(f"\n{failures} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
