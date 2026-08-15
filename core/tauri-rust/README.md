# Hardware Agent Studio — Rust Core

The Tauri application shell: this is what actually launches, owns the Python daemon's lifecycle,
and bridges the frontend to it. See [the root README](../../README.md) for how the three layers
fit together.

## What's here

*   `main.rs` / `lib.rs` — the Tauri app entry point and the `dispatch_to_daemon` command the
    frontend's IPC client calls into.
*   `daemon.rs` — spawns the Python daemon (a real `python3 daemon.py` in dev builds, the frozen
    sidecar binary in release builds — resolved automatically, not hardcoded per build type), owns
    its stdin/stdout, and forwards JSON-RPC responses/notifications to the frontend as Tauri events.
*   `supervisor.rs` — the OS-level crash shield: Windows Job Objects / Linux `prctl` process-group
    ownership so the daemon (and anything it spawned, like a headless FreeCAD subprocess) can never
    outlive the app.
*   `secrets.rs` — real OS keychain access for LLM provider API keys — they never touch a config
    file on disk.
*   `config.rs` — the app's own persisted, non-secret configuration (provider/model selection,
    storage root, etc.).

Every module above has a real `SPEC-*.md`/`CTX-*.md` pair, mostly under the repo root's own
`specs/`/`context/` (this crate is largely cross-cutting platform work, not one product surface) —
read those for the real design reasoning, including honestly-recorded wrong predictions along the
way.

## Running it

This crate *is* the app — running it also brings up the frontend dev server and spawns the daemon
for you:

```bash
npx @tauri-apps/cli@2 dev
```

## Testing

```bash
cargo test
```

Real unit tests only — no live KiCad/FreeCAD dependency lives at this layer (that's the Python
daemon's job); this crate's own tests cover process lifecycle, config persistence, and the
daemon-invocation resolution logic (dev script path vs. release sidecar).
