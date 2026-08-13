---
id: SPEC-109
title: "Parametric Enclosure Generator"
status: Draft
type: Feature
created: 2026-08-13
last_updated: 2026-08-13
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-109: Parametric Enclosure Generator

## 1. Executive Summary & Goals

*   **High-Level Goal:** Read a project's real board outline and mounting-hole positions from KiCad
    (via `kicad_bridge`'s existing live connection) and feed them into `freecad_bridge`'s existing
    subprocess pipeline to generate a hollow, walled enclosure that actually fits that board — walls
    at a configurable thickness and clearance, standoffs at each real mounting hole, corner fillets —
    exported as both the `.glb` `EnclosureViewer` already renders and a real `.step` file usable in
    other mechanical CAD tools. This is the first spec where `kicad_bridge` and `freecad_bridge`
    genuinely compose in one route, instead of being exercised independently the way `SPEC-103`/`104`
    and `SPEC-108` each left them.
*   **Business / Technical Value:** This is the feature `README.md` actually promises, and the point
    at which the product stops being two disconnected toys (a KiCad script runner and a FreeCAD box
    generator) and starts being one thing. It also closes a real, already-named gap: `SPEC-304`'s
    schema enforces `board_revision` on every enclosure `Artifact` (`ROADMAP.md` §3.3, the one gap
    the `SPEC-304` ID-collision resolution carried forward), but nothing today ever calls
    `save_artifact` for an enclosure at all — `freecad.generate_enclosure` returns a bare `.glb`
    path with no project or board tie-in. This spec makes that requirement real, not just enforced
    in the abstract.
*   **Non-Goals:**
    *   **Not a general-purpose enclosure CAD tool.** Fixed rectangular box geometry only — no
        custom wall shapes, no cable/connector cutouts, no ventilation patterns. Those are real,
        plausible follow-ups, not this spec.
    *   **Not multi-board or multi-cavity enclosures.** One board, one enclosure, matching
        `SPEC-304`'s one-`board_revision`-per-Artifact model.
    *   **Not fastener hardware selection.** Standoffs get a hole sized for a screw diameter
        parameter; choosing a specific screw, heat-set insert, or lid-latching mechanism is out of
        scope.
    *   **Not a live FreeCAD GUI editor.** `SPEC-104`'s subprocess-handoff execution strategy is
        unchanged — this spec extends what geometry the temp script builds, not how it's built or
        run.

## 2. System Architecture & Design Choices

*   **Board data extraction (new, `kicad_bridge`):** Two new read operations against the live board,
    both real `kipy` `GetItems` calls, not a KiCad file parse:
    *   **Outline:** `BoardShape` items on the `Edge.Cuts` layer, reduced to the closed polygon (or
        bounding box, if the shapes don't form one closed loop) that defines the board's physical
        edge.
    *   **Mounting holes:** non-plated through-hole pads matching a recognized mounting-hole
        convention (footprint library name or reference-designator prefix — the same kind of
        table-driven recognition `SPEC-108`'s `PACKAGE_REFERENCE` already uses for packages, not a
        one-off heuristic invented here).
    A board with no closed `Edge.Cuts` outline, or with ambiguous/unrecognized mounting-hole
    footprints, **fails closed** with a clear error — the same "fails closed on unrecognized input"
    posture `SPEC-202`'s package-safety checks already established, not a silent bounding-box guess
    presented as if it were the designed edge.
*   **Enclosure geometry (extends `freecad_bridge.generate_enclosure`):** The existing signature
    (`width`/`depth`/`height` → a solid `Part::Box`) is extended to accept a board outline (or a
    manually-entered bounding box, for a project with no live KiCad connection), wall thickness,
    board-to-wall clearance, per-hole standoff height/screw diameter, and a corner fillet radius. The
    generated script becomes a real boolean shell (outer box minus an inset inner box) plus standoff
    cylinders unioned in at each real hole position, still built inside `SPEC-104`'s unchanged
    subprocess-handoff pattern (temp script → `freecadcmd` → geometry → export → exit).
*   **Output & persistence:** The build now exports **both** `.glb` (unchanged, for
    `EnclosureViewer`) and `.step` (new — the real mechanical-CAD interchange format this spec's own
    value proposition depends on), written under the project's real `storage_root`-scoped artifacts
    directory (`SPEC-304`/`SPEC-110`), and registered as a real `Artifact` (`kind: "enclosure"`,
    `board_revision` set from the board data actually read) via `library_store.save_artifact` — for
    the first time closing that schema requirement with a real call, not just an enforced-but-unused
    validation rule.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: `kicad_bridge` gains the two new read operations;
        `freecad_bridge.generate_enclosure`'s signature and build-script template are extended, not
        replaced; `daemon.py`'s existing `freecad.generate_enclosure` async route (`SPEC-105`'s job
        pattern, already in place) gains the board-read step and the `save_artifact` call.
    *   `apps/tauri-ui`: the Enclosure tab's current three-field width/depth/height form
        (`App.tsx`'s `EnclosurePanel`) needs new inputs — likely a later child context, the same way
        `CTX-108.3` followed `CTX-108.1` for the KiCad write path's own UI trigger.

## 3. Known Constraints & Risks

*   **Coordinate-frame mismatch is a real, specific risk here, not a rounding footnote.**
    `kipy` reports board positions in KiCad's own internal coordinate system; the FreeCAD build
    script constructs geometry directly in mm. `CTX-108.1` already hit and fixed exactly this class
    of unit bug on the KiCad-write side of this same board-data boundary — it should be treated as a
    known, expected hazard here too, not rediscovered independently.
*   **`freecadcmd` cold-boot time gets worse, not better.** `SPEC-104` already flagged a 1-3 second
    cold boot for a single `Part::Box`. A real boolean shell cut plus fillets plus per-hole standoff
    unions is meaningfully more OpenCASCADE work; this must stay on `SPEC-105`'s existing async job
    path (already true for `generate_enclosure` today) rather than assuming the UI can treat it as
    synchronous.
*   **Mounting-hole recognition is a real judgment call, not just plumbing.** Not every
    non-plated through-hole on a board is a mounting hole (some are tooling or fiducial holes). An
    unrecognized or ambiguous board must fail with a clear, actionable error rather than silently
    guessing which holes to standoff — the cost of guessing wrong here is a physically unusable
    enclosure, not just a cosmetic mismatch.
*   **A board with no live KiCad connection still needs a path forward.** Not every enclosure
    generation happens with KiCad open and reachable. Falling back to `SPEC-104`'s original
    manually-entered width/depth/height (now as an explicit "no board data" mode, not the only mode)
    keeps the feature usable without a live connection — this must be a real, intentional fallback
    path, not an accidental one.

## 4. Module Map & Reference Links

*   [Root Architecture: SPEC-000](../../../specs/SPEC-000-architecture-overview.md)
*   [SPEC-104: FreeCAD Headless Bridge](SPEC-104-freecad-headless.md) — the subprocess-handoff
    execution strategy this spec extends, unchanged.
*   [SPEC-108: KiCad Write Path](SPEC-108-kicad-write-path-footprint-symbol-injection.md) — the
    sibling board-data boundary that already hit and fixed the same coordinate-frame hazard this
    spec must account for.
*   [SPEC-304: Project & Library Storage](../../../apps/tauri-ui/specs/SPEC-304-project-library-storage.md)
    — the `Artifact` schema (`board_revision` required on `kind: "enclosure"`) this spec is the
    first to actually satisfy with a real `save_artifact` call.
*   [SPEC-110: Configurable Storage Root](../../../specs/SPEC-110-configurable-storage-root.md) — the
    real storage location the generated `.glb`/`.step` files land under.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-109] Parametric Enclosure Generator
          └── [Context 109.1] (not yet written)
```

## 5. User & Interaction

*   **Product Stage:** The Enclosure area tab — the last stage in `SPEC-300`'s
    Discovery → Detail → Schematic → PCB → Enclosure flow, reached after a project's board layout is
    real (not a placeholder).
*   **What the user is trying to accomplish:** Get a 3D-printable (or CNC-able) enclosure that
    actually fits the board they've already laid out in KiCad, without manually measuring board
    dimensions and hole positions and re-typing them into a generic box generator.
*   **What the user sees and does:** In place of today's plain width/depth/height number fields, the
    Enclosure tab offers a "Generate from board" option that reads the project's real KiCad board
    outline and mounting holes automatically, alongside wall thickness / clearance / standoff /
    fillet fields with sensible defaults (and the original manual width/depth/height entry stays
    available as an explicit fallback when no board is connected). Clicking Generate produces a real
    preview in the existing `EnclosureViewer`, plus a `.step` file the user can open directly in
    FreeCAD, Fusion 360, or SolidWorks for further mechanical work.
