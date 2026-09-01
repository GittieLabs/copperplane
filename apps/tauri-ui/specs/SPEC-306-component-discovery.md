---
id: SPEC-306
title: "Component Discovery"
status: Completed
type: Feature
created: 2026-08-12
last_updated: 2026-09-01
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-306-component-discovery.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-306: Component Discovery

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace the Components area's `NotBuiltPlaceholder` (`SPEC-305`) with the
    real first stage of `PRODUCT-PLAN.md` §2.3's stage machine: a free-text search that returns
    ranked candidate parts, each with enough evidence (manufacturer, package, datasheet link,
    confidence) for the user to pick the right one from a *did you mean* card — never a silent
    substitution.
*   **Business / Technical Value:** `PRODUCT-PLAN.md` §1 names the exact failure this fixes: typing
    "looking for esp32-s3" fell through to the chatbot, and "generate atiny85" — misspelled —
    silently produced a correct ATtiny85 with nothing surfacing that a correction had occurred. That
    silent-substitution mechanism is the bug, independent of whether the guess happened to be right.
    `PRODUCT-PLAN.md` §6 M2 names this spec directly as "the flow whose absence produced the
    reported bug."
*   **Non-Goals:**
    *   **Not real supplier-database search.** `SPEC-203` (Supplier API Integration) was explored
        and retired 2026-08-18 — see its tombstone; distributor APIs don't return pin/identity data
        at all, so this was never going to be a source of ground truth here. Candidate ranking here
        is the LLM's own knowledge of part numbers and packages, the same kind of inference
        `SPEC-202`'s extraction agent already does — not a live query against Octopart/DigiKey/etc.
        The confidence signal this spec requires is exactly what makes that honest rather than a
        query result dressed up as one.
    *   **Not Part Detail, pin display, or library persistence.** `SPEC-307` (Part Detail & Library
        Export) owns the pin table, per-pin guidance, and the actual `library.save_part` call. This
        spec stops at a *confirmed candidate* — a part number, manufacturer, package, and datasheet
        URL the user has explicitly picked — and hands it off; it never itself writes to the parts
        library `SPEC-304` built.
    *   **Not footprint or schematic creation.** `SPEC-308`'s job entirely.
    *   **Not multi-part or BOM search.** One query produces one disambiguation card at a time; a
        bulk-import flow is a different, unwritten spec.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Ambiguity always surfaces as a structured choice, even for a single high-confidence
        result.** `PRODUCT-PLAN.md` §3.3 is explicit: "atiny85" produces a *did you mean* card "which
        the user confirms. It does not produce a silent substitution" — no wording there carves out
        an exception for a single obvious match. This spec's search route always returns a
        candidate list and always requires an explicit confirm click, even when there is exactly one
        candidate and the model reports high confidence. A UI convenience shortcut (auto-selecting a
        lone high-confidence result) is exactly the mechanism `PRODUCT-PLAN.md` §1 diagnosed as the
        root cause of the reported bug, reintroduced with a confidence threshold instead of a regex.
    *   **A new agent, not a reuse of `SPEC-202`'s extraction prompt.** `component_extraction.prompt.md`
        takes an already-known part number and returns one best-effort geometry schema with no
        manufacturer, no datasheet URL, and no confidence field at all (verified by reading the
        prompt directly, not assumed) — it answers "what does this part look like," not "which part
        did the user mean." This spec's search step is a distinct extraction shape (a ranked list of
        `{part_number, manufacturer, package, datasheet_url, confidence, rationale}`), and needs its
        own prompt file and pipeline function alongside, not instead of, `generate_component`.
    *   **Confidence is model-reported, and the card is the safety mechanism, not a downstream
        validator.** `SPEC-202`'s three safety checks (pin count, pitch, courtyard) work because
        package geometry is deterministic and checkable against a reference table. Whether "atiny85"
        means ATtiny85 has no equivalent deterministic check — there's nothing to validate a part
        *identity* guess against without a real supplier database (`SPEC-203`, not built). The
        disambiguation card is therefore load-bearing, not cosmetic: it's the only place low
        confidence gets caught, so it can't degrade to a dismissible toast or a footnote.
    *   **Confirming a candidate caches its datasheet, extending a gap `library_store.py` already
        names as its own.** That module's docstring lists `library/datasheets/<part_id>.pdf` in
        `PRODUCT-PLAN.md` §4's own layout, annotated `(not managed by this module yet)`. This spec is
        the first consumer that needs a real datasheet URL fetched and cached, so it's also the spec
        that has to close that gap — a real network fetch and disk write, not a URL string carried
        around unchecked.
