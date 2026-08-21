---
id: SPEC-202
title: "Component Intelligence Pipeline"
status: Draft
type: Feature
created: 2026-08-09
last_updated: 2026-08-09
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: false
---

# SPEC-202: Component Intelligence Pipeline

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace `kicad.generate_component`'s `time.sleep(1.5)` mock with a real
    pipeline: a part number or datasheet excerpt in, a validated structured component schema out
    (pins, numbers, names, electrical types, package dimensions, courtyard) — expressed as an
    AgentFlow `.workflow.md` DAG (an agent node for the LLM extraction, a handler node for
    deterministic, no-LLM-call schema/geometry validation), not bespoke glue code.
*   **Business / Technical Value:** This is the sixth of six nodes on M1's critical path
    (`ROADMAP.md` §4) and, per that same section, "still the heart of the product." The specific
    checks this spec owns — pin count matches the package, pitch is sane, courtyard encloses the
    pads — are what stand between a hallucinated footprint and a real, expensive PCB spin. No
    framework ships this; it is domain logic particular to this product.
*   **Non-Goals:**
    *   **Not supplier API integration.** `ROADMAP.md` §3.2 originally listed `SPEC-203` as a
        dependency of this spec, but `ROADMAP.md` §4 separately and explicitly excludes `SPEC-203`
        from M1, and M1's own critical-path diagram goes straight from `SPEC-201` to this spec with
        no `SPEC-203` node at all — a real contradiction in the roadmap, not a nuance. Resolved here:
        this spec's M1-scoped pipeline is **LLM-only extraction**, permanently, not a "degraded mode"
        of a supplier-augmented pipeline. `SPEC-203` was subsequently explored and retired
        2026-08-18 (see its tombstone) — its own §2.1 finding confirms distributor APIs don't return
        pin assignments from any vendor, so there was never a real enhancement this pipeline could
        have consumed there. LLM-only extraction is the permanent design, not a placeholder for one.
    *   **Not KiCad injection.** `SPEC-108` is what actually writes the validated schema into a live
        board/schematic. This spec's own contract ends at "a validated structured component," the
        same boundary `ROADMAP.md` already draws.
    *   **Not confirmation-gate UI.** `SPEC-204`'s "confirmation gate on all writes"
        (`ROADMAP.md` §6 risk register) is the human-in-the-loop check before anything reaches a real
        board. This spec's validation is the last automated check before that gate, not a
        replacement for it.
    *   **Not session/memory state.** Per `SPEC-201`'s own resolution of this exact question: a
        single request through this pipeline needs no session state. Multi-turn refinement
        ("actually, make pin 3 the enable pin") is future work, not this spec's.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **The `agentflow/` directory (`SPEC-201`'s deferred decision) becomes real here.**
        `services/python-daemon/agentflow/` gains `agents/` (the extraction agent's `.prompt.md`),
        `workflows/` (this pipeline's own `.workflow.md` DAG), and `shared/` (the component schema
        definition, package reference tables §2 below names) — `domains/` stays empty until a spec
        that actually needs it exists. This is the first real content in that directory; `SPEC-201`
        only reserved the location.
    *   **Two-node DAG: agent node → handler node, connected by `inputs` mappings, not bespoke glue.**
        The agent node calls the configured LLM provider (`SPEC-201`) with the part number/datasheet
        excerpt and a schema-shaped prompt; the handler node is plain, deterministic Python — no LLM
        call, no network — that runs the actual safety checks. AgentFlow's own DAG mechanism is the
        orchestration; this spec supplies the prompt content and the handler's validation logic, not
        a new execution engine.
    *   **The component schema is this spec's own, concrete contract, not left to prompt
        improvisation:**
        ```json
        {
          "part_number": "string",
          "package": "string",
          "pins": [
            {"number": "string", "name": "string", "electrical_type": "input|output|bidirectional|power|ground|passive|no_connect"}
          ],
          "package_dimensions": {"length_mm": "number", "width_mm": "number", "height_mm": "number", "pitch_mm": "number"},
          "courtyard": {"length_mm": "number", "width_mm": "number"}
        }
        ```
        `electrical_type` deliberately mirrors KiCad's own pin electrical-type vocabulary
        (`SPEC-108` will need that alignment to inject a real symbol later) — not invented fresh.
    *   **The handler node's checks, concretely — this is the spec's real substance, not left
        implicit:**
        1. **Pin count matches the package.** A small reference table of common package families
           (e.g. `SOIC-8` → 8, `0603` → 2, `TQFP-32` → 32) the extracted `pins` count must match
           exactly for any package this pipeline recognizes.
        2. **Pitch is sane for the package family.** `package_dimensions.pitch_mm` must fall inside
           that family's real-world range (e.g. 0.4mm–2.54mm) — catches an LLM inventing an
           impossible value, not just a wrong one.
        3. **Courtyard encloses the package body.** `courtyard.length_mm`/`width_mm` must be ≥
           `package_dimensions.length_mm`/`width_mm` plus a standard clearance margin — a courtyard
           smaller than the part itself is physically nonsensical and must never reach a board.
        A component failing any check is a validation error, not a best-effort warning — `SPEC-204`'s
        confirmation gate is the human review step; this handler is the automated one before it.
*   **Data Flow / Interactions:**

    ```text
    kicad.generate_component (real, replaces the time.sleep mock)
       │  part number or datasheet excerpt
       ▼
    AgentFlow WorkflowExecutor runs this pipeline's .workflow.md DAG:
       │
       ├─> Agent node: calls the configured LLM provider (SPEC-201's
       │   llm.chat / provider layer) with an extraction prompt, returns
       │   the component schema shape above (unvalidated)
       │
       ▼
       └─> Handler node (deterministic, no LLM call): runs the three
           checks above against the extracted schema
       │
       ▼
    Validated schema returned to kicad.generate_component's caller, or a
    specific validation error naming which check failed and why
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: new `agentflow/agents/`, `agentflow/workflows/`,
        `agentflow/shared/` content; `kicad_bridge.py`'s existing mock
        `mock_generate_component` is replaced by this real pipeline, wired through the same
        `kicad.generate_component` route name so no frontend/Rust change is needed.
    *   No impact on `core/tauri-rust` or `apps/tauri-ui` — same route name, same async-job wrapping
        pattern `SPEC-105`/`SPEC-201` already established (a real LLM-backed extraction is
        multi-second, same reasoning as `llm.chat`/`freecad.generate_enclosure`).

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   None yet — `kicad.generate_component` today is `time.sleep(1.5)` plus fabricated filenames;
        this spec has no existing broken *validation* behavior to fix, only a real gap (no
        validation exists at all) to close.
*   **Gotchas & Hazards:**
    *   **A hallucinated-but-plausible component is the single highest-consequence failure mode in
        this product** (`ROADMAP.md` §6's risk register names it explicitly: "a wasted PCB spin; the
        fastest way to lose a hardware engineer's trust permanently"). The three checks in §2 are
        deliberately concrete and named, not "the LLM should double-check its own work" — a model is
        not a reliable check on its own output.
    *   **The package reference table (pin counts, sane pitch ranges) is necessarily incomplete.** A
        package this pipeline doesn't recognize can't be checked against #1/#2 above — this context
        needs to decide explicitly whether an unrecognized package fails closed (validation error,
        safer) or passes through unchecked (more permissive, riskier) rather than defaulting into
        one silently.
    *   **The handler node must stay genuinely deterministic.** The instant it makes its own LLM
        call "to double check," it stops being the independent safety net this design relies on —
        AgentFlow's handler-node mechanism (Python, no model call) is the reason this design works,
        not an implementation detail to drift away from.

## 4. Module Map & Reference Links

*   [ROADMAP.md](../../../ROADMAP.md) §3.2, §4, §6 — this spec's backlog entry, the M1 critical path
    it completes, and the risk register entry it directly addresses.
*   [SPEC-201](SPEC-201-llm-provider-abstraction.md) / [CTX-201.1](../context/CTX-201.1-llm-provider-abstraction.md) —
    the `agentflow/` directory location this spec's content actually populates, and the provider
    layer the agent node calls through.
*   [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) — the async job
    pattern this pipeline's real (multi-second) extraction call should very likely use, same as
    `llm.chat`/`freecad.generate_enclosure`.
*   [SPEC-108](#) (not yet written) — the KiCad-injection consumer of this spec's validated schema.
*   [SPEC-204](#) (not yet written) — the human confirmation gate downstream of this spec's
    automated validation.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-202] Component Intelligence Pipeline
          └── [Context 202.1] (not yet written)
```
