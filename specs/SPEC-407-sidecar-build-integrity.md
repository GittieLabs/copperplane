---
id: SPEC-407
title: "Sidecar Build Integrity & Fail-Loud Packaging"
status: In-Progress
type: Feature
created: 2026-08-27
last_updated: 2026-09-03
target_version: v0.2.1
location: "specs/SPEC-407-sidecar-build-integrity.md"
parent_spec: "SPEC-401-python-sidecar-packaging.md"
child_specs: []
user_facing: true
---

# SPEC-407: Sidecar Build Integrity & Fail-Loud Packaging

> **Still open, 2026-09-03:** §5's user-facing half is **not built**. The daemon reports degraded modules in `daemon.ready`, in `daemon.get_capabilities` and now in `daemon.list_routes`, and `ensure_sidecar` fails a build on them — but nothing in `apps/tauri-ui` reads any of it, so a user whose *installed* app has a degraded daemon still sees a healthy-looking app with missing features. That is the exact experience §1 exists to end, surviving on the one path the build gate cannot reach.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Make it impossible for a local build to report success while producing an
    app that cannot work. Every stage that can silently substitute a broken sidecar — the freeze,
    the bundle, the spawn, the daemon's own startup — gains a check that fails loudly at that stage,
    and the app surfaces a daemon that started with missing capabilities instead of presenting
    itself as healthy.

*   **Business / Technical Value:** On 2026-08-27 the maintainer built the app from a clean
    checkout and hit **seven** distinct failure modes in sequence, every one of which produced a
    green build. The costly ones were not the loud errors — those were fixed in minutes. They were
    the two silent ones: a placeholder sidecar that bundles cleanly and kills the app fifteen
    seconds after launch with no visible cause, and a mis-frozen sidecar that starts, reports
    `daemon.ready`, passes the heartbeat shield, and runs with the **entire AI surface disabled**.
    The second is worse than a crash. A crash sends you to the packaging; a healthy-looking daemon
    with no `chat.send`, no `agent.dispatch_tool`, no `kicad.generate_component` and no
    `datasheet.generate_guidance` sends you hunting for a UI bug that does not exist.

    `CONTRIBUTING.md` asks outside contributors for Windows and Linux platform reports
    (`SPEC-406`). Those reports are worth nothing if a contributor's build can be quietly broken in
    seven ways, because the report will describe the breakage rather than the platform.

*   **Non-Goals:**
    *   **Not a change to how the daemon degrades.** `daemon.py`'s per-module `try/except` import
        guards are correct and stay exactly as they are — a missing optional module must not take
        the whole daemon down. This spec surfaces that state; it does not remove it.
    *   **Not code signing, notarization, or updater work.** `SPEC-402` owns those. This spec is
        about integrity of the artifact, not its provenance.
    *   **Not cross-platform verification.** `SPEC-403` owns that. Every check here must work
        identically on all three platforms, but proving it does is `SPEC-403`'s job.
    *   **Not a build wrapper, Makefile, or task runner.** `SPEC-406` §1 already rejected that, and
        nothing found here changes the reasoning. Checks belong in the steps that already exist.
    *   **Not removing the committed placeholder.** It exists because `tauri-build`'s own `build.rs`
        checks the `externalBin` path on every `cargo build`, including a plain debug build. It
        stays; it just stops being silently bundleable.

## 2. System Architecture & Design Choices

### 2.1 The seven failure modes, as found

Every one of these was hit for real in a single session, in this order. They are recorded here
because the *pattern* is the finding: each stage trusts the previous stage's output without
checking it.

| # | Failure | Where it surfaces today |
| :--- | :--- | :--- |
| 1 | PyInstaller refuses a non-framework Python interpreter | Loud, at freeze time — fine as-is |
| 2 | `CONTRIBUTING.md` Tier 3 never states the framework-Python requirement | Nowhere; the knowledge lives only in `daemon.spec`'s header and `CTX-401.1` |
| 3 | `daemon.spec`'s header still recommends Homebrew, superseded by `CTX-402.4` | Nowhere; actively misleads |
| 4 | Arch prefix applied inconsistently across venv, pip and freeze | Loud once, then silently bypassed by PyInstaller's `build/` cache |
| 5 | Frozen binary is never renamed to the target-triple sidecar name | Nowhere; the placeholder is bundled instead |
| 6 | `verify_sidecar.py` discards the child's `stderr`, and one check prints FAIL without counting it | Nowhere; the gate can print FAIL and exit 0 |
| 7 | A mis-frozen sidecar starts, reports ready, and runs with every AI route disabled | Only in a log file nobody opens |
| 8 | A real freeze overwrites a TRACKED placeholder, leaving a permanent ~50MB git modification | Nowhere; `git add -A` would commit the binary and `git checkout -- .` would destroy the freeze |

### 2.2 Fail at the stage that knows, not the stage that suffers

**Decided: each check lives where the information is, not where the symptom appears.**

