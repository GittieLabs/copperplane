---
id: SPEC-903
title: "Python & Frontend CI"
status: Draft
type: System
created: 2026-08-08
last_updated: 2026-08-08
target_version: v0.1.0
location: "specs/SPEC-903-python-frontend-ci.md"
parent_spec: null
child_specs: []
---

# SPEC-903: Python & Frontend CI

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give `services/python-daemon` and `apps/tauri-ui` the same CI coverage
    `core/tauri-rust` already has. `.github/workflows/rust-core-ci.yml` runs the Rust suite across
    `ubuntu-latest`/`windows-latest`/`macos-latest` on every PR; there is no equivalent for Python
    or the frontend, so `test_daemon.py`, `test_kicad_bridge.py`, `test_freecad_bridge.py`,
    `test_agent_docs.py`, and `ipc.test.ts` are only ever green on Keith's Mac.
*   **Business / Technical Value:** `rust-core-ci.yml` has already caught real bugs before they
    shipped (`CTX-101.1` Deviation 4: a Windows compile failure and a Linux test race, both on the
    very first run). There is no reason to believe the Python or frontend suites are any less
    likely to have latent OS-specific bugs — they simply haven't had the chance to be checked
    anywhere but one developer's machine. `ROADMAP.md` §1.1 names "cross-platform CI caught real
    bugs" as a norm worth preserving; right now it only applies to a third of the codebase.
*   **Non-Goals:**
    *   Not a rewrite of the test suites themselves — this spec wires up runners for the tests that
        already exist. Writing more tests is each module's own ongoing work.
    *   Not `SPEC-902` (Spec Graph Validator v2). Running `scripts/validate_spec_context.py` in CI
        is arguably in scope for "CI," but `ROADMAP.md` explicitly separates graph-validation
        tooling into its own spec; this one is about running the *product's* test suites.
    *   Not solving `CTX-103.1`/`CTX-104.1`'s "verified on exactly one machine" gap for the live
        KiCad/FreeCAD integration tests. Neither tool can be installed on a GitHub-hosted runner.
        This spec's job is making sure those tests *skip themselves visibly* in CI rather than
        silently passing zero assertions — actually running them for real on Windows/Linux is
        `SPEC-403`'s job (self-hosted runners or containerized CAD tools).

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   Two independent workflows, mirroring the existing `rust-core-ci.yml` pattern rather than
        one monolithic workflow — a frontend-only PR shouldn't wait on a Python matrix job and
        vice versa. Both are scoped with `paths:` filters the same way `rust-core-ci.yml` is scoped
        to `core/tauri-rust/**`.
    *   Python: matrix over `ubuntu-latest`/`windows-latest`/`macos-latest`, `uv` for environment
        setup (matching `services/python-daemon/README.md`'s documented workflow — don't introduce
        a second Python tooling convention), running
        `python -m unittest discover services/python-daemon/tests` and
        `python -m unittest discover scripts/tests`. Both directories use the same
        `python -m unittest discover <dir>` convention already; there's no reason to invent a
        different one for `scripts/tests/test_agent_docs.py`.
    *   Frontend: single job (Node has far less OS-specific surface than a daemon that shells out
        to native CAD tools), running `npx vitest run`, `npm run lint` (`oxlint`), and `npx tsc -b`
        against `apps/tauri-ui`.
    *   **Skip verification, not just exit-code trust.** `ROADMAP.md` §3.5 explicitly calls this
        out: "verify the skips actually happen rather than silently passing zero assertions." A
        `self.skipTest(...)` that never fires because a code path silently changed still returns
        exit code 0 — the CI step must positively assert that `test_kicad_bridge.py`'s and
        `test_freecad_bridge.py`'s live-integration tests are actually reported as **skipped** on
        every OS (since none of them have KiCad/FreeCAD installed), not merely that the overall
        suite passed.

