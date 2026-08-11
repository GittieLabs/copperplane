---
id: SPEC-302
title: "Chat & Command Surface"
status: Draft
type: Feature
created: 2026-08-11
last_updated: 2026-08-11
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-302-chat-command-surface.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
---

# SPEC-302: Chat & Command Surface

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace `App.tsx`'s current one-input-one-button-one-`<pre>`-dump UI with a
    real conversational surface: message history, per-message loading/error states, and inline
    rendering of what each message actually produced (a schema, an "Injected into the open board"
    confirmation, a `.glb` preview) — the last unwritten node on M1's own critical path
    (`ROADMAP.md` §4).
*   **Business / Technical Value:** This is what turns two disconnected single-shot actions
    (`kicad.generate_component`, `kicad.inject_component`) into the thing the README actually
    promises: type "generate a footprint for BME280," watch it happen. Every route this spec's UI
    calls already exists and is already verified for real (`SPEC-202`, `SPEC-108`) — this spec's own
    job is the conversational shell around them, not new backend capability.
*   **Non-Goals:**
    *   **Not real token-by-token streaming.** Checked directly against the installed
        `gittielabs-agentflow==0.8.2` source before writing this: every provider's `chat()` (`AnthropicProvider`,
        `GoogleGenAIProvider`, `OpenAICompatProvider`) is a single `async def` returning one complete
        `AgentResponse` — there is no streaming variant anywhere in the library today. `ROADMAP.md`
        §3.2's own "streaming tokens" aspiration for this spec is not achievable without adding real
        streaming support to AgentFlow itself first (a separate, upstream undertaking, per this
        repo's own "fix AgentFlow bugs/gaps upstream" norm) — out of scope here. The UI shows one
        loading state per message while its request is in flight, the same pattern `App.tsx` already
        uses today, not a simulated/fake stream.
    *   **Not agentic tool-calling.** `SPEC-204` (Agent Tool Registry, explicitly out of M1 per
        `ROADMAP.md` §4) is what would let a model autonomously decide which route to call from
        open-ended natural language. This spec does not attempt that: a message either matches one
        of a small, explicit set of real commands this surface recognizes (see §2), or it's treated
        as a plain chat turn with no tool call. `CTX-108.3` already proved the manual-trigger path
        for `kicad.inject_component` works end-to-end without any agentic reasoning — this spec
        keeps that same directness, just inside a chat-shaped UI instead of two separate buttons.
    *   **Not session persistence across app restarts.** `SPEC-201`'s own resolution of this exact
        question (a single request needs no session state) was scoped to the single-shot
        `generate_component` pipeline specifically; a chat surface is different — conversation
        continuity *within one running session* is this spec's actual subject — but persisting that
        history to disk across app restarts is real, separate scope this spec doesn't take on.
    *   **Not a confirmation gate.** `SPEC-204`'s risk-register entry (`ROADMAP.md` §6) for a
        confirmation step before any board write is a separate concern from this spec's own UI
        shell. `kicad.inject_component` still mutates the board the instant it's invoked, from
        inside this chat surface exactly as it did from `CTX-108.3`'s plain button — this spec does
        not add a review/confirm step of its own.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **A small, explicit command set — not open-ended parsing.** Given no real tool-calling
        exists yet (§1), this spec needs its own, deliberately narrow rule for turning a typed
        message into an action: recognize `generate <part number>` and `inject` (acting on the most
        recently generated schema in the conversation) as real commands; anything else is sent as a
        plain chat turn to the configured LLM via `llm.chat` with no tool call. This is a real,
        concrete design decision this context needs to make, not left implicit — a future `SPEC-204`
        replacing this rule-based recognizer with real agentic tool-calling is the intended upgrade
        path, not a redesign.
    *   **Real multi-turn context, not per-message amnesia.** AgentFlow's `AgentExecutor.run()`
        already accepts a `history` parameter (verified against the installed package before writing
        this) — each chat turn's prior messages get threaded through on the next call, so a plain
        chat turn ("what does pin 3 do on that part?") can refer back to what was already generated
        in the same conversation. In-memory only for this spec (see Non-Goals) — held in React state,
        not `AgentFlow`'s own `SessionManager`/on-disk storage, which would be real but unnecessary
        scope for a single running session.
    *   **Each message renders what it actually did, not just text.** A `generate` command's message
        renders the returned schema (structured, not a raw `<pre>` dump — this spec's own
        presentational improvement over today's `App.tsx`); an `inject` command's message renders
        success/failure exactly as `CTX-108.3`'s button did; a plain chat turn renders the model's
        text response. `freecad.generate_enclosure` keeps its own existing panel
        (`CTX-105.2`/`CTX-301.1`/`CTX-301.2`) rather than folding into the message list — enclosure
        generation isn't part of the README's "type to generate a footprint" conversational promise,
        and moving it wouldn't serve this spec's own goal.
*   **Data Flow / Interactions:**

    ```text
    User types a message
       │
       ├─ matches "generate <part number>" ──> kicad.generate_component (existing route,
       │                                        SPEC-202) ──> message renders the schema
       │
       ├─ matches "inject" ──────────────────> kicad.inject_component (existing route,
       │                                        SPEC-108/CTX-108.3) against the most
       │                                        recently generated schema in this
       │                                        conversation ──> message renders success/failure
       │
       └─ anything else ─────────────────────> llm.chat (existing route, SPEC-201) with this
                                                 conversation's history ──> message renders
                                                 the model's real text response
    ```

*   **Cross-Module Impacts:**
    *   `apps/tauri-ui`: replaces `App.tsx`'s current single-input UI with the message-list surface
        described above. `EnclosurePanel` (`CTX-105.2`) is unaffected — kept as its own panel per the
        design rationale above.
    *   No impact on `services/python-daemon` or `core/tauri-rust` — every route this spec's UI calls
        (`kicad.generate_component`, `kicad.inject_component`, `llm.chat`) already exists, already
        real, already async-job-wrapped. This is a real claim to verify against the actual caller
        before trusting it (`CTX-202.1` Deviation 2 found exactly this kind of claim wrong once
        already in this repo) — but unlike that case, this spec adds no new params to any existing
        route, only a new UI calling them the same way `App.tsx` already does.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   None yet — `App.tsx` today is a working but minimal UI; this spec has no existing broken
        behavior to fix, only a real UX gap (no conversation, no message history, raw JSON dumps) to
        close.
*   **Gotchas & Hazards:**
    *   **The `generate <part number>` / `inject` command-recognition rule is this spec's own
        invention, not a real NLP capability.** A message that almost but doesn't quite match either
        pattern (e.g. "please generate a footprint for BME280") needs a defined fallback — falling
        through to a plain chat turn (per §2) rather than a confusing partial match or a hard error
        is the safer default, but the exact matching rule (case sensitivity, whitespace, punctuation
        tolerance) is this context's own decision to make explicitly, not implicit in this spec.
    *   **`inject` acting on "the most recently generated schema in this conversation" needs a clear
        empty-state.** If no `generate` command has succeeded yet in the current conversation, this
        must be a clean, specific message ("nothing to inject yet — generate a component first"),
        not a null-pointer-shaped error reaching the user.
    *   **Real LLM response latency is still real latency.** Every route this spec calls is already
        async-job-wrapped (`SPEC-105`), so the UI must not block — but a chat-shaped UI raises the
        stakes on this being visually obvious (a spinner or "thinking…" state per in-flight message)
        compared to today's single global `pending` boolean, since a user mid-conversation
        reasonably expects to see progress on the specific message they just sent, not just "the app
        is busy."

## 4. Module Map & Reference Links

*   [ROADMAP.md](../../../ROADMAP.md) §3.2, §4, §6 — this spec's backlog entry, the M1 critical path
    it completes (the last unwritten node), and the confirmation-gate risk-register entry this spec
    deliberately does not attempt to close.
*   [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) /
    [CTX-105.2](../context/CTX-105.2-frontend-job-progress-client.md) — the `submitJob`/`JobHandle`
    client this spec's message-send logic reuses for every route it calls, unchanged.
*   [SPEC-201](../../../services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md) — the
    `llm.chat` route a plain (non-command) chat turn calls, and the real, verified fact (checked
    directly against the installed package for this spec) that no provider supports streaming today.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) /
    [CTX-202.1](../../../services/python-daemon/context/CTX-202.1-component-intelligence-pipeline.md) —
    the `generate` command's real route, unchanged.
*   [SPEC-108](../../../services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md) /
    [CTX-108.1](../../../services/python-daemon/context/CTX-108.1-kicad-write-path-footprint-injection.md),
    [CTX-108.3](../context/CTX-108.3-inject-component-ui.md) — the `inject` command's real route and
    its existing plain-button precedent, unchanged.
*   [SPEC-204](#) (not yet written) — the eventual real agentic tool-calling upgrade path for the
    rule-based command recognizer this spec introduces.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-302] Chat & Command Surface
          └── [Context 302.1] (not yet written)
```
