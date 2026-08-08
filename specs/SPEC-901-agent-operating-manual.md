---
id: SPEC-901
title: "Agent Operating Manual & Context Generation Protocol"
status: Draft
type: System
created: 2026-08-08
last_updated: 2026-08-08
target_version: v0.1.0
location: "specs/SPEC-901-agent-operating-manual.md"
parent_spec: null
child_specs: []
---

# SPEC-901: Agent Operating Manual & Context Generation Protocol

## 1. Executive Summary & Goals

*   **High-Level Goal:** Turn the spec → context → execute loop that has so far been followed by
    hand-prompting one agent session into something any Claude Code session in this repo follows
    the same way: a root `CLAUDE.md` encoding the repo's engineering norms, and four slash commands
    (`/spec-status`, `/new-spec`, `/new-context`, `/close-context`) that generate and close out
    `SPEC-*.md`/`CTX-*.md` files correctly by construction rather than by careful prompting.
*   **Business / Technical Value:** CTX-101.1, CTX-103.1, and CTX-104.1 each independently
    discovered the same handful of norms — verify against the real thing when it's available, record
    Plan Drift honestly including wrong predictions, wire `parent_spec`/`child_specs` in both
    directions, never write a test path into the matrix that doesn't exist on disk — because one
    agent session happened to carry that judgment forward. None of it is written down anywhere an
    agent is guaranteed to read. `ROADMAP.md` §1.3 records two bidirectional-linking misses
    (SPEC-102, SPEC-103/104) that this exact class of tooling would have caught mechanically. The
    16-spec backlog in `ROADMAP.md` is only cheap to execute if the next agent doesn't have to
    rediscover all of this from scratch.