*   **Data Flow / Interactions:**

    ```text
    Components area tab (SPEC-305's placeholder, replaced here):

      [ search box: "atiny85"            ] [ Search ]

      Did you mean:
      +--------------------------------------------------+
      | ATtiny85            Microchip        DIP-8/SOIC-8 |
      | confidence: high    [ view datasheet ]  [ This one] |
      +--------------------------------------------------+
      | ATtiny84            Microchip        DIP-14       |
      | confidence: low     [ view datasheet ]  [ This one] |
      +--------------------------------------------------+

    search box --component.search(query)--> ranked candidates (no library write yet)
    "This one" --> datasheet fetched + cached (library/datasheets/<part_id>.pdf) -->
                    confirmed candidate handed to SPEC-307 (hand-off mechanism: SPEC-307's own call)
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new AgentFlow prompt (alongside `component_extraction.prompt.md`,
        not replacing it), a new `component_pipeline` search function returning ranked candidates, a
        new daemon route (e.g. `component.search`), and a `library_store.py` extension to actually
        cache a datasheet PDF by URL — the one piece of `PRODUCT-PLAN.md` §4's layout no existing
        module writes today.
    *   `apps/tauri-ui`: the Components area (`App.tsx`'s `NotBuiltPlaceholder` slot from `SPEC-305`)
        gets a real search UI; a new `lib/` wrapper for the search route, following the same
        `dispatch`-wrapping pattern `lib/projects.ts` established.
    *   No impact on `core/tauri-rust` — pure daemon-route and frontend work, same shape as
        `SPEC-305`.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **No real ground truth for part identity.** Ranking is LLM inference over its own training
        knowledge, not a live distributor lookup. `SPEC-203` (Supplier API Integration) was explored
        and retired 2026-08-18 — no vendor returns pin/identity data anyway, so there was never a
        real replacement waiting there. This spec's confidence field is what keeps the LLM's own
        guess honest, permanently, not as a stopgap for a future integration.
*   **Gotchas & Hazards:**
    *   **A failed datasheet fetch must fail closed with a clean, specific error, not a silent skip.**
        Matching the existing bridge-module convention (`kicad_bridge`/`freecad_bridge`): a
        confirmed candidate whose datasheet can't be fetched should say so, not quietly hand off a
        candidate with a dead or missing local cache.

        **Amended 2026-09-01 (`CTX-306.8`): this applies to every surface that offers the
        datasheet, not only to confirmation.** The rule was implemented for the confirm path --
        `cacheDatasheet` runs on "This one" and its failure is captured as `cacheError` -- but the
        candidate card's own "view datasheet" link handed `datasheet_url` straight to the OS
        unverified. A real search for `CR2032` produced
        `https://industrial.panasonic.com/cdbs/www-data/pdf/AAA4000/AAA4000C417.pdf`, which 404s;
        clicking the link dropped the user into a browser error page with nothing in the app
        explaining why. Every path that opens a datasheet now goes through the same fetch, and
        reports failure in the app.

        A detail worth recording because it defeats the obvious check: that 404 returns
        `Content-Type: application/pdf` with `Content-Length: 0`. **A content-type check passes
        it.** Only the response status catches it.
    *   **`datasheet_url` is a model guess and the UI must not present it as a verified fact.**
        `component_search.prompt.md` explicitly asks for a "best real guess" and calls a wrong one
        "a normal, recoverable outcome" -- which is the right call for a *guess*, and the reason
        `§3`'s no-ground-truth constraint exists at all. What is not right is rendering that guess
        identically to a checked fact. `confidence` on the card describes the **part identity**,
        not the URL, but sitting directly above a "view datasheet" link it reads as covering both.
        The link states that it is unverified until something actually fetches it.
    *   **Extending `library_store.py` for datasheet caching must not touch Part's existing
        provenance contract.** `CTX-304.1` already validates that `datasheet_url` has a provenance
        entry; a cached local PDF path is a new, additional fact about a Part, not a replacement for
        the URL, and a Part must remain valid (per the existing schema check) whether or not its
        datasheet has been cached yet.
    *   **The hand-off from a confirmed candidate to `SPEC-307` is explicitly not decided here.**
        Whether that's React state, a route, or something else is `SPEC-307`'s own design call to
        make when it's written — this spec's own scope ends at producing a confirmed candidate, not
        at deciding how the next stage receives it.

## 4. Module Map & Reference Links

*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) §2.3, §3.3 — the stage machine this spec
    builds stage 1 of, and the "ambiguity surfaces as a structured choice" rule this spec's
    disambiguation card exists to satisfy.
*   [SPEC-305](SPEC-305-app-shell-navigation.md) — the Components area tab this spec replaces the
    placeholder in.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) —
    the existing extraction pipeline this spec adds a sibling search capability alongside, not a
    replacement for.
*   [SPEC-304](SPEC-304-project-library-storage.md) — the Part schema and `library_store.py` module
    this spec extends with real datasheet caching.
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §1, §2.3, §3.3, §5.1, §6 M2 — the reported bug this
    spec fixes, the stage machine, the AI-boundary rule, this spec's own scope row, and the milestone
    it's step 4 of.
*   `SPEC-307` *(not yet written — no file to link to)* — Part Detail & Library Export, the spec
    that receives this spec's confirmed candidate and owns the actual library save.

```text
[SPEC-300] Product IA & Interaction Model
   └── [SPEC-305] App Shell & Navigation
          └── [SPEC-306] Component Discovery
                 └── [Context 306.1] (not yet written)
```

## 5. User & Interaction

*   **Product Stage:** Component Discovery — stage 1 of `PRODUCT-PLAN.md` §2.3's stage machine, the
    entry point for adding any part to a project.
*   **What the user is trying to accomplish:** Type a part name or number they may have
    misremembered or misspelled, and get back the real part it means — with enough evidence
    (manufacturer, package, a datasheet link) to trust the match before it becomes anything
    persistent.
*   **What the user sees and does:** The Components area tab shows a search box instead of the
    "not built yet" placeholder. Submitting a query renders a ranked *did you mean* list — each
    candidate showing its part number, manufacturer, package, a confidence label, and a "view
    datasheet" link. The user picks one with an explicit "This one" click; nothing is silently
    assumed or auto-selected, even when there's only one candidate.
