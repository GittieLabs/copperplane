---
id: SPEC-111
title: "Board Retention: Standoffs the Board Actually Mounts To"
status: Draft
type: Feature
created: 2026-09-03
last_updated: 2026-09-03
target_version: v0.4.0
location: "services/python-daemon/specs/SPEC-111-board-retention-standoffs.md"
parent_spec: "SPEC-109-parametric-enclosure-generator.md"
child_specs: []
user_facing: true
---

# SPEC-111: Board Retention: Standoffs the Board Actually Mounts To

> **Deferred by the maintainer on 2026-09-03, the day it was written.** After running the
> enclosure review against a properly linked project he reported: *"The standoffs are created. The
> issue is that they don't show through the mount holes. I no longer want to work on the standoffs
> issue. This is a minor display issue."*
>
> That is a correct reading of the severity and it also confirms this spec's premise: the posts
> generate, and nothing passes through the holes, because they are solid cylinders stopping flush
> at the board's underside. Everything below stays accurate and unbuilt. The spec is kept rather
> than closed because the underlying defect is real — a board sitting on posts it cannot be
> fastened to — and because the reason it went unbuilt is now recorded rather than rediscovered.
>
> Worth knowing before picking this up: his first attempt to see the problem produced an enclosure
> with **no posts at all**, because the project had a folder linked but no `.kicad_pro` (see
> `SPEC-337` in `ROADMAP.md`). From the 3D view, "no standoffs generated" and "standoffs with
> nothing through the holes" look identical.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Make a generated enclosure's standoffs something a board can actually be
    fastened to — a post wider than the hole it sits under, bored for a screw — so the mounting
    holes read as mounted rather than empty.

*   **Business / Technical Value:** Reported by the maintainer from the running app on 2026-09-01:
    *"when the board is added to the enclosure, you can see mounting holes but not the standoffs
    through the holes."* Confirmed in the geometry rather than guessed —
    `freecad_bridge._STANDOFF_CYLINDER_TEMPLATE` unions a **solid** `Part.makeCylinder` at each
    recognised hole, and the preview lifts the board by `wall_thickness_mm + standoff_height_mm`
    (`EnclosureViewer.computeBoardOffset`). The post therefore stops flush at the board's underside
    by construction: it supports the board and nothing passes through the hole. **The render is
    faithful; the geometry really is like that.**

*   **This is unfinished `SPEC-109`, not new scope.** `ROADMAP.md` recorded the opposite — that
    `SPEC-109` §1 *"explicitly ruled out fastener hardware — so this is a deliberate scope
    re-opening, not an oversight to be quietly patched."* Read directly, `SPEC-109` §1 says:

    > **Not fastener hardware selection.** Standoffs get a hole sized for a screw diameter
    > parameter; choosing a specific screw, heat-set insert, or lid-latching mechanism is out of
    > scope.

    The bore was **in** scope; only *choosing hardware* was out. `SPEC-109` §2 lists the inputs as
    *"per-hole standoff height/screw diameter"*. Neither exists in the code:
    `generate_enclosure()` has no screw parameter at all, and no cut is ever made. So this spec
    closes a gap between `SPEC-109`'s stated scope and what shipped, and the roadmap's own
    explanation of why it was missing is corrected in the same change.

*   **A second defect the roadmap did identify correctly.** The standoff radius comes from the
    hole's own `diameter_mm` (`daemon.py`, `radius=s["diameter_mm"] / 2`), making the post exactly
    as wide as the hole it is meant to sit under. Even bored, it would have no shoulder for the
    board to bear on. A standoff needs an outer diameter larger than the hole; that is what makes
    it a standoff rather than a peg.

*   **Non-Goals:**
    *   **Choosing hardware.** `SPEC-109`'s non-goal stands unchanged: a screw *diameter*
        parameter with a sane default, not a recommendation of a specific screw, insert or length.
    *   **Heat-set inserts, threaded inserts, or moulded threads.** A pilot bore for a self-tapping
        screw is the whole mechanism.
    *   **A locating boss through the hole.** Considered and not chosen (§2). It fills the hole
        visually but does not retain the board until the lid is on.
    *   **Lid fastening.** Still `SPEC-109`'s non-goal, still out.

