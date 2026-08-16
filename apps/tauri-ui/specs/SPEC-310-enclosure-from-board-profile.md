---
id: SPEC-310
title: "Enclosure from Board Profile"
status: Draft
type: Feature
created: 2026-08-16
last_updated: 2026-08-16
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-310-enclosure-from-board-profile.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-310: Enclosure from Board Profile

## 1. Executive Summary & Goals
*   **High-Level Goal:** Generate a real parametric enclosure from a `.kicad_pcb` **file**, with no
    live KiCad connection required -- `PRODUCT-PLAN.md` §6 M5, deliberately last: "low stakes, high
    usefulness," and only viable now that M3/M4 have proven the rest of the product model out.
*   **Business / Technical Value:** `SPEC-109`'s board-driven enclosure mode is real and already
    shipped, but it only ever reads whatever board KiCad currently has open, live, over IPC
    (confirmed directly -- see §2). A user who wants an enclosure for a board they aren't actively
    editing right now -- someone else's design, an old project, a board on a different machine's
    KiCad session -- has no path to one. This spec closes exactly that gap: point at a real
    `.kicad_pcb` file, get a real enclosure, KiCad doesn't need to be running at all.
*   **Non-Goals:**
    *   **Not a new FreeCAD geometry pipeline.** `freecad_bridge.generate_enclosure`
        (`services/python-daemon/freecad_bridge.py:193`) is already source-agnostic -- it consumes a
        plain `board_outline` dict and a `standoffs` list with no knowledge of where they came from.
        This spec's only real job is producing those same two things from a file instead of a live
        connection; the geometry generator itself is reused entirely unchanged.
    *   **Not a `.kicad_sch`-equivalent for schematics.** Enclosures are board-only by definition.
    *   **Not schematic/board editing.** Read-only import, matching `SPEC-309`'s own read-only
        advisor precedent -- this spec never writes to the imported file.

## 2. System Architecture & Design Choices
*   **A real, direct verification ruled out the obvious approach first.** `kiutils` (PyPI, the most
    current real third-party pure-Python KiCad-file-parsing library, version 1.4.8 -- the latest
    available) was installed and run against two real personal `.kicad_pcb` files during this
    spec's own research. It parsed a simple board fine, but **crashed with a real `IndexError`**
    (`kiutils/items/common.py`, `Net.from_sexpr`) on a second, more typical real KiCad 10 board --
    a genuine version-compatibility gap in that library, not something this project can fix.
    Hand-parsing the raw `.kicad_pcb` S-expression format directly was the fallback considered next,
    but rejected for the same reason `SPEC-308` §2 already gave for `.kicad_mod` parsing: real board
    outlines can include arcs and polygons, and correct arc/polygon bounding-box math is real,
    error-prone geometry work, not a quick parse.
*   **Resolved instead by reusing KiCad's own real export tools -- the same `kicad-cli` subprocess
    pattern `CTX-309.1` already established, extended to a new pair of real subcommands, both
    confirmed by actually running them against real board files, not assumed from `--help` text:**
    *   `kicad-cli pcb export dxf --layers Edge.Cuts --mode-single`: a real DXF containing the
        board's real outline geometry (confirmed: `LINE` entities with `10/20`/`11/21` start/end
        group codes on a real rectangular board; `CIRCLE` entities also appear on `Edge.Cuts` for
        board-edge round cutouts on a more complex real board -- harmless for a bounding-box
        computation, since a hole strictly inside a board can never expand its true bbox beyond
        what the outline's own boundary entities already establish).
    *   `kicad-cli pcb export drill --format excellon`: a real Excellon drill file, confirmed
        against the same real boards -- tool definitions (`T<N>C<diameter_mm>`) each preceded by a
        real `; #@! TA.AperFunction,{Plated,PTH|NonPlated,NPTH},...` comment classifying the hole
        type, followed by real `X..Y..` coordinate lines per tool. This is KiCad's own real,
        unambiguous PTH/NPTH classification -- exactly the same distinction
        `kicad_bridge.get_mounting_holes` already uses live (`pad.pad_type != PT_NPTH`), here read
        directly from the file KiCad itself wrote, guaranteed version-matched since the same real
        KiCad install produces both the board file and its own export.
    *   Since both are real KiCad exports (not a third-party parser guessing at the format),
        there's no version-compatibility risk analogous to `kiutils`'s -- whatever `kicad-cli`
        version wrote the `.kicad_pcb` also generates its own DXF/drill export.
*   **A real, honest difference from the live path, not silently glossed over:** live
    `get_mounting_holes` additionally checks whether a hole's footprint comes from KiCad's own
    `MountingHole` library or matches the `H<digits>` reference-designator convention, setting a
    `recognized` flag `SPEC-109`'s own UI uses to distinguish likely-standoff holes from other NPTH
    drilling. A drill file has no footprint-library or reference-designator information at all --
    only geometry and PTH/NPTH classification. This spec's file-based extraction can therefore only
    ever produce the coarser NPTH/PTH signal, not the finer `recognized` one; every NPTH hole from a
    file import is treated as a real mounting-hole candidate, full stop, since NPTH-ness alone is
    already a strong real signal in practice (through-hole component pads are PTH, not NPTH, in the
    overwhelming majority of real designs).