The through-line of all seven is distance between cause and symptom. An arch mismatch introduced at
`pip install` surfaced as a `dlopen` failure inside a frozen binary two stages later. A missing
`mv` surfaced as an app whose every request fails. The fix is not better error messages at
the end; it is refusing to hand a known-bad artifact to the next stage.

Three checkpoints, each owning what only it can know:

*   **Freeze time** (`services/python-daemon`) — the interpreter is a framework build; the
    resulting binary's architecture matches the interpreter that produced it.
*   **Bundle time** (`core/tauri-rust`) — the file about to be bundled as `externalBin` is not the
    placeholder, and its architecture matches the Tauri build target.
*   **Run time** (`core/tauri-rust` + `apps/tauri-ui`) — the daemon that answered `daemon.ready`
    reports which optional modules failed to import, and the app shows it.

### 2.3 The placeholder must be detectable, not just documented

The placeholder is a 922-byte `/bin/sh` script whose only job is to satisfy `tauri-build`'s
existence check. Today the only thing standing between it and a shipped bundle is a human
remembering a `mv`. When it does get bundled, `Command::spawn` **succeeds** — it is a real,
executable file — so nothing in the Rust supervisor treats it as an error. It exits 1 to a `stderr`
that `Stdio::inherit()` sends nowhere visible from a `.app` launched by Finder. Fifteen seconds
later `spawn_heartbeat_monitor` concludes a hard crash and calls `DaemonHandle::shutdown`, which is
`child.kill()` on a process that is already dead — **the app itself keeps running**. Every
`dispatch_to_daemon` call then returns `Err` from writing to a closed pipe, so the window stays
open and nothing works, with no explanation anywhere the user can see.

**Decided: the check is a build-time file inspection, not a runtime behavioural probe.** All four
committed placeholders carry a literal `PLACEHOLDER` marker and a `#!/bin/sh` shebang; a real
PyInstaller binary is Mach-O, PE or ELF and never contains it. That makes the test exact rather
than heuristic, and a build-time failure is worth more than a better runtime error.

**Decided (revising `SPEC-406` §1): the check runs from `tauri.conf.json`'s own
`beforeBuildCommand`, and it may fix the problem rather than only report it.** `SPEC-406` §1
rejected "a `Makefile`, `just` file, or wrapper script" on two grounds: that a documented one-line
command was the deliverable, and that a wrapper is "a second thing to keep in sync with
`release.yml`". The first ground is now falsified by evidence — the documented one-line command
produces a broken app, and did so seven different ways in a single session. The second is answered
rather than accepted: `release.yml` calls the *same* script, so its own freeze and rename steps
collapse into one line. This is not a second implementation to keep in sync; it is the only one,
where previously the sequence existed twice (once in CI, once as prose in `CONTRIBUTING.md`).

`beforeBuildCommand` is Tauri's own hook and already runs the frontend build, so this adds no new
mechanism. The fast path — sidecar present, not the placeholder, right architecture — is a file
read and exits immediately, so only a genuinely missing or broken sidecar pays for a freeze.

### 2.4 `daemon.ready` must carry degraded state

**Decided: `daemon.ready`'s existing `params` gains a list of optional modules that failed to
import.** `daemon.py` already knows this — it logs each one — and `daemon.ready` already carries a
real capability payload (`kicad_available`, `freecad_available`, `fts5_available`,
`llm_providers`). Adding the failure list is an extension of a contract that exists, not a new one.

The rejected alternative was having the frontend probe each route and infer availability. It is
strictly worse: N round trips to rediscover something the daemon knew at import time, and it can't
distinguish "module missing" from "route failed for this input."

`SPEC-107` owns diagnostics; this is a capability field on an existing handshake, not a new
diagnostics channel.

### 2.5 What the user sees

A daemon that comes up with missing modules is not a crash and must not be presented as one —
`SPEC-101`'s crash shield has its own surface and this is not it. It is also not dismissible noise:
a user whose AI features are all silently gone needs to know *why* before they file a bug against
the wrong thing.

This is the one genuinely user-facing piece of this spec, and §5 covers it.

### 2.6 Cross-Module Impacts

*   `services/python-daemon` — `daemon.py` collects import failures into the `daemon.ready`
    payload; `daemon.spec`'s stale header corrected; `scripts/verify_sidecar.py` captures `stderr`
    and counts every failure.
*   `core/tauri-rust` — build-time sidecar integrity check; the `daemon.ready` payload gains a
    field the supervisor forwards unchanged.
*   `apps/tauri-ui` — surfaces degraded capability (§5).
*   `CONTRIBUTING.md` — the Tier 3 row gains the interpreter requirement, the arch-consistency
    rule, and the rename step.
*   `.github/workflows/release.yml` — no change expected; CI already does all three correctly. The
    checks must not break it, which is itself a real risk (§3).

## 3. Known Constraints & Risks

