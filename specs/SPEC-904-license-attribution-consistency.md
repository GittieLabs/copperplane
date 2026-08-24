---
id: SPEC-904
title: "Repository License & Attribution Consistency"
status: Completed
type: System
created: 2026-08-14
last_updated: 2026-08-24
target_version: v0.1.0
location: "specs/SPEC-904-license-attribution-consistency.md"
parent_spec: null
child_specs: []
user_facing: false
---

# SPEC-904: Repository License & Attribution Consistency

## 1. Executive Summary & Goals

*   **High-Level Goal:** Make every machine-readable license declaration in this repo agree with
    the actual grant: the root `LICENSE` file (Apache-2.0). Fill in the `LICENSE` appendix's own
    placeholder copyright line, add a `NOTICE` file, and correct the two package-manifest fields
    that currently contradict or omit the real license.
*   **Business / Technical Value:** `core/tauri-rust/Cargo.toml` declared `license = "MIT"` — a
    leftover from the Tauri scaffold — while the repo's actual `LICENSE` is Apache-2.0. That field
    is exactly what crates.io and automated dependency/license scanners read; it is the version of
    the truth a machine is most likely to believe, and it was wrong. `apps/tauri-ui/package.json`
    had no `license` field at all, which npm's own tooling and license scanners read as "no license
    asserted" rather than inheriting the repo's real one. Separately, `LICENSE` line ~189 still read
    the unfilled Apache-2.0 appendix boilerplate (`Copyright [yyyy] [name of copyright owner]`) —
    the license text itself never actually named a copyright holder anywhere in the repo.
*   **Non-Goals:** Not a relicense — this repo was already Apache-2.0 (root `LICENSE`, stated in
    `README.md`). This spec only makes the metadata match what was already true. Not a change to
    `services/python-daemon`'s `pyproject.toml`, which was already correct.

## 2. System Architecture & Design Choices

*   **Design Rationale:** Fix the declarations in place rather than generating them from a single
    source of truth (e.g. a repo-wide license-sync script) — three fields in two ecosystems is not
    enough duplication to justify that machinery, and it would be new, untested infrastructure for
    a one-time correction.
*   **Data Flow / Interactions:** None — static metadata only, no runtime behavior changes.
*   **Cross-Module Impacts:**
    *   `core/tauri-rust` — `Cargo.toml` `license` field.
    *   `apps/tauri-ui` — `package.json` `license` field.
    *   Root — `LICENSE` appendix copyright line, new `NOTICE` file.
    *   `services/python-daemon/requirements.txt` — separately, the `gittielabs-agentflow` pin
        bumps from `==0.8.2` to `==0.9.0` now that AgentFlow's own relicense to Apache-2.0 has
        shipped to PyPI; bundled into this same CTX since both are small, unrelated-in-code-content
        but same-shape "metadata/pin correction" changes touching files the gatekeeper already
        requires a CTX for.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:** None introduced. `NOTICE`'s attribution text
    (`Copyright 2026 GittieLabs`) is written to match `~/repos/agentflow`'s `NOTICE` verbatim in
    structure, so the two projects attribute identically — if that wording ever changes for one, it
    should change for both.
*   **Gotchas & Hazards:** `scripts/validate_spec_context.py`'s `CODE_EXTENSIONS` includes `.toml`
    and `.json` (ROADMAP.md §1.3), so touching `Cargo.toml` and `package.json` requires a CTX file
    in the same PR even though the change is pure metadata, not application logic — this spec and
    its context exist specifically to satisfy that honestly rather than routing the fix through an
    unrelated spec's context.

## 4. Module Map & Reference Links

```text
[SPEC-904](SPEC-904-license-attribution-consistency.md)
   └── [CTX-904.1](../context/CTX-904.1-license-attribution-consistency.md)
```
