---
id: SPEC-902
title: "Spec Graph Validator v2"
status: Draft
type: System
created: 2026-08-08
last_updated: 2026-08-08
target_version: v0.1.0
location: "specs/SPEC-902-spec-graph-validator-v2.md"
parent_spec: null
child_specs: []
---

# SPEC-902: Spec Graph Validator v2

## 1. Executive Summary & Goals

*   **High-Level Goal:** Upgrade `scripts/validate_spec_context.py` from a `CTX-*.md`-only context
    linter into a real graph validator: parse `SPEC-*.md` frontmatter too, verify every
    `parent_spec`/`child_specs`/`spec_ref` path actually resolves on disk, check `id` uniqueness and
    that each file's `id` matches its own filename, and check that `location:` matches the file's
    real path.
*   **Business / Technical Value:** Every framework-graph breakage recorded in `ROADMAP.md` §1.3 —
    a misspelled filename with every `parent_spec` pointing at the correct spelling, a spec
    referenced by two others but never written, a root spec's `child_specs` silently missing two
    real children — sailed through this repo's own CI, because the validator that runs on every PR
    never opens a `SPEC-*.md` file at all. Each of those was mechanically detectable. A human reading
    carefully caught them this time; the framework should catch them every time, on the PR where
    they're introduced, not on a later read-through.
