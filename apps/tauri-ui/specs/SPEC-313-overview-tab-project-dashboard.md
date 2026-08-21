---
id: SPEC-313
title: "Overview Tab: Per-Project Dashboard"
status: Completed
type: Feature
created: 2026-08-19
last_updated: 2026-08-19
target_version: v0.2.0
location: "apps/tauri-ui/specs/SPEC-313-overview-tab-project-dashboard.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-313: Overview Tab: Per-Project Dashboard

## 1. Executive Summary & Goals
*   **High-Level Goal:** Resolve `SPEC-312`'s own deferred item 4, undecided since `CTX-305.1` first
    re-housed chat there: the Overview tab becomes a real per-project dashboard, not just a bare
    chat surface with a name implying more. Three real pieces: the existing chat (unchanged), a
    real status summary across the project's other area tabs (PCB/Schematic/Enclosure/Components),
    and a real activity history for the project.
*   **Business / Technical Value:** Today, opening a project and landing on Overview shows only
    chat — indistinguishable from any other tab that happens to have a text box. A user has no way
    to tell, without clicking into every area tab, whether their board has any outstanding
    Schematic/PCB advisor issues, whether an enclosure has ever been generated for it, or what they
    last did on this project. A real dashboard makes Overview worth landing on first, matching what
    its name already implies.
*   **Non-Goals:**
    *   A cross-project landing page (recent projects, app updates, roadmap news) — explicitly
        decided against for this spec; the Projects rail (`SPEC-305`) already owns cross-project
        navigation, and duplicating that inside a per-project tab would fight the existing IA rather
        than complete it.
    *   Component library discovery/search against an external service (`ROADMAP.md` §3.3 item 5,
        `SPEC-312`'s other deferred item) — a separate, still-unscoped decision, untouched here.
    *   Making every area tab persist a result it doesn't already persist. This spec defines what
        Overview *shows*; whether `BoardAdvisor`/`SchematicAdvisor` start writing their own results
        into `Project.last_results` (today only `Enclosure` does, per `CTX-312.1`) is real,
        necessary follow-on work this spec names but does not implement.
    *   A generalized, unified activity-log data model spanning every area tab's own actions
        (generate, inject, export, save). What "activity" means for this first version is scoped in
        §2 to the two real data sources that already exist today.

## 2. System Architecture & Design Choices
*   **Design Rationale:**
    *   **Status summary is honest about what's real today, not aspirational.** `CTX-312.1` gave
        `Project` a generic `last_results: Record<string, unknown>` keyed by area tab, but only the
        Enclosure area currently writes into it (on "Save Project"). A per-area status card for
        Schematic/PCB/Components would have nothing real to show yet — this spec's dashboard must
        render an honest "not yet checked this session" (or equivalent) for areas with no persisted
        result, rather than silently omitting them or inventing a fake "OK" state. Enclosure's own
        card is the one that can show something concrete on day one: last-generated dimensions,
        whether a lid exists, and the most recent `export_history` entry's destination path.
    *   **Activity history is the union of two things that already exist, not a new log.** The
        project's own `conversation.jsonl` (chat, real today) and `Project.export_history`
        (`CTX-311.13`/`CTX-312.1`, real today) are the two genuine, persisted timelines available
        right now. This spec's activity feed merges and time-orders those two — it does not invent
        a new persisted event stream. A future spec can widen "activity" once more area tabs persist
        their own events (see Non-Goals).
    *   **Chat stays exactly where it is, visually subordinate to the new dashboard content, not
        replaced.** `CTX-305.1`/`SPEC-302` already made chat real and per-project; this spec adds
        dashboard content around it, decided in a future context, not a redesign of chat itself.
*   **Data Flow / Interactions:** A future `CTX-313.x` phase plan defines the exact dashboard
    layout (status cards above/beside/below chat), which daemon route(s) assemble the merged
    activity feed (a new `project.get_overview`-style route vs. the frontend composing
    `project.load_conversation` + the already-loaded `Project.export_history` itself), and how a
    "not yet checked" status renders distinctly from a real pass/fail result.
*   **Cross-Module Impacts:**
    *   `apps/tauri-ui` — Overview tab layout changes (status cards, activity feed, existing chat);
        no other area tab's own UI changes.
    *   `services/python-daemon` — likely a new read-oriented route assembling the dashboard's data
        from existing `library_store.py` state (`Project.last_results`, `Project.export_history`,
        `conversation.jsonl`); no new persisted schema unless a future context finds one genuinely
        necessary.
    *   `core/tauri-rust` — none expected; this is a data-shape and layout change, not a new native
        capability.

## 3. Known Constraints & Risks
*   **Known Issues / Technical Debt:** Schematic/PCB/Components status cards will show "not yet
    checked" for every existing project on this spec's own ship date, since nothing currently
    persists a result for those areas — this is an honest, not a broken, initial state, but worth
    naming so it isn't mistaken for a bug during review.
*   **Gotchas & Hazards:** `Project.last_results`'s value type is `Record<string, unknown>`
    (`CTX-312.1`) — deliberately loose since only Enclosure has ever written to it. A dashboard that
    renders per-area cards needs to handle an area key that's absent entirely (never checked) as a
    genuinely different state from one present but empty/malformed (checked, nothing to report),
    without assuming every future area's result shape in advance.

## 4. Module Map & Reference Links
```text
[Root Spec](../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-313-overview-tab-project-dashboard.md)
                 └── [Context 313.1](../context/CTX-313.1-subfeature.md)
```

## 5. User & Interaction
*   **Product Stage:** Per-project, first landing tab — the very first thing a user sees after
    opening or creating a project, before choosing a specific area to work in.
*   **What the user is trying to accomplish:** Get oriented on one project without clicking through
    every area tab first — is there anything outstanding on the board, has an enclosure ever been
    generated for it, what did I last do here — while still being able to jump straight into chat
    the way Overview already supports today.
*   **What the user sees and does:** A per-project dashboard: status cards summarizing
    Schematic/PCB/Enclosure/Components (real data where it exists, an honest "not yet checked"
    where it doesn't), a merged activity feed (chat history + export history, time-ordered), and
    the existing chat surface, still fully functional. No new area tab, no new project-level action
    — Overview becomes worth landing on, not a new capability surface.
