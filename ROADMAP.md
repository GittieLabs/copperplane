# 🗺️ Hardware Agent Studio — Roadmap

**Status:** Draft · **Last updated:** 2026-08-07 · **Current version:** `v0.1.0` (in progress)

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
| [SPEC-103](services/python-daemon/specs/SPEC-103-kicad-ipc.md) | `services/python-daemon` | [CTX-103.1](services/python-daemon/context/CTX-103.1-kicad-ipc.md) | 🔍 Review | `kipy` connection manager, version gate, `kicad.get_version` verified live against KiCad 10.0.3 |
| [SPEC-104](services/python-daemon/specs/SPEC-104-freecad-headless.md) | `services/python-daemon` | [CTX-104.1](services/python-daemon/context/CTX-104.1-freecad-headless-bridge.md) | 🔍 Review | `freecadcmd` path resolution, temp-script handoff, STL → GLB via `trimesh`, verified live against FreeCAD 1.1.1 |

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

#### SPEC-105 — Daemon Async Job & Progress Protocol
*Module:* `services/python-daemon` + `core/tauri-rust` + `apps/tauri-ui` · *Depends on:* SPEC-102, SPEC-101

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

#### SPEC-106 — Configuration & Secrets Store
*Module:* `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-102

One place for: `freecadcmd` path override (SPEC-104 §3 explicitly asks for this), KiCad IPC
settings, selected LLM provider and model, and supplier API keys. Keys must go to the OS keychain,
not a plaintext JSON file — and must never be passed as command-line arguments to the daemon, where
they'd be visible in `ps`.

*Open question:* does Rust own config and inject it into the daemon at spawn, or does the daemon
read the config file itself? The former keeps secrets out of Python's memory longer; the latter
lets the daemon reload without an app restart.

#### SPEC-107 — Structured Logging, Startup Handshake & Diagnostics
*Module:* all three · *Depends on:* SPEC-102

`stdout` is reserved for JSON-RPC frames, so **any** stray `print()` or library banner corrupts the
stream and produces a request that hangs forever with no error. This spec defines `stderr` as the
log channel, a rotating log file, and a `daemon.ready` startup handshake reporting detected
capabilities (KiCad present? FreeCAD present? which LLM providers reachable?).

*Why this matters more than it looks:* today, if `import kipy` fails, `daemon.py` dies before its
read loop starts, Rust sees a child that exited instantly, and the user sees a UI that simply never
responds. There is no path for that failure to reach a human.

#### SPEC-108 — KiCad Write Path: Footprint & Symbol Injection
*Module:* `services/python-daemon` · *Depends on:* SPEC-103, SPEC-202

The follow-through CTX-103.1 explicitly deferred: taking a structured component definition and
injecting a real `.kicad_mod` into the open board. Needs to cover placement coordinates,
transactions/undo grouping (a half-applied footprint is worse than none), library vs. board-local
footprints, and what happens when the user has unsaved changes.

*Known gotcha:* CTX-103.1's `FutureVersionError`-as-warning decision is untested against a real
breaking protocol change. Write operations are where that assumption gets expensive — a read that
returns garbage is annoying, a write that corrupts a board is not.

#### SPEC-109 — Parametric Enclosure Generator
*Module:* `services/python-daemon` · *Depends on:* SPEC-104, SPEC-108

The feature the README actually promises: read board outline and mounting-hole positions **from
KiCad**, feed them to FreeCAD, get an enclosure that fits. This is the first spec where the two
bridges talk to each other, and it's where the product stops being two disconnected toys.

Scope: board outline extraction, hole positions, wall thickness/tolerance/standoff parameters,
fillets, and STEP export alongside `.glb` so the result is usable in real mechanical CAD.

### 3.2 `2xx` — Intelligence layer

#### SPEC-201 — LLM Provider Abstraction
*Module:* `services/python-daemon` · *Depends on:* SPEC-102, SPEC-106, SPEC-105

The "Local AI (Privacy First)" promise, made real. One interface over local Ollama and remote
providers, with model selection, streaming, timeouts, retries, and a clear statement of what leaves
the machine under each configuration.

*Constraint inherited from SPEC-000 §3:* heavy imports block `stdout` for 2–4 seconds at startup.
Prefer lazy import of provider clients so the daemon's `ready` handshake isn't delayed by a
provider the user never selected.

#### SPEC-202 — Component Intelligence Pipeline
*Module:* `services/python-daemon` · *Depends on:* SPEC-201, SPEC-203

The heart of the product, and the thing that replaces the `time.sleep(1.5)` mock. Datasheet or part
number in → validated structured component (pins, numbers, names, electrical types, package
dimensions, courtyard) out. The structured schema is the contract SPEC-108 consumes.

*Design position worth taking early:* the LLM should produce **structured data validated against a
schema**, never raw `.kicad_mod` s-expression text. Generated geometry must be checked (pin count
matches the package, pitch is sane, courtyard encloses pads) before anything reaches a board. A
hallucinated footprint that looks plausible costs a PCB spin — this is the highest-consequence
failure mode in the product, and it deserves its own section in the spec.

#### SPEC-203 — Supplier API Integration
*Module:* `services/python-daemon` · *Depends on:* SPEC-106

DigiKey / Octopart / Mouser: authentication, rate limits, a local cache (part data barely changes;
re-querying on every request wastes quota and adds latency), and graceful degradation to
LLM-only extraction when no key is configured or the user is offline.

#### SPEC-204 — Agent Tool Registry
*Module:* `services/python-daemon` · *Depends on:* SPEC-201, SPEC-102

What makes this an *agent* studio rather than a form with an LLM behind it: exposing the `ROUTES`
registry to the model as callable tools, so "put a BME280 near the ESP32 and give me an enclosure
that fits" decomposes into a plan across the KiCad and FreeCAD bridges. Needs a policy for which
tools are auto-approved versus confirmation-gated — **anything that writes to a board should be
confirmation-gated by default.**

*Note:* SPEC-000 §1 explicitly rules out MCP as the transport, for good reasons (binary `.glb`
streaming, bespoke UI rendering). That decision is about the *wire protocol*; MCP's tool-description
conventions are still worth borrowing as a schema shape.

### 3.3 `3xx` — Product surface

#### SPEC-301 — 3D Viewer
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-104, SPEC-105

SPEC-101 names React Three Fiber, but nothing renders today — `freecad.generate_enclosure` returns
a `.glb` path that the UI simply never opens. Scope: R3F canvas, camera/lighting defaults that make
a grey box legible, loading and error states, and disposal on unmount (leaking GPU buffers across
repeated generations is the standard Three.js failure).

*Known gotcha, and it will bite immediately:* the `.glb` is written to the system temp directory,
and `tauri.conf.json` currently configures no `assetProtocol` scope at all (`csp` is `null`, no
`fs`/asset permissions in `capabilities/default.json`). The WebView cannot load an arbitrary
absolute path from disk. Either scope the asset protocol to the daemon's output directory, or have
Rust read the bytes and hand them to the frontend as a blob. **Decide this in the spec, not
mid-implementation.**

#### SPEC-302 — Chat & Command Surface
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-105, SPEC-201

`App.tsx` is one input, one button, and a `<pre>` dump of raw JSON. The README's framing — "type
'Generate a footprint for BME280'" — implies a conversation: message history, streaming tokens,
tool-call rendering, per-message error states, and inline `.glb` previews.

#### SPEC-303 — Settings UI
*Module:* `apps/tauri-ui` · *Depends on:* SPEC-106, SPEC-107

The surface for SPEC-106, plus the diagnostics panel SPEC-107 makes possible: is KiCad reachable,
is its IPC server enabled, where is `freecadcmd`, which model is selected, and a one-click "copy
diagnostics" for bug reports. The single highest-leverage thing for reducing "it doesn't work"
issues from contributors.

#### SPEC-304 — Project & Workspace Model
*Module:* `apps/tauri-ui` + `services/python-daemon` · *Depends on:* SPEC-108, SPEC-109

Binding a session to a KiCad project on disk: which board is being edited, where generated
artifacts are written (next to the project, not `/tmp`), and how enclosure revisions are tracked
alongside board revisions. Deferrable until SPEC-108 and SPEC-109 make artifacts worth keeping.

### 3.4 `4xx` — Distribution & operations

#### SPEC-401 — Python Sidecar Packaging
*Module:* `core/tauri-rust` + `services/python-daemon` · *Depends on:* SPEC-107

**The highest-risk unsolved problem in the project.** Two concrete blockers, both quoted in §1.2:
`env!("CARGO_MANIFEST_DIR")` bakes the developer's checkout path into the binary, and
`Command::new("python3")` assumes a system Python with `kipy`, `pynng`, and `trimesh` importable.

Scope: freeze the daemon (PyInstaller or equivalent) into a per-target binary, ship it via Tauri's
`externalBin`/sidecar mechanism, resolve it from the app's resource directory at runtime, and keep
the crash shield working across that change. Budget real time for `pynng`'s native extension and
`trimesh`'s optional dependencies — frozen native wheels are where this kind of work goes wrong.

*Do this before showing the app to anyone who isn't sitting at Keith's desk.*

#### SPEC-402 — Release, Signing & Auto-Update
*Module:* repo-wide · *Depends on:* SPEC-401

Tagged releases, macOS notarization, Windows code signing, Tauri updater, and a changelog derived
from the `CTX-*.md` implementation logs — which the framework already collects, and which nothing
currently reads.

#### SPEC-403 — Cross-Platform Verification Matrix
*Module:* repo-wide · *Depends on:* SPEC-903

Every live CAD test to date has run on exactly one machine: Keith's Mac, with KiCad 10.0.3 and
FreeCAD 1.1.1. Both CTX-103.1 and CTX-104.1 say so explicitly. This spec defines how the live paths
get exercised on Windows and Linux — self-hosted runners with real CAD installs, a documented
manual checklist, or containerized KiCad. Until then, "works on Windows" is an untested claim about
the two most fragile integration points in the codebase.

### 3.5 `9xx` — The framework itself

#### [SPEC-901](specs/SPEC-901-agent-operating-manual.md) — Agent Operating Manual & Context Generation Protocol
*Module:* repo-wide · *Depends on:* nothing — **start here**

**Written 2026-08-08.** No `CTX-901.1` yet — the spec exists, `CLAUDE.md` and the four slash
commands (`/spec-status`, `/new-spec`, `/new-context`, `/close-context`) don't. See §5 below for the
workflow it formalizes.

#### SPEC-902 — Spec Graph Validator v2
*Module:* `scripts/` · *Depends on:* SPEC-901

Upgrade `validate_spec_context.py` from a context linter into a graph validator: parse `SPEC-*.md`
frontmatter too, verify every `parent_spec` / `child_specs` / `spec_ref` path resolves on disk,
check id uniqueness and that `id` matches the filename, flag orphan specs and specs with no
context, and check that `location:` matches the file's actual path. Every one of the §1.3 breakages
is mechanically detectable — the framework should catch them instead of a human reading carefully.
Also fix the `.json`/`README.md` exclusion bugs noted there.

#### SPEC-903 — Python & Frontend CI
*Module:* `.github/workflows/` · *Depends on:* nothing

`rust-core-ci.yml` is a good template; Python and the frontend need the equivalent. Python: `uv`
matrix over the three OSes running `python -m unittest discover tests/` (live CAD tests skip
themselves cleanly by design — verify the skips actually happen rather than silently passing zero
assertions). Frontend: `vitest` plus `oxlint` plus `tsc -b`.

---

## 4. Milestones

### M0 — Framework repair *(days, do first)*
Unblocks everything else and makes the repo safe for parallel agent work.

| # | Work | Spec |
| :--- | :--- | :--- |
| 1 | ~~Fix spec graph links, write SPEC-102~~ ✅ done 2026-08-07 | — |
| 2 | Agent operating manual + context-generation commands | SPEC-901 |
| 3 | Python & frontend CI | SPEC-903 |
| 4 | Validator v2 | SPEC-902 |
| 5 | Merge `feat/CTX-103.1-*` and `feat/CTX-104.1-*` into `develop`; move both CTX files Review → Completed | — |

### M1 — `v0.1.0` "It's real" — the end-to-end vertical slice
**Goal:** type a part number, watch an AI generate a real footprint, see it land in a live KiCad
board, get an enclosure sized to it, and rotate that enclosure in the app. One journey, working,
on a dev machine.

Critical path, in dependency order:

```text
SPEC-105 (async jobs & progress)   ─┬─> SPEC-201 (LLM provider) ──> SPEC-202 (component pipeline) ──> SPEC-108 (KiCad injection)
SPEC-106 (config & secrets)        ─┘                                                                        │
SPEC-107 (logging & handshake)     ─────────────────────────────────────────────────────────────────────────┤
SPEC-301 (3D viewer) ──────────────────────────────────────────────────────────> SPEC-302 (chat surface) ────┴──> demo
```

SPEC-105 comes first because without it the UI locks up for the entire duration of every AI call,
which makes the demo unwatchable regardless of how good the generation is. SPEC-301 has no
dependency on the AI work and can run fully in parallel — the `.glb` pipeline already produces
valid output today.

**Explicitly out of M1:** packaging (SPEC-401), enclosure-from-board-geometry (SPEC-109), supplier
APIs (SPEC-203), agent tool-calling (SPEC-204). M1 proves the product is possible; it does not
produce something installable.

### M2 — `v0.2.0` "It ships"
SPEC-401 packaging, SPEC-106/303 settings and diagnostics surfaced, SPEC-107 logging, SPEC-402
signing and updates, SPEC-903/403 verification on Windows and Linux. This is the milestone where
the `.app` works on a machine that has never seen the repo.

### M3 — `v0.3.0` "It's an agent"
SPEC-204 tool-calling, SPEC-203 supplier data, SPEC-109 enclosures derived from real board
geometry, SPEC-304 workspace model. The point where "Hardware Agent Studio" earns the middle word.

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

---

## 6. Risk register

| Risk | Impact | Where it's handled |
| :--- | :--- | :--- |
| Packaging the Python sidecar proves harder than expected (native wheels: `pynng`, `trimesh`) | The app is undeliverable; M2 slips indefinitely | SPEC-401 — worth a spike before M1 finishes, so the surprise lands early |
| An LLM hallucinates a plausible-but-wrong footprint that reaches a real board | A wasted PCB spin; the fastest way to lose a hardware engineer's trust permanently | SPEC-202 validation layer + SPEC-204 confirmation gate on all writes |
| KiCad's IPC API changes across a major version | The KiCad bridge breaks wholesale; CTX-103.1's "patch bumps are safe" assumption is untested against a real break | SPEC-103 version gate, revisited in SPEC-108 |
| Windows and Linux live paths stay unverified | "Cross-platform" is a claim, not a fact, at the two most fragile integration points | SPEC-403, SPEC-903 |
| macOS crash shield never gets its heartbeat | Orphaned Python and FreeCAD processes accumulate on the platform being developed on | Unowned — needs a home in SPEC-107's handshake work |
| Solo-maintainer bandwidth vs. a 16-spec backlog | Half-built layers, none finished | Milestones are ordered so each one ends at a demonstrable state; M1 is deliberately narrow |

---

## 7. Immediate next actions

1.  Merge the two open CAD branches into `develop` and close out CTX-103.1 / CTX-104.1.
2.  Write **SPEC-901** and land `CLAUDE.md` + the four slash commands. Everything downstream gets
    cheaper once an agent can generate its own context files reliably.
3.  Write **SPEC-903** and get Python + frontend tests running in CI on all three OSes.
4.  Spike **SPEC-401** packaging far enough to know whether frozen `pynng`/`trimesh` is a day or a
    fortnight. Find out now, not in M2.
5.  Write **SPEC-105**, then start M1.