*   **Data Flow / Interactions:** a real `.kicad_pcb` file path (user-picked, no live-open-board
    auto-resolution possible or attempted -- there is no live connection in this path at all) →
    `kicad-cli pcb export dxf`/`pcb export drill` as two real subprocess calls → each real export
    parsed (a small, purpose-built DXF entity parser for `LINE`/`CIRCLE`/`ARC`/`LWPOLYLINE`, and a
    line-based Excellon parser) → the exact same `{x_mm, y_mm, width_mm, height_mm}` /
    `[{x_mm, y_mm, diameter_mm, recognized}]` shapes `kicad_bridge`'s live functions already
    produce → `freecad_bridge.generate_enclosure`, completely unchanged.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new module for file-based outline/hole extraction (mirrors
        `kicad_cli.py`'s own real subprocess-plus-parse shape); a new `freecad.generate_enclosure`
        mode (file-path-driven, alongside the existing manual and live-board modes) in `daemon.py`.
    *   `apps/tauri-ui`: a new "Import board file" option in the Enclosure area's existing
        board-driven-mode UI, using a real native file picker (mirrors `boardAdvisor.ts`'s own
        `.kicad_sch` picker pattern, filtered to `.kicad_pcb` instead) -- available even when
        `kicad_available` is `false`, since this path needs no live connection at all, unlike the
        existing board-driven mode which currently requires one.

## 3. Known Constraints & Risks
*   **DXF entity coverage is real but not exhaustive.** `LINE` and `CIRCLE` entities were both
    confirmed against real board files this session; `ARC` and `LWPOLYLINE` (real, common shapes for
    rounded-corner or non-rectangular boards) were not exercised against any real fixture -- neither
    personal board used this session happens to have one. The implementation context must still
    handle them (a board with rounded corners is a completely normal real design), but that handling
    will necessarily be verified against a hand-constructed or conservative-approximation basis, not
    a real board that happens to have arcs, unless one becomes available.
*   **The `recognized` gap (see §2) means a file-imported board's mounting-hole detection is
    strictly coarser than the live path's.** A board with real NPTH holes that aren't actually
    intended as mounting standoffs (rare, but real designs exist) would be over-included via file
    import in a way live IPC's `recognized` flag would have excluded. Named explicitly as a real,
    accepted tradeoff for this slice, not hidden.
*   **No live KiCad connection also means no live version-compatibility check.** `kicad_bridge`'s
    live path benefits from `FutureVersionError`'s already-tolerant handling (`CTX-103.1`); running
    `kicad-cli` against a `.kicad_pcb` written by a KiCad version meaningfully newer or older than
    the installed `kicad-cli` binary is a real, unexamined risk this spec doesn't resolve --
    `kicad-cli`'s own real behavior in that case is this implementation context's job to observe,
    not assume.

## 4. Module Map & Reference Links
```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-310-enclosure-from-board-profile.md)
                 └── [Context 310.1](../../../services/python-daemon/context/CTX-310.1-subfeature.md)
```
*   [SPEC-104](../../../services/python-daemon/specs/SPEC-104-freecad-headless.md) -- the headless
    FreeCAD subprocess bridge this spec's own file-based extraction is architecturally modeled on
    (real subprocess, not a live/in-process dependency).
*   [SPEC-109](../../../services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md) --
    `generate_enclosure`'s own real, already-shipped, source-agnostic geometry pipeline this spec
    reuses completely unchanged; its own spec text (`SPEC-109 §2`) explicitly scoped live-IPC-only
    board reads as deliberate, not an oversight this spec is fixing so much as extending.
*   [SPEC-309](SPEC-309-board-advisor.md) -- `kicad_cli.py`'s real subprocess-location pattern this
    spec's own new module reuses directly; `CTX-309.2`'s `pickSchematicFile` is the direct UI
    precedent for this spec's own `.kicad_pcb` file picker.
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §5.1, §6 (M5) -- the real, already-decided scope.

## 5. User & Interaction
*   **Product Stage:** The Enclosure area, after a project exists -- extends `SPEC-109`'s own
    already-shipped board-driven mode rather than introducing a new area or stage.
*   **What the user is trying to accomplish:** get a real, board-shaped enclosure for a
    `.kicad_pcb` file they have, without needing KiCad open and connected right now.
*   **What the user sees and does:** in the Enclosure area's existing board-driven option, a new
    "Import board file…" action alongside (not replacing) the existing live-board mode; picking a
    real `.kicad_pcb` file generates the enclosure the same way the live path already does --
    the enclosure result, viewer, and STEP export are all `SPEC-109`'s own existing, unchanged UI.
