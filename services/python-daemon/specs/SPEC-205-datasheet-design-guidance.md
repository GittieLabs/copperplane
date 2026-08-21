---
id: SPEC-205
title: "Datasheet-Driven Design Guidance"
status: In-Progress
type: Module
user_facing: true
created: 2026-08-18
last_updated: 2026-08-20
target_version: v0.3.0
location: "services/python-daemon/specs/SPEC-205-datasheet-design-guidance.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
---
# SPEC-205: Datasheet-Driven Design Guidance
## 1. Executive Summary & Goals
*   **High-Level Goal:** Given a part and its datasheet, surface what someone needs *around*
    that part to use it correctly — supply range and current, decoupling capacitors, pull-ups,
    crystal load capacitance, protection components, and layout constraints — with **every item
    citing the section of the datasheet it came from**.
*   **Business / Technical Value:** This is the question a builder actually asks before committing
    a part to a board, and the one that costs the most when answered wrong. It is also the clearest
    expression of the product's "advisor, not generator" framing: the app is not placing capacitors,
    it is telling the builder what the datasheet requires and showing them where it says so. No
    distributor API sells this data (see [SPEC-203](SPEC-203-supplier-api-integration.md), retired);
    it exists only in datasheet prose, tables, and reference designs.
*   **Real audience correction (2026-08-20), from live use of the first shipped slice**: this
    spec's original text assumed a practicing hardware engineer as the reader. Real user testing of
    `CTX-205.4`'s shipped panel against a real datasheet showed that assumption was wrong for this
    product: the actual audience is a **maker/hobbyist**, not someone who reads datasheets for a
    living. Correctly cited, verbatim datasheet prose — even once the extraction itself is accurate
    — is not the right *reading experience* for that audience; it is proof, not explanation. §2.1
    now names a synthesis layer that addresses this without touching the citation contract itself.
