# The example project

One KiCad project, used by the [product video](product-video-script.md), the docs screenshots, and
the downloadable quick start. **One project for all three**, so a reader who watches the video and
then downloads the project sees the same board.

## Why it must be slightly broken

A clean project makes the app look like it does nothing. Its checks report "No violations found",
its enclosure comes out fine, and the video has nothing to explain.

This is not a guess. The maintainer's own `Hello_World_Blinky` returns **0 ERC violations**, and
that is precisely why the ERC explanation path had never once run with real findings until a
deliberately broken copy was made — the whole reason `SPEC-332` was written.

## What it should contain

*   A circuit a beginner recognises: a microcontroller or a 555, an LED, a resistor, a power source.
    Something whose *purpose* needs no explanation, so the viewer's attention is on the app.
*   A finished **board**, not just a schematic — outline and at least two mounting holes, so the
    enclosure step has real geometry to measure.
*   At least one **through-hole part with no 3D model**, so the footprint detail view has something
    honest to say about a height that has to be supplied by hand.
*   **Small.** Under a dozen components. Every extra part is another thing on screen that the
    viewer has to ignore.

## The defects to introduce, and what each produces

Measured against a real schematic with `kicad-cli sch erc --format json --severity-all`, not
guessed:

| Edit, in KiCad | What ERC then reports |
| :--- | :--- |
| Delete **one wire** | 1 × `pin_not_connected` (error) |
| Delete the **`PWR_FLAG`** symbols | 2 × `power_pin_not_driven` + 2 × `pin_not_connected` |
| Delete **all** wires (34 in the sample) | 28 × `pin_not_connected`, 4 × `pin_not_driven`, 2 × `power_pin_not_driven` |

**Aim for variety, not volume.** One deleted wire plus one deleted `PWR_FLAG` gives two genuinely
different classes — and `power_pin_not_driven` is the one worth demonstrating, because the schematic
is usually *correct* and missing only a KiCad convention. A maker reads "not driven" and hunts for a
wiring fault that is not there, which is exactly the translation the app exists to do.

On the board side, the sample's DRC reports **2 unconnected items** on `U2` and `D1` — enough for
the PCB tab without any deliberate damage.

### Two edits that do nothing

Recorded so nobody repeats them. Both were tried:

*   Renaming a `Reference` property to force a duplicate designator: **no violations**. KiCad 7+
    keeps effective references in `(instances)` blocks, so editing the property text is inert.
*   Breaking `PWR_FLAG`'s `lib_id`: **no violations**.

Make these edits **in the KiCad GUI**, which keeps the file internally consistent in ways a text
edit does not.

## Open, and needing the maintainer

**This project has to be drawn in KiCad by a person.** Authoring a schematic and a board by writing
s-expressions produces a file that opens badly, and nothing here is worth that risk. What this
document fixes is *what it must contain* and *what the defects must produce*; the drawing is a
half-hour in KiCad and cannot be done from here.

Also still open:

*   **Where it lives and how a user gets it.** A directory in this repo, a release asset, or a
    separate repo. It has to survive `git clone` and a direct download equally well.
*   **Which KiCad version it is saved from.** File formats change between majors, and a project
    saved from a newer KiCad will not open in an older one. The README asks for KiCad 9+; saving
    from the oldest supported version is the safer choice.
*   **Licensing.** It is original work, so it needs an explicit licence anyway — most likely the
    repo's own Apache-2.0, stated in a README beside it.