*   **Non-Goals:**
    *   Not a general-purpose agent framework — this is specific to this repo's Spec & Context
        model.
    *   Not a replacement for `CONTRIBUTING.md`. `CONTRIBUTING.md` remains the human-facing contract
        that CI enforces; `CLAUDE.md` is the agent-facing operating manual and defers to
        `CONTRIBUTING.md` for anything already written there, rather than duplicating it (the same
        single-source-of-truth call made when the spec numbering scheme moved out of `ROADMAP.md`
        and into `CONTRIBUTING.md`).
    *   Not mechanical graph validation. `/spec-status` reports on the graph by reading it, and the
        other three commands must not hand-author a link the way a human easily gets wrong — but
        building a validator that parses `SPEC-*.md` frontmatter and catches this in CI is
        `SPEC-902`'s job, not this one's. Where useful, these commands should shell out to the
        *existing* `scripts/validate_spec_context.py` rather than reimplement its checks.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   `CLAUDE.md` lives at the repo root because Claude Code loads it automatically for every
        session in this repo — it is the one artifact guaranteed to be read without the agent
        choosing to read it, which `CONTRIBUTING.md` is not.
    *   The four commands are deliberately scoped to the four transitions in the loop (§2, Data
        Flow below), not to the work done *inside* a phase. They scaffold and close out
        `SPEC-*.md`/`CTX-*.md` files correctly; they do not write application code, decide
        architecture, or replace the judgment calls an agent makes mid-implementation (e.g.
        CTX-104.1's STL→GLB pivot). Over-scoping these into "the agent does the whole feature"
        commands would make them unreviewable black boxes and re-introduce the exact
        prompting-dependent inconsistency this spec exists to remove.
    *   `/new-context` is the highest-leverage command of the four: it is where a hallucinated test
        path or a missing `parent_spec` link has actually happened in this repo. `/spec-status` and
        `/close-context` are comparatively low-risk (read-only, or a thin wrapper around commands an
        agent already runs by hand).

*   **Data Flow / Interactions** (formalizes `ROADMAP.md` §5.1):

    ```text
    ROADMAP.md entry
          │  human picks the next item and approves scope
          ▼
      /new-spec <id> <title>   → scaffolds SPEC-xxx.md from SPEC-TEMPLATE.md,
          │                        pre-filled frontmatter, ID chosen per
          │                        CONTRIBUTING.md §2, parent_spec/child_specs
          │                        wired in BOTH directions on save
          ▼
      SPEC-xxx.md               ← the What and Why. Stable. Rarely edited after approval.
          │  agent derives an execution plan
          ▼
      /new-context SPEC-xxx     → reads the spec, decomposes it into phases,
          │                        drafts the Testing Requirements Matrix with
          │                        paths that will actually exist, sets the
          │                        branch name to feat/CTX-xxx.n-<slug>, creates
          │                        the branch
          ▼
      CTX-xxx.n.md               ← the How and When. Phases, testing matrix, branch name.
          │  agent implements phase by phase, committing as it goes
          ▼
       code + tests               ← test paths must match the matrix exactly; CI enforces it
          │  agent runs /close-context
          ▼
      /close-context             → collects commit hashes from the branch into
          │                        frontmatter, flips status, prompts for Plan
          │                        Drift entries, runs the validator locally,
          │                        opens the PR
          ▼
      CTX closed → PR → develop
          │
          └─> anything learned that contradicts the spec is written back into the SPEC

      /spec-status                → callable at any point: walks the graph from
                                     SPEC-000, reports specs with no context, open
                                     contexts, and unspecced ROADMAP.md items
    ```

*   **Cross-Module Impacts:**
    *   Adds `CLAUDE.md` (repo root) and `.claude/commands/` (or wherever this Claude Code
        installation resolves project-level slash commands from — confirm the exact mechanism
        during `CTX-901.1` rather than assuming; do not guess a path and ship it unverified).
    *   Reads, but does not modify, `CONTRIBUTING.md`, `SPEC-TEMPLATE.md`, `CONTEXT-TEMPLATE.md`,
        and `scripts/validate_spec_context.py`.
    *   No impact on `apps/tauri-ui`, `core/tauri-rust`, or `services/python-daemon` runtime code —
        this spec is tooling, not product.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   `scripts/validate_spec_context.py` only validates `CTX-*.md` frontmatter and test paths — it
        never opens a `SPEC-*.md` (`ROADMAP.md` §1.3). `/new-spec` and `/new-context` are the two
        places a bad `SPEC-*.md` link gets created, so until `SPEC-902` lands, correctness there
        depends on these commands' own logic, not CI.
    *   `CODE_EXTENSIONS`/`EXCLUDE_PATHS` in the same script have known gaps (`.json` too broad,
        `EXCLUDE_PATHS` only exempts the root `README.md`). Slash commands that touch `.json`/`.md`
        files near those edges may trip the gatekeeper's Rule 1 in ways that look like a false
        positive but aren't fixable here — that's `SPEC-902` territory too.
*   **Gotchas & Hazards:**
    *   **Bidirectional linking is the norm most likely to be dropped again.** It was missed twice
        already (SPEC-102's parent pointing at SPEC-000 before SPEC-102 existed; SPEC-000's
        `child_specs` omitting SPEC-103/104) by a careful human-prompted agent. `/new-spec` must
        write both ends of the link in the same operation, not rely on a second pass.
    *   **Command output must not silently overwrite an existing file.** `/new-spec` and
        `/new-context` scaffold new files; if the target ID already exists (e.g. a typo'd re-run),
        the command must fail loudly rather than clobber an in-progress spec or context.
    *   **`/close-context` runs the validator locally before opening a PR** — but the validator
        needs a `--base` ref, and this repo's actual base has drifted mid-session before (this
        session's `docs/roadmap-and-spec-graph` branch needed `origin/develop`, not the stale local
        `develop`, after two PRs merged underneath it). The command must resolve the base branch the
        same way a careful human would (fetch first), not assume local refs are current.
    *   **Do not encode the seven norms from `ROADMAP.md` §5.3 by copying its prose verbatim into
        `CLAUDE.md`.** Restate them for an agent that has not read `ROADMAP.md` — `ROADMAP.md` is
        allowed to be revised or archived once its backlog entries become real specs; `CLAUDE.md`
        should not become stale by inheriting phrasing tied to a specific point-in-time plan.

## 4. Module Map & Reference Links

This spec is deliberately **not** a child of `SPEC-000`: `SPEC-000` describes the product's runtime
architecture (the three-tier CAD orchestrator), and this spec describes the development process
used to build it — a different, parallel concern, not a component of the system SPEC-000 depicts.
It sits at the root of its own `9xx` branch of the graph, same as `SPEC-000` sits at the root of the
`000`/`1xx`-`4xx` branch.

*   [ROADMAP.md](../ROADMAP.md) §3.5, §5 — the backlog entry and workflow this spec formalizes.
*   [CONTRIBUTING.md](../CONTRIBUTING.md) — the human-facing framework this spec's tooling
    generates artifacts for; `CLAUDE.md` defers to it rather than duplicating it.
*   `SPEC-902` *(not yet written — no file to link to)* — depends on this spec per `ROADMAP.md`
    §3.5; mechanizes the graph checks this spec's commands perform by hand.

```text
[SPEC-901] (root of the 9xx / framework branch — no parent)
   └── [Context 901.1] (not yet written) — CLAUDE.md + four slash commands
```