*   **Non-Goals:**
    *   **Not placing components.** No schematic is generated, no netlist is written, nothing is
        injected into a board.
    *   **Not a substitute for reading the datasheet.** Every claim links back to it; the goal is to
        get the builder to the right page faster, not to replace the page.
    *   **Not general electronics tutoring.** Explaining what a decoupling capacitor *is in general*
        still belongs to the project conversation surface, not here. Translating *this document's
        own cited facts* into plain language (§2.1's synthesis layer) is in scope; teaching
        electronics from first principles is not — the difference is whether the sentence is
        grounded in a specific citation or not.
    *   **Not application notes or reference designs** in this pass. The datasheet is the boundary —
        see §3.
    *   Not a compliance, safety, or sign-off tool.
## 2. System Architecture & Design Choices
### 2.1 Design Rationale: three classes of output, three different contracts
The single most important decision in this spec is that **not all guidance is the same kind of
claim**, and collapsing them is what makes this feature dangerous.
| Class | What it is | Contract | Example |
| :--- | :--- | :--- | :--- |
| **A — Tabular fact** | Values from Absolute Maximum Ratings, Recommended Operating Conditions, DC/AC characteristics | Typed, unit-bearing, range-checked, **must cite**. Has a right answer. | `V_CC: 2.7–5.5 V` |
| **B — Cited guidance** | Design requirements stated in datasheet prose | Quoted or closely paraphrased, **must cite**, never invented | "A 100 nF decoupling capacitor should be placed close to each V_CC pin" |
| **C — General practice** | Conventional engineering knowledge the model holds, not found in this document | **Must be labelled as such**, visually segregated, never cited to the datasheet | "Bulk capacitance near the regulator is common practice" |
**Class C exists deliberately, and that is a considered decision.** The obvious instinct is to
forbid unsourced knowledge entirely. In practice, a model told never to use general knowledge tends
to *launder* it into Class B phrasing — producing advice that looks cited but isn't. Giving it a
legitimate, clearly-labelled outlet reduces contamination of the cited set. Class C may be disabled
entirely by configuration, but it should not be silently forbidden.
**A guidance item without a resolvable citation is invalid and must not render.** This is a schema
constraint enforced in the pipeline, not a UI convention. It is the mechanism that converts "the AI
says 100 nF" into "the datasheet says this, §7.2, page 31" — checkable in five seconds.
### 2.1.1 Synthesis: a plain-language layer over the citations, not a fourth class
Added 2026-08-20, after the audience correction in §1. This is **not** a new class of claim — it
introduces no new citable fact and does not weaken the citation requirement above. Per category,
once its Class B items are validated, one additional short (2–4 sentence) plain-language paragraph
is generated **from those same validated items and nothing else** — no new facts, no general
knowledge, no filler when the underlying items are too sparse to say anything substantive (the
synthesis says so honestly in that case, rather than padding). It is grounded translation of
real, already-cited evidence, not independent generation — the underlying citations remain the
actual checkable claim; the summary is a reading aid on top of them, never a replacement for them.
A category with zero validated items gets no summary (`None`), matching the "empty is a valid,
honest answer" rule already established for the items themselves — the synthesis step is skipped
entirely for an empty category, the same real cost/latency discipline as the extraction step's own
"zero candidates, no LLM call" rule.
### 2.2 Retrieval, not one-shot extraction
Datasheet length varies by more than an order of magnitude — a couple hundred pages for an
ATtiny85, well over a thousand for an ESP32-S3 technical reference manual. One-shot extraction over
the whole document is neither affordable nor accurate.
The pipeline locates before it extracts:
```text
datasheet PDF (user-supplied, or resolved by SPEC-306)
      │
      ├─ 1. Structure pass: parse TOC / section headings / page map
      │       identify candidate sections by heading match and keyword search
      │       (Absolute Maximum, Recommended Operating, Power, Decoupling,
      │        Reset, Clock/Oscillator, Layout, Typical Application)
      ▼
   candidate page ranges  ──> 2a. Class A extraction (typed, structured)
      │                  └──> 2b. Class B extraction (cited prose)
      ▼
   3. Validation: units present, ranges ordered, every item's citation
      resolves to a real page in THIS document, no Class B item without a quote
      ▼
   4. Assembly: group by category, attach provenance, emit typed result
```
Page numbers are carried through every stage. An item that loses its citation during assembly is
dropped, not promoted.
Per the AgentFlow adoption decision, this is a `.workflow.md` DAG, not bespoke orchestration.
### 2.3 Cross-Module Impacts
*   **SPEC-202** — shares the datasheet and the provenance model. This spec extends provenance to
    carry a section/page locator, not just a source identifier.
*   **SPEC-304** — guidance items persist on the Part record. They derive from a document the user
    supplied or opened, so no distributor caching constraint applies.
*   **SPEC-306** — supplies the datasheet (resolution and user upload).
*   **SPEC-307** — renders the output; per-pin selection filters guidance to that pin.
*   **SPEC-105** — extraction over a long document is a multi-minute job; it needs the async job and
    progress protocol, not a blocking call.
*   No impact on `core/tauri-rust`.
## 3. Known Constraints & Risks
*   **Confident, unsourced advice is the primary risk, and it is worse here than anywhere else in
    the product.** The model knows general EE practice and will produce fluent, plausible
    recommendations that no page supports. Presented alongside cited items, uncited advice inherits
    their credibility without earning it. Class C labelling plus the hard citation requirement are
    the mitigations; neither is perfect.
*   **Failure is asymmetric and silent.** A wrong footprint fails loudly at assembly — the part does
    not fit and the engineer finds out immediately. **Missing or wrong decoupling advice fails
    intermittently, in the field, months later, and gets attributed to something else.** This is why
    the citation requirement is a schema constraint rather than a best effort.
*   **Guidance hides in images.** A required RESET pull-up frequently appears only in a typical
    application schematic, never in prose. Vision extraction from schematic images is markedly less
    reliable than text extraction. **Decide explicitly**: either handle images with a lower
    confidence class, or declare them out of scope — and if out of scope, say so in the UI, because
    an engineer who assumes full coverage is worse off than one who knows the boundary.
*   **Multi-variant datasheets.** One document routinely covers ATtiny25/45/85 or a whole family
    with differing pin counts and supply ranges. Attributing a variant-specific requirement to the
    wrong variant is a realistic and dangerous failure. Variant scoping must be explicit in the
    extraction, not assumed.
*   **Citations drift across revisions.** Datasheet revisions renumber pages. "Page 31" of rev C is
    wrong for rev D. Store the document revision and a content hash alongside the citation, and
    prefer section identifiers over bare page numbers where the document provides them.
*   **Cost and latency scale with document size**, and the largest documents are the ones users most
    want help with. The structure pass is what keeps this bounded; if it fails to find candidate
    sections, the fallback must be a clean "couldn't locate the relevant sections" rather than a
    full-document sweep.
*   **Tone carries liability weight.** Output must read as "the datasheet says X, here" and never as
    engineering sign-off. No imperative phrasing without a citation behind it.
*   **Application notes are out of scope for this pass, and that is a real gap.** For many parts the
    most useful guidance lives in a separate app note or reference design, not the datasheet.
    Deliberately deferred to keep the citation model tractable against a single known document.
## 4. Module Map & Reference Links
*   [Root Architecture: SPEC-000](../../../specs/SPEC-000-architecture-overview.md)
*   [SPEC-202: Component Intelligence Pipeline](SPEC-202-component-intelligence-pipeline.md)
*   [SPEC-203: Supplier API Integration (retired)](SPEC-203-supplier-api-integration.md)
*   [SPEC-105: Daemon Async Job & Progress Protocol](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md)
*   [Product plan](../../../ROADMAP.md)
## 5. User & Interaction
*   **Stage.** Component Detail (stage 2 of the product stage machine). Also feeds the Schematic
    stage (stage 3), where per-pin guidance is the primary content.
*   **User goal.** *"Before I use this part in my project, what do I need to know about it — in
    plain terms, from someone who actually read the datasheet?"* (Corrected 2026-08-20: the real
    reader is a maker/hobbyist, not a practicing hardware engineer — see §1.)
*   **What the user sees and does.**
    *   On a part's detail view, a **Design Requirements** panel beside the pin diagram, grouped by
        category: Power, Decoupling, Reset/Boot, Clock, Protection, Layout.
    *   Each category leads with its §2.1.1 **plain-language summary** where one exists — this is
        the primary reading surface. The underlying cited items sit below it, collapsed by default,
        available on demand as proof, not as the first thing the user has to parse.
    *   Every Class A and Class B item carries a **citation chip** (e.g. `§7.2 · p31`) that opens
        the datasheet at that page. The chip is the point of the feature — an item without one does
        not appear.
    *   Class C items sit in a separate, visually distinct group headed **"General practice — not
        from this datasheet."** Never interleaved with cited items.
    *   Selecting a pin in the diagram filters the panel to guidance affecting that pin.
    *   A first-class empty state: when the datasheet yields nothing for a category, the app says so
        plainly. Silence must not be readable as "no requirements."
    *   Where variants were detected, the panel states which variant the guidance applies to.