## 2. System Architecture & Design Choices

*   **Settled: a bored post for a screw, chosen by the maintainer on 2026-09-03** over a locating
    boss and over offering both. It is what `SPEC-109` already specified, it retains the board
    without the lid, and it puts real hardware through the hole — which is what "not the standoffs
    through the holes" was asking for. The rejected alternative is recorded because it is the
    cheaper build and someone will suggest it again: a stepped boss needs no screws at all, but a
    board that is only located and not held is a board that falls out of an open enclosure.

*Open questions this spec must settle:*

*   **The outer diameter rule.** Fixed default, or derived from the hole diameter plus a shoulder
    width? Derived keeps it proportional to the fastener the hole implies; fixed is predictable and
    easier to print. Whichever it is, it must never be less than the hole diameter — the current
    behaviour — and must be checked against the board's own keep-out, since a post wider than the
    hole can foul a nearby component's courtyard.
*   **The pilot bore diameter for a given screw diameter.** A self-tapping screw needs a hole
    *smaller* than its thread, and the right undersize depends on the material. Settle the default
    ratio and where it is documented, since getting it wrong produces either a stripped post or a
    split one.
*   **How deep the bore goes**, and whether it stops short of the floor. A bore through the floor
    is a hole in the enclosure's bottom.
*   **What happens when a post cannot fit.** Two mounting holes close to a wall, or to each other,
    can produce overlapping or wall-merged posts. Decide whether that is silently fused (today's
    behaviour, since everything is `fuse`d), warned about, or refused.
*   **Whether the preview shows the screw.** The 3D view is how the maintainer noticed the problem;
    a bore that only exists in the STEP export would not have been visible either.

## 3. Known Constraints & Risks

*   **Nothing here is verified until something is printed.** Every dimension in this spec is a
    number in a file until a real enclosure comes off a printer with a real board screwed into it.
    That is the only test that counts, and no CI job can run it. This is the same exposure
    `SPEC-302` and `SPEC-336` both recorded, in a form where the feedback loop is hours long.
*   **`freecadcmd` cold-boot cost is already the enclosure's dominant expense** (`SPEC-109` §3,
    `SPEC-311` §3). A bore is a second boolean per standoff on top of a union; on a board with six
    mounting holes that is twelve operations. Measure before assuming it is free.
*   **The board preview and the exported geometry come from two different toolchains** and have
    disagreed before — `CTX-311.15` records a real coordinate-convention bug found by a live
    click-through that this file's own tests missed. A screw shown in the preview but absent from
    the STEP, or at a different depth, is the same class of failure.
*   **A wider post can foul a component.** `SPEC-326`'s courtyard data already measures where
    components sit; a standoff that overlaps one is a physical collision that the current
    equal-to-the-hole diameter cannot cause and this change can.

## 4. Module Map & Reference Links

*   `services/python-daemon/freecad_bridge.py` — `_STANDOFF_CYLINDER_TEMPLATE`,
    `generate_enclosure`.
*   `services/python-daemon/daemon.py` — builds the `standoffs` list from `recognized_holes`, and
    is where `diameter_mm` becomes a radius today.
*   `apps/tauri-ui/src/components/EnclosureViewer.tsx` — `computeBoardOffset`, the preview that
    made the problem visible.
*   `apps/tauri-ui/src/components/EnclosurePanel.tsx` — where a screw-diameter input would live.
*   `services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md` — parent; §1 and §2
    already specify the bore this spec delivers.
*   `apps/tauri-ui/specs/SPEC-326-component-volume-placeholders.md` — courtyard data, for the
    fouling check.

## 5. User & Interaction

*   **Product Stage:** Enclosure — after a board exists and its outline and mounting holes have
    been read.
*   **What the user is trying to accomplish:** Getting an enclosure they can print, drop their
    board into, and screw down — without working out screw sizes or standoff geometry themselves.
*   **What the user sees and does:** Generates an enclosure as today. The preview now shows posts
    the board sits on with holes down their centres, and the mounting holes line up with something
    instead of empty space. A screw-diameter field sits with the other enclosure parameters, with a
    default that works for the common case, so a user who does not know what M3 means never has to
    touch it.
