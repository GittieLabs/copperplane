---
id: SPEC-329
title: "Assisted Authoring: Adding a Part on Request"
status: Draft
type: Feature
created: 2026-09-05
last_updated: 2026-09-05
target_version: v0.7.0
location: "apps/tauri-ui/specs/SPEC-329-assisted-authoring-adding-a-part.md"
parent_spec: "../../../services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md"
child_specs: []
user_facing: true
---

# SPEC-329: Assisted Authoring: Adding a Part on Request

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let a person say "add this part to my design" and have it arrive somewhere
    KiCad will actually use it — with a reference designator, in the schematic, reaching the board
    through KiCad's own flow.

*   **Deliberately last, and the reason still holds.** The maintainer's own call: *"I think we need
    to add it but we can do this last to see if things shape in a way where it is not needed."*
    Everything before it reads and explains. This is the only stage that writes, and read-only may
    yet prove sufficient.

*   **The distinction this must hold is authoring versus assisting.** Wiring nets, placing parts
    and routing are KiCad's job and should stay there. Adding a part the user explicitly asked for
    — unconnected, with the footprint they chose — is what an add-on does, and both KiCad and
    FreeCAD have add-on ecosystems that do exactly that. The line is not "does it write" but "did
    the user ask for this specific thing".

*   **Evidence from a real session, which changes what this spec has to answer.** On 2026-09-04 a
    user injected an NE555 into a live board through `SPEC-108`. It worked — and read back out of
    the board file afterwards it carried KiCad's `REF**` placeholder, no net assignments, a
    schematic that knew nothing about it, and a fresh DRC warning about a footprint library the
    configuration did not include. Nothing was broken. That is simply what writing to a board while
    bypassing the schematic produces, and it is why "the only stage that writes" needs a better
    answer than the one that exists.

*   **Two routes, and one of them is now drafted.**
    *   **Write a library, let KiCad place it.** `SPEC-112` covers exactly this: a real
        `.kicad_sym` and `.pretty` the user registers once, after which the part is placeable from
        the symbol chooser and reaches the board through **Update PCB from Schematic**, with its
        designator and its nets. It is the smaller, safer half of this spec's ground, and it exists
        as a draft.
    *   **A real KiCad add-on this app talks to.** Puts the write inside KiCad's own process rather
        than behind its back, makes the permission boundary explicit, and is the only route that
        could ever touch a schematic — KiCad's IPC API cannot, and `kicad-python` 0.8.0's
        `schematic` module does not even import.

*   **Non-Goals:**
    *   **Never wiring nets or routing.** Not a scope question — a product identity question.
    *   **Not a setting.** Per-action authorisation, every time. A checkbox that grants standing
        write permission is the version of this that damages somebody's board.
    *   **Not superseding `SPEC-112`.** If the library route proves sufficient, this spec should
        close having built nothing, and that is a success.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Whether it is needed at all.** The honest first question. If `SPEC-112` lands and placing a
    part from KiCad's own chooser feels fine, there is nothing left here worth the risk.

*   **Library route or add-on.** The add-on is the only path to a schematic write, and it is a
    second distributable with its own install, versioning and KiCad-version compatibility. That is
    a large commitment for a project that cannot currently verify itself on two of its three
    platforms.

*   **What the confirmation says.** `SPEC-108`'s said "This will write into the board KiCad
    currently has open" — true, and it told nobody what state they would end up in. It now
    enumerates the consequences because a user was surprised by them. Any write this spec adds
    inherits that standard: say what will exist afterwards, not what will happen.

*   **What happens to `SPEC-108`'s board write.** It has a real use for a board with no schematic.
    Whether it remains, is renamed, or is retired once a better route exists is decided here.

*   **Undo.** KiCad has its own undo stack, and a write through the IPC API is a real commit inside
    it. A write through a library file is not undoable at all — it is a file on disk. Those are
    different promises and the UI cannot use one word for both.

## 3. Known Constraints & Risks

*   **This is the only spec that can damage a user's work.** Everything else reads. A wrong write
    lands in a file somebody spent hours on.

*   **KiCad's API cannot reach the schematic, and that is not a temporary state.**
    `kicad-python` 0.8.0 is the newest published version; its `schematic` module raises
    `ImportError` on import and the client exposes `get_board()` with no `get_schematic()`.
    Anything promising schematic writing today is promising an add-on.

*   **A file KiCad has open is contested.** The board write sidesteps this by going through the
    IPC API. A library write does not have that option, and "KiCad may overwrite what you just
    wrote" is a failure mode with no good error message.

*   **Doing this badly is worse than not doing it.** The audience is people who do not yet know
    what a correct board looks like, and therefore cannot check the tool's work.

## 4. Module Map & Reference Links

*   `services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md` —
    parent; the write that exists, and the evidence for why it is not enough.
*   `services/python-daemon/specs/SPEC-112-placing-a-part-through-kicads-own-libraries.md` — the
    library route, drafted, and the smaller half of this ground.
*   `services/python-daemon/context/CTX-202.5-symbol-width-and-honest-advice.md` — the live session
    that produced the `REF**` finding.
*   `services/python-daemon/kicad_write.py`, `kicad_bridge.py` — the existing write path.
*   `apps/tauri-ui/specs/SPEC-325-kicad-project-integration.md` — the read this builds on.

## 5. User & Interaction

*   **Product Stage:** Authoring — the only stage in the product that writes to the user's files,
    reached from the library or the part detail view once a part has been chosen.

*   **What the user is trying to accomplish:** Getting a part they have already found into their
    design without hand-copying a symbol and a footprint into KiCad, and without discovering later
    that it arrived somewhere KiCad does not really know about it. The failure this exists to
    prevent is the one already observed: a part that is on the board, carries `REF**`, has no nets,
    and is invisible to the schematic.

*   **What the user sees and does:** The user asks for a specific part to be added and is shown,
    before anything is written, exactly what will change and where — which file, which library,
    and what they will need to do in KiCad afterwards. They authorise that one action; there is no
    setting that grants it standing. If the route taken is `SPEC-112`'s library, what they see
    afterwards is an instruction to place the part from KiCad's own symbol chooser, not a claim
    that the design has been edited.
