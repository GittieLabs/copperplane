---
id: SPEC-319
title: "AI Review"
status: Draft
type: Feature
created: 2026-08-24
last_updated: 2026-08-24
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-319-ai-review.md"
parent_spec: "SPEC-318-in-context-agent-chat-and-review.md"
child_specs: []
user_facing: true
---

# SPEC-319: AI Review

## 1. Executive Summary & Goals

*   **High-Level Goal:** Build the seam `SPEC-318` §2.5 deliberately defined but did not build: a
    **Run Review** action in each area that invokes that area's own chat agent — same tools, same
    retrieval scope, same source contract — with a fixed internal prompt instead of a user question,
    and renders a typed `ReviewFinding[]` instead of a conversational answer. A review reads; it
    never writes, exactly like `SPEC-309`'s ERC/DRC advisor it sits alongside.
*   **Business / Technical Value:** Every area already has a real, sourced agent (`SPEC-318`) that
    can answer a question about that area's own state. The only thing missing is asking it a
    *standing* question — "what's worth flagging here" — proactively, instead of waiting for the
    user to think to ask. This is the cheapest possible next capability given what already exists:
    no new agent, no new tool, no new retrieval scope. It is also the reason `SPEC-318` §2.5 was
    written at all — building the seam without ever using it would have been wasted design.
