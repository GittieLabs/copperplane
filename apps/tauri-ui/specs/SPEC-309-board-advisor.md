---
id: SPEC-309
title: "Board Advisor"
status: Draft
type: Feature
created: 2026-08-16
last_updated: 2026-08-16
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-309-board-advisor.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-309: Board Advisor

## 1. Executive Summary & Goals
*   **High-Level Goal:** Run KiCad's own Electrical Rules Check (schematic) and Design Rules Check
    (board), turn the real, structured violation list each produces into plain-language explanation
    and suggested fixes via an LLM call. `PRODUCT-PLAN.md` §6 M4 -- deliberately sequenced after
    `SPEC-308`/M3, since it depends on file-access patterns M3 already established (a real, saved
    Project pointing at real KiCad files).
*   **Business / Technical Value:** KiCad's own ERC/DRC output is real and already correct -- the
    tool isn't wrong, it's just terse and assumes the reader already knows what "pin_to_pin" or
    "invalid_outline" implies about the fix. This spec doesn't reimplement rule-checking (that would
    be redundant and worse than KiCad's own real engine); it makes KiCad's own real results legible
    to someone who hasn't memorized its violation vocabulary yet.
*   **Non-Goals:**
    *   **Not auto-fixing anything.** Read-only: run the check, explain the results, suggest what a
        human could do. Never writes to the schematic or board -- there is no confirmation gate here
        because there is nothing this spec's own scope ever mutates.
    *   **Not a custom rule-authoring UI.** Runs whatever ERC/DRC rules the project already has
        configured (KiCad's own project settings); no rule-editing surface.
    *   **Not schematic or board editing of any kind.** Complements `SPEC-108`'s write path and
        `SPEC-308`'s footprint work; doesn't touch either.

## 2. System Architecture & Design Choices
*   **`kicad-cli` subprocess, not kipy live IPC -- confirmed, not assumed.** Grepped the real,
    installed `kipy` proto definitions (`board_commands_pb2.py` and siblings) for anything
    ERC/DRC-shaped: the only hit is `InjectDrcError`, a test-utility RPC for manually injecting a
    fake DRC marker into the UI -- there is no real "run DRC and return results" RPC anywhere in the
    live IPC protocol, and no ERC-shaped RPC at all. `services/python-daemon/freecad_bridge.py`
    already established the real precedent for this repo: shell out to the real CLI tool
    (`freecadcmd`) as a subprocess, don't invent a fake substitute. `kicad-cli` is that same real
    tool for KiCad, confirmed present and working on this machine:
    `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc --help` /
    `kicad-cli pcb drc --help`, both real, both support `--format json`.
*   **Real JSON schema, confirmed by actually running both commands against real personal board
    files on this machine, not guessed from `--help` text:**
    *   `kicad-cli sch erc --format json`: `{$schema, coordinate_units, date, ignored_checks,
        included_severities, kicad_version, sheets: [{path, uuid_path, violations: [{description,
        items: [{description, pos: {x, y}, uuid}], severity, type}]}]}` -- nested per schematic
        sheet (a schematic can have several).
    *   `kicad-cli pcb drc --format json`: `{$schema, coordinate_units, date, ignored_checks,
        included_severities, kicad_version, schematic_parity, source, unconnected_items,
        violations: [{description, items, severity, type}]}` -- flat, since a board is one PCB, not
        several sheets. Real severity values seen: `error`, `warning`, `exclusion`.
*   **PCB path resolves automatically via live IPC; schematic path does not -- both confirmed live
    against a real, running KiCad 10.0.3 instance, not assumed from documentation:**
    *   `kc.get_open_documents(DocumentType.DOCTYPE_PCB)` returns a real, resolvable full path
        (`project.path` + `board_filename`) for whatever board is currently open. DRC can target
        "the board you have open right now" with no manual file-picking for the common case.
    *   The identical call for `DocumentType.DOCTYPE_SCHEMATIC` raises
        `kipy.errors.ApiError: KiCad returned error: no handler available for request of type
        kiapi.common.commands.GetOpenDocuments` -- a real, current API gap, confirmed by the actual
        error text on a live connection, not a hypothetical limitation. This is the same real
        constraint `SPEC-103`'s own deferred-schematic-access decision already named; this spec
        doesn't reopen that decision, it works within it. ERC needs an explicit `.kicad_sch` path
        from the user -- reusing `SPEC-110`'s already-real native file/folder-picker pattern, not a
        new picking mechanism.
*   **Data Flow / Interactions:** resolve a real file path (auto for PCB, user-supplied for
    schematic) → `kicad-cli {sch erc|pcb drc} --format json -o <tmpfile>` as a subprocess → parse
    the real JSON → an LLM call (single agent, no DAG -- parallels `CTX-308.7`'s
    `connection_guidance` shape) turns the structured violation list into plain-language explanation
    plus suggested fixes, grounded in the real `description`/`type`/`severity` fields, never
    inventing a violation that wasn't in the real report.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new module (mirrors `freecad_bridge.py`'s own
        subprocess-plus-real-binary-location pattern) for locating `kicad-cli` and running/parsing
        `sch erc`/`pcb drc`; a new agentflow prompt + pipeline function for the explain-and-suggest
        step; new daemon routes.
    *   `apps/tauri-ui`: a real "Check Board" / "Check Schematic" surface, most naturally a new area
        of the shell (`SPEC-305`) rather than another sub-panel inside Part Detail -- board advisory
        is project-level, not part-level, unlike `SPEC-308`'s footprint work.
    *   `daemon.get_capabilities` (`SPEC-107`): should report whether `kicad-cli` was actually
        located on this machine, the same way it already reports `kicad_available`/
        `freecad_available` -- a broken/missing `kicad-cli` shouldn't take down the rest of the app,
        it should surface as an honest capability gap.