*   **Data Flow / Interactions:**

    ```text
    PR touches services/python-daemon/** or scripts/**
          │
          ▼
    python-ci.yml (matrix: ubuntu/windows/macos)
          │  uv venv + uv pip install -r requirements.txt
          ▼
    python -m unittest discover services/python-daemon/tests -v
    python -m unittest discover scripts/tests -v
          │  capture verbose output
          ▼
    assert "test_002_real_kicad_version_round_trip ... skipped" appears
    assert "test_004_real_enclosure_round_trip ... skipped" appears
          │
          ▼
    pass/fail reported on the PR check

    PR touches apps/tauri-ui/**
          │
          ▼
    frontend-ci.yml (single job)
          │  npm ci
          ▼
    npx vitest run   +   npm run lint   +   npx tsc -b
          │
          ▼
    pass/fail reported on the PR check
    ```

*   **Cross-Module Impacts:**
    *   Adds `.github/workflows/python-ci.yml` and `.github/workflows/frontend-ci.yml`.
    *   Reads, but does not modify, `services/python-daemon/requirements.txt`,
        `services/python-daemon/tests/`, `scripts/tests/`, and `apps/tauri-ui/package.json`.
    *   No impact on `core/tauri-rust` or `rust-core-ci.yml` — that workflow is untouched.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   `services/python-daemon` has no `pyproject.toml`/lockfile, only `requirements.txt` — matches
        the module's existing (deliberate, per `CTX-103.1`) convention, but means CI can't pin
        transitive versions the way a lockfile would. Not this spec's problem to fix; noted so a
        future flaky CI run isn't mistaken for a workflow bug.
    *   `kicad-python`, `pynng`, and `trimesh` all need to install cleanly on `windows-latest` and
        `ubuntu-latest` via `uv pip install -r requirements.txt` for the Python job to even reach
        the test step. `CTX-101.1`'s Deviation 4 shows Windows-specific install/compile failures
        are a real, not hypothetical, risk category in this repo — budget for the first CI run to
        fail on environment setup before it ever reaches a test.
*   **Gotchas & Hazards:**
    *   **A `self.skipTest(...)` for a missing live dependency looks identical to a test that
        silently stopped running.** Both report 0 failures. The CI step for the Python matrix must
        parse verbose test output and fail loudly if the expected skip markers are absent — a green
        checkmark with the wrong reason behind it is worse than a red one.
    *   **`services/python-daemon`'s dependencies are not trivially pure-Python.** `pynng` has a
        native extension; per `ROADMAP.md` §3.4 (`SPEC-401`), frozen native wheels are "where this
        kind of work goes wrong." A CI install failure here is a leading indicator for that same
        packaging spike, not just a CI configuration bug — read it that way if it happens.
    *   **Node/npm version drift between this CI job and `apps/tauri-ui`'s actual dev setup** could
        make CI pass while a real contributor's `npm install` fails, or vice versa. Pin a specific
        Node major version in the workflow rather than trusting the runner image's default.

## 4. Module Map & Reference Links

This spec is not a child of `SPEC-000`: like `SPEC-901`, it's about the development framework's own
guarantees (does the test suite that already exists actually run, everywhere), not a component of
the product architecture `SPEC-000` describes. `ROADMAP.md` §3.5 groups it with `SPEC-901`/`SPEC-902`
under "the framework itself" for the same reason.

*   [ROADMAP.md](../ROADMAP.md) §1.1, §1.3, §3.5 — where this spec's motivation and scope come from.
*   [CTX-101.1](../apps/tauri-ui/context/CTX-101.1-ui-ipc-bridge.md) — the precedent this spec
    extends: `rust-core-ci.yml`'s Deviation 4 is the concrete evidence that cross-platform CI catches
    real bugs in this repo, not a hypothetical benefit.
*   `SPEC-902` *(not yet written — no file to link to)* — a sibling `9xx` spec; not a dependency in
    either direction, but grouped together in `ROADMAP.md`.

```text
[SPEC-903] (root of its own framework-quality concern — no parent)
   └── [Context 903.1] (not yet written) — python-ci.yml + frontend-ci.yml
```