*   **Non-Goals:**
    *   **A review never mutates anything.** No tool with a write effect may be called from a
        review invocation, full stop — not gated, not confirmed, **excluded**. `SPEC-309`'s advisor
        already established the pattern (read a board, explain it, never touch it); this spec
        inherits it for every area, including Schematic, whose chat agent's own tool allow-list
        (`SPEC-318` §2.3) includes the gated `library.save_confirmed_part`. §2.2 below states
        exactly how that tool is excluded from a review's own dispatch.
    *   **Scheduled or automatic review.** Every review is a single, explicit user click. No
        background polling, no "review on save," no notification badge.
    *   **Cross-area review.** One review call is scoped to exactly one area, same as chat. A
        project-wide "review everything" digest is a real, plausible future feature and explicitly
        not this spec's job — `SPEC-318` §1's own Non-Goals list already ruled out a
        cross-project or router-style surface; a cross-*area* digest is the analogous mistake at a
        smaller scope and gets the same answer here.
    *   **Persisting findings as their own record type.** A finding is ephemeral — recomputed on
        every click, never diffed against a prior run, never itself promotable to a note. Promotion
        exists on chat answers (`SPEC-318` §5's own "Save as note") and is not duplicated here in
        this first version; a finding worth keeping is worth asking the chat about, which already
        has that path. Revisit if real use shows this is the wrong call.
    *   **A finding count or severity badge on the tab itself.** The button says what it does; it
        does not turn into a persistent notification surface. Consistent with `SPEC-318` §2.2's own
        "chat is collapsible, not a nag."

## 2. System Architecture & Design Choices

### 2.1 Reusing chat's own dispatch, not a parallel pipeline

`services/python-daemon/chat_agents.py`'s `_dispatch(area, scope, scope_id, project_name, message,
history, secrets, provider, model)` already does everything a review needs before the LLM call:
router-based agent selection with no LLM on the routing path, the per-area `AgentConfig`/tool
registry/context assembly `SPEC-318` §2.3 declares, and after the call, mechanical + self-reported
source validation. A new `review(area, scope, scope_id, project_name, secrets, provider, model)`
function in the same module calls the same `_dispatch()` with two real differences from `send()`:

*   **`message` is a fixed, per-area internal prompt** ("Review this area for anything worth
    flagging — a real risk, a gap, or a suggestion — and return your findings in the format
    below."), not free user text, and **`history` is always `[]`** — a review has no turn of its
    own to remember and must not see the area's chat transcript, which could otherwise leak an
    unrelated user question's framing into an unrelated review.
*   **The agent is asked to return a structured findings block, not prose.** `chat_agents.py`'s
    existing `_extract_self_reported`/`<<<CITATIONS>>>...<<<END_CITATIONS>>>` contract already
    proves the pattern (a model reliably emits a trailing structured block after its visible
    prose); review reuses the identical mechanism with a second trailing block,
    `<<<FINDINGS>>>[...]<<<END_FINDINGS>>>`, a JSON array matching §2.2's `ReviewFinding` shape
    minus `sources`/`area` (both filled in server-side, exactly as `general_practice`/`sources` are
    today for chat). No visible prose is expected or rendered for a review call — the "answer" *is*
    the findings list. Every one of the five `chat_*.prompt.md` files gets a short **Review format**
    section alongside its existing **Citation format** section, matching that section's own
    per-agent-appropriate-subset convention.

This is a deliberate, load-bearing choice: reusing `_dispatch()` means a review can never drift out
of sync with what that area's chat is actually grounded in and allowed to call — the two share one
implementation, not two hand-maintained ones.

### 2.2 Excluding writes from a review's own tool registry

`_dispatch()` calls `tool_registry.build_tool_registry()` unconditionally today — the same registry
`send()` uses, which includes gated write tools like `library.save_confirmed_part`
(`CONFIRMATION_REQUIRED_TOOLS`, `SPEC-204`). A review must never be able to reach a write tool even
through the confirmation gate, since nothing in a review's own flow can ever answer a confirmation
prompt. `_dispatch()` gains an optional `tools` parameter (defaulting to the full registry, so
`send()`'s own call site is unchanged); `review()` passes a **read-only-filtered** registry —
`tool_registry.build_tool_registry(exclude=CONFIRMATION_REQUIRED_TOOLS)` or equivalent — so the
agent physically cannot call a gated tool during a review, not merely instructed not to. Named here
because retrofitting this after review ships would mean re-auditing every area's own tool list for
new gated tools added later; excluding by the registry's own existing gate list keeps this correct
by construction as `CONFIRMATION_REQUIRED_TOOLS` grows.

### 2.3 The real finding shape

```ts
interface ReviewFinding {
  severity: 'info' | 'suggestion' | 'warning'
  title: string
  detail: string
  sources: SourceRef[]        // same union as chat -- SPEC-206 §2.3
  area: Area
}
```

Exactly `SPEC-318` §2.5's own already-designed shape, unchanged. `sources`/`area` are filled in
server-side (`area` from the route's own parameter, `sources` validated through the identical
`validate_source_refs`/`_enrich_source_ref` path chat answers already go through) — the model never
supplies either directly, matching `content_hash` in `_enrich_source_ref` today. A finding with no
real sources must self-report `general_practice: true` at the finding level (not a single
thread-wide flag as chat has today) — a review naming five things can have some cited and some not
in the same call, and the UI must be able to tell them apart per-finding, not just for the whole
response.

### 2.4 Where the button lives

*   **In-area:** a **Run Review** action in each area's existing action row (`SPEC-318` §2.7 names
    "the collapsible chat panel"; review sits beside it as a sibling action, not inside it — a
    review is a flow step with a typed result, per `PRODUCT-PLAN.md` §3.3's rule, not a
    conversational turn, so it does not live inside `AgentChat`'s own message list). Findings render
    in a dismissible panel above or beside the chat panel, each with its severity, title, detail,
    and the same clickable `SourceRef` chips chat answers already use — reusing `AgentChat`'s own
    source-chip rendering rather than a second implementation.
*   **Native `Design` menu, per `SPEC-316`, but only for the three areas that actually have a Design
    submenu.** Checked directly against `core/tauri-rust/src/menu.rs`: the `Design` menu holds
    exactly `Schematic`, `PCB`, and `Enclosure` submenus — **Components and Overview have no Design
    submenu at all today**, and this spec does not add one. Overclaiming "the Design submenu" for
    all five areas the way `SPEC-318` §2.5's own text loosely did would be the exact kind of
    unverified claim this repo's whole framework exists to catch. A **Run Review** item is added to
    each of the three existing submenus (`design_schematic_run_review`, `design_pcb_run_review`,
    `design_enclosure_run_review`, matching the existing `snake_case` id / `MENU_DESIGN_*_EVENT`
    convention `CTX-316.1`/`CTX-316.2` already established); Components and Overview only get the
    in-area button.

### 2.5 Cross-Module Impacts

*   `services/python-daemon/chat_agents.py` — `_dispatch()` gains an optional `tools` parameter;
    new `review()` function; new `_extract_findings`/`_FINDINGS_PATTERN` alongside the existing
    citation-extraction functions.
*   `services/python-daemon/daemon.py` — new `chat_review` async route (an LLM call, so
    `submitJob`-shaped like `chat_send`, not `dispatch`-shaped).
*   `services/python-daemon/agentflow/agents/chat_{overview,components,schematic,pcb,enclosure}.prompt.md`
    — each gains a **Review format** section.
*   `apps/tauri-ui/src/lib/chat.ts` — `ReviewFinding` type, `runReview(area, scope, scopeId,
    projectName)` client function (`submitJob`-shaped, matching `sendChatMessage`).
*   `apps/tauri-ui/src/components/` — a new shared `ReviewPanel` component (mirrors `AgentChat`'s own
    `PromotionTarget`-less, simpler shape: severity-grouped findings, source chips via the same
    `isOpenableSource`/`handleOpenSource` logic `AgentChat.tsx` already has, generalized rather than
    copied), mounted by `Overview`, `PartDetail`, `SchematicAdvisor`, `BoardAdvisor`, `EnclosurePanel`
    — the same five mount points `AgentChat` already has, per §2.4.
*   `core/tauri-rust/src/menu.rs` — three new `Run Review` items under the existing `Schematic`/
    `PCB`/`Enclosure` submenus, three new `MENU_DESIGN_*_RUN_REVIEW_EVENT` constants.

## 3. Known Constraints & Risks

*   **No streaming, same as chat.** A review can take as long as a chat answer that calls the same
    tools (`kicad.check_schematic`, `datasheet.read_pages`, etc.) — `SPEC-318` §3's own "reading the
    ATtiny85 datasheet" progress-state precedent applies unchanged; a review's own in-flight state
    should say what it's doing, not imply a token stream.
*   **A model asked for structured findings can still return zero, one, or many — including zero
    when there is genuinely nothing to flag.** An empty findings list is a normal, honest result
    ("nothing stood out"), not an error state, mirroring `SPEC-205`'s "empty concerns are normal"
    precedent for design guidance.
*   **The Components area's chat is Part-scoped, not project-scoped** (`SPEC-318` §2.2) — a review
    on Components reviews the currently-open Part, not the whole project, and its own button must
    be gated the same way `AgentChat` already is there (`savedPart` must exist).
*   **Excluding gated tools from review changes what a review *can* find, not just what it can do.**
    A review of the Schematic area, for instance, cannot propose "save this part to the library" as
    a finding action the way a chat conversation theoretically could walk toward — it can only
    *describe* that a part is unsaved, never act on it. This is intentional (§2.2) but worth stating
    plainly: a review is strictly read-only in what it can attempt, not just in what ships without
    confirmation.
*   **Reusing `_dispatch()`'s tool registry parameter is new, not yet exercised.** `send()`'s own
    call site passes no `tools` argument today and must be verified to still receive the full,
    unfiltered registry once the parameter is added — a regression here would silently narrow every
    existing chat conversation's own tool access, not just review's.

## 4. Module Map & Reference Links

```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [SPEC-318](SPEC-318-in-context-agent-chat-and-review.md)
                 └── [This Spec](SPEC-319-ai-review.md)
                        ├── depends on [SPEC-206](../../../services/python-daemon/specs/SPEC-206-agent-context-store.md) (SourceRef union, agent dispatch)
                        ├── depends on [SPEC-204](../../../services/python-daemon/specs/SPEC-204-agent-tool-registry.md) (CONFIRMATION_REQUIRED_TOOLS, the gate this spec excludes rather than relies on)
                        └── depends on [SPEC-316](SPEC-316-native-menu-command-surface.md) (the three real Design submenus this spec's menu items join)
```

## 5. User & Interaction

*   **Product Stage:** Cross-cutting, same five surfaces as `SPEC-318`'s chat — Components,
    Schematic, PCB, Enclosure, plus the project-level Overview.
*   **What the user is trying to accomplish:** Catch something worth knowing about an area without
    having to think of the right question to ask. They have just finished a datasheet review, an
    ERC pass, or an enclosure generation, and want a second, standing pass over the same state before
    moving on — the same instinct `SPEC-309`'s advisor already serves for ERC/DRC specifically, now
    available for every area's own grounded knowledge.
*   **What the user sees and does:** A **Run Review** button beside each area's existing actions.
    Clicking it shows a real in-progress state, then a list of findings — each with a severity, a
    plain-language title and detail, and source chips identical to chat's own, one click from the
    real page or record it came from. A finding offered as general engineering practice rather than
    something the area's own state supports is visibly marked as such, per-finding. An empty result
    is shown as an honest "nothing stood out," not silence or an error.
