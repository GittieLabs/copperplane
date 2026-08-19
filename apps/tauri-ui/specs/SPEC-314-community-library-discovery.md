---
id: SPEC-314
title: "Community Footprint & Symbol Library Discovery"
status: Draft
type: Feature
created: 2026-08-19
last_updated: 2026-08-19
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-314-community-library-discovery.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-314: Community Footprint & Symbol Library Discovery

## 1. Executive Summary & Goals
*   **High-Level Goal:** Real component library discovery, resolving `SPEC-312`'s deferred item 5
    -- but scoped to what's actually verified buildable, not the original vague framing. Given real
    research (2026-08-19, see §2 Design Rationale), this means: search a real, curated set of
    MIT/permissively-licensed, GitHub-hosted KiCad community footprint/symbol libraries, and offer
    to import a real match into this app's own local library (`SPEC-304`) -- an alternative,
    community-vetted source alongside `SPEC-308`'s existing installed-library search and
    datasheet-driven generation (`CTX-308.5`).
*   **Business / Technical Value:** `SPEC-308`'s only footprint sources today are the user's own
    installed KiCad libraries and fresh LLM generation from datasheet dimensions. A footprint that
    already exists in a real, community-maintained, widely-used library (e.g. a vendor's own
    official KiCad repo) is generally more trustworthy than a freshly LLM-generated one -- someone
    else has already used it on a real board. Offering it as a real option, before falling back to
    generation, reduces both hallucination risk and redundant LLM calls.
*   **Non-Goals:**
    *   **Not Ultra Librarian.** Real research found Ultra Librarian's redistribution terms are
        actually permissive, and its catalog (16M+ parts) dwarfs anything scoped here -- but no
        public, documented API for programmatic access could be found (it appears to be a web
        download portal plus CAD-plugin integrations, not a REST API a daemon could call). A real,
        separate follow-up if/when real API access is confirmed directly with them; not blocked on
        or silently assumed here.
    *   **Not an unbounded, live GitHub-wide search.** GitHub's own search only weakly targets code
        content, returns wildly inconsistent licensing/quality, and gives no way to distinguish a
        maintained library from a five-year-old fork. Scoped to a real, maintained allowlist of
        known-good repos instead (§2), extensible over time, not "search all of GitHub."
    *   **Not footprint/symbol generation.** That's `CTX-308.5`'s job, unchanged. This spec finds
        and imports *existing* files; it never invents geometry.
    *   **Not automatic import.** Matches this app's own established "every AI/external step
        confirmable, never silent" precedent (Board Advisor, Connection Guidance, `kicad.
        inject_component`'s confirmation gate) -- a match is proposed, the user imports it
        explicitly.
    *   **Not schematic symbol *placement*.** Same boundary `SPEC-308` already draws for symbols in
        general (`CTX-108.2`'s own reserved slot) -- this spec can locate and import a `.kicad_sym`
        file into the local library the same way it does a `.kicad_mod`, but placing it into a
        schematic is out of scope everywhere in this app today.

## 2. System Architecture & Design Choices
*   **Design Rationale -- why a curated allowlist, verified during scoping, not assumed:** real
    search (2026-08-19) found genuine GitHub-hosted KiCad community libraries exist and are real,
    concretely integrable candidates -- `kitspace/kicad_footprints` (an MIT-licensed aggregator of
    many community repos via git submodules, explicitly describing itself as "a collection of all
    the KiCad footprints on the internet"), plus individual vendor-maintained repos (SparkFun,
    Espressif, and similar real, MIT/CC-style-licensed examples). KiCad's own *official* libraries
    (`kicad-symbols`/`kicad-footprints`/`kicad-packages3D`) are real too, but live on **GitLab**, not
    GitHub -- and are already bundled with any local KiCad install, so `SPEC-308`'s existing
    installed-library search already covers them; nothing new to build there. The allowlist starts
    small and real (a handful of confirmed, actively-maintained, clearly-licensed repos) and grows
    by adding entries, not by broadening a live search -- keeps every source's license and
    provenance individually known, matching the attribution discipline `SPEC-203`'s own retirement
    doc established for external content generally (its "per-source attribution is mandatory"
    standing rule applies just as much here as it did to distributor data).
*   **Auth is bring-your-own GitHub token, optional, never bundled.** The GitHub REST API allows 60
    unauthenticated requests/hour per IP -- workable for occasional lookups but real and easy to
    exhaust during active use. A personal access token raises this to 5,000/hour. Reuses `SPEC-106`'s
    existing OS-keychain secret mechanism with a new `github_token` key, exactly the same
    `KNOWN_SECRET_KEYS` pattern `SPEC-201`'s LLM provider keys already use -- never a project-held
    credential, per the same "never bundle an API key" reasoning `SPEC-203`'s retirement already
    established as a standing rule for this project generally. The feature must degrade gracefully
    (real, working, just rate-limited) with no token configured -- not require one.
*   **A real, unresolved parsing risk, named honestly rather than assumed away:** `.kicad_mod` and
    `.kicad_sym` are both KiCad's S-expression format. This project's own prior research
    (`kicad_pcb_import.py`'s own docstring, `SPEC-310`) already found `kiutils 1.4.8` -- a real
    third-party KiCad-file parser -- crashing with a real `IndexError` on a real, current KiCad 10
    board file. Footprint/symbol files are far smaller and simpler than a full board, so this may
    not recur, but it must be verified directly against real files pulled from the real allowlist
    repos before being relied on, not assumed safe because it's a "simpler" format. `kicad-cli`
    itself may offer a safer validate/import path (the same real pattern `kicad_pcb_import.py`
    already chose over parsing `.kicad_pcb` directly) -- a real implementation-context decision,
    not resolved here.
*   **Data Flow / Interactions:** A part/package query (from Part Detail, already known via
    `SPEC-307`) → search the allowlist's real, current file trees via the GitHub REST API (contents/
    search endpoints) for a filename/path match → real candidates surfaced with their real repo,
    file path, and license → user selects one → the real file content is fetched and parsed →
    persisted through `library_store.save_footprint`/`save_symbol` (`CTX-304.1`, reused as-is,
    matching `SPEC-308`'s own established reuse of the same functions) with real provenance
    recording the source repo URL, file path, commit SHA, and license -- traceable back to its real
    origin, not just "found on GitHub."
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new module for the curated allowlist, GitHub REST API search/
        fetch (a plain HTTP client, same class of integration `SPEC-203`'s own text already
        described distributor APIs as -- "not an LLM-orchestration concern"), and real `.kicad_mod`/
        `.kicad_sym` parsing (parser choice deferred to context, per above). New `get_capabilities`
        entry reflecting whether a `github_token` is configured (mirrors every existing optional-
        credential capability flag already in this codebase).
    *   `core/tauri-rust`: one new `KNOWN_SECRET_KEYS` entry (`github_token`).
    *   `apps/tauri-ui`: a new Settings field for the optional token; a real search/results surface
        in Part Detail (or Footprint search, `SPEC-308`'s own existing UI) offering community-library
        matches alongside installed-library results and the generate-from-datasheet action.

## 3. Known Constraints & Risks
*   **The allowlist is real curation work, not a technical build -- and it will always be
    incomplete.** Every repo added is a real, individual judgment call (is it actively maintained,
    clearly licensed, trustworthy); the feature's own honesty depends on this list staying small and
    verified rather than growing indiscriminately. A "not found in our known libraries" result is a
    normal, expected, honest outcome -- never implied as "doesn't exist anywhere."
*   **License diversity across repos is real, not uniform.** Even within a curated allowlist,
    different repos may use different permissive licenses (MIT, CC-BY-SA, CERN-OHL, etc.) with
    different real attribution requirements. Each imported footprint/symbol's own provenance must
    record its real, specific license -- not a single project-wide assumption.
*   **GitHub API rate limits are real and will be hit during active use without a configured
    token.** 60 requests/hour unauthenticated is easy to exhaust in a single active search session;
    the UI must surface this honestly (a real "rate limited, try again in N minutes, or add a GitHub
    token in Settings" message) rather than a generic failure.
*   **The kiutils/S-expression parsing risk (§2) could block this spec's real usefulness entirely**
    if no reliable parser is found for real-world footprint/symbol files -- this is named as the
    single highest-risk open question for the implementation context to resolve early, before
    building the search/UI layers on top of an unverified assumption.
*   **A found file's real geometry still needs the same safety validation `SPEC-202`'s own component
    pipeline already established** (pin count/pitch/courtyard sanity) before it's ever injected into
    a real board via `kicad.inject_component` -- a community file is more trustworthy than a fresh
    LLM generation, but "more trustworthy" is not "unconditionally safe to inject unchecked."

## 4. Module Map & Reference Links
```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-314-community-library-discovery.md)
                 └── [Context 314.1](../context/CTX-314.1-subfeature.md)
