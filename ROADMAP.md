# 🗺️ Hardware Agent Studio — Roadmap

**Status:** Draft · **Last updated:** 2026-08-12 · **Current version:** `v0.1.0` (in progress)

This document is the planning layer above the [Spec & Context framework](CONTRIBUTING.md). It
answers three questions:

1. **Where are we actually?** — an honest read of what is built versus what the README promises.
2. **What specs still need to exist?** — the full backlog, with scope, dependencies, and the
   gotchas already discovered so a future author doesn't rediscover them.
3. **How does an agent turn a spec into working code?** — the spec → context → execute loop that
   Claude Code follows in this repo.

> **Roadmap ≠ spec.** Nothing here is a commitment or a design. Each entry below is a *promise to
> write a spec*, sized so that one `SPEC-*.md` plus one-to-three `CTX-*.md` slices can carry it.
> When a spec gets written, it supersedes its entry here and this file links to it instead.

---

## 1. Where the project stands today

### 1.1 Built and recorded

| Spec | Module | Context | Status | What actually works |
| :--- | :--- | :--- | :--- | :--- |
| [SPEC-101](apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md) | `apps/tauri-ui` + `core/tauri-rust` | [CTX-101.1](apps/tauri-ui/context/CTX-101.1-ui-ipc-bridge.md) | ✅ Completed | Tauri shell boots, React frontend, `dispatch_to_daemon` string transport, daemon `stdout` → frontend events, crash shield green on all three CI runners |
| [SPEC-102](services/python-daemon/specs/SPEC-102-daemon-rpc-router.md) | `services/python-daemon` | [CTX-102.1](services/python-daemon/context/CTX-102.1-json-rpc-daemon.md) | ✅ Completed | `stdin` read loop, JSON-RPC 2.0 parse/error mapping, `ROUTES` registry |
| [SPEC-103](services/python-daemon/specs/SPEC-103-kicad-ipc.md) | `services/python-daemon` | [CTX-103.1](services/python-daemon/context/CTX-103.1-kicad-ipc.md) | ✅ Completed | `kipy` connection manager, version gate, `kicad.get_version` verified live against KiCad 10.0.3 |
| [SPEC-104](services/python-daemon/specs/SPEC-104-freecad-headless.md) | `services/python-daemon` | [CTX-104.1](services/python-daemon/context/CTX-104.1-freecad-headless-bridge.md) | ✅ Completed | `freecadcmd` path resolution, temp-script handoff, STL → GLB via `trimesh`, verified live against FreeCAD 1.1.1 |
| [SPEC-901](specs/SPEC-901-agent-operating-manual.md) | repo-wide (`.claude/`) | [CTX-901.1](context/CTX-901.1-agent-operating-manual.md) | ✅ Completed | `CLAUDE.md`, four slash commands (`/spec-status`, `/new-spec`, `/new-context`, `/close-context`), bloat guard test |
| [SPEC-903](specs/SPEC-903-python-frontend-ci.md) | `.github/workflows/` | [CTX-903.1](context/CTX-903.1-python-frontend-ci.md) | ✅ Completed | `python-ci.yml`, `frontend-ci.yml`, three-OS matrix, expected-skip verification |
| [SPEC-902](specs/SPEC-902-spec-graph-validator-v2.md) | `scripts/` | [CTX-902.1](context/CTX-902.1-spec-graph-validator-v2.md) | ✅ Completed | `validate_spec_context.py` upgraded to a full graph validator (id/location/link integrity across every `SPEC-*.md`), path-exclusion matcher fixed, 22-test suite green on all three OSes |
| [SPEC-105](specs/SPEC-105-daemon-async-job-progress-protocol.md) | `services/python-daemon` + `core/tauri-rust` + `apps/tauri-ui` | [CTX-105.1](context/CTX-105.1-daemon-async-job-protocol.md), [CTX-105.2](apps/tauri-ui/context/CTX-105.2-frontend-job-progress-client.md) | ✅ Completed | Async job dispatch + atomic `stdout` notifications + real cancellation (daemon side); frontend `JobHandle` client replacing the CTX-101.1 single-in-flight guard |
| [SPEC-106](specs/SPEC-106-configuration-secrets-store.md) | `core/tauri-rust` + `services/python-daemon` | [CTX-106.1](context/CTX-106.1-config-secrets-store.md) | ✅ Completed | Non-secret config injected as a spawn-time env var, secrets via the OS keychain handed over as the daemon's first `stdin` line; wired into `freecadcmd` path override and `kicad_bridge` connection settings |
| [SPEC-107](specs/SPEC-107-structured-logging-diagnostics.md) | `services/python-daemon` + `core/tauri-rust` | [CTX-107.1](context/CTX-107.1-structured-logging-diagnostics.md) | ✅ Completed | `stderr`/rotating-file logging, capability-aware bridge imports, `daemon.ready` startup handshake, `daemon.heartbeat` closing `CTX-101.1`'s deferred macOS crash-shield heartbeat |
| [SPEC-110](specs/SPEC-110-configurable-storage-root.md) | `core/tauri-rust` + `services/python-daemon` + `apps/tauri-ui` | [CTX-110.1](context/CTX-110.1-configurable-storage-root.md) | ✅ Completed | Revisits `CTX-304.1`'s deferred decision with real evidence: a `storage_root_override` sibling field (reusing `SPEC-106`'s override mechanism) resolved with a real `create_dir_all` attempt and safe fallback, plus a real native folder picker in Settings backed by `daemon.get_capabilities` (never `config.json`, since `storage_root` stays Rust-computed). An unplanned phase, added directly from live testing, replaces a passive "restart to apply" notice with a native confirmation modal and a real quit-and-relaunch for this one field, given the real risk of files scattering across two roots if a restart is skipped. Two real bugs found and fixed by that same live testing: a dev-mode-only relaunch artifact (root-caused, no fix needed — doesn't reproduce in a production build) and a false-positive change-detection modal on re-selecting the already-active folder. Found but explicitly not fixed: `project.json`'s `name` field can drift from its folder on disk if a user renames it — tracked as a follow-up, not squeezed in here. |
| [SPEC-301](apps/tauri-ui/specs/SPEC-301-3d-viewer.md) | `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` | [CTX-301.1](apps/tauri-ui/context/CTX-301.1-3d-viewer.md), [CTX-301.2](apps/tauri-ui/context/CTX-301.2-orbit-controls.md) | ✅ Completed | R3F viewer with GPU-disposal-on-replace, `.glb` output relocated to an app-owned directory, `assetProtocol` scoped to exactly that directory, real `OrbitControls` + a visible background (`CTX-301.2`, found by a real human click-through). Completes the `.glb`-generation → render half of M1's vertical slice — `SPEC-201`/`202`/`108`/`302` have since landed; M1's critical path is complete, see §4. |
| [SPEC-201](services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md) | `services/python-daemon` | [CTX-201.1](services/python-daemon/context/CTX-201.1-llm-provider-abstraction.md) | ✅ Completed | `llm.chat` async route wrapping AgentFlow's provider classes; verified for real against Anthropic, Google, Perplexity, and a local Ollama server — OpenAI's code path exists but is unverified (no usable key). `SPEC-202`/`108`/`302` have since landed; M1's critical path is complete, see §4. |
| [SPEC-202](services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) | `services/python-daemon` + `apps/tauri-ui` | [CTX-202.1](services/python-daemon/context/CTX-202.1-component-intelligence-pipeline.md) | ✅ Completed | `kicad.generate_component` real AgentFlow extract → validate DAG; three safety checks (pin count, pitch sanity, courtyard clearance) against a package reference table, fails closed on an unrecognized package; verified live against Anthropic for a real part (ATtiny85), and since verified again in the real native window (`ATtiny85` → `DIP-8`). `SPEC-108`/`302` have since landed; M1's critical path is complete, see §4. |
| [SPEC-108](services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md) | `services/python-daemon` + `apps/tauri-ui` | [CTX-108.1](services/python-daemon/context/CTX-108.1-kicad-write-path-footprint-injection.md), [CTX-108.3](apps/tauri-ui/context/CTX-108.3-inject-component-ui.md), [CTX-108.4](apps/tauri-ui/context/CTX-108.4-inject-confirmation-gate.md) | ✅ Completed | `kicad.inject_component` — a real `kipy` `FootprintInstance`/`Pad`/courtyard build plus a real KiCad transaction (`begin_commit`/`create_items`/`push_commit` or `drop_commit`, then `save`); live-verified against an actually-running KiCad 10.0.3 PCB Editor session (both a real SMD and a real through-hole footprint). Schematic symbol injection (this spec's other half) is deliberately deferred to `CTX-108.2` — `kipy`'s `Schematic` support needs KiCad 11, this machine has 10.0.3. `CTX-108.3` originally added a plain "Inject into Board" button, later replaced by `SPEC-302`'s chat surface (an `inject` text command, not a button). `CTX-108.4` closes the confirmation-gate gap: the `inject` command now proposes the write via `agent.dispatch_tool` (`SPEC-204`) and only actually mutates the board on an explicit **Confirm** click — real, mocked-test-verified; the one thing not yet verified is a live human click-through in the native window (no accessibility permission this session, see `native-window-verification-gap`). |
| [SPEC-109](services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md) | `services/python-daemon` + `apps/tauri-ui` | [CTX-109.1](services/python-daemon/context/CTX-109.1-parametric-enclosure-generator.md), [CTX-109.2](apps/tauri-ui/context/CTX-109.2-enclosure-tab-ui.md), [CTX-109.3](services/python-daemon/context/CTX-109.3-enclosure-floor-fix.md) | ✅ Completed | The feature `README.md` actually promises, and the first spec where `kicad_bridge` and `freecad_bridge` genuinely compose in one route: `get_board_outline`/`get_mounting_holes` read a real board's `Edge.Cuts` bounding box and recognized `MountingHole`-library holes; `generate_enclosure` builds a real hollow shell with standoff cylinders and fillets, exporting both `.glb` and a new `.step`; `freecad_generate_enclosure` closes `SPEC-304`'s `board_revision`-required Artifact schema with the first real `save_artifact` call for an enclosure (`project_name`-gated, so today's frontend contract stays unmodified). Explicit mode selection (manual dims never silently overridden by a live KiCad connection) and recognized-only standoffs (an unrecognized hole is excluded from geometry but still reported, not a build-wide failure) were both real design corrections made mid-implementation, not the spec's original framing. `CTX-109.2` wires all of this into the Enclosure tab: a "From board"/"Manual dimensions" mode toggle, real `project_name` threading so a generated enclosure is actually saved as an Artifact, and a `.step` "Open" affordance -- its own real click-through wasn't performed at the time (no screen-control tool available), flagged honestly rather than assumed equivalent to the mocked suite. That gap mattered: the user's own click-through in `CTX-109.3` found a real bug no automated geometry test had caught -- the hollow shell cut its inner cavity the *full* height starting at the floor, producing an open-both-ends tube with no floor and no lid ("a wrapper... no top or bottom"). Fixed with a real solid floor and an open top (the standard 3D-printable tray design), re-verified against real FreeCAD geometry and confirmed fixed by the user directly. |
| [SPEC-302](apps/tauri-ui/specs/SPEC-302-chat-command-surface.md) | `apps/tauri-ui` + `services/python-daemon` | [CTX-302.1](apps/tauri-ui/context/CTX-302.1-chat-command-surface.md) | ✅ Completed | Real chat & command surface — a `generate`/`inject` command recognizer plus a plain-chat fallback with real multi-turn `history`, wired to the same two already-real routes `SPEC-202`/`108` built. Two real bugs found and fixed by actually running it in the native window: a stale daemon process rejecting the new `history` param, and no LLM provider ever configured on a fresh install (`llm_chat` now falls back to a default provider). Completes M1's critical path — see §4. |
| [SPEC-303](apps/tauri-ui/specs/SPEC-303-settings-ui.md) | `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` | [CTX-303.1](apps/tauri-ui/context/CTX-303.1-settings-plumbing-and-ui.md), [CTX-303.2](apps/tauri-ui/context/CTX-303.2-generate-provider-override.md), [CTX-303.3](apps/tauri-ui/context/CTX-303.3-copy-diagnostics.md) | ✅ Completed | Real Settings UI, all three tiers: LLM provider/model/API-key management (live, no daemon restart), KiCad/FreeCAD reachability + path overrides (restart to apply), and a "Copy Diagnostics" button bundling capability flags, the daemon's real log path, and app/Python/KiCad versions to the clipboard. Registered previously-dead-code keychain commands, added `config.json`'s first-ever writer, and installed the Tauri clipboard plugin. Verified live against real Anthropic and Google keys. `CTX-303.2` fixed a real bug that verification found — `generate` had always ignored the provider picker, hardcoded to Anthropic. |
| [SPEC-304](apps/tauri-ui/specs/SPEC-304-project-library-storage.md) | `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` | [CTX-304.1](apps/tauri-ui/context/CTX-304.1-library-storage.md), [CTX-304.2](apps/tauri-ui/context/CTX-304.2-project-identity-folder-rename.md) | ✅ Completed | Real file-based storage for all six `SPEC-300` §2.1 objects (Project/Part/Symbol/Footprint/Artifact/Conversation), matching `PRODUCT-PLAN.md` §4's layout exactly, exposed via fourteen `library.*`/`project.*` daemon routes. Provenance is schema-enforced on Part, not documented as a convention; enclosure Artifacts must record `board_revision`, the one real gap the `SPEC-304` ID-collision resolution carried forward. `storage_root` resolves the inherited project-root-location question by reusing `output_dir`'s exact Rust-computed mechanism. `CTX-304.2` closes a gap `CTX-110.1` found: `load_project` now reports the real folder name a project was loaded from rather than a possibly-stale one saved inside `project.json`, so renaming a project's folder outside the app can't leave the two disagreeing. The `.index/` SQLite cache and KiCad `.kicad_sym`/`.pretty` import/export are still deliberately deferred, to a future context — not `CTX-304.2`, which ended up covering the folder-rename fix instead. |
| [SPEC-305](apps/tauri-ui/specs/SPEC-305-app-shell-navigation.md) | `apps/tauri-ui` | [CTX-305.1](apps/tauri-ui/context/CTX-305.1-app-shell.md) | ✅ Completed | The real `SPEC-300` §2 shell: a Projects rail backed by `SPEC-304`'s real storage, a Library entry, a Settings anchor, and five per-project area tabs (Overview/Components/Schematic/PCB/Enclosure), replacing `App.tsx`'s `showSettings` toggle and single floating chat surface. Overview re-houses the existing chat flow unchanged in substance, now scoped per-project and persisted via `project.load_conversation`/`append_conversation_turn`. Enclosure re-houses `EnclosurePanel`/`EnclosureViewer` unchanged. Components/Schematic/PCB render as visible-but-empty placeholders naming `SPEC-306`/`308`/`309`. Verified live in the running app via screenshots covering the empty state, Settings, all five area tabs, and the re-housed Enclosure controls. |
| [SPEC-306](apps/tauri-ui/specs/SPEC-306-component-discovery.md) | `apps/tauri-ui` + `services/python-daemon` | [CTX-306.1](apps/tauri-ui/context/CTX-306.1-component-discovery.md) | ✅ Completed | Real free-text search → ranked candidates with a confidence signal → a "did you mean" disambiguation card, replacing `SPEC-305`'s placeholder in the Components tab. A new `component_search` agent distinct from `component_extraction`; `cache_datasheet` closes the datasheet-cache gap `library_store.py` had named as unmanaged. Stops at a confirmed candidate -- pin display and `library.save_part` stay `SPEC-307`'s job. Five real bugs found and fixed across five rounds of live verification: prompt `max_tokens` truncation on Gemini, a URL-fallback prompt instruction that produced bot-blocked links, a broken default SSL cert path, an uncaught stalled-read `TimeoutError`, and confirmation blocking on a failed (not just slow) datasheet fetch -- now best-effort instead of a gate. Also wired up `tauri-plugin-shell` for real so datasheet links actually open, after discovering `"open": true` silently applies an overly narrow default regex. |
| [SPEC-307](apps/tauri-ui/specs/SPEC-307-part-detail-library-export.md) | `apps/tauri-ui` + `services/python-daemon` | [CTX-307.1](apps/tauri-ui/context/CTX-307.1-part-detail-library-export.md) | ✅ Completed | Replaces `SPEC-306`'s confirmed-candidate dead end with a real Part Detail view: a real pin table (re-running `SPEC-202`'s extraction), "Save to Library" assembling Part provenance from the search candidate + extraction call, and a real, KiCad-openable `.kicad_sym` export -- verified with `kicad-cli sym export svg`, not just plausible-looking text. Defines the Symbol record's pin/layout schema (previously undefined) with a pure auto-layout on KiCad's own real 2.54mm grid; `symbol_id` is a package+pin-count signature so identical parts converge on one Symbol. Two more real bugs found by live verification: search's `max_tokens` still occasionally truncated on longer responses (2048 → 3072), and a real extraction returned "PDIP-8," a package-name synonym `PACKAGE_REFERENCE` didn't recognize -- fixed with a generated alias for every `DIP-N` entry. Found but explicitly not fixed: exported files land in a buried, non-configurable storage path -- tracked as a new follow-up task, not squeezed in here. |

The foundation is in better shape than most projects at this stage, and two things in particular
are worth preserving as norms rather than accidents:

*   **Cross-platform CI caught real bugs.** CTX-101.1's Deviation 3 predicted the Windows path had
    never been compiled; Deviation 4 records that the first CI run found four genuine defects,
    including a `Send + Sync` violation that would have failed at `app.manage(...)`. That workflow
    exists for Rust only — extending it to Python and the frontend is tracked below (SPEC-903).
*   **"Verify for real, not just mocks."** CTX-103.1 and CTX-104.1 both ran against genuinely
    installed CAD tools and both found things mocks would have hidden: `kipy`'s
    `FutureVersionError` fires on a benign patch-version lag, and `freecadcmd -c <script>` hangs
    forever on stdin. This norm should be written into the agent operating manual (SPEC-901), not
    left to whoever happens to remember it.

### 1.2 The gap between the README and the binary

The README advertises four features. Measured honestly:

| README claim | Reality |
| :--- | :--- |
| "KiCad Bridge … interact with live PCB designs" | **Read-only.** One route exists, `kicad.get_version`. Nothing is ever written to a board. |
| "FreeCAD Bridge … generate 3D enclosures based on your PCB mounting holes" | **Half.** A parametric box is generated and converted to `.glb`. It has no mounting holes and never sees a PCB — nothing connects the KiCad bridge to the FreeCAD bridge. |
| "Local AI … plug in local Ollama models … generate symbols and footprints from datasheets" | **Not started.** The primary UI button calls `kicad.generate_component`, which is `time.sleep(1.5)` followed by fabricated filenames. There is no LLM client, no datasheet ingestion, and no supplier API in the repo. |
| "No Dangling Processes" | **True on Windows and Linux, partial on macOS.** `RunEvent::Exit` only fires on graceful quit; the Python-side heartbeat SPEC-101 calls for was deferred out of CTX-101.1 (Deviation 1) and is currently unowned. |

Also worth naming plainly: **the app cannot be given to anyone yet.** `daemon_script_path()` in
`core/tauri-rust/src/lib.rs` resolves through `env!("CARGO_MANIFEST_DIR")` — a path baked in at
compile time pointing at the developer's own checkout — and `spawn_daemon` shells out to
`python3` expecting `kipy` and `trimesh` to already be importable. A bundled `.app` or `.msi` on a
second machine will fail at startup, silently, with no error surfaced to the UI. (The doc comment
on `spawn_daemon` claims resolution happens "relative to the app's own resource directory"; the
code does not do that yet.) This is the single biggest blocker between "impressive demo" and
"product," and it is deliberately *not* on the v0.1 critical path — see §4.

### 1.3 Framework debt found while reading the repo

*   ~~`specs/SPEC-000-architecture-overiew.md` is misspelled, while every `parent_spec` in every
    child spec points at `…-overview.md`.~~ **Fixed 2026-08-07** — file renamed, links resolve.
*   ~~SPEC-102 was referenced by SPEC-000 and SPEC-101 but never written.~~ **Fixed 2026-08-07** —
    written retroactively against the shipped daemon; CTX-102.1 repointed at it.
*   ~~SPEC-000's `child_specs` omitted SPEC-103 and SPEC-104.~~ **Fixed 2026-08-07.**
*   `scripts/validate_spec_context.py` validates `CTX-*.md` only. It never opens a `SPEC-*.md`, so
    exactly the three link breakages above sailed through CI. → SPEC-902.
*   `CODE_EXTENSIONS` includes `.json`, so touching `package-lock.json` demands a context file;
    `EXCLUDE_PATHS` uses `path.startswith(...)`, so only the *root* `README.md` is exempt, not
    module READMEs. → SPEC-902.
*   The Python test suite has **never run in CI**. `rust-core-ci.yml` is scoped to
    `core/tauri-rust/**`; there is no Python or frontend workflow, so `test_daemon.py`,
    `test_kicad_bridge.py`, `test_freecad_bridge.py`, and `ipc.test.ts` are only ever green on
    Keith's Mac. → SPEC-903.
*   There is no `CLAUDE.md`. Every agent session so far has rediscovered the framework by reading
    `CONTRIBUTING.md` from scratch. → SPEC-901.

---

## 2. Spec numbering scheme

Now a permanent convention, not a roadmap detail — see [CONTRIBUTING.md](CONTRIBUTING.md), §2 "Spec ID
Numbering." The backlog below is organized by that same `1xx`/`2xx`/`3xx`/`4xx`/`9xx` layering.

---

## 3. Spec backlog

Each entry is a spec that does not exist yet. `Depends on` means the named spec must be *written*
(not necessarily fully implemented) first, because it defines a contract this one consumes.

### 3.1 `1xx` — Platform foundation

#### [SPEC-105](specs/SPEC-105-daemon-async-job-progress-protocol.md) — Daemon Async Job & Progress Protocol — ✅ done 2026-08-09
*Module:* `services/python-daemon` + `core/tauri-rust` + `apps/tauri-ui` · *Depends on:* SPEC-102, SPEC-101

[CTX-105.1](context/CTX-105.1-daemon-async-job-protocol.md) (daemon side) and
[CTX-105.2](apps/tauri-ui/context/CTX-105.2-frontend-job-progress-client.md) (frontend side) both
landed — see §1.1. Kept here for the design rationale.

The daemon is strictly serial and the frontend enforces a hard single-in-flight guard, so a
3-second `freecadcmd` cold boot or a 30-second LLM call freezes the entire UI with no feedback.
This spec should define: a job-submission response (`{"job_id": …}` returned immediately), JSON-RPC
*notifications* for progress and streamed tokens, cancellation, and how the daemon executes work
off the read loop without breaking the "one response per line, `stdout` is sacred" contract.
Also the natural home for **per-route parameter validation** — today `ROUTES[method](**params)`
turns a typo'd key into an opaque `-32000`, where it should be `-32602 Invalid params`.

*Known gotcha:* whatever concurrency model is chosen must keep `sys.stdout` writes atomic per line.
Two threads mid-write will interleave and corrupt the frame.
*Likely slices:* `CTX-105.1` job protocol + daemon worker; `CTX-105.2` frontend job/progress client
replacing the single-in-flight guard.

*AgentFlow interaction (see §3.2's decision):* AgentFlow's `EventBus` already emits
`NODE_STARTED`/`NODE_COMPLETED`/`LLM_CALL_STARTED`/`LLM_CALL_COMPLETED`/`TOOL_CALLED`/`TOOL_RESULT`/
`ERROR` (plus custom events) for exactly the kind of progress reporting this spec needs once
SPEC-201/202/204 land. That's the likely mechanism for the progress/streaming half of this spec —
don't invent a second event system alongside it. Whether `EventBus` events get forwarded as JSON-RPC
notifications directly or need a translation layer is this spec's own call, made once AgentFlow is
actually wired in, not before.

#### [SPEC-106](specs/SPEC-106-configuration-secrets-store.md) — Configuration & Secrets Store — ✅ done 2026-08-09
*Module:* `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-102

[CTX-106.1](context/CTX-106.1-config-secrets-store.md) landed — see §1.1. Kept here for the design
rationale, including the open question below, which this context resolved.

One place for: `freecadcmd` path override (SPEC-104 §3 explicitly asks for this), KiCad IPC
settings, selected LLM provider and model, and supplier API keys. Keys must go to the OS keychain,
not a plaintext JSON file — and must never be passed as command-line arguments to the daemon, where
they'd be visible in `ps`.

*Open question, resolved by `CTX-106.1`:* does Rust own config and inject it into the daemon at
spawn, or does the daemon read the config file itself? **Decided: Rust owns it, injects at spawn**
— non-secret settings as an env var, secrets as a `daemon.configure` request written as the first
line on the daemon's `stdin`. Keeps secrets out of Python's memory longer; costs a daemon restart
(already cheap) to pick up a changed setting.

#### [SPEC-107](specs/SPEC-107-structured-logging-diagnostics.md) — Structured Logging, Startup Handshake & Diagnostics — ✅ done 2026-08-09
*Module:* all three · *Depends on:* SPEC-102

[CTX-107.1](context/CTX-107.1-structured-logging-diagnostics.md) landed — see §1.1. Kept here for
the design rationale.

`stdout` is reserved for JSON-RPC frames, so **any** stray `print()` or library banner corrupts the
stream and produces a request that hangs forever with no error. This spec defines `stderr` as the
log channel, a rotating log file, and a `daemon.ready` startup handshake reporting detected
capabilities (KiCad present? FreeCAD present? which LLM providers reachable?).

*Why this matters more than it looks:* today, if `import kipy` fails, `daemon.py` dies before its
read loop starts, Rust sees a child that exited instantly, and the user sees a UI that simply never
responds. There is no path for that failure to reach a human.

#### SPEC-108 — KiCad Write Path: Footprint & Symbol Injection — ✅ done (footprint half) 2026-08-10
*Module:* `services/python-daemon` · *Depends on:* SPEC-103, SPEC-202

[CTX-108.1](services/python-daemon/context/CTX-108.1-kicad-write-path-footprint-injection.md)
landed — see §1.1. Kept here for the design rationale. Schematic symbol injection (this spec's
other half) is deliberately deferred to a future `CTX-108.2`: `kipy`'s `Schematic` support needs
KiCad 11, and no machine available to this project runs it yet.

The follow-through CTX-103.1 explicitly deferred: taking a structured component definition and
injecting a real `.kicad_mod` into the open board. Needs to cover placement coordinates,
transactions/undo grouping (a half-applied footprint is worse than none), library vs. board-local
footprints, and what happens when the user has unsaved changes.

*Known gotcha:* CTX-103.1's `FutureVersionError`-as-warning decision is untested against a real
breaking protocol change. Write operations are where that assumption gets expensive — a read that
returns garbage is annoying, a write that corrupts a board is not.

#### [SPEC-109](services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md) — Parametric Enclosure Generator — ✅ done 2026-08-13
*Module:* `services/python-daemon` · *Depends on:* SPEC-104, SPEC-108

The feature the README actually promises: read board outline and mounting-hole positions **from
KiCad**, feed them to FreeCAD, get an enclosure that fits. This is the first spec where the two
bridges talk to each other, and it's where the product stops being two disconnected toys.

Scope: board outline extraction, hole positions, wall thickness/tolerance/standoff parameters,
fillets, and STEP export alongside `.glb` so the result is usable in real mechanical CAD.

#### SPEC-111 — Enclosure Lid & Component-Height Clearance
*Module:* `services/python-daemon` · *Depends on:* SPEC-109, SPEC-202

Real user feedback exercising the shipped enclosure generator: `SPEC-109` only ever builds an
open-top tray (its own §1 Non-Goals rule out lid/fastener hardware) sized from a board's *bounding
box*, not its real outline — both the live IPC path (`kicad_bridge.get_board_outline`) and the
file-based path (`kicad_pcb_import.extract_board_outline`) reduce the real Edge.Cuts polygon down
to a rectangle before it ever reaches FreeCAD. Two real, related gaps worth addressing eventually,
neither attempted here:

1.  **A real lid, not just a bottom shell.** Needs the enclosure's own interior height to clear
    every placed component's real body height, not just the board's flat 2D outline — today's
    pipeline has no per-component Z-height data at all (`SPEC-202`'s extraction doesn't currently
    capture component body height; `library_store`'s own Part schema would need it).
2.  **A true polygon-traced shell, not a rectangular bounding box**, for a genuinely
    non-rectangular board — real OpenCASCADE work (extrude an arbitrary closed wire, offset it
    inward by wall thickness for the shell, handle concave sections at each corner), not a small
    tweak to the existing `Part.makeBox` boolean-cut script.

Neither is a quick fix — both need real design work (what "component height" means for a part with
no 3D model at all; how a non-rectangular offset behaves at a concave corner) before
implementation, which is exactly why this is a backlog entry, not a context.

### 3.2 `2xx` — Intelligence layer

**Decision (2026-08-08): the AI runtime for this layer is [AgentFlow](https://github.com/GittieLabs/agentflow)
(`gittielabs-agentflow` on PyPI, MIT, our own library) — a context-engineering framework for
multi-agent systems: `.prompt.md`/`.workflow.md`/`.context.md` definitions, a `ConfigLoader`,
`RouterEngine`, `WorkflowExecutor` (DAG, sync/parallel/async nodes, handler nodes, `foreach`), a
`ToolRegistry` with local and HTTP dispatchers, `SessionManager`/`MemoryManager`, pluggable
providers (Anthropic / OpenAI-compatible / Google / Mock), an `EventBus`, and Langfuse telemetry.
This replaces most of what SPEC-201/202/204 were originally scoped to build from scratch — see each
entry below for what survives as this product's own work.**

**This decision is scoped to the application only.** AgentFlow has no role in the development
workflow this repo uses to build itself. Claude Code stays vanilla, and `SPEC-901` (§3.5) must not
gain an AgentFlow dependency. The two `context/` concepts — AgentFlow's tree of agent/workflow
definitions, and this repo's own `CTX-*.md` implementation-plan files — are unrelated and must not
be blurred; see the open question below about where AgentFlow's tree actually lives on disk.

#### [SPEC-201](services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md) — LLM Provider Abstraction — ✅ done 2026-08-09
*Module:* `services/python-daemon` · *Depends on:* SPEC-102, SPEC-106, SPEC-105

[CTX-201.1](services/python-daemon/context/CTX-201.1-llm-provider-abstraction.md) landed — see
§1.1. Kept here for the design rationale, including both open questions below, which this context
resolved.

Collapses to adopting AgentFlow's provider layer: `AnthropicProvider`, `OpenAICompatProvider`
(covers OpenAI, Azure, **and Ollama** — Ollama rides the OpenAI-compatible provider, not a bespoke
client), `GoogleGenAIProvider`, and `MockLLMProvider` for tests. AgentFlow already solves streaming,
the provider protocol, and per-agent model selection in `.prompt.md` front-matter; there is no
reason to write a second one.

What actually survives as this spec's own work: the model-selection UI/config surface, and a clear,
written statement of what leaves the machine under each provider configuration. The "Local AI
(Privacy First)" promise from the README is a data-egress claim, not a code interface — AgentFlow
picks the provider you configure, it doesn't make privacy guarantees for you.

*Constraint inherited from SPEC-000 §3:* heavy provider SDK imports block `stdout` for 2–4 seconds
at startup. Prefer lazy import of provider clients so the daemon's `ready` handshake isn't delayed
by a provider the user never selected.

#### [SPEC-202](services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) — Component Intelligence Pipeline — ✅ done 2026-08-09
*Module:* `services/python-daemon` · *Depends on:* SPEC-201

[CTX-202.1](services/python-daemon/context/CTX-202.1-component-intelligence-pipeline.md) landed —
see §1.1. Kept here for the design rationale.

[Its own spec](services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) drops the
`SPEC-203` dependency listed here — a real contradiction with §4's explicit "SPEC-203 is out of
M1" and the M1 diagram, which never routes through it. This spec's M1-scoped pipeline is LLM-only
extraction, permanently, not a degraded mode of a supplier-augmented pipeline that doesn't exist
yet; `SPEC-203` becomes an optional future enhancement, never a hard prerequisite.

Still the heart of the product, and still the thing that replaces the `time.sleep(1.5)` mock — but
the *orchestration* changes. Datasheet or part number in → validated structured component (pins,
numbers, names, electrical types, package dimensions, courtyard) out, expressed as an AgentFlow
`.workflow.md` DAG: an agent node does the LLM extraction, a handler node (deterministic Python, no
LLM call — see AgentFlow's handler-node mechanism) does the schema/geometry validation, connected
through `inputs` mappings instead of bespoke glue code. The structured schema is still the contract
SPEC-108 consumes.

What AgentFlow does **not** supply, and what remains this spec's real substance: the validated
component schema itself, and the specific checks that stop a hallucinated footprint from reaching a
board (pin count matches the package, pitch is sane, courtyard encloses pads) — before anything
reaches a board. That is domain logic particular to this product; no framework ships it. A
hallucinated footprint that looks plausible costs a PCB spin — this is still the
highest-consequence failure mode in the product, and it still deserves its own section in the spec.

#### SPEC-203 — Supplier API Integration
*Module:* `services/python-daemon` · *Depends on:* SPEC-106

DigiKey / Octopart / Mouser: authentication, rate limits, a local cache (part data barely changes;
re-querying on every request wastes quota and adds latency), and graceful degradation to
LLM-only extraction when no key is configured or the user is offline. Unaffected by the AgentFlow
decision — this is a plain HTTP integration, not an LLM-orchestration concern.

#### [SPEC-204](services/python-daemon/specs/SPEC-204-agent-tool-registry.md) — Agent Tool Registry — ✅ Completed ([CTX-204.1](services/python-daemon/context/CTX-204.1-agent-tool-registry.md)) 2026-08-14
*Module:* `services/python-daemon` · *Depends on:* SPEC-201, SPEC-102

Replaced the daemon's hand-rolled `ROUTES` dict thinking with AgentFlow's real `ToolRegistry`,
registering `kicad.inject_component`, `freecad.generate_enclosure`, `kicad.generate_component`, and
`component.search` via `ToolRegistry.add_tool()` — never `LocalToolDispatcher`, which silently
swallows handler exceptions into strings (a real, verified difference between AgentFlow's two
registration paths, not a documentation nuance). New `agent.dispatch_tool` JSON-RPC route is the
real entry point, reusing `SPEC-105`'s existing async job protocol directly rather than reinventing
job tracking.

The confirmation-gating policy this spec's own job was to define — **`kicad.inject_component` stays
confirmation-gated by default, full stop** — landed as an explicit `confirmed` flag the tool's own
wrapper checks: an unconfirmed call returns a pending result with zero side effects; only a
confirmed re-call actually mutates the board. Every other registered tool (reads, or writes only to
this app's own local storage) auto-executes.

**A real correction along the way, worth flagging here too:** this spec's own first draft assumed
AgentFlow needed two upstream fixes (structured tool results, exception propagation) before this
work could start. Verified with real scripts against the installed library before writing any
AgentFlow code — neither gap existed. No AgentFlow commit, version bump, or PyPI release happened;
`SPEC-204` §§1-3 were corrected in place same-day. See `CTX-204.1`'s Plan Drift for the full account.

**Still not done:** no `AgentExecutor` conversation loop actually calls this registry yet — a model
deciding which tool to call from open-ended natural language (`"put a BME280 near the ESP32..."`)
is real, unstarted follow-up work, not something this spec claimed to finish. The UI side of the
confirmation gate is done, though: `CTX-108.4` (2026-08-14) wired the chat surface's `inject`
command through `agent.dispatch_tool`, so it now proposes and requires an explicit **Confirm**
before actually writing to the board.

*Note:* SPEC-000 §1 explicitly rules out MCP as the transport, for good reasons (binary `.glb`
streaming, bespoke UI rendering). That decision is about the *wire protocol*; AgentFlow's own tool
schema shape (`name`/`description`/`input_schema`) already resembles MCP's tool-description
conventions closely enough that no separate borrowing decision is needed here.

#### Open questions for this layer — both resolved by `SPEC-201`/`CTX-201.1`

*   **Where does AgentFlow's `context/` tree live inside `services/python-daemon`?** AgentFlow
    expects a directory of `agents/`, `workflows/`, `domains/`, `shared/` — but
    `services/python-daemon/context/` already means something else in this repo (`CTX-*.md`
    implementation plans, per `CONTRIBUTING.md` §3). **Decided:** `services/python-daemon/agentflow/`
    — not created yet, since `CTX-201.1` calls AgentFlow's provider classes directly, not its
    `ConfigLoader`/`RouterEngine`/`.prompt.md` system; the directory becomes real once `SPEC-202`
    defines actual per-task prompts.
*   **Does AgentFlow's session/memory layer (`SessionManager`, `Scratchpad`, `ArtifactStore`,
    `MemoryManager`) replace the daemon's own state, or sit beside it?** **Decided: neither, yet.**
    `SPEC-201`/`CTX-201.1` adopt none of it — a single LLM call per request needs no session state,
    matching M1's actual demo shape. Whether `SPEC-202`'s pipeline needs it is that spec's own call
    once it actually needs multi-step orchestration.

### 3.3 `3xx` — Product surface

**Superseded by [PRODUCT-PLAN.md](PRODUCT-PLAN.md), approved 2026-08-11, for everything from
SPEC-300 onward.** Its own §5.2 re-scopes SPEC-301/302; its §5.1 adds SPEC-300/304-310. The four
entries below are kept for historical record, not as the current backlog — read PRODUCT-PLAN.md
§5 before picking up any 3xx work. The SPEC-304 ID conflict this section originally flagged was
resolved 2026-08-11 (see that entry). SPEC-303 is now written but still isn't addressed by the plan
— its own spec names the open shell-entry-point question rather than resolving it here. That
question is resolved now: `SPEC-305` (see §1.1) builds the real shell and anchors Settings behind
the rail, exactly where `SPEC-300` §2 already said it would go.

#### [SPEC-301](apps/tauri-ui/specs/SPEC-301-3d-viewer.md) — 3D Viewer — ✅ done 2026-08-09
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-104, SPEC-105

[CTX-301.1](apps/tauri-ui/context/CTX-301.1-3d-viewer.md) landed — see §1.1. Kept here for the
design rationale, including the asset-loading gotcha below, which this context resolved.

SPEC-101 names React Three Fiber, but nothing renders today — `freecad.generate_enclosure` returns
a `.glb` path that the UI simply never opens. Scope: R3F canvas, camera/lighting defaults that make
a grey box legible, loading and error states, and disposal on unmount (leaking GPU buffers across
repeated generations is the standard Three.js failure).

*Known gotcha, resolved by `CTX-301.1`:* the `.glb` was written to the system temp directory, and
`tauri.conf.json` configured no `assetProtocol` scope at all. **Decided: scope the asset protocol
to the daemon's own output directory** (not a Rust-mediated blob read) — `.glb` output moved to
`<app_data_dir>/generated`, `assetProtocol.scope` narrowed to exactly that directory, and the
frontend loads it via `convertFileSrc()`.

#### [SPEC-302](apps/tauri-ui/specs/SPEC-302-chat-command-surface.md) — Chat & Command Surface — ✅ done 2026-08-11
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-105, SPEC-201

`App.tsx` is one input, one button, and a `<pre>` dump of raw JSON. The README's framing — "type
'Generate a footprint for BME280'" — implies a conversation: message history, per-message error
states, and inline `.glb` previews. Its own spec resolves two things this blurb used to promise
that turned out not to be real, checked directly against the installed `gittielabs-agentflow==0.8.2`
source rather than assumed: no provider supports real token streaming today (explicit non-goal),
and no agentic tool-calling exists either (`SPEC-204`'s job, out of M1) — a small, explicit
`generate`/`inject` command recognizer wraps the same two already-real routes instead.

**Re-scoped by `PRODUCT-PLAN.md` §5.2 → Project Conversation.** The command-parsing half
(`parseCommand` in `apps/tauri-ui/src/lib/commands.ts`) is deleted, not improved — it's the
mechanism that produced the reported bug. The chat half survives intact and moves into the
Overview area. `CTX-302.x` should record this as Plan Drift when the re-scope is actually
implemented.

**Re-scope partially shipped.** `CTX-305.1` moved the chat half into a per-project Overview area
(see §1.1's `SPEC-305` row) exactly as described above. `parseCommand` itself is still not deleted —
`CTX-305.1`'s own Plan Drift names this explicitly as inherited, unresolved debt, matching
`SPEC-305` §3's own named issue.

#### [SPEC-303](apps/tauri-ui/specs/SPEC-303-settings-ui.md) — Settings UI — ✅ done 2026-08-12
*Module:* `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-106,
SPEC-107, SPEC-201

The surface for SPEC-106, plus the diagnostics panel SPEC-107 makes possible: is KiCad reachable,
is its IPC server enabled, where is `freecadcmd`, which model is selected, and a one-click "copy
diagnostics" for bug reports. The single highest-leverage thing for reducing "it doesn't work"
issues from contributors. Its own spec found this isn't purely a frontend surface — `set_secret`/
`delete_secret` exist in Rust but were never registered as Tauri commands, there is no `config.json`
*writer* at all, and `daemon.ready`'s `llm_providers` field is hardcoded to `[]`.

**Resolved by `SPEC-305`.** The plan's §5 spec list and §5.3 "Unaffected" section still don't
mention SPEC-303 by name, but the open question SPEC-303 §1/§3 named — where Settings anchors in
SPEC-300's shell model — is answered now: `SPEC-305`/`CTX-305.1` anchor it at the bottom of the
rail, exactly where `SPEC-300` §2 said it would go.

#### [SPEC-304](apps/tauri-ui/specs/SPEC-304-project-library-storage.md) — Project & Library Storage — ✅ done (schemas + file I/O) 2026-08-12
*Module:* `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-300

See §1.1 above for what actually shipped (`CTX-304.1`). The `.index/` SQLite cache and KiCad
`.kicad_sym`/`.pretty` import/export named below are still open, tracked as `CTX-304.2`.

**ID conflict from the original `PRODUCT-PLAN.md` sync (PR #44) resolved 2026-08-11: absorbed, not
renumbered.** This entry used to read "Project & Workspace Model" (binding a session to a KiCad
project on disk, artifact placement, enclosure-revision tracking), a different scope than
`PRODUCT-PLAN.md` §5.1's `SPEC-304 Project & Library Storage` under the same ID. On inspection the
two turned out to be ~90% the same concern: the plan's `project.json` (KiCad project link,
component refs) and `projects/*/artifacts/` layout already cover "which board" and "artifacts next
to the project, not `/tmp`." The one real gap — **enclosure revisions tracked alongside board
revisions** — didn't exist in the plan's storage section and is carried forward here as a named
requirement for this spec's Artifact schema, not dropped. No renumbering was needed; this replaces
the old entry rather than sitting beside it.

Scope, per `PRODUCT-PLAN.md` §4/§5.1: the file-based storage layout (`library/parts|symbols|
footprints|datasheets/`, `projects/<name>/{project.json, conversation.jsonl, artifacts/}`,
a rebuildable `.index/` SQLite cache — never authoritative), the Project/Part/Symbol/Footprint/
Artifact schemas from `SPEC-300` §2.1 (provenance required per §2.2), index rebuild-on-stale-check,
and import/export to KiCad's own `.kicad_sym`/`.pretty` library formats.

**Dependency change worth naming explicitly, not just cosmetic:** the old entry depended on
`SPEC-108`/`SPEC-109` ("deferrable until there's something worth persisting"); this one depends on
`SPEC-300` only. That means the schema and index can be written before `SPEC-109`
(enclosure-from-geometry) exists — the schema doesn't need `SPEC-109` done, only to eventually
produce `Artifact`s it stores.

### 3.4 `4xx` — Distribution & operations

#### [SPEC-401](specs/SPEC-401-python-sidecar-packaging.md) — Python Sidecar Packaging — ✅ Completed ([CTX-401.1](context/CTX-401.1-python-sidecar-macos.md), [CTX-401.2](context/CTX-401.2-tauri-sidecar-wiring.md)) 2026-08-14
*Module:* `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-107

**The highest-risk unsolved problem in the project — now solved for macOS, this spec's own scope.**
Two concrete blockers, both quoted in the spec itself: `env!("CARGO_MANIFEST_DIR")` bakes the
developer's checkout path into the binary, and `Command::new("python3")` assumes a system Python
with `kipy`, `pynng`, `trimesh`, and `gittielabs-agentflow` (already a real, shipped dependency
since `SPEC-201` — not a future addition, corrected in the spec's own §2) all importable.

`CTX-401.1` landed the first real slice: a working, committed, verified macOS PyInstaller freeze of
the daemon itself, driven directly over its real JSON-RPC wire (a real `kicad.get_version` round
trip, a real HTTPS call to Anthropic's API). Found and corrected a real wrong prediction along the
way — no `--hidden-import` declarations were needed for AgentFlow's lazily-imported provider SDKs,
contrary to what this spec originally predicted.

`CTX-401.2` finished the wiring: a dev/release-branched daemon-invocation resolver, real
`externalBin` sidecar config (scoped to macOS via `tauri.macos.conf.json` after a genuinely
CI-breaking discovery — a top-level `externalBin` entry makes `tauri-build`'s own build.rs require
the resource file on *every* `cargo build`/`cargo test`, not just bundling, which broke all three CI
platforms until scoped), and end-to-end verification against a real built `.app` bundle, including
the user directly click-testing the running dev-mode app afterward. `SPEC-101`'s crash shield was
left untouched, as designed. Windows/Linux freezing remains real, explicitly out-of-scope follow-up
(`SPEC-403`).

#### [SPEC-402](specs/SPEC-402-release-signing-and-auto-update.md) — Release, Signing & Auto-Update
*Module:* repo-wide · *Depends on:* SPEC-401

**Rescoped 2026-08-16: unsigned first, deliberately.** A real macOS-only release pipeline (unsigned
`.dmg` via GitHub Actions, a real Gatekeeper-bypass doc), the Tauri auto-updater (its own real,
maintainer-generated keypair — no OS-level code-signing certificate, no cost, no identity tied to
one person), and a changelog derived from the `CTX-*.md` implementation logs — which the framework
already collects, and which nothing currently reads. Code signing/notarization is explicitly
deferred: it requires either a personal Apple/Windows identity tied to releases indefinitely, or a
real *organization* account under a project entity (GittieLabs, if it becomes the enrolled entity)
— a real, separate, future decision this spec doesn't make. Windows/Linux builds wait on
`SPEC-403`'s own cross-platform verification, which hasn't happened.

#### SPEC-403 — Cross-Platform Verification Matrix
*Module:* repo-wide · *Depends on:* SPEC-903

Every live CAD test to date has run on exactly one machine: Keith's Mac, with KiCad 10.0.3 and
FreeCAD 1.1.1. Both CTX-103.1 and CTX-104.1 say so explicitly. This spec defines how the live paths
get exercised on Windows and Linux — self-hosted runners with real CAD installs, a documented
manual checklist, or containerized KiCad. Until then, "works on Windows" is an untested claim about
the two most fragile integration points in the codebase.

### 3.5 `9xx` — The framework itself

**All three done as of 2026-08-08.** SPEC-901/CTX-901.1, SPEC-903/CTX-903.1, and SPEC-902/CTX-902.1
are all merged and `Completed` — see §1.1. Kept here for the design rationale each spec still
records.

#### [SPEC-901](specs/SPEC-901-agent-operating-manual.md) — Agent Operating Manual & Context Generation Protocol
*Module:* repo-wide · *Depends on:* nothing — **start here**

[CTX-901.1](context/CTX-901.1-agent-operating-manual.md) landed `CLAUDE.md` and the four slash
commands (`/spec-status`, `/new-spec`, `/new-context`, `/close-context`). See §5 below for the
workflow it formalizes.

**AgentFlow-free, deliberately.** §3.2 adopts AgentFlow as the AI runtime for the *application*.
This spec is not the application — it's the development process used to build it — and stays
vanilla. Claude Code itself, `CLAUDE.md`, and the four slash commands must never gain an AgentFlow
dependency. Keeping the two clearly separated is the point; don't blur them because both happen to
involve "agents" and "context" files.

#### SPEC-902 — Spec Graph Validator v2
*Module:* `scripts/` · *Depends on:* SPEC-901

[CTX-902.1](context/CTX-902.1-spec-graph-validator-v2.md) upgraded `validate_spec_context.py` from
a context linter into a graph validator: parses `SPEC-*.md` frontmatter too, verifies every
`parent_spec` / `child_specs` / `spec_ref` path resolves on disk, checks id uniqueness and that
`id` matches the filename, flags orphan specs and specs with no context, and checks that
`location:` matches the file's actual path. Every one of the §1.3 breakages is now mechanically
detectable. Also fixed the `.json`-lockfile exclusion bug noted there (the `README.md` claim turned
out not to reflect a live bug — see CTX-902.1's Plan Drift).

#### SPEC-903 — Python & Frontend CI
*Module:* `.github/workflows/` · *Depends on:* nothing

[CTX-903.1](context/CTX-903.1-python-frontend-ci.md) added `python-ci.yml` (uv matrix over three
OSes running `python -m unittest discover tests/`, with expected-skip verification for the live
CAD tests) and `frontend-ci.yml` (`vitest` plus `oxlint` plus `tsc -b`), following the pattern
`rust-core-ci.yml` already established.

---

## 4. Milestones

### M0 — Framework repair *(days, do first)* — ✅ complete as of 2026-08-08
Unblocked everything else and made the repo safe for parallel agent work.

| # | Work | Spec |
| :--- | :--- | :--- |
| 1 | ~~Fix spec graph links, write SPEC-102~~ ✅ done 2026-08-07 | — |
| 2 | ~~Agent operating manual + context-generation commands~~ ✅ done 2026-08-08 | SPEC-901 |
| 3 | ~~Python & frontend CI~~ ✅ done 2026-08-08 | SPEC-903 |
| 4 | ~~Validator v2~~ ✅ done 2026-08-08 | SPEC-902 |
| 5 | ~~Merge `feat/CTX-103.1-*` and `feat/CTX-104.1-*` into `develop`; move both CTX files Review → Completed~~ ✅ done 2026-08-08 | — |

### M1 — `v0.1.0` "It's real" — the end-to-end vertical slice
**Goal:** type a part number, watch an AI generate a real footprint, see it land in a live KiCad
board, get an enclosure sized to it, and rotate that enclosure in the app. One journey, working,
on a dev machine.

Critical path, in dependency order:

```text
SPEC-105 (async jobs & progress) ✅ ─┬─> SPEC-201 (LLM provider) ✅ ──> SPEC-202 (component pipeline) ✅ ──> SPEC-108 (KiCad injection) ✅
SPEC-106 (config & secrets) ✅       ─┘                                                                            │
SPEC-107 (logging & handshake) ✅     ─────────────────────────────────────────────────────────────────────────────┤
SPEC-301 (3D viewer) ✅ ──────────────────────────────────────────────────────────────> SPEC-302 (chat surface) ✅ ─┴─> demo ✅
```

SPEC-105 comes first because without it the UI locks up for the entire duration of every AI call,
which makes the demo unwatchable regardless of how good the generation is. SPEC-301 has no
dependency on the AI work and can run fully in parallel — the `.glb` pipeline already produces
valid output today.

**M1 is complete as of `CTX-302.1`'s merge.** All eight critical-path nodes are done, closed out
2026-08-12 alongside three other contexts that had been merged but never flipped past `Review`
(`CTX-901.2`, `CTX-303.1`, `CTX-303.2`) — a real, if small, instance of exactly the closeout-hygiene
gap this repo's own framework exists to catch mechanically where it can and via `/spec-status`
where it can't. SPEC-201's own two open questions (§3.2) are resolved. Real gaps found while
device-testing the shipped pieces, all closed the same way — by a human actually using the surface,
not just its capability tests passing: `EnclosureViewer` gained real `OrbitControls` plus a visible
background (`CTX-301.2`); `kicad.inject_component` (`SPEC-108`) gained a plain "Inject into Board"
button (`CTX-108.3`); the chat surface (`SPEC-302`) had two real bugs (a stale daemon rejecting a
new param, no LLM provider ever configured) found and fixed the same session it shipped
(`CTX-302.1`).

**Explicitly out of M1:** packaging (SPEC-401), enclosure-from-board-geometry (SPEC-109), supplier
APIs (SPEC-203), agent tool-calling (SPEC-204). M1 proves the product is possible; it does not
produce something installable.

### M2+ — see [PRODUCT-PLAN.md](PRODUCT-PLAN.md) §6

**Superseded 2026-08-11.** `PRODUCT-PLAN.md`'s own frontmatter states it supersedes this section;
its §6 M2 ("Shell, Projects, Components") through M5 ("Enclosure from geometry, then ambition")
replace the M2/M3 originally described here, kept below for historical record.

**Not carried forward, and not yet re-slotted anywhere — flagged, not resolved.** The original M2
below was packaging/signing/cross-platform verification (SPEC-401/402/403). `PRODUCT-PLAN.md` §5.3
("Unaffected") doesn't mention distribution at all, and its M2-M5 sequence has no room for it either.
This is a real gap, not a decision to drop packaging — SPEC-401 landed for macOS (CTX-401.1,
CTX-401.2, 2026-08-14), so this is no longer the highest-risk unsolved problem §1.2 once called it,
but SPEC-402 (signing/auto-update) and SPEC-403 (Windows/Linux verification) are still real,
unstarted work with no milestone right now. Needs a home once the product-model milestones are far
enough along to package, or its own milestone number.

<details>
<summary>Original M2/M3 (superseded, kept for record)</summary>

### M2 — `v0.2.0` "It ships"
SPEC-401 packaging, SPEC-106/303 settings and diagnostics surfaced, SPEC-107 logging, SPEC-402
signing and updates, SPEC-903/403 verification on Windows and Linux. This is the milestone where
the `.app` works on a machine that has never seen the repo.

### M3 — `v0.3.0` "It's an agent"
SPEC-204 tool-calling, SPEC-203 supplier data, SPEC-109 enclosures derived from real board
geometry, SPEC-304 workspace model. The point where "Hardware Agent Studio" earns the middle word.

</details>

---

## 5. The Claude Code loop: spec → context → execute

This is the workflow SPEC-901 formalizes. It is written down here because it's the reason the
roadmap exists in this shape — every backlog entry above is sized to be one pass through this loop.

### 5.1 The loop

```text
ROADMAP.md entry
      │  human picks the next item and approves scope
      ▼
  SPEC-xxx.md          ← the What and Why. Stable. Rarely edited after approval.
      │  agent derives an execution plan
      ▼
  CTX-xxx.1.md         ← the How and When. Phases, testing matrix, branch name.
      │  agent implements phase by phase, committing as it goes
      ▼
   code + tests        ← test paths must match the matrix exactly; CI enforces it
      │  agent records commit hashes, flips status, writes Plan Drift
      ▼
  CTX closed → PR      ← validator gate, then merge to develop
      │
      └─> anything learned that contradicts the spec is written back into the SPEC
```

### 5.2 What the agent tooling needs to provide

*   **`/spec-status`** — walk the spec graph from SPEC-000, report which specs have no context,
    which contexts are open, and which roadmap items are unspecced. The map the agent reads before
    choosing anything.
*   **`/new-spec <id> <title>`** — scaffold from `SPEC-TEMPLATE.md` into the right module directory,
    pre-fill frontmatter, and wire `parent_spec` / `child_specs` links in *both* directions.
    Bidirectional linking is exactly what was missed for SPEC-102 and SPEC-103/104.
*   **`/new-context SPEC-xxx`** — the core of the user-facing goal. Read the spec, decompose §1–§3
    into discrete reviewable phases, draft the Testing Requirements Matrix **with paths that will
    actually exist**, set the branch name to `feat/CTX-xxx.n-<slug>`, and create the branch.
*   **`/close-context`** — collect commit hashes from the branch into frontmatter, flip status,
    prompt for Plan Drift entries, and run the validator locally before the PR is opened.

### 5.3 Norms `CLAUDE.md` must encode

These are drawn from what already worked in this repo, not invented:

1.  **Read SPEC-000 first, then follow `parent_spec` / `child_specs` links** to the module you're
    touching. (Already in `CONTRIBUTING.md` §"Tips for AI Agents" — keep it.)
2.  **Never write a test path into the matrix that doesn't exist on disk.** CI fails on this, and
    it's the most common way an agent produces a plausible-looking but broken CTX.
3.  **Verify against the real thing when the real thing is available.** CTX-103.1 and CTX-104.1
    each found a bug that mocks would have hidden. If KiCad or FreeCAD is installed on the machine,
    the integration test runs for real and skips itself cleanly in CI — that pattern is the
    standard, not an extra.
4.  **Record Plan Drift honestly, including your own wrong predictions.** CTX-101.1's Deviation 3
    predicted the Windows code might not compile; Deviation 4 records that it didn't, and why. That
    is the single most useful artifact in the repo. Deviations are the point of the framework, not
    an admission of failure.
5.  **`stdout` in the Python daemon is sacred.** No `print()`. Ever. `stderr` for everything.
6.  **One CTX per PR, one feature branch per CTX**, branch named after the context id.
7.  **State what was *not* verified.** Both CAD contexts explicitly note that their live paths ran
    on exactly one machine. That sentence is worth more than a green checkmark.
8.  **A spec that adds a user-facing surface states what the user is doing, not just what the
    machine does.** A capability spec can be perfect — every route it calls real, every test green —
    and still be the wrong thing to build. `SPEC-302` was: twelve PRs of correct spec/context
    process produced three unrelated functions (`generate`/`inject`/plain-chat) sharing one text box,
    routed by string-matching prose, because no section of `SPEC-TEMPLATE.md` ever asked the
    question. `SPEC-TEMPLATE.md`'s `## 5. User & Interaction` section exists to force it.
9.  **Verify as the user, not just as the capability.** Norm 3 is satisfied by proving a route
    returns the right value. This one is only satisfied by a human using the actual surface the way
    a user would, and recording what happened. Every capability test for `SPEC-302` passed; nobody
    tried to look up a part.

---

## 6. Risk register

| Risk | Impact | Where it's handled |
| :--- | :--- | :--- |
| Packaging the Python sidecar proves harder than expected (native wheels: `pynng`, `trimesh`) | The app is undeliverable; M2 slips indefinitely | ✅ Closed for macOS by CTX-401.1 (freeze) + CTX-401.2 (sidecar wiring) — no `--hidden-import` issues found in practice. Windows/Linux freezing remains open (SPEC-403). |
| An LLM hallucinates a plausible-but-wrong footprint that reaches a real board | A wasted PCB spin; the fastest way to lose a hardware engineer's trust permanently | SPEC-202 validation layer + ✅ SPEC-204's confirmation gate, wired end-to-end (CTX-204.1 daemon-side, CTX-108.4 the real inject command) — not yet closed by a live human click-through in the native window (native-window-verification-gap) |
| KiCad's IPC API changes across a major version | The KiCad bridge breaks wholesale; CTX-103.1's "patch bumps are safe" assumption is untested against a real break | SPEC-103 version gate, revisited in SPEC-108 |
| Windows and Linux live paths stay unverified | "Cross-platform" is a claim, not a fact, at the two most fragile integration points | SPEC-403, SPEC-903 |
| macOS crash shield never gets its heartbeat | Orphaned Python and FreeCAD processes accumulate on the platform being developed on | ✅ Closed by CTX-107.1's `daemon.heartbeat` + macOS-only monitor thread — not yet verified end-to-end under a live running app (see CTX-107.1 Plan Drift) |
| Solo-maintainer bandwidth vs. a 16-spec backlog | Half-built layers, none finished | Milestones are ordered so each one ends at a demonstrable state; M1 is deliberately narrow |

---

## 7. Immediate next actions

M0 is complete as of 2026-08-08 (see §4) — items 1-4 below are done. SPEC-105 and SPEC-106
(items 6-7 as originally written here) are also done as of 2026-08-09, ahead of M1 rather than
blocking it.

1.  ~~Merge the two open CAD branches into `develop` and close out CTX-103.1 / CTX-104.1.~~ ✅ done
2.  ~~Write **SPEC-901** and land `CLAUDE.md` + the four slash commands.~~ ✅ done
3.  ~~Write **SPEC-903** and get Python + frontend tests running in CI on all three OSes.~~ ✅ done
4.  ~~Write **SPEC-902** and upgrade the validator into a full graph checker.~~ ✅ done
5.  ~~Write **SPEC-105** (async job/progress protocol), **SPEC-106** (config & secrets store), and
    **SPEC-107** (structured logging, startup handshake & diagnostics).~~ ✅ done
6.  ~~Spike **SPEC-401** packaging far enough to know whether frozen `pynng`/`trimesh` is a day or a
    fortnight.~~ ✅ done — no spike needed; CTX-401.1/CTX-401.2 landed the real macOS packaging.
7.  Start M1.
