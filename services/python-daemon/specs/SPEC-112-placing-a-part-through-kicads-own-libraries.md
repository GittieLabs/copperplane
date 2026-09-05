---
id: SPEC-112
title: "Placing a Part Through KiCad's Own Libraries"
status: Draft
type: Feature
created: 2026-09-04
last_updated: 2026-09-04
target_version: v0.5.0
location: "services/python-daemon/specs/SPEC-112-placing-a-part-through-kicads-own-libraries.md"
parent_spec: "SPEC-108-kicad-write-path-footprint-symbol-injection.md"
child_specs: []
user_facing: true
---

# SPEC-112: Placing a Part Through KiCad's Own Libraries

## 1. Executive Summary & Goals

*   **High-Level Goal:** Write a generated symbol and footprint into a real KiCad library, so a
    person places the part from KiCad's own symbol chooser and it reaches the board through
    **Update PCB from Schematic** — with a reference designator, with its nets, and with the
    schematic knowing it exists.

*   **Why, concretely.** `SPEC-108`'s `kicad.inject_component` writes a footprint straight into the
    open `.kicad_pcb`. It works: an NE555 injected during live testing on 2026-09-04 reached the
    board correctly. What it produces is an orphan. Read back out of the real board file
    afterwards:

    | | |
    | :--- | :--- |
    | Reference | `REF**` — KiCad's unassigned placeholder |
    | Nets | none |
    | Schematic | unchanged; it has no idea the part exists |
    | DRC | one new warning: *the current configuration does not include the footprint library* |

    None of that is a bug in the write path. It is what writing to a board while bypassing the
    schematic means. KiCad's flow is schematic → netlist → board, and a footprint that skips it can
    never be reconciled by forward annotation.

*   **Why not fix injection instead.** There is nothing to fix it with. KiCad's IPC API has no
    schematic writing: `kicad-python` **0.8.0 is the newest published version**, its `schematic`
    module raises `ImportError` on import, and the client exposes `get_board()` with no
    `get_schematic()`. Confirmed directly against the installed package, not inferred from
    documentation. This is upstream work in KiCad, not ours.

*   **Why the library route works.** A `.kicad_sym` is a container of symbols and a `.pretty` is a
    directory of footprints. Both are plain files that KiCad reads through `sym-lib-table` and
    `fp-lib-table`. Nothing needs a running KiCad, an enabled IPC API, or a focused document.
    Verified on the maintainer's own machine: six registered symbol libraries, five of them custom
    (`MyComponentLibs`, `Button_Switches`, `KeySwitch`, `Adafruit`, `Adafruit-Feather-RP2040`), and
    a hand-written project-local `sym-lib-table` in `NFC_Reader_ESP32` pointing at a single-symbol
    library exported from this app. The workflow already exists; people are doing it by hand.

*   **Non-Goals:**
    *   **Not writing into a library the user already owns.** `MyComponentLibs.kicad_sym` is their
        file, KiCad may have it open, and a merge that goes wrong costs them every symbol in it.
    *   **Not schematic editing.** See above; the API does not exist. This makes a part *placeable*,
        it does not place it.
    *   **Not removing `SPEC-108`'s board write.** It has a real use for boards with no schematic.
        What changes is its name and its billing.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **One library or one file per part.** The app currently writes a whole `.kicad_sym` containing a
    single symbol, and the maintainer's `NFC_Reader_ESP32` table registers exactly that — one
    library per part, which does not scale past a handful. A single `Copperplane.kicad_sym`
    accumulating every generated symbol needs read-modify-write on a file KiCad may hold open, and
    an answer for what happens when the same part is generated twice.

*   **Global or project-local registration.** The maintainer uses both: five global entries and a
    project-local `sym-lib-table` beside one project. Project-local keeps a generated part with the
    project that needed it and survives being copied to another machine; global means registering
    once ever. This decides whether the feature needs `kicad_project_path` to be set.

