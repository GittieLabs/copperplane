---
id: SPEC-203
title: "Supplier API Integration"
status: Draft
type: Feature
created: 2026-08-16
last_updated: 2026-08-16
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-203-supplier-api-integration.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-203: Supplier API Integration

## 1. Executive Summary & Goals
*   **High-Level Goal:** Real, on-demand price-and-stock lookup for a Part against DigiKey, Mouser,
    and Octopart (Nexar), layered on top of `SPEC-202`'s existing LLM-only extraction as optional
    enrichment -- never a hard requirement for `generate_component` to keep working exactly as it
    does today.
*   **Business / Technical Value:** A `Part` today carries `manufacturer`/`package`/`pins`/
    `datasheet_url` -- everything an LLM can reliably know from a datasheet -- but zero real-world
    purchasing signal. Price and stock are exactly the kind of data an LLM structurally can't know:
    they change hourly, per distributor, per region, and no amount of better prompting fixes that.
    `ROADMAP.md` §3.2 already named this gap explicitly and deferred it: "Unaffected by the
    AgentFlow decision -- this is a plain HTTP integration, not an LLM-orchestration concern."
*   **Non-Goals:**
    *   **Not a checkout/ordering integration.** Read-only price/stock lookup only -- this spec never
        places an order or touches a cart.
    *   **Not a required part of `generate_component`.** A Part must remain fully usable with zero
        supplier keys configured, exactly as it is today -- this is additive enrichment, not a new
        dependency on the existing extraction path.
    *   **Not real-time streaming stock alerts.** An on-demand refresh model (mirrors `SPEC-309`'s
        own "Check Board" precedent: the user asks, nothing runs automatically or in the
        background), not a poller.

## 2. System Architecture & Design Choices
*   **Design Rationale:** Each supplier's real API differs enough (auth flow, rate limits, response
    shape) that this spec doesn't assume a shared client abstraction up front -- DigiKey's real API
    uses OAuth2 client-credentials; Mouser and Octopart/Nexar use simpler API-key auth. One client
    module per supplier, verified against that supplier's own real API, not a shared mock standing
    in for all three.
*   **Local cache, not a live call on every request.** Keyed on `(part_number, supplier)`, TTL-based
    -- `ROADMAP.md`'s own stated reasoning: "part data barely changes; re-querying on every request
    wastes quota and adds latency." Reuses `library_store.py`'s existing JSON-file-per-record
    storage convention (the same pattern `Part`/`Footprint`/`Symbol` already use) rather than
    introducing a new storage layer.
*   **Graceful degradation is a first-class state, not an error path.** No supplier key configured
    at all means the feature simply doesn't offer itself in the UI -- mirrors
    `daemon.get_capabilities`'s existing `kicad_cli_available`/`freecad_available` pattern
    (`CTX-309.1`, `CTX-104.1`), not a new convention.
*   **Secrets reuse the existing OS-keychain mechanism (`SPEC-106`/`SPEC-303`) with new key names,
    not a new storage path.** `digikey_api_key`, `mouser_api_key`, `octopart_api_key` (exact naming
    -- e.g. `nexar_api_key` if Octopart's current public API branding requires it -- confirmed
    during implementation, not assumed here) extend `core/tauri-rust/src/daemon.rs`'s
    `KNOWN_SECRET_KEYS` the same way LLM provider keys already work. These are a materially
    different kind of provider than `ALL_PROVIDERS` (LLM providers) -- a new Settings UI section,
    not folded into the existing provider list.
*   **Data Flow / Interactions:** Part Detail's on-demand "Check pricing" action (never automatic)
    -> a daemon route -> cache lookup (return immediately if fresh) or a real supplier HTTP call on
    a cache miss/stale entry -> real price breaks, stock quantity, and a real "as of" timestamp
    returned and shown to the user, so staleness is visible, never hidden.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new client module per supplier, a new daemon route (async --
        a real outbound HTTP call, matching every other real-network route's own `ASYNC_ROUTES`
        precedent), new `get_capabilities` entries per configured supplier.
    *   `core/tauri-rust`: new `KNOWN_SECRET_KEYS` entries.
    *   `apps/tauri-ui`: a new Settings UI section for supplier keys; a pricing/stock display in
        Part Detail.

## 3. Known Constraints & Risks
*   **Real credentials are a real, current blocker -- the same class of gap `SPEC-402` was just
    deferred over for signing certificates.** DigiKey/Mouser/Octopart developer accounts don't exist
    in this repo's history yet. Per `CLAUDE.md`'s "verify against the real thing" norm, each
    supplier's real integration should ship (and be verified for real) only once its own credentials
    exist -- most likely one `CTX-203.n` per supplier, so partial credential availability for one
    supplier doesn't block progress on the others.
*   **Each supplier's real rate limits, auth flow, and response shape are genuinely different, not
    assumed uniform.** Confirming this for one supplier does not imply the others behave the same
    way; each client module needs its own real verification.
*   **Currency and region are real, unresolved scope questions.** Supplier pricing is
    region/currency-dependent; this spec's first implemented slice must state plainly which
    region/currency it targets, not silently assume USD/US availability.
*   **Cache staleness could show a wrong price at order time.** This spec's job is to always show
    the real "as of" timestamp next to any cached number, not to guarantee real-time accuracy --
    honest recency, not a promise this spec can't keep.

## 4. Module Map & Reference Links
```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [This Spec](SPEC-203-supplier-api-integration.md)
          └── [Context 203.1](../context/CTX-203.1-subfeature.md)
```
*   [SPEC-106](../../../specs/SPEC-106-configuration-secrets-store.md) -- the real OS-keychain
    secrets mechanism this spec's new supplier keys extend, unchanged.
*   [SPEC-202](SPEC-202-component-intelligence-pipeline.md) -- the existing LLM-only Part
    extraction this spec layers real pricing/stock enrichment on top of, without changing.
*   [SPEC-303](../../../apps/tauri-ui/specs/SPEC-303-settings-ui.md) -- the real Settings UI Tier 1
    pattern (provider/model/keys) this spec's new supplier-key section follows.
*   [SPEC-309](../../../apps/tauri-ui/specs/SPEC-309-board-advisor.md) -- the real, established
    on-demand-not-automatic precedent ("Check Board") this spec's own "Check pricing" action follows.
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md), [ROADMAP.md](../../../ROADMAP.md) §3.2 -- where this
    gap was originally named and deferred.

## 5. User & Interaction
*   **Product Stage:** Part Detail, once a part already exists -- mirrors `SPEC-308`'s own
    footprint/connection-guidance placement: an enrichment action on an already-real part, not part
    of initial generation.
*   **What the user is trying to accomplish:** know whether a part is actually in stock and roughly
    what it costs, before committing it to a real design or BOM.
*   **What the user sees and does:** a "Check pricing" action in Part Detail (per-supplier or
    combined, resolved during implementation); results show real price breaks by quantity, real
    stock count, and the real supplier name, each tagged with a real "as of" timestamp. Nothing
    happens automatically without the user asking -- consistent with the product's existing
    "every AI/external step confirmable, never silent" principle already established for Board
    Advisor and Connection Guidance.
