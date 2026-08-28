---
id: SPEC-311
title: "Enclosure Refinement & Interactive Preview"
status: Completed
type: Feature
created: 2026-08-18
last_updated: 2026-08-24
target_version: v0.2.0
location: "apps/tauri-ui/specs/SPEC-311-enclosure-refinement-interactive-preview.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-311: Enclosure Refinement & Interactive Preview

## 1. Executive Summary & Goals

*   **High-Level Goal:** Turn enclosure generation from a one-shot, blind form submission into a
    real iterative workflow: derive the enclosure's shape and required interior height directly
    from the real board (its real outline and its real placed components' heights, not sane
    defaults), generate, show an interactive 3D preview the user can actually navigate, let them
    adjust parameters and regenerate against the same board without starting over, and decide
    whether/how a lid gets built and shown alongside the base.
*   **Business / Technical Value:** `SPEC-109`/`SPEC-310` (both shipped, `CTX-310.3` just fixed
    their picker UX) produce a fixed-shape open-top box from a *bounding box* with hard-coded
    default wall/clearance/fillet/standoff numbers — real, deliberate scope decisions at the time
    (`SPEC-109` §1's own Non-Goals), but real use of the shipped feature (`CTX-310.3`'s own Plan
    Drift, Deviation 3) confirmed they now block real usefulness: no lid, no shape beyond a
    rectangle, and no way to know if the numbers you typed are even close to right for the
    components actually on the board. This spec is the next real increment, not a rewrite of what
    shipped.
*   **Non-Goals:**
    *   **Not a general-purpose parametric CAD editor.** Refine means adjusting this spec's own
        named parameters (wall thickness, clearance, fillet, standoff height, lid on/off) and
        regenerating — not free-form geometry editing, custom cutouts, or connector/cable routing.
    *   **Not fastener hardware selection.** Unchanged from `SPEC-109`'s own Non-Goal — a lid
        existing at all is new scope here; screws, latches, and hinges are not.
    *   **Not a repo-wide shell/layout redesign.** The real "every tab is a fixed, narrow column"
        observation applies to the whole app, not just Enclosure — this spec widens the Enclosure
        area specifically (it has the clearest case: a 3D viewer genuinely needs the room), and
        names the broader layout question as a real, separate follow-up rather than silently
        expanding this spec to redesign `App.tsx`'s shell.
    *   **Not solving component-height data for every part unconditionally.** See §2's own named
        open question — this spec uses real height data where it already exists and degrades
        honestly (not silently) where it doesn't; backfilling every existing Part's height data is
        out of scope.

## 2. System Architecture & Design Choices

*   **Component height is derivable from KiCad's own real 3D models — confirmed live, end to end,
    not assumed.** Every real `FootprintInstance` exposes `.definition.models` (kipy's
    `Footprint.models`, a real property since kipy 0.3.0), each a real `Footprint3DModel` with a
    `filename` plus its own `scale`/`rotation`/`offset` transform. Verified against this dev
    machine's real board: a `PinHeader_1x04` footprint's real model resolved to
    `${KICAD10_3DMODEL_DIR}/Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x04_P2.54mm_Vertical.step`,
    a real file confirmed to exist on disk (KiCad's own bundled-library path,
    `<KiCad install>/SharedSupport/3dmodels` on macOS — the same per-OS-install-path pattern
    `find_freecadcmd`/`find_kicad_cli` already use elsewhere in this codebase), and `freecadcmd`
    loaded that exact real STEP file and computed a real bounding box (2.54 × 10.16 × **11.54mm**
    — the Z dimension is the real component height) directly, with no invented data. This is a
    **better, more universal** height source than `Part.package_dimensions.height_mm`
    (`CTX-308.5`) — it works for *any* board with real KiCad footprints, including one never
    touched by this app's own Part library, not only components this app itself placed.
    **Real, not-yet-solved work this still requires:** resolving KiCad's own env-var path
    convention robustly (varies by KiCad version/OS — `KICAD10_3DMODEL_DIR` today, will drift with
    future major versions the same way `find_kicad_cli`'s own version-numbered paths already
    do); applying each model's own real `scale`/`rotation`/`offset` transform before computing its
    bounding box (a raw, untransformed bounding box would be wrong for a rotated or scaled model);
    and handling models that don't exist as `.step` (some libraries ship `.wrl`/VRML instead --
    `trimesh`, already a dependency for `.glb` export, reads that format, so a per-format branch is
    real but not yet written). **Confirmed gap, not solved by this either:** some real footprints
    have zero attached models at all (4 of 9 on the same test board) -- height for those components
    genuinely can't be derived from anything in the pipeline today. The user's own proposed
    fallback -- report which components' heights are known versus unknown, and ask for an overall
    height (including the lid) when coverage is incomplete -- is the right posture for this real
    gap, not something to paper over with a guessed default.