```
*   [SPEC-106](../../../specs/SPEC-106-configuration-secrets-store.md) -- the real OS-keychain
    secrets mechanism this spec's new `github_token` key extends, unchanged.
*   [SPEC-203](../../../services/python-daemon/specs/SPEC-203-supplier-api-integration.md) --
    retired, but its own "never bundle an API key" and "per-source attribution is mandatory"
    standing rules apply directly to this spec's own external-content integration.
*   [SPEC-308](SPEC-308-footprints-schematic-advisor.md) -- the existing installed-library search
    and datasheet-generation flow this spec adds a third, community-sourced option alongside;
    reuses its own `library_store.save_footprint`/`save_symbol` persistence.
*   [SPEC-310](SPEC-310-enclosure-from-board-profile.md) -- where the real `kiutils`
    parsing-failure finding this spec's own risk section cites was first made
    (`kicad_pcb_import.py`'s own docstring).

## 5. User & Interaction
*   **Product Stage:** Component Detail / Footprint search (`SPEC-307`/`SPEC-308`'s own existing
    surfaces) -- a real part or package is already known before this feature has anything useful to
    search for.
*   **What the user is trying to accomplish:** find a real, already-proven footprint or symbol for
    a part instead of generating a fresh one from datasheet dimensions every time -- especially for
    common parts (connectors, common ICs, dev-board modules) where a well-maintained community
    library almost certainly already has exactly the right file.
*   **What the user sees and does:** alongside `SPEC-308`'s existing installed-library results, a
    real "Community libraries" section showing matches with their real source repo name, file path,
    and license, each with an "Import" action. Selecting one fetches and parses the real file, shows
    a real preview before committing, and on confirmation persists it through the same
    `save_footprint`/`save_symbol` path any other footprint uses -- indistinguishable afterward
    except for its own recorded provenance. A real, honest "nothing found in known libraries" state
    when no allowlist repo has a match, distinct from a rate-limit or network error.