*   **A build-time check that runs on every `cargo build` would break the debug loop.** The
    placeholder exists precisely so a plain `cargo build`/`cargo test` works without a 32MB freeze.
    A check that rejects the placeholder unconditionally would make the repo un-buildable for
    anyone not doing a release build. It must fire only on a real bundle, and establishing where
    that hook actually exists in Tauri v2 is real work, not an assumption. **This is the single
    most likely thing to go wrong in implementation.**
*   **The `build/` cache can bypass PyInstaller's own arch check.** Observed directly: the same
    mismatch that produced a hard `IncompatibleBinaryArchError` on the first run was silently
    accepted on a re-run, moving the failure from build time to a `dlopen` error at runtime. Any
    freeze-time check must not itself be cacheable.
*   **`verify_sidecar.py` currently reads `stderr` into a pipe it never drains.** Beyond hiding the
    error, an undrained pipe blocks the child once the buffer fills, so a sufficiently chatty
    failure deadlocks the daemon rather than merely being invisible. The fix must drain on a
    thread, not merely redirect.
*   **The ~11s Gatekeeper cold-launch delay sits against a 15s heartbeat timeout.** `CTX-401.1`
    measured the delay; `HEARTBEAT_TIMEOUT_S` is 15. That is roughly four seconds of margin on an
    ad-hoc-signed sidecar, and a slower machine could trip the crash shield on a perfectly good
    build. **Not this spec's to fix, but adjacent enough to name**, because it produces the same
    symptom as failure mode 5 and would be misdiagnosed as one.
*   **Degraded state must not become a nag.** `SPEC-404` §3 and `SPEC-320` §1 hold a hard line
    against interstitials and badges. A permanent banner for a condition most users will never see
    would violate the same principle from a different direction.
*   **Every check must hold on all three platforms.** The arch checks are macOS-shaped by origin
    (universal2, Rosetta, `arch`). Windows and Linux have no equivalent and must not inherit a
    check that cannot pass there. Real verification of that is `SPEC-403`'s.
*   **Resolved — the bundle-time check lives in `beforeBuildCommand`** (§2.3), which also settles
    that it is enforcement rather than documentation: a contributor cannot skip it, because it is
    the build. The `build.rs` alternative was rejected for the reason named above — it would fire
    on every `cargo build`/`cargo test` and make the repo un-buildable without a 32MB freeze.
*   **The freeze needs an interpreter a contributor may not have.** The script fails with the exact
    remedy rather than a vague error, which is strictly better than today's silent placeholder —
    but it is still a hard stop on a machine with no framework Python, and on macOS that means a
    `sudo installer` run before a first successful build.
*   **Open question — whether CI needs the same checks.** CI already does all three things
    correctly, so the checks would be no-ops there. Adding them anyway guards against a future
    `release.yml` edit reintroducing the bug; not adding them keeps the pipeline simpler. Worth
    deciding deliberately rather than by omission.

## 4. Module Map & Reference Links

```text
[Root Spec](SPEC-000-architecture-overview.md)
   └── [SPEC-401 Python Sidecar Packaging](SPEC-401-python-sidecar-packaging.md)
          └── [This Spec](SPEC-407-sidecar-build-integrity.md)
```

*   [SPEC-402 Release, Signing & Auto-Update](SPEC-402-release-signing-and-auto-update.md) — owns
    signing and the updater; this spec must not change either.
*   [SPEC-406 Contributor Local Builds](SPEC-406-contributor-local-builds.md) — established the
    three-tier local build model these checks defend.
*   [SPEC-403 Cross-Platform Verification Matrix](../ROADMAP.md) — unspecced; owns proving these
    checks hold on Windows and Linux.
*   [SPEC-107 Structured Logging & Diagnostics](SPEC-107-structured-logging-diagnostics.md) — owns
    the diagnostics bundle; §2.4's field is a capability on an existing handshake, not diagnostics.
*   [SPEC-101 UI & Rust Process Supervisor](../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md) — the
    crash shield whose surface degraded-start must stay distinct from.
*   [CTX-401.1](../context/CTX-401.1-python-sidecar-macos.md) — the framework-Python requirement and
    the ~11s Gatekeeper measurement.
*   [CTX-402.4](../context/CTX-402.4-intel-macos-build.md) — the arch-prefix pattern and the
    target-triple rename, both of which this spec turns from convention into check.

## 5. User & Interaction

*   **Product Stage:** App startup, across every stage — the condition is global, not scoped to one
    tab, because it disables routes several stages depend on.
*   **What the user is trying to accomplish:** Use the AI features. When they are not there, find
    out that the build is at fault rather than concluding the product is broken or, worse, filing a
    bug against a UI that is working correctly.
*   **What the user sees and does:** When the daemon reports optional modules that failed to
    import, the app states plainly that it started with reduced capability, names what is
    unavailable in the user's terms ("AI chat and review are unavailable in this build"), and
    points at the daemon log for the reason. It is dismissible and does not block work — KiCad,
    FreeCAD, the library and the viewer are all still real. It is not a crash dialog, and there is
    no retry button, because nothing the user can do at runtime will fix a bad build.
