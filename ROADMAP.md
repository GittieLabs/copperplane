# 🗺️ Copperplane — Roadmap

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
| [SPEC-902](specs/SPEC-902-spec-graph-validator-v2.md) | `scripts/` | [CTX-902.1](context/CTX-902.1-spec-graph-validator-v2.md), [CTX-902.2](context/CTX-902.2-verify-commit-hashes-are-real.md) | ✅ Completed | `validate_spec_context.py` upgraded to a full graph validator (id/location/link integrity across every `SPEC-*.md`), path-exclusion matcher fixed; `CTX-902.2` added real, reachability-checked `commit_hashes` verification, 31-test suite green on all three OSes |
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
| [SPEC-305](apps/tauri-ui/specs/SPEC-305-app-shell-navigation.md) | `apps/tauri-ui` | [CTX-305.1](apps/tauri-ui/context/CTX-305.1-app-shell.md), [CTX-305.2](apps/tauri-ui/context/CTX-305.2-widen-narrow-tab-content.md), [CTX-305.3](apps/tauri-ui/context/CTX-305.3-enclosure-empty-result-column-width.md) | ✅ Completed | The real `SPEC-300` §2 shell: a Projects rail backed by `SPEC-304`'s real storage, a Library entry, a Settings anchor, and five per-project area tabs (Overview/Components/Schematic/PCB/Enclosure), replacing `App.tsx`'s `showSettings` toggle and single floating chat surface. Overview re-houses the existing chat flow unchanged in substance, now scoped per-project and persisted via `project.load_conversation`/`append_conversation_turn`. Enclosure re-houses `EnclosurePanel`/`EnclosureViewer` unchanged. Components/Schematic/PCB render as visible-but-empty placeholders naming `SPEC-306`/`308`/`309`. Verified live in the running app via screenshots covering the empty state, Settings, all five area tabs, and the re-housed Enclosure controls. Two real layout bugs found via `SPEC-313`'s own live click-through and fixed same-day: every tab but Enclosure was stuck at a 448px content column (`CTX-305.2`), and Enclosure's own responsive layout reserved space for a 3D-viewer result before one existed, squeezing its form narrow for no reason (`CTX-305.3`). |
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

#### SPEC-111 — Enclosure Lid & Component-Height Clearance — superseded in scope by SPEC-311

*Module:* `services/python-daemon` · *Depends on:* SPEC-109, SPEC-202

Real user feedback exercising the shipped enclosure generator: `SPEC-109` only ever builds an
open-top tray (its own §1 Non-Goals rule out lid/fastener hardware) sized from a board's *bounding
box*, not its real outline — both the live IPC path (`kicad_bridge.get_board_outline`) and the
file-based path (`kicad_pcb_import.extract_board_outline`) reduce the real Edge.Cuts polygon down
to a rectangle before it ever reaches FreeCAD. Two real, related gaps worth addressing eventually,
neither attempted here:

1.  **A real lid, not just a bottom shell.** Needs the enclosure's own interior height to clear
    every placed component's real body height, not just the board's flat 2D outline.
    **Correction, found while scoping `SPEC-311`:** `SPEC-202`'s extraction already persists
    `package_dimensions.height_mm` on every saved `Part` (`CTX-308.5`) — the real gap is that no
    stored link exists from a specific *placed footprint on a real board* back to the `Part`
    record it came from, not a missing height field.
2.  **A true polygon-traced shell, not a rectangular bounding box**, for a genuinely
    non-rectangular board — real OpenCASCADE work (extrude an arbitrary closed wire, offset it
    inward by wall thickness for the shell, handle concave sections at each corner), not a small
    tweak to the existing `Part.makeBox` boolean-cut script.

