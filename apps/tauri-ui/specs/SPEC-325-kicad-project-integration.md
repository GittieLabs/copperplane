---
id: SPEC-325
title: "KiCad Project Integration & Schematic Component Table"
status: In-Progress
type: Feature
created: 2026-09-01
last_updated: 2026-09-01
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-325-kicad-project-integration.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-325: KiCad Project Integration & Schematic Component Table

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let a user point the app at their `.kicad_pro` and, from that alone, see
    every component in their schematic — reference, value, footprint, datasheet, 3D model status —
    without KiCad running. This is the read half of the product, and it is the foundation every
    later stage stands on.

*   **Business / Technical Value:** Today the app can *observe nothing about a design*. It advises
    on parts the user searched for, and has no idea what is actually in their schematic. Every
    insight ends in "now go do that in KiCad yourself," and the maintainer named the cost directly:

    > "I'm beginning to question if we are creating a reference tool for experienced pcb designers
    > over a co-pilot for hobbyist."

    That framing is right, and the diagnosis underneath it is that **the app can observe but not
    participate**. This spec fixes the observing half, which turns out to be most of the value and
    none of the risk.

*   **The capability was there the whole time.** `kicad-cli sch export bom` and
    `kicad-cli sch export netlist` read a **closed** `.kicad_sch` — no GUI, no IPC, no running
    KiCad. Verified 2026-09-01 against a real project (`Hello_World_Blinky`):

    ```
    "BT1","Battery_Cell","Battery:Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles"
    "D1","LED","LED_THT:LED_D1.8mm_W3.3mm_H2.4mm"
    "R1","1K","Resistor_THT:R_Axial_DIN0309_L9.0mm_D3.2mm_P2.54mm_Vertical"
    ```

    The netlist gives real connectivity — `(net (name "+9V"))` with
    `(node (ref "BT1") (pin "1") (pinfunction "+_1") (pintype "passive"))`. The app has simply
    never asked.

*   **A concrete gap this exposes immediately.** That same real project assigns
    `Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles`, whose footprint references
    `Battery_Panasonic_CR2032-HFN_Horizontal.step` — **a file that does not exist**. KiCad's own
    `Battery` library ships **53 footprints and 29 STEP models: 25 dangling references, and zero
    `.wrl` fallbacks**. So a user's enclosure cannot be sized for their own battery, and nothing in
    the current pipeline is at fault — it correctly reports "unknown" and stops. Surfacing *which*
    components have no model is this spec's job; doing something about it is `SPEC-326`'s.

*   **Non-Goals:**
    *   **Not writing to any KiCad file.** Not the schematic, not the PCB, not the project. This
        spec reads. Assisted authoring is `SPEC-329` and is deliberately last.
    *   **Not rendering the schematic.** KiCad already draws it, better, and is usually open. This
        is a *table*, not a canvas.
    *   **Not replacing the live IPC path.** `SPEC-103`'s `kicad_bridge` stays for anything that
        genuinely needs the running editor. This adds a file-based path alongside it (§2.2).
    *   **Not design advice.** Layout warnings, spacing, THT/SMD mixing — `SPEC-327`.
    *   **Not component volumes or placeholders.** `SPEC-326`.
    *   **Not project intent or parts-list generation.** `SPEC-328`.

## 2. System Architecture & Design Choices

### 2.1 The project file becomes the anchor, replacing "whatever is open"

**Decided: a project links to a `.kicad_pro`, and the schematic and PCB are resolved from it.**

Today the app operates on whatever board KiCad happens to have open, which requires KiCad running,
its IPC API enabled, and the right document focused. Three preconditions, each a silent failure
mode, for a fact that is sitting in a file.

A `.kicad_pro` is JSON, and its siblings share its basename — verified on a real project:
`Hello_World_Blinky.kicad_pro`, `.kicad_sch`, `.kicad_pcb`. The project file also carries a
`sheets` list for multi-sheet designs.

`SPEC-312` already has "Link to folder…"; this narrows it to a *KiCad project*, which is a stronger
and more useful claim. The existing folder link stays for projects that have no KiCad files yet.

### 2.2 Read through `kicad-cli`, not the IPC API

**Decided: schematic reading is `kicad-cli` on files. The IPC path is not extended to cover it.**

Checked directly against the installed versions rather than assumed:

| surface | schematic access | needs KiCad running |
| :--- | :--- | :--- |
| `kicad-cli` 10.0.3 | `sch export bom`, `sch export netlist` | **no** |
| `kipy` 0.7.1 (pinned) | `KiCad` client has **no `get_schematic`** | yes |

`kipy` ships a `schematic` module, but importing it against KiCad 10.0.3 raises
`ImportError: cannot import name 'BusEntryType'` — the binding is behind the installed KiCad. So
schematic access over IPC is not merely unbuilt, it is currently broken, and building on it would
mean owning that version skew.

`kicad-cli` is also the only surface that works with KiCad closed, which is the common case for
someone opening this app to ask a question.