*   **`kicad-cli pcb export glb` gives a simpler, more robust path to both real height *and* a real
    visual fit check — confirmed live, superseding part of the per-footprint approach above.**
    `kicad-cli` (already this pipeline's own tool, used for `sch erc`/`pcb drc`/DXF/drill export)
    has a real `pcb export glb` subcommand: one subprocess call against the real `.kicad_pcb` file
    exports the *entire assembled board* — substrate plus every real component's real 3D model,
    already correctly positioned and transformed by KiCad itself — as one real `.glb`. Verified
    live against the real, currently-open board: a real 634KB file, 1159 real meshes, a real
    bounding box of **49.50 × 11.54 × 106.50mm** — the same 11.54mm tallest-component height the
    per-footprint approach above found independently, this time for the *whole populated board* in
    one call, with no manual per-footprint model resolution, path resolution, or transform math
    needed. This directly enables the user's own follow-up idea: load this real board `.glb`
    *inside* the generated enclosure's own `.glb` in one scene — a real, visual "does this fit"
    check (does the board clear the walls in X/Y, does its tallest point clear the lid in Z) instead
    of trusting a number. The per-footprint `.definition.models` check above is still the right,
    complementary mechanism for the honesty requirement: `kicad-cli`'s own export silently omits any
    component with no 3D model, so its bounding box could *understate* the real required clearance
    if the tallest real component happens to be one with no model — the per-footprint check is what
    catches that and surfaces it, not the whole-board export alone. **Decided posture for the visual
    preview specifically (distinct from the height-derivation fallback above):** a component with no
    attached 3D model is simply absent from the rendered board — `kicad-cli`'s own export already
    skips it, and this spec does not attempt to synthesize a placeholder box or guess its shape. The
    UI states this plainly (naming the affected reference designators where known) and directs the
    user to add or fix that footprint's 3D model assignment in KiCad and regenerate — never a silent
    gap and never an invented stand-in shape.
*   **Real, confirmed, independent bug found while investigating the above: the enclosure's own
    `.glb` output is scaled 1000x too large relative to the real-meter convention `kicad-cli`'s own
    export correctly uses.** `freecad_bridge.py`'s build script sets `box.Height = {height}` etc.
    directly in millimeters with no unit conversion before `exportStl()`; `trimesh` then converts
    that unitless STL to `.glb` with no scale correction either, so a real 20mm-tall box's `.glb`
    reports a bounding box of 20 *meters*, not 20mm. Purely cosmetic on its own — `EnclosureViewer`'s
    camera was evidently tuned empirically around this same wrong scale, so today's single-model
    viewer still looks right — but a real, hard blocker for compositing the enclosure with any
    correctly-scaled model (like `kicad-cli`'s own board export) in the same scene, and worth fixing
    on its own merits regardless of whether the board-overlay feature ships (`.step` export, the
    format this spec's own "real mechanical CAD" value proposition depends on, is presumably
    correctly scaled already since STEP embeds real units — only the derived `.glb`/viewer path is
    suspected to carry this bug; confirm before assuming symmetric).
*   **The real board outline is available as raw geometry today; only the reduction step throws
    it away.** `kicad_bridge.get_board_outline()` already reads every real `BoardShape` on
    `Edge.Cuts` via a real `kipy` call before reducing them to a bounding box; the file-based path
    (`kicad_pcb_import.extract_board_outline`) does the equivalent via a DXF export. Tracing the
    real closed outline (rather than its bounding box) means assembling those raw line/arc segments
    into a closed polygon/wire and extruding *that* in FreeCAD instead of `Part.makeBox` — real,
    non-trivial geometry work (segment-chaining, concave-corner handling for the inward wall-
    thickness offset), not a parameter tweak. Confirmed accessible; not confirmed easy.
*   **A lid means two real FreeCAD bodies, not one.** The existing build script produces a single
    `Part::Feature` shape exported to one `.glb`/`.step`. A lid needs its own real shape (sized to
    fit the same outline, closing the open top the base already has) either as a second object in
    the same document/export or a fully separate `.step`/`.glb` pair. `EnclosureViewer.tsx`
    (confirmed by reading it) currently loads exactly one `.glb` into one `THREE.Group` via
    `useGlbScene` — showing/hiding a lid independently needs either two named, independently-
    toggleable nodes in one scene graph, or two separately-loaded scenes composited in the same
    `Canvas`. Real, bounded frontend work; not yet decided which of the two.
*   **Persistence of the generated design is a genuinely open product question, not a technical
    one — named honestly, not resolved here.** Every regenerate-after-refine produces a new real
    `.glb`/`.step` pair; without a decision, old ones either leak (SPEC-301 §3's already-named risk)
    or get silently overwritten. Three real options exist (auto-save every generation as the
    project's current enclosure Artifact; only persist on an explicit user "Save" action, discarding
    interim iterations; keep every version, `SPEC-304`-style) — each has real, different trade-offs
    for disk usage and "did I lose my last good design" risk. This spec's own implementation
    context must pick one and say why, not default to whichever is easiest to code.
*   **The Enclosure tab must match the PCB/Schematic tabs' own "last-open-board" pattern, with one
    deliberate difference.** `BoardAdvisor`/`SchematicAdvisor` show their last-scanned board list
    immediately on load; `EnclosurePanel` (post-`CTX-310.3`) currently only shows a board once the
    user has explicitly scanned or picked a file this session. This spec makes Enclosure consistent
    with that pattern for the *list* — but generation itself still requires an explicit "Generate"
    click even when a board was auto-selected from a remembered previous session, since the
    underlying file could have moved or been deleted since the app was last open; a real,
    successful generate is the actual validation that the remembered path is still real, not an
    assumption.
*   **Mounting-hole detection already exists and is more solid than first assumed — confirmed by
    reading `kicad_bridge.get_mounting_holes()` directly, not assumed missing.** It already reads
    every real footprint's real NPTH pads (position + real drill diameter, not a guess), and
    already tags each as `recognized` (KiCad's own `MountingHole` library, or the `H<digits>`
    reference convention) or not -- both position, diameter, and a recognized/unrecognized split
    already ship today (`SPEC-109`). **The real, confirmed gap is narrower than "mounting holes are
    overlooked":** the existing UI only warns about *unrecognized* holes (`result.unrecognized_
    holes.length > 0`); a board with **zero** holes of any kind -- recognized or not -- triggers no
    warning at all today, silently producing a standoff-free enclosure with no way for the user to
    tell "this board really has no mounting holes" apart from "the detection missed them." This
    spec's own context should add that explicit, honest "no mounting holes found on this board" flag
    when generating, distinct from the existing unrecognized-holes warning.
*   **Camera presets are a real, bounded addition to the existing `OrbitControls` setup.** Top,
    bottom, and left/right rotation-by-increment buttons around the existing free-orbit behavior
    (`CTX-301.2`), not a replacement for it — `@react-three/drei`'s `OrbitControls` already exposes
    a controllable camera object; presets just animate/snap it to known positions.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: `kicad_cli.py` gains a real `export_board_glb`-style wrapper
        (mirroring its own existing `run_drc`/`run_erc` subprocess pattern) around `kicad-cli pcb
        export glb`; `kicad_bridge`/`kicad_pcb_import` gain the per-footprint "does this component
        have a real 3D model" check (for the honesty flag, decoupled from height derivation now
        that the whole-board export owns that); `freecad_bridge`'s build script gains a real second
        (lid) body, a real `.glb` unit-scale fix (§2/§3), and, if pursued, real polygon-outline
        extrusion instead of `Part.makeBox`; `daemon.py`'s route gains whatever persistence model is
        chosen.
    *   `apps/tauri-ui`: `EnclosurePanel.tsx` gains a refine-and-regenerate loop against the same
        selected board, the last-open-board list-on-load pattern, and a wider layout;
        `EnclosureViewer.tsx` gains lid show/hide, camera presets, and loading a second (real board)
        `.glb` composited into the same scene as the enclosure.

## 3. Known Constraints & Risks

*   **A "safe" default clearance height above the tallest known component is still a real product
    risk, not just a UX nicety.** If component-height data is missing or only partially known for a
    board (see §2), whatever this spec's context ships must make that gap visible to the user
    rather than silently sizing the enclosure only for what it happened to know about — a
    confidently-wrong enclosure that doesn't clear a real component is worse than an honest "I
    don't know, please confirm" prompt.
*   **`freecadcmd` cold-boot + real geometry cost compounds with every refine-and-regenerate
    click.** `SPEC-109` §3 already flagged this for one shape; a real iterative workflow means this
    cost is paid repeatedly per session, not once — worth watching for whether the existing async
    job path (`SPEC-105`) still feels responsive enough for a "tweak a number, see the result"
    loop, or whether a real debounce/explicit-regenerate-only (not live-as-you-type) posture is
    needed.
*   **Polygon-outline extrusion is real, unproven OpenCASCADE work in this repo.** Every enclosure
    shape shipped so far has been `Part.makeBox`; there is no precedent here yet for extruding an
    arbitrary closed wire or offsetting it inward at a concave corner. Should be prototyped for
    real against `freecadcmd` before being assumed feasible on the timeline this spec's context
    picks, the same "prototype the real tool before wiring it in" norm `CTX-109.1`'s own Plan Drift
    already used for edge-selection logic.

## 4. Module Map & Reference Links

```text
[SPEC-300](SPEC-300-product-ia-interaction-model.md)
   └── [This Spec](SPEC-311-enclosure-refinement-interactive-preview.md)
          ├── (context files land under apps/tauri-ui/context/ and services/python-daemon/context/
          │    once implementation begins)
```

*   [SPEC-109](../../../services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md) —
    the original enclosure geometry this spec refines, not replaces.
*   [SPEC-310](SPEC-310-enclosure-from-board-profile.md) — the board-driven/file-import modes this
    spec's refine loop builds on.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) —
    owns `package_dimensions.height_mm`, the real data source §2 names for component height.
*   `ROADMAP.md` §3.1's `SPEC-111` backlog entry — the earlier, narrower capture of the lid/outline
    gap; superseded in scope by this spec once this spec exists (leave `SPEC-111` as historical
    record of when the gap was first named, per this repo's own "Plan Drift is not embarrassing"
    norm — don't delete it).

## 5. User & Interaction

*   **Product Stage:** Enclosure (the fifth and last stage in `SPEC-300`'s own stage machine),
    entered once a real board exists — either checked already on the PCB tab, or loaded fresh here.
*   **What the user is trying to accomplish:** Get a real, board-fitting enclosure — sized to
    actually clear the components on the board, with or without a lid — without hand-typing
    dimensions they'd have to guess, and without starting over from scratch every time they want to
    try a different wall thickness or see the lid on versus off.
*   **What the user sees and does:** Arriving at the Enclosure tab, they see the same board (or
    board list) they last had open, exactly like the PCB/Schematic tabs already show — picking one
    and clicking Generate produces a real enclosure sized from that board's own real outline and
    component heights, shown in a real, now-larger interactive 3D preview with camera presets
    (top/bottom/rotate) alongside free orbit, and a lid shown or hidden as its own toggle. Adjusting
    a refine parameter and regenerating updates the same preview against the same board, not a
    blank form. If some components' real heights couldn't be derived (no attached 3D model, or an
    unresolvable one), or the board has no mounting holes at all, the user sees that stated plainly
    before/alongside the result — never a confident-looking enclosure quietly built on an unstated
    gap. The preview can show the real, assembled board *inside* the generated enclosure (not just
    the empty shell) — a genuine visual fit check, letting the user actually see a component
    crowding a wall or a lid sitting too close to the tallest part, not just trust a number. A
    component missing its 3D model simply doesn't appear in that board-inside-enclosure view — the
    app never guesses its shape — and the user is told plainly to fix that footprint's 3D model
    assignment in KiCad and regenerate to see it reflected, rather than the app attempting to work
    around a gap it can't honestly fill.