*   **Non-Goals:**
    *   Not a rewrite from scratch. The existing `CTX-*.md` checks (required frontmatter fields,
        non-empty `commit_hashes`, Testing Requirements Matrix path validation) already work and
        already gate every PR in this repo — this spec extends the same script and CLI contract
        (`python scripts/validate_spec_context.py --base <ref>`), it doesn't replace it. Breaking
        that contract breaks `.github/workflows/spec-container-gatekeeper.yml` for every future PR,
        including this one's own.
    *   Not `/spec-status`. `/spec-status` (from `CTX-901.1`) already reports specs with no context
        and unspecced roadmap items conversationally, on demand, for a human or agent to read. This
        spec's validator runs in CI and must produce a small number of unambiguous pass/fail
        signals — "orphan spec" and "no context yet" are informational in `/spec-status`'s report
        and must **not** become hard CI failures here (a freshly-written `Draft` spec with no
        context yet, e.g. `SPEC-105` today, is normal, not a bug).
    *   Not a fix for every `CODE_EXTENSIONS`/`EXCLUDE_PATHS` edge case that could theoretically
        exist — see §3 for what's actually verified to matter today versus what's currently dormant.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   Extend `scripts/validate_spec_context.py` in place. Same file, same `--base` CLI contract,
        same exit-code convention (0 = pass, 1 = fail with a printed report). New checks are
        additive; no existing passing check may start failing for a case it previously accepted,
        and no existing failing case may start silently passing.
    *   **Severity split, explicit:** *hard failures* (block the PR, matching the existing
        `CTX-*.md` checks' behavior) are dangling links, id collisions, id/filename mismatches, and
        `location:` mismatches — these are unambiguously bugs, never a legitimate in-progress state.
        *Informational findings* (printed, never block) are orphan specs and specs with no context —
        both are normal for a spec that's `Draft` and not yet picked up.
    *   **Correctness over the specific symptom.** `ROADMAP.md` §1.3 names "module READMEs aren't
        exempt" as the `EXCLUDE_PATHS` bug — verified directly (see §3) that this specific claim
        doesn't currently trigger anything, because `.md` was never in `CODE_EXTENSIONS` to begin
        with. The actual fix here is making the path-exclusion matching correct in general (real
        path-prefix/basename matching, not bare `str.startswith`), not special-casing the one
        symptom that happens to be inert today.
*   **Data Flow / Interactions:**

    ```text
    PR opened/updated against develop or main
          │
          ▼
    spec-container-gatekeeper.yml
          │  python scripts/validate_spec_context.py --base origin/<target>
          ▼
    git diff --name-only <base>...HEAD
          │
          ├─> CTX-*.md changed?  ──> existing checks (frontmatter, hashes, testing matrix)
          │
          └─> SPEC-*.md changed? ──> NEW: parse frontmatter, then for every SPEC-*.md
                                       in the repo (not just the changed ones -- a change to
                                       SPEC-A can break a link FROM SPEC-B that already existed):
                                         - parent_spec / child_specs / spec_ref resolve on disk?
                                         - id unique across the whole repo?
                                         - id matches this file's own name?
                                         - location: matches this file's own real path?
          │
          ▼
    hard failures -> exit 1, PR blocked
    informational findings -> printed, exit 0 if nothing else failed
    ```

*   **Cross-Module Impacts:**
    *   Modifies `scripts/validate_spec_context.py` only.
    *   Read by `.github/workflows/spec-container-gatekeeper.yml` — no change needed there; the CLI
        contract (`--base` argument, exit code) is unchanged.
    *   No impact on `apps/tauri-ui`, `core/tauri-rust`, or `services/python-daemon` runtime code.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **Real and currently triggering:** `CODE_EXTENSIONS` includes `.json`. Every
        `package-lock.json` change (e.g. an incidental transitive-dependency bump from `npm install`,
        not a deliberate feature) currently demands a `CTX-*.md` update in the same PR. Verified
        directly against the real matcher logic with `apps/tauri-ui/package-lock.json` as input:
        it does count as "code changed" today. Whether the fix is excluding lockfiles specifically
        or removing `.json` from `CODE_EXTENSIONS` entirely is this context's call to make, not
        pre-decided here.
    *   **Claimed but currently dormant, verified directly rather than assumed:** `ROADMAP.md` §1.3
        says `EXCLUDE_PATHS`'s `str.startswith(...)` matching means only the *root* `README.md` is
        exempt, not module READMEs. Tested this directly: `services/python-daemon/README.md` and
        the root `README.md` both currently produce `counts_as_code=False`, identically — because
        `.md` was never in `CODE_EXTENSIONS`, the `EXCLUDE_PATHS` check is never even reached for
        either. The claim as stated doesn't reflect a live bug today. The underlying matching
        mechanism (bare-prefix `startswith`, which also silently fails to exempt module-level
        `specs/`/`context/` directories, e.g. `services/python-daemon/specs/`) is still wrong in
        principle and worth fixing correctly — just not because of the specific symptom named in
        the roadmap. Fix the mechanism; don't just patch around one currently-harmless case.
*   **Gotchas & Hazards:**
    *   **This script gates every PR in the repo, including its own.** A false-positive hard failure
        blocks all future work; a false-negative silently defeats the point of this spec. Any change
        here needs real, direct test coverage — including a case that exercises the actual CLI
        against a constructed temporary git history, not only unit tests of individual helper
        functions in isolation.
    *   **Checking `parent_spec`/`child_specs` for every `SPEC-*.md` in the repo, not only the ones
        changed in the diff, is deliberate and slower than the current CTX-only check.** A change to
        `SPEC-A`'s `child_specs` can break a link *from* `SPEC-B` that already existed and wasn't
        touched in this PR. Scoping the new checks to "only files changed in this diff" would miss
        exactly the class of bug this spec exists to catch.
    *   **"Orphan spec" must not fire for every currently-unimplemented roadmap item.** `SPEC-105`
        through `SPEC-109`, `SPEC-201`-`SPEC-204`, etc. all exist only as `ROADMAP.md` prose today,
        with no `SPEC-*.md` file at all — that's not an orphan, that's simply not-yet-written, and
        is entirely out of this check's scope (it only examines files that exist on disk).

## 4. Module Map & Reference Links

Like `SPEC-901` and `SPEC-903`, this spec is not a child of `SPEC-000` — it's tooling for the
development framework itself, not a component of the product architecture `SPEC-000` describes.

*   [ROADMAP.md](../ROADMAP.md) §1.3, §3.5 — the three real breakages this spec's checks would have
    caught mechanically, and the backlog entry this spec formalizes.
*   [scripts/validate_spec_context.py](../scripts/validate_spec_context.py) — the file this spec
    extends in place.
*   [CTX-901.1](../context/CTX-901.1-agent-operating-manual.md) — `/spec-status`'s existing,
    conversational, non-blocking version of "specs with no context" reporting; this spec's
    validator must not duplicate it as a CI-blocking check.

```text
[SPEC-902] (root of its own framework-quality concern — no parent)
   └── [Context 902.1] (not yet written) — extended validate_spec_context.py
```