*   **Whether to write `sym-lib-table` at all.** It is a file KiCad owns and rewrites. Editing it is
    how the part becomes available without the user doing anything; refusing to edit it means every
    part ends with a paragraph of instructions. There is no third option that is both automatic and
    hands-off.

*   **Whether a running KiCad notices.** Unknown, and it decides what the success message can
    promise. Appending a symbol to a registered library and having KiCad pick it up without a
    rescan or restart has not been tested. If it does not, the instruction has to say so, and
    "added to your library" becomes "added — reopen the symbol chooser".

*   **The footprint half.** A symbol alone lets someone place the part and leaves them assigning a
    footprint by hand, which is most of the work this app exists to remove. The `.kicad_mod` needs
    to land in a registered `.pretty` and the symbol's `Footprint` field needs to point at it.

*   **What `SPEC-108`'s button becomes.** "Inject into open board" describes a mechanism, and the
    mechanism is the part people should not usually want. Renaming it is not cosmetic — it decides
    whether the board write is the obvious action or the advanced one.

## 3. Known Constraints & Risks

*   **This writes outside the storage root, for the first time.** Every file this app has written so
    far lives under its own storage directory. A KiCad library lives wherever the user's projects
    live, and `sym-lib-table` lives in KiCad's config directory — on the maintainer's machine,
    `~/Library/Preferences/kicad/10.0/`, which is **KiCad 10**, while this project's docs and
    requirements say KiCad 9+. The version in that path is not decoration; it is part of where the
    file is.

*   **A corrupted library is worse than a missing feature.** `CTX-408.2` already records the
    judgement that hand-authoring KiCad s-expressions "produces a file that opens badly". Appending
    to a library is far more tractable than authoring a schematic, but the failure mode is a file
    the user cannot open, containing symbols this app did not create.

*   **KiCad may hold the file open.** The same class of problem as writing to a board: the app and
    KiCad both believe they own the file. Injection sidesteps it by going through the IPC API;
    file-level writing does not have that option.

*   **`REF**` and the missing-library warning are already in a real user's board.** Whatever this
    spec builds, the existing behaviour has produced at least one board carrying an orphan
    footprint. Anything that makes the old path less prominent should say what to do about parts
    already injected.

## 4. Module Map & Reference Links

*   `services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md` — the
    board write this reframes; parent.
*   `services/python-daemon/kicad_write.py` — `build_footprint_instance`, `generate_pad_layout`, and
    `_LIBRARY_NAME`, the nickname stamped onto every generated footprint.
*   `services/python-daemon/library_store.py` — `_build_kicad_sym_text` already emits a valid
    single-symbol `.kicad_sym`; `export_symbol`/`export_footprint` already write real files.
*   `apps/tauri-ui/src/components/PartDetail.tsx` — "Inject into open board", its confirmation, and
    the export buttons this would sit beside.
*   `apps/tauri-ui/specs/SPEC-325-kicad-project-integration.md` — owns `kicad_project_path`, which a
    project-local registration would depend on.
*   `services/python-daemon/context/CTX-202.5-symbol-width-and-honest-advice.md` — the live session
    that produced the evidence above.

## 5. User & Interaction

*   **Product stage:** After a part has been found and saved — the same screen that currently offers
    "Inject into open board", which is the moment someone has a part and wants it in their design.

*   **What the user is trying to accomplish:** Put a part they just found into the schematic they
    are drawing. Not "write a footprint to a board" — that is a mechanism, and on 2026-09-04 a user
    who chose it got a part on their PCB that their schematic knew nothing about, which is the
    opposite of what they wanted.

*   **What the user sees and does:** *Open question, and the one most worth getting right.* The
    shape to settle: what the button says, whether the app registers the library itself or hands
    over instructions, what it reports when the part is already in the library, and how it tells
    someone the part is now in KiCad without implying it has been placed in their schematic — a
    distinction the current confirmation failed to make and which is exactly what brought this
    spec into existence.