### 2.3 Components are read, never cached as truth

**Decided: the table is derived on demand from the file, with the file's mtime as the freshness
signal.** A stored copy of a schematic's contents is a second source of truth that goes stale the
moment the user edits in KiCad — and they will, because KiCad is open next to this app. The
existing `library/` remains the app's own store; a schematic's contents are not part of it.

### 2.4 What the table shows, and what it admits it does not know

Per component: reference, value, footprint, whether that footprint resolves in the user's installed
libraries, whether it has a 3D model **and whether that model's file actually exists**, and a
datasheet link when the app knows one.

The last two matter and are the point of §1's finding: a footprint can name a model that is not
there. Reporting "has a model" from the footprint's own `(model ...)` line would be wrong for 25 of
53 entries in KiCad's own battery library. **The check is the file, not the reference.**

Where the app cannot resolve something — an unknown footprint, no datasheet — it says so. Nothing
is inferred.

### 2.5 Matching schematic components to the app's own library

**Decided: matched by footprint identity first, then part number, and a match is displayed, never
written.** The maintainer named the real case: a project's library may hold parts that are not in
the schematic, and the schematic holds parts the app has never seen. Both are normal. The table
shows what the app knows about each schematic component, and the library view continues to show
everything saved — they are different questions and neither is a subset of the other.

### 2.6 Cross-Module Impacts

*   `services/python-daemon` — a new `kicad_project` module (resolve a `.kicad_pro` to its
    schematic and PCB), `kicad-cli` BOM/netlist parsing, footprint and 3D-model resolution reusing
    `kicad_bridge`'s existing `_resolve_3d_model_path`, and new routes.
*   `apps/tauri-ui` — project linking narrowed to a `.kicad_pro`; the Schematic tab becomes a real
    component table.
*   `SPEC-312` — its folder link is extended, not replaced.
*   `SPEC-103` — unchanged; the IPC path keeps its current scope (§2.2).
*   `SPEC-311` — gains a real answer to "which components have no usable model", which is what
    `SPEC-326` needs.

## 3. Known Constraints & Risks

*   **`kicad-cli` is a subprocess per call, and this runs on user action.** Every route here must
    be `ASYNC_ROUTES`-registered, and must not sit in `_detect_capabilities` — `SPEC-107` §3
    requires that probe to stay cheap and non-blocking, and `CTX-107.2` records what happens when a
    `freecadcmd` call is added to it.
*   **A schematic open in KiCad may have unsaved changes.** The file is what this reads, so the
    table can lag the editor. It must say what it read and when, not imply live sync.
*   **Version skew is a live risk, not a theoretical one.** `kipy` 0.7.1 is already broken against
    KiCad 10.0.3. `kicad-cli`'s output format is a CLI contract that can change between KiCad
    majors; a parser must fail loudly on an unrecognised shape rather than silently return an empty
    component list, which would read as "your schematic is empty".
*   **Multi-sheet schematics.** The `.kicad_pro` `sheets` list exists; `sch export bom` on the root
    sheet is expected to cover the hierarchy, but that is **unverified** against a real multi-sheet
    project and must be before this ships.
*   **A locked project.** The real project inspected carried `~*.lck` files from a running KiCad.
    Reading must be unaffected by them, and must never remove one.

## 4. Module Map & Reference Links

*   `services/python-daemon/kicad_bridge.py` — `_resolve_3d_model_path`, `list_footprint_models`
*   `services/python-daemon/kicad_cli.py` — the existing `kicad-cli` invocation pattern
*   `services/python-daemon/library_store.py` — the app's own part store, for §2.5 matching
*   `apps/tauri-ui/src/components/App.tsx` — the project header and Schematic tab slot
*   [SPEC-312](SPEC-312-application-shell-project-portability-persistence.md) — the folder link this narrows
*   [SPEC-103](../../../services/python-daemon/specs/SPEC-103-kicad-ipc.md) — the IPC path this does not extend
*   [SPEC-311](SPEC-311-enclosure-refinement-interactive-preview.md) — the consumer of "which components lack a model"
*   [SPEC-306](SPEC-306-component-discovery.md) / [SPEC-308](SPEC-308-footprints-schematic-advisor.md) — search and footprints, which this gives a real target

## 5. User & Interaction

*   **Product Stage:** Design review. After a user has a schematic — theirs or one they are
    learning from — and before or during layout.
*   **What the user is trying to accomplish:** Understand what is actually in their design and what
    is missing from it, without leaving the app or reading KiCad's own dialogs. Concretely: which
    parts have no footprint, which footprints have no usable 3D model, and which parts they have no
    datasheet for.
*   **What the user sees and does:** They pick their `.kicad_pro` once. The Schematic tab becomes a
    table — one row per component, with reference, value, footprint, datasheet, and a plain marker
    where something is missing or unresolvable. Selecting a row opens the existing part detail view
    to ask questions about that component. The schematic itself stays in KiCad.