Left here as the historical record of when this gap was first named (this repo's own "Plan Drift is
not embarrassing" norm) — **[SPEC-311](apps/tauri-ui/specs/SPEC-311-enclosure-refinement-interactive-preview.md)**
is the real spec that now owns this scope, expanded well beyond just lid/outline once actually
written up.

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

#### [SPEC-203](services/python-daemon/specs/SPEC-203-supplier-api-integration.md) — Supplier API Integration — ❌ RETIRED 2026-08-18, never built

*Module:* `services/python-daemon` · *Depends on:* SPEC-106

Real research against live vendor documentation (2026-08-18) found the distributor APIs
(DigiKey/Mouser/Octopart/Arrow/element14/LCSC/JLCPCB) return essentially none of what this product
actually needs — no pin assignments, no footprints/symbols/3D models except Nexar Enterprise, no
design guidance — and that nearly every vendor's terms structurally forbid what a local-first CAD
tool does (no caching/building a local database, no multi-source aggregation, principal purpose
must be driving that vendor's own sales). `CTX-203.1` had already shipped credential-independent
plumbing for this (Settings UI, OS-keychain storage, a pricing cache) before this research
happened; that code was real but never wired to a live HTTP client, and is being removed
(`CTX-203.2`) now that the vendor-API path is permanently closed rather than left as dead,
misleading UI. Full reasoning, the one vendor (TME) that would have actually worked, and the
standing rules that survive this retirement for any future work in this area: read the spec itself
— it's kept as a tombstone at its original path specifically so this isn't rediscovered from
scratch. What replaced each of this spec's original goals: pin layouts stay `SPEC-202`; footprints
stay `SPEC-308`; datasheet resolution stays `SPEC-306`; "open at a distributor" stays `SPEC-307`'s
plain deep link; and design/application guidance (decoupling, pull-ups, protection, layout) gets
its own new spec, [SPEC-205](services/python-daemon/specs/SPEC-205-datasheet-design-guidance.md),
below.

#### [SPEC-205](services/python-daemon/specs/SPEC-205-datasheet-design-guidance.md) — Datasheet-Driven Design Guidance — 🚧 in progress, Class B + plain-language synthesis usable end-to-end ([CTX-205.1](services/python-daemon/context/CTX-205.1-datasheet-structure-pass.md), [CTX-205.2](services/python-daemon/context/CTX-205.2-datasheet-guidance-extraction.md), [CTX-205.3](services/python-daemon/context/CTX-205.3-datasheet-guidance-storage-route.md), [CTX-205.4](apps/tauri-ui/context/CTX-205.4-design-requirements-ui.md), [CTX-205.5](services/python-daemon/context/CTX-205.5-structure-pass-heading-detection.md), [CTX-205.6](services/python-daemon/context/CTX-205.6-heading-noise-and-symbol-encoding.md), [CTX-205.7](services/python-daemon/context/CTX-205.7-guidance-synthesis.md), [CTX-205.8](apps/tauri-ui/context/CTX-205.8-guidance-synthesis-ui.md), [CTX-205.9](apps/tauri-ui/context/CTX-205.9-citation-page-label-clarity.md) done, Class A/C planned) 2026-08-20

*Module:* `services/python-daemon` · *Depends on:* SPEC-105, SPEC-202, SPEC-304, SPEC-306, SPEC-307

The real replacement for `SPEC-203`'s "design guidance" goal, since no distributor API sells this
data — it only exists in datasheet prose, tables, and reference designs. Given a part and its
datasheet, surfaces what an engineer needs *around* that part to use it correctly (supply range,
decoupling, pull-ups, crystal load capacitance, protection, layout constraints), with three
explicitly different output classes and different contracts: **A** (tabular fact, typed and
range-checked, must cite), **B** (cited datasheet prose, must cite, never invented), and **C**
(general engineering practice the model holds, visually segregated, never cited to the datasheet
itself). A guidance item with no resolvable citation is a schema-level invalid state, not a UI
choice — the mechanism that keeps "the AI says 100 nF" checkable against a real page in five
seconds. Retrieval-first, not one-shot extraction, given datasheet length varies from ~200 pages to
1000+: a structure pass locates candidate sections before any extraction runs. Real, named risks
the spec itself is explicit about: unsourced-but-fluent advice is worse here than anywhere else in
the product since a wrong decoupling recommendation fails silently in the field months later, not
loudly at assembly; guidance that only appears in a schematic image (not prose) is a real, harder
extraction case the spec requires an explicit in/out-of-scope decision on, not a silent gap;
multi-variant datasheets (one document covering several part numbers) need explicit variant
scoping; and citations must carry the document revision, since page numbers drift across datasheet
revisions.

`CTX-205.1` (2026-08-20) shipped the first real slice: `datasheet_structure.py`, real PDF text
extraction (`pdfplumber`, MIT -- `pymupdf`/`fitz` was considered and rejected as AGPL-3.0, ruled out
by `SPEC-904`'s own license-consistency norm) plus deterministic, non-LLM candidate-section location
across the spec's own 8 named structure-pass targets -- the "locate before extract" half of the
pipeline, proven against a real, committed 8-page synthetic datasheet fixture. Deliberately scoped
narrow (no LLM call, no AgentFlow workflow, no daemon route, no storage, no UI yet), mirroring how
`SPEC-308`/`SPEC-311` shipped across many small contexts rather than one big-bang implementation --
every extraction class and the UI panel remain real, open work for `CTX-205.2`+.

`CTX-205.2` (2026-08-20) shipped the first real extraction class -- Class B (cited datasheet
prose) -- via a real AgentFlow `extract -> validate` DAG mirroring `component_pipeline.py`'s own
`component_intelligence` shape. A real AgentFlow constraint found by reading the vendored source
directly: a handler node can't see the workflow's own `initial_message` past the entry node, so
citation validation (which needs the real page texts) is wired via a closure-bound handler built
per call, not AgentFlow's own node-output references -- the DAG itself stays 100% real AgentFlow.
Citation contract implemented literally: an item whose page or quote doesn't check out is dropped,
not repaired. Verified end-to-end with real Anthropic calls against `CTX-205.1`'s own fixture PDF.
Class A, Class C, the daemon route, Part-record storage, and the UI panel remain real, open work.

`CTX-205.3` (2026-08-20) wired the real pipeline into the app: a new async
`datasheet.generate_guidance` route loads a real Part, ensures its datasheet is really cached
locally (confirmed by reading the real save path: caching is best-effort and non-gating at
Part-save time, not guaranteed), runs the real pipeline, and persists cited guidance onto the
Part record. New storage follows this repo's real, established schema-evolution convention
(read-time backfill via `setdefault`, never a `schema_version` bump) -- `design_guidance`
backfills as `None`, not `{}`, keeping "never generated" and "generated, found nothing"
distinguishable. Real `cancel_event` support added, matching the FreeCAD routes' own pattern.
Verified end-to-end through `handle_request` with a real HTTP server and a real Anthropic call.
Class A, Class C, and the UI panel remain real, open work.

`CTX-205.4` (2026-08-20) shipped the UI panel -- a real "Design Requirements" section on Part
Detail, grouped by category, each cited item with a citation button that opens the cached
datasheet at that page (not verified working through the real packaged webview in this session,
named honestly). Available as soon as a Part exists, not gated on a footprint. Only Class B (cited
prose) exists on the backend, so this renders exactly that -- real category-by-category empty
states, not fabricated Class A/C placeholders. A real, pre-existing inconsistency was caught and
fixed while typing the frontend interface: `save_part` only backfilled `design_guidance` via
`load_part`, never on its own real return value. **SPEC-205's Class B slice is now usable
end-to-end** (generate -> persist -> view -> open citation); Class A (typed facts), Class C
(general practice), and the fuller `SPEC-205 §5` grouping (which needs pin association and a
Class marker the backend doesn't produce yet) remain real, open work.

`CTX-205.5` (2026-08-20) fixed a real, serious bug found by live user testing of `CTX-205.4`'s
just-shipped UI against a real 234-page ATtiny85 datasheet, never exercised by `CTX-205.1`'s own
small synthetic fixture: the structure pass's whole-page keyword search matched `reset` on 84/234
real pages and `clock`/`oscillator` on 141/234 -- both words appear constantly in ordinary
register/peripheral prose, not just the real dedicated sections -- and handing that many pages to
one LLM call produced a response long enough to hit `max_tokens` mid-string, surfacing as
`Extraction did not return valid JSON: Unterminated string...` in the real running app. Fixed by
replacing whole-page keyword matching with heading-based detection: a real numbered section-heading
line bounds each category's candidate pages (capped at 4), falling back to the original keyword
search only when no heading matches anywhere. Verified against the real ATtiny85 PDF: `reset`
dropped from 84 to 9 candidate pages, `clock_oscillator` from 141 to 18, full pipeline completed
end-to-end with zero JSON errors. A second, unrelated real bug found in the same live-testing
session is recorded in this context's own Plan Drift, not repeated here: the dev-mode daemon's
Python interpreter (separate from this repo's own `.venv`) was missing `pdfplumber` -- a real,
local-environment gap, not a code change.

`CTX-205.6` (2026-08-20) fixed two more real bugs found by continued live testing against the same
real ATtiny85 datasheet: a garbled degree sign (the datasheet's embedded font places `°` at PDF
Private Use Area codepoint `U+F0B0`, a font missing a `ToUnicode` CMap entry, which `pdfplumber`
surfaced raw), and a "Power" guidance panel built entirely from meaningless pin-listing labels
("1.1.1 VCC Supply voltage.") -- its only heading match anywhere in the real 234-page document was
that one pin-description entry, not a narrative section. Confirmed narrow before fixing: exactly 8
of 286 real detected headings are a single all-caps word, and every one is a pin name, instruction
mnemonic, or table fragment, never a real section title. Verified end-to-end with a real Anthropic
call: "power" now returns 5 real cited items instead of 2 pin labels. **A larger, real, open
question surfaced by the same testing is explicitly deferred, not answered by this context**:
whether verbatim Class B citations -- even correctly cited ones -- are the right shape at all for
this feature's actual audience, a maker/hobbyist rather than a practicing hardware engineer. This is
`SPEC-205`'s real next decision point.

`CTX-205.7`/`CTX-205.8` (2026-08-20) answered that open question directly, with the user rather than
guessed at: `SPEC-205` was amended (§1, §2.1.1, §5) to record the real audience correction and a new
synthesis layer -- **not** a fourth output class, and **not** a weakening of the citation contract.
Per category, once its Class B items are validated, a second, single-node AgentFlow workflow
generates one short plain-language paragraph strictly from those same already-cited items (never a
new fact, never called for a category with zero valid items). Verified end-to-end against the real
ATtiny85 PDF with a real Anthropic call across four categories, each read back for accuracy --
`power`'s real summary correctly surfaces the brown-out/EEPROM-corruption risk and the Brown-out
Detector mitigation, in plain language, grounded strictly in its own cited excerpts. `CTX-205.8`
shipped the frontend the same day: each category's summary now leads as the primary reading surface
on Part Detail, with its underlying citations collapsed below via a native `<details>` element,
available on demand as proof rather than the first thing a reader has to parse. **SPEC-205's real
audience-fit problem now has a first real answer, live in the app** -- whether it's the complete
answer, or the category taxonomy itself also needs to become task-oriented (a real, live
alternative the user named but didn't choose this round), is left for direct feedback once used.

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

#### [SPEC-206](services/python-daemon/specs/SPEC-206-agent-context-store.md) — Agent Context Store, Retrieval & Conversation Persistence — ✅ done 2026-08-24

*Module:* `services/python-daemon` · *Depends on:* SPEC-205, SPEC-204, SPEC-304, SPEC-105, SPEC-201
· *Parent:* [SPEC-318](apps/tauri-ui/specs/SPEC-318-in-context-agent-chat-and-review.md) (3xx, not
SPEC-000 — a deliberate deviation named in its own §3, since this spec exists solely to serve
SPEC-318 and has no independent architectural meaning)

The daemon-side layer SPEC-318's five per-area agents stand on: a durable JSONL conversation store
the app fully owns (project-scoped and Part-scoped threads, replacing AgentFlow's in-memory,
tool-call-blind `MultiUserHistory`), a validated `SourceRef` model extending SPEC-205's
drop-not-repair citation contract to chat, a rebuildable FTS5 retrieval index over
`PRODUCT-PLAN.md` §4's long-unbuilt `.index/` (with a `LikeScanRetriever` fallback and no vector
store — see its own §2.6 for the argument), a promotion path from resolved conversation to durable
cited note, and router-based agent dispatch with no LLM on the routing path. Also closed a real
prerequisite gap: SPEC-308's connection guidance used to be generated and discarded
(`kicad.generate_connection_guidance` returned its result; nothing persisted it) —
[CTX-206.1](services/python-daemon/context/CTX-206.1-persist-connection-guidance.md) persisted it,
the first of eight slices (`CTX-206.1`–`CTX-206.8`) that shipped the full store, retrieval index,
and `chat.send`/`chat.promote_turn` routes SPEC-318's five per-area agents and `AgentChat` panels
now run on.

#### [SPEC-207](services/python-daemon/specs/SPEC-207-managed-provider-adapter.md) — Managed Provider Adapter — ✅ done ([CTX-207.1](services/python-daemon/context/CTX-207.1-chat-usage-return-shape.md), [CTX-207.2](services/python-daemon/context/CTX-207.2-managed-provider-and-error-taxonomy.md)) 2026-08-25
*Module:* `services/python-daemon` · *Depends on:* SPEC-201, SPEC-105, SPEC-106 · *Parent:* SPEC-404

The daemon-side half of `SPEC-404`: a `managed` branch on the existing provider wrapper pointing
`OpenAICompatProvider` at the gateway, plus a structured error taxonomy so "your allowance ran out",
"your token was revoked" and "the service is down" reach the UI as distinct codes rather than one
string.

Two findings from reading the installed source rather than assuming, both of which changed the spec.
**AgentFlow already returns token usage on every provider** — `providers/openai_compat.py`,
`anthropic.py` and `google_genai.py` all normalise to `{input_tokens, output_tokens}`, so no
AgentFlow change is needed; what loses it is `llm_providers.chat()` ending in `return response.text`.
Widening that return shape is a breaking change to every caller, should land as its own context
first, and is worth doing for the free build regardless — a project premised on provenance for every
field currently cannot say what any AI call cost. And **no naked vendor-SDK calls exist anywhere in
daemon application code**; the real hazard is one layer in, where `chat_agents.py` and
`component_pipeline.py` build a provider via `_build_provider()` and call `.chat()` directly, so
anything added only to `chat()` is invisible to two of the three paths.

#### [SPEC-208](services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md) — Provider Records & Model Role Resolution — ✅ done ([CTX-208.1](services/python-daemon/context/CTX-208.1-provider-records-and-resolver.md), [CTX-208.2](services/python-daemon/context/CTX-208.2-model-roles-across-prompt-files.md), [CTX-208.3](services/python-daemon/context/CTX-208.3-capability-preflight.md)) 2026-08-25
*Module:* `services/python-daemon` + `core/tauri-rust` · *Depends on:* SPEC-201, SPEC-106 · *Parent:* SPEC-201

Closes three couplings `SPEC-201` left behind, found by reading the code rather than from a failure
report. A provider is a *name* matched against a hardcoded if-chain with a hardcoded endpoint, so
"plug in local models" means exactly one shape — Ollama, this machine, port 11434 — and an Ollama
server on another box, LM Studio, `llama.cpp` or vLLM has no config field that could reach it. The
Settings override is one global provider+model pair applied to every agent, so the per-agent
differentiation the twelve `.prompt.md` files already encode is destroyed the moment anyone sets a
model: bring-your-own-model and right-model-per-job are mutually exclusive today. And an agent's real
requirements are undeclared, so a model that cannot tool-call returns text on round 1, the executor
loop simply ends, and the answer arrives ungrounded with every citation dropped — no error anywhere.

The design: provider *records* (`{id, kind, base_url, api_key_ref, models}`) with construction
switching on `kind` rather than vendor name, today's five providers reseeded as editable presets;
`.prompt.md` naming a **role** (`reasoning`/`fast`) that each record resolves to its own model; and
`requires:` declarations checked before the first call. **`managed` stays locked** — `SPEC-207` §2.1
rules a settable managed endpoint an exfiltration surface, and this spec honours it by construction.

*Sequencing:* both this and `SPEC-207` edit the same three call sites and the same function. Landing
this first makes `SPEC-207` smaller; landing `SPEC-207` first means writing an if-branch this spec
then deletes. *Known gotcha, verified in the installed source:* AgentFlow's `AgentConfig` is a
pydantic model with `extra` defaulting to `"ignore"`, so `model_role`/`requires` are parsed and
silently dropped — the daemon needs its own small sidecar reader, and a typo in either key is
discarded just as quietly.

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
SPEC-300 onward.** Its own §5.2 re-scopes SPEC-301/302; its §5.1 adds SPEC-300/304-310. The
SPEC-301–SPEC-304 entries below are kept for historical record, not the current backlog — read
PRODUCT-PLAN.md §5 before picking up any 3xx work. Everything from SPEC-308 onward is a record of
work already shipped, added as it landed. SPEC-300 itself has no entry of its own: it is the
umbrella every 3xx spec below hangs off, and is marked Completed now that all fifteen of its
`child_specs` have shipped. The SPEC-304 ID conflict this section originally flagged was
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

#### [SPEC-308](apps/tauri-ui/specs/SPEC-308-footprints-schematic-advisor.md) — Footprints & Schematic Advisor — ✅ done (twelve contexts, `CTX-308.1`–`CTX-308.12`) 2026-08-24

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-300, SPEC-304, SPEC-307, SPEC-202

Makes the Footprint a first-class object with its own find-or-create flow, per `PRODUCT-PLAN.md`
§5.1 — find one in the user's installed KiCad libraries, or build one from datasheet package
dimensions, export it to a real `.pretty` library, and link it to an already-real Part. `SPEC-304`
had already reserved the storage (`library_store.save_footprint`/`load_footprint`, `CTX-304.1`), so
this spec is the flow on top of it, not new persistence. Shipped as twelve small contexts rather
than one drop, the same way `SPEC-311` did: installed-library search (`CTX-308.1`) and its UI
(`CTX-308.2`), KiCad's bundled libraries (`CTX-308.3`), saved-footprint search (`CTX-308.4`),
generation from datasheet package dimensions (`CTX-308.5`), real `.pretty` export (`CTX-308.6`),
and connection guidance (`CTX-308.7`).

Two honest caveats worth keeping visible. The connection guidance this spec generated was
**generated and discarded** — `kicad.generate_connection_guidance` returned a result and nothing
persisted it — a real prerequisite gap not closed until `SPEC-206`'s
[CTX-206.1](services/python-daemon/context/CTX-206.1-persist-connection-guidance.md). And five of
the twelve contexts are fixes found only by live use, not by tests: a through-hole footprint
attribute written wrong (`CTX-308.8`), a missing per-project override (`CTX-308.9`), agent-guided
search (`CTX-308.10`), and two preview defects — scaling plus project wiring (`CTX-308.11`) and
zoom-on-scroll (`CTX-308.12`).

#### [SPEC-309](apps/tauri-ui/specs/SPEC-309-board-advisor.md) — Board Advisor — ✅ done ([CTX-309.1](services/python-daemon/context/CTX-309.1-board-advisor-backend.md), [CTX-309.2](apps/tauri-ui/context/CTX-309.2-board-advisor-ui.md), [CTX-309.3](apps/tauri-ui/context/CTX-309.3-board-open-state-guidance.md)) 2026-08-24

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-300, SPEC-304, SPEC-103, SPEC-110

Runs KiCad's own Electrical Rules Check and Design Rules Check and turns each real, structured
violation list into plain-language explanation and suggested fixes via an LLM call. It deliberately
does not reimplement rule-checking — KiCad's engine is already correct, just terse, assuming the
reader knows what `pin_to_pin` or `invalid_outline` implies about the fix. Strictly read-only: run
the check, explain the results, suggest what a human might do; never auto-fix. That non-goal is a
direct consequence of `SPEC-204`'s confirmation-gate model, so no gate was needed here. `CTX-309.3`
is the live-use follow-up — the advisor needed to say something useful when no board is open,
rather than failing opaquely.

#### [SPEC-310](apps/tauri-ui/specs/SPEC-310-enclosure-from-board-profile.md) — Enclosure from Board Profile — ✅ done ([CTX-310.1](services/python-daemon/context/CTX-310.1-board-profile-import-backend.md), [CTX-310.2](apps/tauri-ui/context/CTX-310.2-board-profile-import-ui.md), [CTX-310.3](apps/tauri-ui/context/CTX-310.3-enclosure-board-picker-ux.md)) 2026-08-24

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-300, SPEC-109, SPEC-104

Generates a real parametric enclosure from a `.kicad_pcb` **file**, with no live KiCad connection
required. `SPEC-109`'s board-driven mode was already real, but it only ever read whatever board
KiCad currently had open over IPC — so a user wanting an enclosure for someone else's design, an
old project, or a board on another machine's KiCad session had no path at all.
`freecad_bridge.generate_enclosure` was already source-agnostic, so this is a new input path, not a
new geometry pipeline. `CTX-310.3` fixed the board-picker UX found in live use, and its own Plan
Drift is what established that the fixed-shape bounding-box output had become the real limit — the
finding `SPEC-311` was then written to address.

#### [SPEC-311](apps/tauri-ui/specs/SPEC-311-enclosure-refinement-interactive-preview.md) — Enclosure Refinement & Interactive Preview — ✅ done (sixteen contexts, `CTX-311.1`–`CTX-311.16`) 2026-08-24

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-300, SPEC-109, SPEC-310, SPEC-202, SPEC-301

Turns enclosure generation from a one-shot, blind form submission into a real iterative workflow:
derive shape and required interior height from the actual board and its actual placed component
heights rather than defaults, generate, show an interactive 3D preview the user can navigate,
adjust and regenerate against the same board without starting over, and decide how a lid gets built
and shown alongside the base. **This is the spec that now owns `SPEC-111`'s scope** (§3.1 above),
expanded well beyond lid-and-outline once actually written up.

Sixteen contexts is the honest number, and their shape is the point. Two were design decisions
recorded before any code (`CTX-311.2` lid/body and persistence, `CTX-311.13` export and save), and
most of the rest are defects only a human looking at a rendered 3D preview could have found:
camera framing wrong after unit scale (`CTX-311.4`), a material that wasn't actually matte
(`CTX-311.7`), a default camera that hid the interior (`CTX-311.8`), near-plane clipping
(`CTX-311.11`), and a board overlay whose click-through was wrong (`CTX-311.16`). A direct and
expensive illustration of this repo's own "verify as the user, not just as the capability" norm:
every one of these would have passed a capability test.

#### [SPEC-312](apps/tauri-ui/specs/SPEC-312-application-shell-project-portability-persistence.md) — Application Shell, Project Portability & Persistence Model — ✅ done (items 1-3) 2026-08-19

*Module:* `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-300, SPEC-304, SPEC-311

Real product questions surfaced while scoping `CTX-311.13` (the Enclosure tab's real Export
action) that its own narrow scope deliberately did not try to answer, now a real spec, per this
repo's own "Plan Drift is not embarrassing" norm. Scoped to three of the five original questions
below (items 1-3, all shipped) -- item 4 (Overview tab purpose) and item 5 (component library
discovery) are explicit Non-Goals in the spec itself, real but separate decisions left for their
own future specs:

1.  **What does "Save" actually save, at the project level?** — ✅ done
    ([CTX-312.1](apps/tauri-ui/context/CTX-312.1-project-directory-link-and-save.md)). Two named
    actions, not three: "Link to folder…" plus "Save Project," which now writes a real manifest
    (`last_results`/`export_history` keyed by area tab) rather than the largely-unused
    `{name, schema_version}` record that existed before.
2.  **Project portability.** — ✅ done (same context as above). A linked project's real state now
    lives at `<directory>/.hardware-agent-studio/project.json` — copy the folder, send it, open it
    on another machine — instead of only the app's own per-machine storage root.
3.  **The native app menu.** — ✅ done
    ([CTX-312.3](apps/tauri-ui/context/CTX-312.3-native-app-menu.md)). Real `File`/`Edit`/`View`/
    `Help` menu via `tauri::menu`; File's Save Project/Open Project… reuse the same handlers as the
    in-app buttons. `CTX-312.3` also built the real reverse of item 2's directory link —
    `project.open_from_directory`, "a folder someone hands me becomes a known project here" — the
    actual payoff of portability, not just writing a portable file no code ever reads back.
4.  **The Overview tab's actual purpose**, undecided since `SPEC-305` first re-housed chat there —
    **now its own spec**, [SPEC-313](apps/tauri-ui/specs/SPEC-313-overview-tab-project-dashboard.md)
    below: decided as a per-project dashboard, not a cross-project landing page.
5.  **Component library discovery/search** — connecting to a real external footprint/component
    library service for searching and pulling in components, distinct from this app's own local
    library (`SPEC-304`) — **now its own spec**,
    [SPEC-314](apps/tauri-ui/specs/SPEC-314-community-library-discovery.md) below, after real
    research ruled vendor pricing APIs out entirely (`SPEC-203`, retired) and found Ultra
    Librarian's real API access unconfirmed -- scoped to real, GitHub-hosted community KiCad
    libraries instead.

#### [SPEC-313](apps/tauri-ui/specs/SPEC-313-overview-tab-project-dashboard.md) — Overview Tab: Per-Project Dashboard — ✅ done ([CTX-313.1](apps/tauri-ui/context/CTX-313.1-project-dashboard.md)) 2026-08-19

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-300, SPEC-305, SPEC-312

Resolves `SPEC-312`'s deferred item 4 above. Decided: a per-project dashboard, not a cross-project
landing page — the Projects rail already owns cross-project navigation. Three pieces, all shipped:
the existing chat (`CTX-305.1`, unchanged), a real status summary across PCB/Schematic/Enclosure/
Components (honest about only Enclosure having any persisted result to show today, per
`CTX-312.1`'s `Project.last_results`), and a real activity feed merging the two genuine timelines
that already exist — `conversation.jsonl` (given a real per-turn timestamp for the first time,
`CTX-313.1`) and `Project.export_history`. No new area tab, no new persisted event log; see the
spec's own Non-Goals for what this first version deliberately doesn't attempt. Two real follow-on
layout bugs found by the user's own live click-through and fixed the same day, tracked under
`SPEC-305` since they turned out to be app-shell-wide, not specific to this dashboard:
[CTX-305.2](apps/tauri-ui/context/CTX-305.2-widen-narrow-tab-content.md) (every tab but Enclosure
was stuck at a 448px column) and
[CTX-305.3](apps/tauri-ui/context/CTX-305.3-enclosure-empty-result-column-width.md) (Enclosure's
own responsive layout reserved space for a 3D-viewer result that didn't exist yet).

#### [SPEC-314](apps/tauri-ui/specs/SPEC-314-community-library-discovery.md) — Community Footprint & Symbol Library Discovery — ✅ done ([CTX-314.1](services/python-daemon/context/CTX-314.1-community-library-search.md), [CTX-314.2](services/python-daemon/context/CTX-314.2-community-library-import.md)) 2026-08-19

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-106, SPEC-304, SPEC-308

Resolves `SPEC-312`'s deferred item 5 above, scoped after real research (2026-08-19) into two real
candidates named directly by Keith: Ultra Librarian and GitHub-hosted KiCad libraries. Ultra
Librarian's own redistribution terms turned out to be genuinely permissive, but no public,
documented API for programmatic access could be found -- real, unconfirmed, explicitly not blocked
on here (see the spec's own Non-Goals). GitHub-hosted community libraries are the confirmed-
buildable half: a real, curated allowlist of MIT/permissively-licensed repos (`espressif/
kicad-libraries`, `sparkfun/SparkFun-KiCad-Libraries` -- verified by direct inspection, not
`kitspace/kicad_footprints`, which uses git submodules and was deliberately excluded from this
first allowlist), searched via GitHub's own REST API with an optional bring-your-own token
(`SPEC-106`'s existing keychain mechanism, `SPEC-203`'s own "never bundle an API key" standing rule
applied here too). The real, named open risk carried over from `SPEC-310`'s own research --
whether `kiutils` reliably handles real footprint/symbol files pulled from these repos, given it
crashed on a full board file during prior work -- resolved positively: `kiutils` parses real
`.kicad_mod`/`.kicad_sym` content from both allowlisted repos correctly (`CTX-314.1`), a different,
simpler S-expression shape than the full-board case that failed. `CTX-314.2` shipped the real
fetch/parse/persist path (raw content preserved verbatim, never lossily re-derived into this app's
own generated-footprint schema), the real `github_token` keychain key, and the Settings/Part Detail
UI -- including a real, two-step browse-then-import flow for `.kicad_sym` files, which turned out
to be genuine multi-symbol libraries (73 real symbols in one file, verified directly), not one
symbol per file the way this app's own hand-built symbol files are.

#### [SPEC-315](apps/tauri-ui/specs/SPEC-315-library-browsing-and-organization.md) — Library Browsing & Organization — ✅ done ([CTX-315.1](apps/tauri-ui/context/CTX-315.1-library-storage-schema.md), [CTX-315.2](apps/tauri-ui/context/CTX-315.2-library-area-ui.md), [CTX-315.3](apps/tauri-ui/context/CTX-315.3-parts-symbols-section-split.md), [CTX-315.4](apps/tauri-ui/context/CTX-315.4-part-detail-from-library.md)) 2026-08-20

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-304, SPEC-305, SPEC-314

Scoped 2026-08-19 from real, hands-on user feedback after clicking through `CTX-314.2`'s own
shipped work: the rail's Library entry has shown a real Part count since `SPEC-305`, but that
spec's own text already named the gap directly -- "a real browsing UI ... is out of scope,
deferred to a future spec." This is that spec. Makes a "library" a real, user-defined grouping tag
on top of `SPEC-304`'s existing global Part/Symbol/Footprint objects (never a project-scoped copy,
extending the same "Footprint is shared, not duplicated per Part" reasoning `SPEC-300`/`SPEC-304`
already committed to) -- an always-present Default library plus real custom ones a user creates,
with membership tracked per object (Part/Symbol/Footprint independently, not bundled), since a
Footprint is already shared across many Parts and a library-membership model that ignored that
would misrepresent it the first time two unrelated Parts shared one Footprint. Also captures three
related-but-out-of-scope findings from the same testing session, aimed at whichever of `SPEC-202`/
`SPEC-306` eventually picks them up: an overly generic search term returning a short candidate
list without a "too broad, please narrow" signal; a real dead datasheet link reaching the user with
no reachability check; and a real "Extraction did not return valid JSON" failure blocking a user
from ever reaching Part Detail at all, which looked like a missing UI from the outside but was an
upstream extraction bug.

`CTX-315.3` (2026-08-20) fixed a real bug shown in a live screenshot: the "Datasheets / Pins"
section rendered Parts and Symbols as siblings under one combined count, so a Part's own generated
Symbol (e.g. `DIP-8_8pin`, `library.save_confirmed_part`'s real symbol_id convention) looked like a
second, unrelated component even though only one Part had ever been saved. Split into two real,
separately-labeled sections, applying `CTX-315.2`'s own already-stated "independently-shared
object" principle to Symbols, which were missed when Footprints got it.

`CTX-315.4` (2026-08-20) closed the last real hole `SPEC-315` §5 itself already named: "find a
Part... they already saved... without re-searching or re-generating it." Until this, "Save to
Library" was the only door into a Part's full detail view -- reopening a saved Part meant starting a
brand-new search from scratch, re-running `SPEC-202`'s LLM extraction as if it were a fresh,
unconfirmed candidate. Adds a properly-typed `loadPart(partId): Promise<SavedPart>` (reusing the
already-existing `library.load_part` route, previously only exposed through a narrower summary
shape), a new `PartDetail` entry point (`initialPart`) that hydrates directly from an already-saved
record and skips re-extraction entirely, and clickable Library Part rows wired to a new top-level
`partDetail` view in `App.tsx` -- a Part is a global `SPEC-304` object, so reopening one doesn't
require a project to be open. A real crash the test suite itself caught on first run (a lazy-init
gap left `extraction`/`savedPart` null on the very first render) is recorded honestly in the
context's own Plan Drift, exactly the value this repo's "verify against the real thing" norm names.
**Not yet verified live in the running app** -- flagged honestly, not assumed equivalent to the
mocked test suite; a real manual click-through is still owed.

#### [SPEC-316](apps/tauri-ui/specs/SPEC-316-native-menu-command-surface.md) — Native Menu Command Surface — ✅ done ([CTX-316.1](apps/tauri-ui/context/CTX-316.1-menu-command-surface-wiring.md), [CTX-316.2](apps/tauri-ui/context/CTX-316.2-native-menu-dynamic-sync.md)) 2026-08-20

*Module:* `apps/tauri-ui` + `core/tauri-rust` · *Depends on:* SPEC-312, SPEC-315

Scoped 2026-08-20 after `CTX-312.3`'s minimal `File`/`Edit`/`View`/`Help` menu shipped and Keith
live-tested a standalone `.app` build of it (surfacing, separately, that the menu bar's total
absence in every prior build was a Rosetta/x86_64-toolchain issue on this dev machine, not a code
bug -- fixed by installing and defaulting to the native `aarch64-apple-darwin` Rust toolchain, not
by this spec). Grows that minimal shell into the app's real command surface: a `Library` top-level
menu mirroring `Rail.tsx`'s existing Projects/Library/Settings peer relationship (`SPEC-315`'s
Default-plus-custom-libraries model), one grouped `Design` menu holding `Schematic`/`PCB`/
`Enclosure` submenus of each area's already-real actions (chosen over three separate top-level
menus specifically so the top-level bar doesn't grow unbounded as each area's action count grows),
and moving Settings/About/Quit into the native macOS app-name menu. Confirmed directly with Keith
via two explicit choices rather than assumed.

`CTX-316.1` shipped the full static structure -- the app-name menu, the `Design` menu wired to
every real, parameterless per-area action (`Open in KiCad`, `Pick Schematic Manually…`, `Pick PCB
File…`, `Generate`), and a `Library` menu with `Default Library` (deep-linked) and `Manage
Libraries…`. `CTX-316.2` closed the two gaps that phase deliberately deferred: the `Library` menu
now shows real custom libraries (the frontend drives the sync via a new `update_library_menu`
command, since the native menu is built before the daemon is ready to answer
`library.list_libraries()` -- sync-on-fetch, not a live push subscription, named honestly rather
than solved with new plumbing this app has never needed before), and the `Design` menu is disabled
whenever no project is open. One deliberate, one-off break from `CTX-316.1`'s own
one-const-per-action event convention: a custom library's identity can't be a compile-time const,
so `menu://open-library` carries a real payload instead.

#### [SPEC-317](apps/tauri-ui/specs/SPEC-317-theme-system.md) — Theme System: Light, Dark & System — ✅ done ([CTX-317.1](apps/tauri-ui/context/CTX-317.1-theme-system.md)) 2026-08-24

*Module:* `apps/tauri-ui` · *Depends on:* SPEC-300, SPEC-303

Lets the user choose Light, Dark, or System appearance instead of being locked into the dark-only
design, with System following the OS preference live. Real, user-stated starting point: "not
everyone will want the dark mode design." The implementation also pays down the "every color is a
raw Tailwind literal" debt found during the pre-planning audit, by introducing a semantic token
layer. Two scope decisions were confirmed with the user rather than assumed: native Tauri window
chrome (the titlebar) is not synced to the theme, so `core/tauri-rust`/`tauri.conf.json` are
untouched; and the preference lives in `localStorage`, not `SPEC-106`'s Rust-owned config store,
since it carries no secrecy or daemon need. The Appearance control itself lives in `SPEC-303`'s
Settings UI.

#### [SPEC-318](apps/tauri-ui/specs/SPEC-318-in-context-agent-chat-and-review.md) — In-Context Agent Chat, Project Intent & AI Review — ✅ done 2026-08-24

*Module:* `apps/tauri-ui` + `services/python-daemon` (via SPEC-206) · *Depends on:* SPEC-206,
SPEC-205, SPEC-308, SPEC-309, SPEC-313, SPEC-204

Gives every working area (Overview, Components, Schematic, PCB, Enclosure) its own scoped agent
chat, grounded in what that area actually knows -- SPEC-205's cited guidance, SPEC-308's connection
guidance (persisted by SPEC-206), SPEC-309's ERC/DRC findings -- selected deterministically by
the tab, never by a model (`PRODUCT-PLAN.md` §3.2 unchanged). Adds an optional project-intent field
every agent reads as the user's stated goal, never a verified fact. Every answer carries validated
source chips or is marked general-practice; nothing is described as "verified." Also finally
deletes `parseCommand` (§2.6), rehoming the two capabilities it currently gates -- component
generation and `SPEC-108`'s inject flow -- into real homes rather than dropping them silently.
Deliberately amends `PRODUCT-PLAN.md` §3.3/§2.1 and `SPEC-300` §2 (see its own §2.1 for the full
argument) and deliberately did not ship the AI Review buttons -- it defines the seam (a typed
`ReviewFinding[]`, the same agent/tools/scope as chat) so building them later is additive, not a
rewrite. Shipped across six contexts (`CTX-318.1`–`CTX-318.6`): the shared `AgentChat` component,
mounted in Components/Schematic/PCB/Enclosure/Overview; a real, editable project-intent field;
`parseCommand`/`lib/commands.ts` deleted, with `kicad.generate_component` rehomed to a "Generate
directly from a part number" fallback in Components and `SPEC-108`'s inject flow rehomed to a real
"Inject into open board" action on `PartDetail`. The AI Review buttons themselves remain unbuilt --
that is this spec's own deliberate scope boundary, not debt.

#### [SPEC-319](apps/tauri-ui/specs/SPEC-319-ai-review.md) — AI Review — ✅ done ([CTX-319.1](apps/tauri-ui/context/CTX-319.1-review-backend-foundation.md), [CTX-319.2](apps/tauri-ui/context/CTX-319.2-review-panel-components.md), [CTX-319.3](apps/tauri-ui/context/CTX-319.3-review-panel-schematic-pcb.md), [CTX-319.4](apps/tauri-ui/context/CTX-319.4-review-panel-enclosure.md), [CTX-319.5](apps/tauri-ui/context/CTX-319.5-review-panel-overview.md), [CTX-319.6](apps/tauri-ui/context/CTX-319.6-review-design-menu.md)) 2026-08-25

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-318, SPEC-206, SPEC-204, SPEC-316 · *Parent:* SPEC-318

Builds the seam `SPEC-318` §2.5 deliberately defined but did not build: a **Run Review** action in
each area that invokes that area's own chat agent — same tools, same retrieval scope, same source
contract — with a fixed internal prompt instead of a user question, rendering a typed list of
review findings instead of a conversational answer. No new agent, no new tool, no new retrieval
scope: the cheapest real capability available given what `SPEC-318` already shipped, and the reason
that seam was designed at all. A review reads and never writes, exactly like `SPEC-309`'s ERC/DRC
advisor it sits alongside — which is why `SPEC-204`'s confirmation-gate tool list is excluded here
rather than relied on. Shipped one area at a time (`CTX-319.3`–`CTX-319.5`) after the backend
foundation and the shared panel components, with the three real Design submenu items from
`SPEC-316` wired last (`CTX-319.6`).

#### [SPEC-320](apps/tauri-ui/specs/SPEC-320-managed-account-signin-and-usage.md) — Managed Account Sign-In & Usage — 📋 Draft 2026-08-25
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-303, SPEC-300, SPEC-106 · *Parent:* SPEC-404

The only part of `SPEC-404` a person touches. Managed appears in `SPEC-303`'s existing provider
dropdown beside Anthropic/OpenAI/Google/Ollama — a peer of Ollama, not a tier above the product —
and nowhere else: no nag banners, no upgrade badges, no upsell surface anywhere in the app. Sign-in
is paste-a-token for v1, since an open-source binary cannot hold a client secret; PKCE with a
loopback redirect is the named successor, revisitable once `SPEC-403` closes.

The weight is in the four failure states, each selected by `SPEC-207`'s structured code and never by
string-matching prose — the same rule `PRODUCT-PLAN.md` established for user input after
`parseCommand` was deleted. Quota exhaustion, token revocation, an unreachable gateway and upstream
vendor trouble each get a structured choice card offering real options, because a subscriber who
hits the monthly ceiling and sees "LLM request failed" concludes the product is broken and leaves.

#### [SPEC-321](apps/tauri-ui/specs/SPEC-321-provider-configuration-ui.md) — Provider Configuration UI — ✅ done ([CTX-321.1](apps/tauri-ui/context/CTX-321.1-provider-config-backend.md), [CTX-321.2](apps/tauri-ui/context/CTX-321.2-provider-config-editor-ui.md)) 2026-08-26
*Module:* `apps/tauri-ui` + `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-208, SPEC-303 · *Parent:* SPEC-208

`SPEC-208` deliberately stops at the daemon and the config schema, which leaves its provider records
unreachable by a person: `SPEC-303`'s picker writes two flat fields and its
`KEY_BASED_PROVIDERS`/`ALL_PROVIDERS` literals are hardcoded provider lists. This spec replaces that
picker with a real editor — add, edit and remove records, bind the two roles, and see which records
are actually usable — plus the migration display for an install arriving with the legacy fields.

Three real gaps found by reading the installed code, not assumed from `SPEC-208`'s own text: the
frontend `DaemonConfig` type never gained `providers`/`provider_roles` fields even though Rust's own
struct has carried both since `CTX-208.1`; `daemon.py` never reads either field into `CONFIG` at
startup or through `daemon.configure`, so `resolve()`'s own `config` parameter has had nothing real
supplying it since it was written; and a custom record's `api_key_ref` can't actually be saved at all
today, since `secrets.rs`'s `validate_known_key`/`collect_known_secrets` both operate over the fixed
`KNOWN_SECRET_KEYS` allowlist `SPEC-208` §2.7 named as needing to stop being fixed, but never built.

**Deliberately excludes Managed.** No hosting decided, no auth chosen, no billing built — `managed`
does not appear as a selectable kind anywhere in this editor, by explicit product decision, not by
placeholder. `SPEC-320` is the only spec that would ever change that.

*Requirement inherited from `SPEC-208` §3, not to be rediscovered:* a record pairing a vendor
`api_key_ref` with a non-loopback `base_url` sends the user's own key to whatever host they typed.
That combination must warn explicitly. `managed` is not editable here at all (`SPEC-207` §2.1).

#### [SPEC-324](apps/tauri-ui/specs/SPEC-324-model-identity-verification.md) — Model Identity Verification — 🚧 in progress ([CTX-324.1](apps/tauri-ui/context/CTX-324.1-model-listing-and-validate.md)) 2026-08-27
*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-321, SPEC-208, SPEC-106 · *Parent:* SPEC-300

The model field is a bare text box. A typo saves cleanly, the record looks configured, and the
first sign of trouble is a vendor error inside an AI feature — the same "looks fine, fails later"
shape as `SPEC-407`'s sidecar, one layer up. A dropdown of what the provider actually offers, free
text for everything else, and an on-demand Validate that works either way.

**Exists because `SPEC-322` §1's non-goal was built on a premise nobody checked.** That spec
declined validation on the grounds that "the app does not know a vendor's model list". Probed
against the real installed SDKs: `anthropic`, `openai_compat` and `google` can all list models, and
two can retrieve one by id — so the app can know, and an existence check costs no tokens. The
non-goal is marked superseded in `SPEC-322` itself with that correction, rather than deleted.

Three decisions carry the design. Listing runs in the **daemon**, reusing `SPEC-208`'s existing
per-`kind` client construction, because doing it from the renderer would put the API key there and
bypass `SPEC-106`'s secret channel — the same reason `CTX-320.1` rejected a renderer-side account
read. The control is a **combobox, not a dropdown**: a private deployment, a model newer than the
SDK's list, or a compat server with its own naming must all still work, so free text is the floor
and the list is a suggestion. And **nothing calls a vendor unless asked** — no startup fetch, no
validation on save — because `SPEC-107` §3 already holds that line for capability probes and
automatic validation would spend real quota to catch a typo a second earlier.

Named risks with weight: `openai_compat` is the widest kind and behaves differently per server
(Ollama lists *locally pulled* models, which is local availability rather than entitlement); vendor
lists can run to hundreds of entries so filtering is a requirement rather than polish; `retrieve`
semantics differ per vendor and Google's was not probed; and a model that exists is not a model
that works — `SPEC-208` §2.4's capability preflight remains the check that decides whether an agent
can actually run on it.

#### [SPEC-323](apps/tauri-ui/specs/SPEC-323-advanced-agent-configuration.md) — Advanced Per-Agent Configuration — 📋 Draft 2026-08-27
*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-208, SPEC-321, SPEC-322, SPEC-106 · *Parent:* SPEC-300

What the maintainer actually wanted when he asked to "address agents by type", separated from
`SPEC-322`'s legibility fix because it is new capability rather than copy: bind an individual agent
to a specific provider, model and reasoning effort, behind an Advanced toggle that is off by
default, with reset back to the role defaults.

The tiering is the design constraint, in his own words: managed users would not care, a
bring-your-own-key user cares little, and it is the contributor fine-tuning the product who needs
it — so per-agent config is an advanced option and nothing else changes. `SPEC-208` §2.3.1's
"exactly two roles, deliberately" is **extended, not reopened**: an agent with no override resolves
exactly as it does today, on the same code path.

Deliberately left undecided rather than guessed: how reasoning effort is represented portably.
Anthropic takes a token budget, OpenAI an effort level, Google its own thinking config. The
proposal is a small ordered enum mapped per provider `kind` in the daemon, with a raw per-vendor
value rejected because it leaks vendor shape into a provider-agnostic UI and silently means nothing
when an agent's provider changes. That needs checking against what each `kind` can actually send.

Three named risks carry real weight: `SPEC-208` §2.4's capability preflight must run on overrides
too or the advanced path becomes the one place that skips the safety check; provider deletion
already warns when a record is role-bound and must learn about overrides or it silently breaks an
agent; and twelve agents is already a lot of settings surface that grows with every new agent.

Worth recording that this is the third consecutive spec in this area written from the maintainer's
own use of the product — `SPEC-321` shipped correct and unreadable, `SPEC-322` made it readable,
this adds what was wanted. None of the three would have been caught by a test.

#### [SPEC-322](apps/tauri-ui/specs/SPEC-322-model-role-legibility.md) — Model Role Legibility in Settings — 🚧 in progress ([CTX-322.1](apps/tauri-ui/context/CTX-322.1-model-role-legibility.md)) 2026-08-27
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-321, SPEC-208, SPEC-303 · *Parent:* SPEC-300

`SPEC-321` shipped 2026-08-26 with every route real and its tests green. The maintainer opened the
resulting screen for the first time the next day and reported: "I see a reasoning with a dropdown
list and fast with a dropdown list. This isn't self explanatory." Nothing said what a role was,
which features used it, or that the model itself is set one level up on the provider record — the
screen had two levels and linked them nowhere.

`SPEC-302`'s lesson repeating in a new surface, and the one `CLAUDE.md` already records: a spec can
be mechanically perfect and still be the wrong thing to build. The difference is that this time a
person used the surface and said so, which is the norm working rather than failing.

Fixed as copy and one derived string, no schema change: each role now shows the model it actually
resolves to, the section says what a role is and where the model comes from, and a closing line
answers the question that was really being asked — which role a feature uses is fixed by the app,
not configurable. Reading the component to write that also surfaced a genuinely invalid state the
screen had been rendering as ordinary: a role bound to a provider with no model for it, which
`SPEC-321`'s own editor permits and which fails at call time with nothing in Settings hinting why.
It now names the provider and says the role cannot run.

Two real requests from the same report are **deferred with reasons rather than absorbed**: a
reasoning-effort control (provider records carry a model id per role and nothing else — new
capability, needs a `SPEC-208` schema change) and per-agent model binding (contradicts `SPEC-208`
§2.3.1's "exactly two roles, deliberately", so that argument has to be reopened first).

#### [SPEC-325](apps/tauri-ui/specs/SPEC-325-kicad-project-integration.md) — KiCad Project Integration & Schematic Component Table — Draft

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-312, SPEC-311

The read half of the co-pilot, and the foundation the four specs below stand on. Verified
2026-09-01 that `kicad-cli sch export bom`/`netlist` read a **closed** `.kicad_sch` with no GUI and
no IPC — the capability was always there and the app never asked. A project links to a
`.kicad_pro`; the Schematic tab becomes a component table.

**The four below are staged deliberately, read-only first.** They came out of one long design
conversation on 2026-09-01 about whether this is a reference tool for experts or a co-pilot for
hobbyists. The diagnosis: the app can observe but not participate, so every insight ends in "now go
do that in KiCad yourself" — and each handoff is a place a novice gives up. Stages 1-3 are entirely
read-only and carry most of the value.

#### [SPEC-326](apps/tauri-ui/specs/SPEC-326-component-volume-placeholders.md) — Component Volume Placeholders — Draft

*Module:* `services/python-daemon` · *Depends on:* SPEC-325, SPEC-311, SPEC-202

The enclosure needs a *volume*, not a model. Found while investigating a real report: KiCad's own
`Battery` library ships **53 footprints and 29 STEP models — 25 dangling references, zero `.wrl`
fallbacks**, and a real `Hello_World_Blinky` project's own CR2032 footprint points at a
`.step` that does not exist. So "download the model" fails for half of a stock library.

`component_extraction` already produces `package_dimensions` (length/width/height), and `SPEC-109`
already generates parametric geometry in FreeCAD. A footprint with no resolvable model gets a
**labelled bounding solid** — a clearance proxy, never presented as a real model. Open question
this must settle: a coin-cell holder's *assembled* height (holder plus installed cell) is the
number that matters for clearance, and is not either part's datasheet height.

Extended mid-flight by §2.7 (`CTX-326.3`): every volume number here is read from the **schematic**,
while the enclosure is built around the **board**, and KiCad keeps those in step only when a user
runs *Update PCB from Schematic* by hand. The maintainer's own board is currently out of sync on
exactly the CR2032 above — schematic says horizontal, board says vertical — so the recommendation
describes a part that is not on the board. `kicad-cli pcb drc --schematic-parity` detects this on
closed files; all three of the maintainer's other boards were also out of sync. Detection ships;
*triggering* the sync needs `kipy`'s explicitly-unstable `run_action`, so it stays in SPEC-329.
Remaining: placeholder geometry in the 3D view (`CTX-326.4`), and the open source-of-truth question
of whether envelopes should be read from the board instead.

#### Small: the wizard's review step repeats itself — reported 2026-09-03

*Module:* `apps/tauri-ui` · *Owner spec:* SPEC-335

Step 4 of the new-project wizard, with no KiCad project linked, prints *"No KiCad project linked,
so this cannot run"* once under each of its four checks. Honest, and four identical sentences read
as a wall rather than as an explanation. One statement above the list, with the checks simply
greyed, would say the same thing once.

Noticed while verifying `SPEC-336`'s skip path, which is why it is logged here rather than fixed in
that change: it is copy on a surface `SPEC-335` owns, and worth doing when something else touches
the wizard.

#### SPEC-337 — Naming the Two Project Links — written and delivered 2026-09-03

*Module:* `apps/tauri-ui` · *Depends on:* SPEC-325, SPEC-312

A project record carries two independent links, and the header presents them inches apart in
language a reader cannot tell apart:

*   `directory` (`SPEC-304` §2.1, built in `CTX-312.1`) — a folder on disk, for artifacts and the
    portable manifest. Set by **Choose project folder…**, which reports `Linked to <path>` in
    green.
*   `kicad_project_path` (`SPEC-325` §2.1) — the `.kicad_pro` everything is actually read from.
    Set by **Link**, and shown as `Linked KiCad project: none yet` until it is.

Reported by the maintainer on 2026-09-03, from a real project, with a screenshot showing all three
of these on screen at once:

> a warning banner: *"No KiCad project linked, so board and schematic checks, the component list
> and the enclosure cannot run."*
> the header: *"Linked KiCad project: none yet"*
> and directly beneath, in green: *"Linked to
> /Users/keithelliott/repos/PCBs/Hello_World_Blinky/Hello_World_Blinky"*

He linked the folder, was told it was linked, and reasonably concluded the project was linked. It
was not: the record read `directory: /Users/.../Hello_World_Blinky`,
`kicad_project_path: <none>`. The consequence is not cosmetic — with no `.kicad_pro` there is no
board outline, so `generate_enclosure` runs in manual mode with `standoffs=[]` and produces an
enclosure with no mounting posts at all. He went looking for a standoff defect and had actually hit
this.

Neither field is wrong and neither is redundant: a project can have a folder before it has KiCad
files. The defect is that one word does both jobs, in the same place, with a green success message
that is true about the less important one.

*   **The word.** "Linked" cannot mean both. Decide what each is called — folder versus KiCad
    project — everywhere they appear, including the success messages.
*   **Whether picking a folder should offer to link the `.kicad_pro` it contains.** In this case
    the chosen folder held exactly one, and the app said nothing about it.
*   **Whether the banner should say which link is missing**, given it fires on
    `kicad_project_path` alone while a folder may well be set.

#### SPEC-327 — Design Advice: Layout & Clearance Warnings — not yet written

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-325, SPEC-326

Pure analysis over what SPEC-325 reads. Mixed through-hole and SMD where it matters, components too
close together, missing mounting holes, headers whose off-board connection is undeclared, trace
width questions. Advises; never edits. The PCB tab becomes a table of components with resolved
models or placeholder volumes, a board view, and warnings — the same shape as SPEC-325's schematic
table.

#### SPEC-328 — Project Intent & Suggested Parts — not yet written

*Module:* `apps/tauri-ui` · *Depends on:* SPEC-325, SPEC-206

The Overview tab's real purpose, which `SPEC-313` deliberately left undecided. A user may arrive
before they have anything: they describe what they want to build, the app asks clarifying
questions, and offers a **general** parts list — "10K resistor, 100µF capacitor, ESP32-S3 devkit" —
not a vendor search. The user searches for real parts through the existing flow; what this adds is
a stated goal, carried forward so the library, schematic, PCB and enclosure stages all know what
the project is *for* (does it need a lid, will a connector exit the enclosure).

#### [SPEC-333](apps/tauri-ui/specs/SPEC-333-project-save-semantics-and-rename.md) — Project Save Semantics & Rename — Draft

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-312

Two reproduced defects in the persistence model, one of which `CTX-326.3` made much easier to hit.

**Save Project discards newer data.** It writes the whole in-memory project snapshot, replacing the
stored record — so anything a dedicated route wrote since that snapshot was loaded is erased. A DRC
result recorded at 10:00 is gone after a Save Project click at 10:05 using a copy loaded at 09:55.
`SPEC-312` already avoided this for intent and footprint overrides by adding dedicated routes; the
Save button itself was never brought along, and now that check results and enclosure parameters are
written on every run, the window routinely contains real work.

**Rename forks the project.** There is no rename route. Saving under a new name writes a second
pointer and leaves the first, so one folder becomes two entries in the project list, and the old one
still loads with a name its own folder's manifest contradicts.

#### [SPEC-336](apps/tauri-ui/specs/SPEC-336-first-run-onboarding-and-launch.md) — First-Run Onboarding & Launch Experience — Draft

*Module:* `apps/tauri-ui` · *Depends on:* SPEC-300, SPEC-303, SPEC-320/404 (for the disabled path)

Three problems at the front door.

**Settings is the onboarding surface and is not one** — a first-time user's first screen is five
provider records, provider kinds, two model-role bindings, a GitHub token and a KiCad socket path:
*"I think this would feel overwhelming for a user who is trying to initially use the app."*

**Nothing tells the user the app cannot work.** KiCad and FreeCAD are hard requirements and are
never verified; a user finds out by watching features fail one at a time. Onboarding detects them
and offers a path picker (they are often installed outside the default location) — but does **not**
block. Every step is skippable and missing requirements become persistent, specific banners, on the
maintainer's own reconsideration: *"Blocking the user may not be the answer... Its really no
different than the manual setup where a user still has to setup before using and they do it at their
own pace."* Consistency settles it — the manual path never gated anyone, so gating the guided path
would punish the user who asked for help.

**Launch opens an arbitrary project.** `App.tsx` takes `names[0]` from a `sorted()` listing — the
*alphabetically first* project, not the most recent. Confirmed in `library_store.list_projects`.
Replaced by a no-project landing view (what the app is, repo and docs links, create or open), which
also becomes the launch view. Adds the close-project action that does not exist today.

The **Managed** path is shown but disabled and marked coming soon: `SPEC-320` and `SPEC-404` are
both Draft and the backing service is unfinished. The docs pages the guided flow links to do not
exist either — placeholders now, their own context to write them, because a link that 404s on first
run is worse than no link.

#### [SPEC-335](apps/tauri-ui/specs/SPEC-335-new-project-wizard.md) — New Project Wizard — Draft

*Module:* `apps/tauri-ui` · *Depends on:* SPEC-312, SPEC-325, SPEC-319

Creating a project is a name and an optional intent in a 192px sidebar column, with no way to
cancel, after which the user lands on a tabbed view with nothing in it. Nothing in this app works
without a linked `.kicad_pro` (SPEC-325), and creation never mentions one — so a user can finish and
find every tab empty with no indication why.

Four steps, specified by the maintainer: name; link the KiCad project (prompting to create one if
none exists, *"as nothing else works without one"*); describe the goal in a short chat the assistant
summarises and confirms; then a real review — parity, board components, missing footprints and 3D
models, initial ERC/DRC — ending in four buttons that dismiss the wizard onto the chosen tab.

Related and deliberately unresolved: the Overview tab's four per-area status cards and its
project-level Run Review were **removed** on 2026-09-02 as *"a guess at what the future would
need"*. What a returning user should see there is a separate question this spec must not quietly
answer.

#### [SPEC-334](apps/tauri-ui/specs/SPEC-334-footprint-literacy-and-component-detail.md) — Footprint Literacy & Component Detail — Draft

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-325, SPEC-332

`SPEC-332` made a DRC finding legible. This does the same one stage earlier, for the parts
themselves. From the maintainer's own board: *"there are often many options to choose from that have
very similar names and it's hard to know what `P2.54mm_Vertical` means when to use over
`P2.00mm_Horizontal`."* And on a real `NE555P` search returning NE555P/NE555D/SA555P/NA555P/SE555P:
*"each option in kicad for adding to a schematic has different pin layouts... Which NE555P am I
getting."*

Also names a namespace gap found the same way: searching a KiCad **footprint** name in **component**
search returns vendor part numbers, because the two were never connected. Whether component search
should recognise a footprint-shaped query and answer from KiCad's own libraries is a question this
spec settles.

#### SPEC-332 — ERC as a Teaching Surface — written 2026-09-03 (the DRC half is delivered)

*Module:* `apps/tauri-ui` · *Depends on:* SPEC-309, SPEC-319

The maintainer, reading a real finding: *"I don't know what [Net-(U2-THRES)] of U2 means or actually
any of the abbreviations in order to find them. We have an opportunity to help the user learn what
these are and know to locate the problem on the board."* And on the target reader: *"a hobbyist/maker
that enjoys getting to the end product but is not a professional in schematics, pcbs, or cad and we
are their co-pilot assisting them with the areas they are weak in."*

Delivered on 2026-09-02: findings now carry KiCad's own `items` (the pad/net/component text and the
millimetre position, previously discarded as "internal uuids" — only `uuid` is), a static glossary
expands the abbreviations without an LLM call, and `ignored_checks` is surfaced with a note per
check saying what it would have caught and whether a maker should care.

Still open, and what this spec is for:

*   ~~**Mirroring KiCad's own tab structure**~~ — Violations / Unconnected / Schematic Parity /
    Ignored. **Decided against, 2026-09-03, for the board review and the schematic review alike:**
    *"since some tabs could be left empty, we chose a different option ... we are not using it in
    the board review either."* `ViolationsList` names each kind KiCad actually reported in one
    sentence with counts, shows one findings list, and collapses the switched-off checks. A
    category with nothing in it does not appear at all, where an empty tab would sit there inviting
    a click. Recorded in `SPEC-332` §2, including the residual risk: a reader cannot filter to one
    kind, and if that becomes a complaint the answer is filtering the one list, not tabs.
*   **Jumping to a finding.** The mm position is shown; nothing uses it. KiCad's own dialog
    centres the view on a double-click, and `kipy` could plausibly do the same when KiCad is open.
*   ~~**A glossary that is not a hard-coded list.**~~ Fine for the dozen terms KiCad's DRC actually
    emits; wrong if it grows into a general PCB dictionary. Answered on 2026-09-03 for the naming
    vocabulary, under `SPEC-334`/`CTX-334.2`: package families come from KiCad's own `Package_*`
    libraries and the variants are decoded compositionally, so 33 entries plus 11 prefix letters
    explain 88.0% of the 15,433 footprints KiCad ships. Still a hard-coded list for the DRC terms
    in `kicadGlossary.ts`, which remains the right shape for a dozen fixed strings.
*   **The same treatment for ERC**, which has its own vocabulary and its own ignored-test set.
    **Written up as `SPEC-332` on 2026-09-03**, with the gap measured rather than asserted:
    `kicad_check_board` returns `violation_count`, `unconnected_count`, `parity_count` and
    `ignored_checks`; `kicad_check_schematic` returns `violation_count` and `source_path`. KiCad's
    ERC report already carries `ignored_checks` — four of them on a clean run — and the route
    throws them away.

#### [SPEC-331](apps/tauri-ui/specs/SPEC-331-enclosure-fit-review.md) — Enclosure Fit Review — Draft

*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-326, SPEC-319

`SPEC-319` mounted a Run Review panel on the Enclosure tab. It was switched off on 2026-09-02,
showing `NotBuiltPlaceholder` rather than a button, at the maintainer's call: *"I don't even know
what the run review check is supposed to show for the enclosure."*

It is a real feature, not a stub — `chat_enclosure.prompt.md` defines it as physical fit: the
board's outline and mounting holes, per-component heights, and the generated enclosure parameters.
The problem is its data. Its one real tool, `kicad.get_component_heights`, goes through `kicad_bridge`
→ `kipy`, which needs **KiCad running**. With KiCad closed it had nothing but the project intent,
and produced confident-sounding advice from no data at all — the exact failure mode `SPEC-326` §1
exists to prevent, reached from a different direction.

The fix is not a patch: `SPEC-326` built a strictly better source that reads **closed** files —
`kicad.component_envelopes`, already driving the interior-height recommendation, with per-part
envelopes and an honest measured/stated/unknown split. Repointing the enclosure agent at it makes
the review work with KiCad closed *and* gives it better data than it ever had. That is this spec.

Settled: **"your box is 16mm and BT1 needs 20mm" is useful; restating the parameters the user just
typed is not** — a review that reads someone's own inputs back to them is worse than silence,
because it looks like analysis. Implemented in `CTX-331.1`: the agent now receives a `fit` block
measured per request from closed files, and the panel is back on.

#### SPEC-111 — Board Retention: Standoffs the Board Actually Mounts To — written 2026-09-03, deferred by the maintainer the same day

*Module:* `services/python-daemon` · *Depends on:* SPEC-109, SPEC-311

Reported by the maintainer from the running app, 2026-09-01: in the enclosure preview you can see
the board's mounting holes, but **nothing comes through them** — the holes read as empty.

Confirmed in the geometry, not guessed. `freecad_bridge.py`'s `_STANDOFF_CYLINDER_TEMPLATE` unions
a **solid** cylinder of `height_mm` at each recognised hole position, and the preview lifts the
board by `wall_thickness_mm + standoff_height_mm` (`EnclosureViewer.computeBoardOffset`). So the
post stops flush at the board's underside by construction: it supports the board and nothing
passes through the hole. The render is faithful — the geometry really is like that.

What a real enclosure has instead: a standoff bored for a screw, with the screw passing through the
board's hole into it, or a moulded boss that enters the hole to locate the board. Either makes the
holes read as mounted rather than empty.

**Correction, 2026-09-03.** This entry previously said `SPEC-109` §1's non-goals "explicitly ruled
out fastener hardware — so this is a deliberate scope re-opening, not an oversight to be quietly
patched." That is the opposite of what `SPEC-109` says. Its non-goal is *"Not fastener hardware
**selection**. Standoffs get a hole sized for a screw diameter parameter; choosing a specific screw,
heat-set insert, or lid-latching mechanism is out of scope."* — and its §2 lists the inputs as
"per-hole standoff height/**screw diameter**". The bore was always in scope; only choosing hardware
was out. Neither the bore nor the screw-diameter parameter was ever built, so this is an
unimplemented part of `SPEC-109`, and this roadmap entry had recorded the omission as a deliberate
decision. Written up as `SPEC-111`, which also renumbers it: `330` is a `3xx` id meaning
`apps/tauri-ui`, and this work is FreeCAD geometry in `services/python-daemon`, beside `SPEC-109`
itself.

Also worth settling here: the standoff diameter currently comes from the hole's own
`diameter_mm`, which makes the post exactly as wide as the hole it is meant to sit under.

#### SPEC-329 — Assisted Authoring: Adding a Part on Request — not yet written, deliberately last

*Module:* `services/python-daemon` + `apps/tauri-ui` · *Depends on:* SPEC-325, SPEC-308

The only stage that writes, and it is last on purpose — the maintainer's own call: *"I think we
need to add it but we can do this last to see if things shape in a way where it is not needed."*

The distinction it must hold is **authoring versus assisting**. Wiring nets, placing parts and
routing are KiCad's job. Adding a part the user explicitly asked for — unconnected, with the
footprint they chose — is what an add-on does, and both KiCad and FreeCAD have add-on ecosystems
that do exactly that.

Two routes to evaluate before choosing: writing a custom library plus a schematic entry directly,
or **a real KiCad add-on this app talks to**, which makes the permission boundary explicit and puts
the write inside KiCad's own process rather than behind its back. Either way, per-action
authorisation, never a setting. Read-only may prove sufficient; that is the point of doing it last.

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

#### [SPEC-402](specs/SPEC-402-release-signing-and-auto-update.md) — Release, Signing & Auto-Update — ✅ done 2026-08-17

*Module:* repo-wide · *Depends on:* SPEC-401

**Rescoped 2026-08-16: unsigned first, deliberately** — then the deferred parts shipped anyway,
across four more contexts, all `Completed`:
[CTX-402.1](context/CTX-402.1-release-pipeline-and-changelog.md) (unsigned macOS pipeline + a
changelog generator reading the framework's own `CTX-*.md` logs, v0.1.0),
[CTX-402.2](context/CTX-402.2-auto-updater.md) (Tauri auto-updater, its own standalone signing
keypair, v0.1.0), [CTX-402.3](context/CTX-402.3-macos-signing-notarization.md) (real macOS code
signing + notarization under a GittieLabs Apple Developer account — the "real *organization*
account" this entry originally deferred on, resolved rather than left open, v0.1.1),
[CTX-402.4](context/CTX-402.4-intel-macos-build.md) (a second, Intel x86_64 macOS build alongside
the original Apple Silicon one, v0.1.3), and
[CTX-402.5](context/CTX-402.5-windows-linux-prerelease-builds.md) (real, unsigned,
explicitly-pre-release Windows and Linux builds, v0.1.3). The Windows/Linux builds here are real
compiled artifacts, not the same thing as `SPEC-403`'s still-open question below — nothing has
live-tested the actual KiCad/FreeCAD bridges on those platforms yet, only that the app itself
builds and launches there.

#### SPEC-403 — Cross-Platform Verification Matrix
*Module:* repo-wide · *Depends on:* SPEC-903

Every live CAD test to date has run on exactly one machine: Keith's Mac, with KiCad 10.0.3 and
FreeCAD 1.1.1. Both CTX-103.1 and CTX-104.1 say so explicitly. This spec defines how the live paths
get exercised on Windows and Linux — self-hosted runners with real CAD installs, a documented
manual checklist, or containerized KiCad. Until then, "works on Windows" is an untested claim about
the two most fragile integration points in the codebase. `SPEC-402`'s `CTX-402.5` (2026-08-17)
shipped real Windows/Linux *builds*, still explicitly pre-release for exactly this reason — this
spec is what would move them past that label.


#### [SPEC-404](specs/SPEC-404-managed-hosted-access.md) — Managed Hosted Access — 📋 Draft 2026-08-25
*Module:* repo-wide + an external gateway service · *Depends on:* SPEC-201, SPEC-106, SPEC-402

An optional paid tier supplying LLM inference through a GittieLabs-operated gateway, so a user can
install the app and use every AI feature without holding an account with a model vendor. Today's
first run sends them out of the product for five steps — vendor account, payment method, API key —
which is where the funnel ends for anyone who wanted to look up a part rather than become an
LLM-API customer.

**The tier sells operation, not capability, and no source is ever withheld from this repository** —
not temporarily, not behind an early-access window. Subscribers receive earlier *builds* of source
that is already public, through a second `SPEC-402` updater channel; anyone building from source has
the same feature the same day. That early-access fleet is also the closest thing to a real answer
for `SPEC-403`'s problem, which is that every live CAD test to date has run on one machine.

Managed is one more entry in `SPEC-201`'s provider abstraction — a base URL and a bearer token — not
a hosted version of the app, which would contradict `PRODUCT-PLAN.md`'s files-as-source-of-truth
model and the local KiCad/FreeCAD process dependency. The gateway is an external system; this spec
carries only the wire contract the client is written against.

Two things it settles rather than defers. **Updates are not sold** — `SPEC-402` already ships
auto-update free to every installed copy, so selling updates would require degrading the free build.
And the contributor policy is **DCO, not CLA**: the cost is that the project can no longer be
relicensed without contributor consent, which is the intended outcome, not an oversight. Vendor
terms were verified rather than assumed (Anthropic Commercial Terms §A.1/§D.4, OpenAI Services
Agreement §2.2/§3.1) — building an application for your own end users is expressly permitted,
reselling account or API access is expressly prohibited, and the gateway must be funded by a paid
API account rather than a consumer subscription.

#### [SPEC-405](specs/SPEC-405-product-rename-copperplane.md) — Product Rename to Copperplane — ✅ done ([CTX-405.3](context/CTX-405.3-identity-guard-tests.md), [CTX-405.1](context/CTX-405.1-rename-app-and-icons.md)) 2026-08-25
*Module:* repo-wide (code, docs, icons) · *Depends on:* SPEC-402, SPEC-106 · *Parent:* SPEC-000

Renames the product from Hardware Agent Studio to **Copperplane** everywhere a person can see it —
window title, menu, About box, docs site, app icon — while freezing the five on-disk identity
strings (bundle identifier, keychain service, both daemon data-directory constants, the
`.kicad_mod` generator stamp) exactly as they are, so a `v0.1.3` user's library, keys and linked
projects survive the update untouched. "Agent Studio" collides with Oracle, Google, Automation
Anywhere and others; Copperplane is clean on USPTO and pulls the name out of AI-tooling vocabulary
into the user's own — the solid ground layer of a PCB.

The real hazard the spec is built around: a global find-and-replace would appear to work, keep CI
green, and silently orphan every existing user's keys and linked projects by renaming the frozen
identity strings along with everything else. Three identity-guard tests are the mitigation. Fully
independent of the managed-tier work above — no shared files, no shared dependency — and can land
on its own branch whenever a clean 75-file diff is convenient.

#### [SPEC-406](specs/SPEC-406-contributor-local-builds.md) — Contributor Local Builds & Signing Defaults — ✅ done ([CTX-406.1](context/CTX-406.1-unsigned-local-build-default.md)) 2026-08-26
*Module:* core/tauri-rust, repo root (`.github/workflows/release.yml`, `CONTRIBUTING.md`) · *Depends on:* SPEC-402, SPEC-401 · *Parent:* SPEC-402

Makes an unsigned, installable local build the **default** outcome of `tauri build`, instead of the
release-only `createUpdaterArtifacts: true` setting living in the shared `tauri.conf.json` and
demanding a `TAURI_SIGNING_PRIVATE_KEY` no contributor can have. Hit for real by the maintainer on
2026-08-26 trying to check the macOS app menu bar, which only exists in a bundled `.app`, not under
`tauri dev` — and `CONTRIBUTING.md` never documented a path past `tauri dev` at all, despite asking
for Windows/Linux platform reports that require one. The fix: a new release-only
`tauri.release.conf.json` overlay, merged by `--config` in `release.yml`'s three build legs only —
CI stays the only path to a signed, update-capable build, for maintainers too. Shipped in a single
context ([CTX-406.1](context/CTX-406.1-unsigned-local-build-default.md), 2026-08-26).

#### [SPEC-407](specs/SPEC-407-sidecar-build-integrity.md) — Sidecar Build Integrity & Fail-Loud Packaging — 🚧 in progress ([CTX-407.1](context/CTX-407.1-fail-loud-daemon-and-packaging-gate.md), [CTX-407.2](context/CTX-407.2-one-command-local-build.md)) 2026-08-27
*Module:* `services/python-daemon`, `core/tauri-rust`, `apps/tauri-ui`, `CONTRIBUTING.md` · *Depends on:* SPEC-401, SPEC-406, SPEC-107 · *Parent:* SPEC-401

Written from a real, single-session failure log, not from speculation: on 2026-08-27 the maintainer
built the app from a clean checkout and hit **seven** distinct failure modes in sequence, every one
of which produced a green build. Five were loud and cost minutes. Two were silent and are the
reason this spec exists.

The first silent one: the committed placeholder sidecar bundles cleanly, `Command::spawn` succeeds
because it is a real executable file, it exits 1 to a `stderr` no Finder-launched `.app` shows, and
`SPEC-107`'s heartbeat monitor kills an already-dead child fifteen seconds later while the app
itself keeps running, so the window stays open and every request fails with nothing user-facing.
The second, and worse: a mis-frozen sidecar (arch mismatch surviving PyInstaller's own `build/`
cache) **starts successfully**, answers `daemon.ready` with KiCad and FreeCAD both live, heartbeats
normally — and runs with `chat.send`, `agent.dispatch_tool`, `kicad.generate_component` and
`datasheet.generate_guidance` all disabled by `daemon.py`'s own import guards. A crash sends you to
the packaging; a healthy-looking daemon with no AI sends you hunting a UI bug that does not exist.

The through-line is distance between cause and symptom — an arch mismatch introduced at `pip
install` surfaced as a `dlopen` failure two stages later. So the design is three checkpoints, each
owning what only it can know: freeze time (framework interpreter, binary arch matches the
interpreter), bundle time (not the placeholder, arch matches the Tauri target), run time
(`daemon.ready` carries the list of optional modules that failed to import, and the app says so).

Also corrects two pieces of documentation that actively mislead: `CONTRIBUTING.md`'s Tier 3 row
never states the framework-Python requirement at all, and `daemon.spec`'s header still recommends
the Homebrew interpreter that `CTX-402.4` superseded with python.org universal2. And two real bugs
in `scripts/verify_sidecar.py` — it pipes the child's `stderr` and never drains it (hiding every
error, and deadlocking the daemon outright if the buffer fills), and its `daemon.configure` check
prints `FAIL` without incrementing the failure counter, so the packaging gate can print a failure
and still exit 0.

Explicitly **not** a change to `daemon.py`'s graceful degradation, which is correct and stays; not
signing or updater work (`SPEC-402`); not cross-platform proof (`SPEC-403`); and not a build
wrapper, which `SPEC-406` §1 already rejected.

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

[CTX-902.2](context/CTX-902.2-verify-commit-hashes-are-real.md) (2026-08-20) closed a real gap found
by reviewing a merged PR's own close-out, then confirmed against ten of the same session's own
context files: the existing `EMPTY COMMIT HASHES` check never verified a recorded hash actually
resolves to a real commit, so a commit hash discarded by `git commit --amend` (a real, then-common
mistake — history rewritten, the original pre-amend commit never pushed) sailed through silently
every time. Real design constraint found while building the fix: `git cat-file -e` isn't sufficient,
since an amended-away commit remains a real, loose object until eventual garbage collection —
`git merge-base --is-ancestor <hash> HEAD` checks real reachability instead (caught by this
context's own test suite on the first implementation attempt, recorded honestly in its Plan Drift).
Deliberately scoped to hashes newly added in the current diff, not every hash a file has ever
recorded — an older, already-merged file can legitimately cite a real commit from a since-deleted
feature branch (`CTX-315.2`'s own precedent, confirmed genuinely unfetchable in a fresh clone once
the branch is gone), and re-checking that on every unrelated future edit would be a false failure,
not a caught bug.

#### SPEC-903 — Python & Frontend CI
*Module:* `.github/workflows/` · *Depends on:* nothing

[CTX-903.1](context/CTX-903.1-python-frontend-ci.md) added `python-ci.yml` (uv matrix over three
OSes running `python -m unittest discover tests/`, with expected-skip verification for the live
CAD tests) and `frontend-ci.yml` (`vitest` plus `oxlint` plus `tsc -b`), following the pattern
`rust-core-ci.yml` already established.

#### [SPEC-904](specs/SPEC-904-license-attribution-consistency.md) — Repository License & Attribution Consistency — ✅ done ([CTX-904.1](context/CTX-904.1-license-attribution-consistency.md)) 2026-08-24

*Module:* repo root (`LICENSE`, `NOTICE`), `core/tauri-rust/Cargo.toml`, `apps/tauri-ui/package.json` · *Depends on:* nothing

Makes every machine-readable license declaration agree with the actual grant. `Cargo.toml` declared
`license = "MIT"`, a leftover from the Tauri scaffold, while the repo's real `LICENSE` is
Apache-2.0 — and that field is precisely what crates.io and automated license scanners read: the
version of the truth a machine is most likely to believe, and it was wrong. `package.json` had no
`license` field at all, which npm tooling reads as "no license asserted" rather than inheriting the
repo's. `LICENSE` itself still carried the unfilled Apache-2.0 appendix boilerplate, so the license
text never named a copyright holder anywhere in the repo. Not a relicense — the repo was already
Apache-2.0; this only makes the metadata match what was already true, and adds the missing
`NOTICE`. This spec's own norm is what later ruled `pymupdf`/`fitz` (AGPL-3.0) out of `SPEC-205` in
favour of `pdfplumber` (MIT).

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
SPEC-204 tool-calling, SPEC-109 enclosures derived from real board geometry, SPEC-304 workspace
model. The point where "Hardware Agent Studio" earns the middle word. (SPEC-203 supplier data,
originally listed here, was explored and retired 2026-08-18 — see its tombstone.)

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