## 3. Known Constraints & Risks
*   **Locating `kicad-cli` reliably is real, unsolved work, not a footnote.** `PRODUCT-PLAN.md` §8
    open question 1 already named this: `kicad-cli` ships as a separate binary inside the KiCad app
    bundle, not something on `PATH` by default. `freecad_bridge.py`'s own `find_freecadcmd`
    (`shutil.which` first, real known-path fallback per OS) is the established pattern to follow --
    this spec's implementation context needs the equivalent for `kicad-cli`, not a hardcoded
    single-OS path.
*   **A real board can produce dozens of violations.** Sending all of them to an LLM in one call
    risks a token-limit truncation the same way `CTX-308.7`'s own Plan Drift (`component_search`'s
    `max_tokens` truncation bug, found by real use) already warns about for verbose LLM output.
    This spec's implementation should decide explicitly whether to cap/batch/summarize rather than
    silently truncate mid-response -- a real decision for the implementation context, not resolved
    here.
*   **ERC/DRC results reflect whatever rules are already configured in the project.** A project with
    loose or misconfigured rules will get a clean report that isn't actually clean in any meaningful
    sense -- this spec explains what KiCad's real engine found, it cannot compensate for what the
    project's own rule configuration was never asked to check.
*   **Real live-machine testing needs a real project with real violations to be meaningful** -- an
    already-clean board only proves the "no violations" path, not the explain-and-suggest path
    itself. Real personal board files exist on this development machine (confirmed real ERC/DRC
    output during spec research) and should be the actual verification fixture, not a fabricated
    one.

## 4. Module Map & Reference Links
```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-309-board-advisor.md)
                 └── [Context 309.1](../context/CTX-309.1-subfeature.md)
```
*   [SPEC-103](../../../services/python-daemon/specs/SPEC-103-kicad-ipc.md) -- the live IPC
    connection this spec's PCB-path auto-resolution reuses, and the spec whose own deferred-
    schematic-access decision this spec confirms still holds and works within, not around.
    §3 -- `freecad_bridge.py`'s real subprocess/binary-location pattern this spec's own `kicad-cli`
    integration follows.
*   [SPEC-107](../../../specs/SPEC-107-structured-logging-diagnostics.md) -- `daemon.get_capabilities`,
    the natural home for reporting whether `kicad-cli` was actually located.
*   [SPEC-110](../../../specs/SPEC-110-configurable-storage-root.md) -- the real native file-picker
    pattern this spec's schematic-path selection reuses.
*   [SPEC-204](../../../services/python-daemon/specs/SPEC-204-agent-tool-registry.md) -- this spec's
    own explicit non-goal (no confirmation gate needed) is a direct consequence of `SPEC-204`'s
    confirmation-gating policy only applying to routes that mutate something; this spec never does.
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §6 (M4), §8 item 1 -- the real, already-resolved
    `kicad-cli` presence question this spec's own research settles with a real, live-verified answer.

## 5. User & Interaction
*   **Product Stage:** After a schematic and/or board exist for a project (post-M3) -- the point
    where "does this actually work" becomes a real question worth asking, not before there's
    anything to check.
*   **What the user is trying to accomplish:** understand why KiCad's own ERC/DRC is complaining,
    in plain language, and get a real, concrete suggestion for what to do about each violation --
    without needing to already know what "four_way_junction" or "invalid_outline" means.
*   **What the user sees and does:** a "Check Board" (or "Check Schematic") action somewhere in the
    project shell; a real violation list, each with KiCad's own real description plus a plain-
    language explanation and suggested fix; a schematic check additionally needs the user to pick
    the `.kicad_sch` file first (no live auto-resolution possible, per §2's own confirmed finding).
    Exact layout/interaction details are this spec's own implementation context's job to fill in
    against the real shell `SPEC-305` already built, not invented here.
