# Copperplane product video — script and shot list

**75 seconds.** A 60-second cut is marked at the end: drop segments 6 and 7.

Rewritten after the tutorial was written and the app was photographed, so every
number here is one the camera will actually show. The first version of this
script was written before any of that existed and guessed at all of them.

---

## The one story

A maker has a working breadboard. They draw a real PCB. KiCad tells them what is
wrong in a language they do not speak — and stays silent about the things that
would actually cost them a board order.

Everything below serves that. If a shot does not, cut it.

### What changed, and why the shape of the video changed with it

The old arc was **run a check → have it explained → and here is the thing checks
cannot see.** Every beat in it started with a click.

The app does not work that way any more. Link a project and it has already read
the schematic's connectivity and has things to say, before the viewer has asked
for anything. **That is a better video than it is a feature**, because the
strongest possible demonstration of "this is not a checker" is a screen that
speaks with nobody touching the mouse.

So there is a new segment 3, and it is the one to protect. Two segments now carry
the argument rather than one:

*   **Segment 3** — it spoke first. Nothing was clicked.
*   **Segment 5** — the part that breaks no rule and was never going to work.

Neither can be copied by adding a feature. Segment 5 is still the sharpest single
idea; segment 3 is the one that lands earliest, on a viewer who has not yet
decided to keep watching.

---

## Before you record

*   Use `examples/Copperplane_Blink_LEDs` — the same project the tutorial ships,
    so a viewer can download it and follow. Its numbers are recorded in
    `examples/README.md`.
*   **Dark theme**, one window size, the rail showing only `Copperplane Blink LEDs`.
*   Have both windows pre-arranged. Never record a window being dragged.
*   Run each check once before recording so nothing shows a spinner you have to
    cut around. **Segment 3 is the exception** — its whole point is that nothing
    was run. Link the project, let Overview settle, and shoot it as it arrives.
*   Leave the project's supply and current fields **empty**. Empty is the honest
    state for a board somebody just linked, and the findings in segment 3 do not
    need them.
*   Quit anything with notifications.

---

## The script

Each segment lists what to capture, what must be legible, and the line. The
**on-screen text** column matters more than the voiceover: most people will watch
this muted.

### 1 — The hook (0:00–0:06)

| | |
| :--- | :--- |
| **Capture** | The example board in KiCad's PCB editor, zoomed so the Arduino shield fills frame. No cursor. Hold still. |
| **Must be legible** | Nothing in particular. This is a picture, not information. |
| **On screen** | `Your breadboard works.` then `Now make it real.` |
| **Voiceover** | "Your breadboard works. Now you want a real board — and a case to put it in." |

Six seconds is generous for a hook. If the board does not read as *a real thing
somebody made* in the first two, reframe tighter.

### 2 — The wall (0:06–0:13)

| | |
| :--- | :--- |
| **Capture** | KiCad's own DRC dialog, run on the example board. Its raw violation list. Let it sit two beats too long. |
| **Must be legible** | One full `Annular width` violation line, in KiCad's own wording — rule name, minimum, actual, all of it. |
| **On screen** | *(nothing — let the dialog speak)* |
| **Voiceover** | "This is where a lot of projects stop." |

The discomfort is the point. Do not cut away early to be kind.

**Whatever that line says on your screen is what segment 4 has to match**, down
to the number. The two shots are the same violation seen twice — once raw, once
explained — and the beat only lands if a viewer can see it is the same one. That
is also why neither segment names a figure here: the minimum comes from whichever
design rules are in force, not from the board.

### 3 — It already knew (0:13–0:27)

| | |
| :--- | :--- |
| **Capture** | Cut to Copperplane, project **just linked**, sitting on **Overview**. Do not click anything. Let the findings be there when the cut lands. |
| **Must be legible** | The `A1` finding: the `+5V` rail on the `VIN` pin, and the sentence saying A1's own 5V pin is not connected to anything. |
| **On screen** | `Nothing was clicked.` |
| **Voiceover** | "Copperplane has already read it. Your five-volt rail is going into the pin that feeds the Arduino's own regulator — and the pin that actually *is* five volts is sitting unconnected next to it. Nobody asked it to look." |

**Shoot the cut so the cursor is visibly still.** The claim is that the app spoke
first; a cursor drifting toward a button undercuts it in a way no caption can
repair.

**Do not narrate the finding as a verdict.** The app's own last line is a
question — *is `+5V` what you meant here?* — because it cannot see inside the
Arduino module, and a different board might accept it. That restraint is worth
the two words it costs: "it asks." A tool that hedges where it should is more
credible than one that never does, and this audience has been burned by the
other kind.

There is a **second** finding on that screen, R1's placeholder value, and a
**third** telling the viewer something the board got right. Both should be in
frame. Neither is narrated — see the note after segment 5 about letting a viewer
find things.

### 4 — The same files, read differently (0:27–0:38)

| | |
| :--- | :--- |
| **Capture** | **PCB** tab. Click **Run board check**. Let it finish, then scroll slowly through the plain-language summary and into the first annular finding. |
| **Must be legible** | The summary paragraph naming the unconnected GND net and the thin annular rings, then one annular finding with **both numbers from your own screen** — the actual ring width against whatever minimum this board is checked against. |
| **On screen** | `Same files. Same checks.` then the two numbers **as your recording shows them**. |
| **Voiceover** | "It runs the same checks KiCad does, on the same files, and then tells you what they mean. A plated hole needs a ring of copper around it. Yours is thinner than the minimum this board is checked against — thin enough for the drill to break through, on a board that looked fine in CAD." |

**Read both numbers off your own screen and caption those.** This script has now
been wrong about a number twice: first a findings count, then an annular minimum
it stated as 0.100 mm when the board was being checked at 0.15 mm. The threshold
is **not a property of the board** — it comes from whichever design rules are in
force, so it changes with the board house selected and with any `.kicad_dru` on
disk. Anything here that hard-codes a figure will rot again.

**Check what the board is being checked against before you roll.** The header
above the results says which rules are in force. If it says a board house, the
numbers are that house's. See the note after segment 5 about a `.kicad_dru` that
outlives the choice that created it.

Two things on this screen are new since the script was first written, and both
are worth the scroll:

*   **A plain-language summary of the whole board**, above the findings — one
    paragraph saying what is actually wrong with it. That is a better opening
    beat than any single finding, because it is the app doing the reading rather
    than the reader doing it.
*   **"5 DRC tests switched off — 3 worth turning back on."** Do not narrate it;
    it costs more seconds than it earns here. Leave it in frame. A viewer
    noticing the app checked KiCad's *configuration* as well as the board reads
    as thoroughness.

**Do not put a findings count on screen**, and do not say one out loud. The count
moves with the rules in force, and a caption is contradicted by your own
recording the moment anything changes.

### 5 — The thing KiCad cannot see (0:38–0:52)

| | |
| :--- | :--- |
| **Capture** | Scroll past the DRC results into **"Review the board"** — a separate panel below them. Stop on the two findings badged **"Not reported by ERC or DRC"**. |
| **Must be legible** | The app's own line, `2 of these were found by Copperplane. ERC and DRC do not report them.`, and then the D1 finding: a 2-pin schematic symbol against a 4-pad RGB footprint. |
| **On screen** | `A symbol with 2 pins.` `A footprint with 4 pads.` `No rule was broken.` |
| **Voiceover** | "And then there is this. A two-pin LED symbol, on a four-pin RGB footprint. Two pads connected to nothing, one resistor where three belong. No rule was broken — this is a part that was never going to work." |

**The three on-screen lines should land as three separate beats.** This is the
whole argument for the product in fourteen seconds: a checker tells you which
rules you broke; knowing what you actually built is a different question.

**The old captions said `ERC passes.` `DRC passes.` Do not use them — they are
false.** ERC reports two violations on this board and DRC reports a genuine
`ERROR`: a ground track that stops short of the Arduino's pad. Putting "every
check passes" on screen while a red error sits two scrolls above it is the exact
failure this product argues against, committed by its own advert.

The replacement is stronger anyway, because **the app says it rather than a
caption**: *"2 of these were found by Copperplane. ERC and DRC do not report
them."* is already on screen, in the product, in green. Frame it.

**The panel is separate from DRC now**, which the script previously assumed it
was not. "Review the board" explicitly says the board check reports its problems
above and that this review does not repeat them — so this is a scroll into a
different card, not further down the same list.

There is a **second** mismatch in the list, SW1, and it is deliberately not in the
script. It is the milder case — a tactile switch whose extra legs are internally
paired — and explaining why one is fatal and the other probably is not costs more
seconds than the segment has. Do not crop it out of frame; just do not narrate
it. A viewer noticing a second finding they were not told about reads as
thoroughness.

> **Before you roll: check for a leftover `.kicad_dru`.**
>
> A board house's numbers are written to `<project>.kicad_dru`, and **KiCad
> applies that file whenever it is present** — including when the app's own
> header says *"Against KiCad's own defaults."* On 2026-09-24 the tutorial board
> was being checked at a house's 0.15 mm annular minimum while the screen said
> defaults, with twelve extra warnings from the verification canary that file
> also carries.
>
> For filming, delete it or reset the profile first. You want KiCad's real
> defaults, the four annular warnings and the one unconnected item the tutorial
> also describes — not sixteen violations, twelve of which are a self-test.

### 6 — The case (0:52–1:02)

| | |
| :--- | :--- |
| **Capture** | **Enclosure** tab. The pre-filled height. Click **Generate**. The 3D preview fills with the case around the board. |
| **Must be legible** | `14.1mm needed, set by D1` and the caveat that some components have no known height. |
| **On screen** | `Measured from your board.` |
| **Voiceover** | "It measures your actual board — outline, mounting holes, component heights — and sizes a case to fit. And it tells you what it could not measure, instead of guessing." |

That last clause is not filler. It is the difference between a tool you can trust
with a board order and one you cannot.

### 7 — Whose machine (1:02–1:09)

| | |
| :--- | :--- |
| **Capture** | Both windows side by side, KiCad unchanged. Then Copperplane's welcome screen with the mark. |
| **Must be legible** | The Copperplane mark. |
| **On screen** | `It reads your files. It doesn't take them over.` |
| **Voiceover** | "It does not replace KiCad or FreeCAD. It reads what you made, explains what it finds, and hands the decision back to you." |

### 8 — Close (1:09–1:15)

| | |
| :--- | :--- |
| **Capture** | The mark, still, with the URL. |
| **Must be legible** | `gittielabs.github.io/copperplane` |
| **On screen** | `Free. Open. Runs on your machine.` + URL |
| **Voiceover** | "Free, open, and it runs on your machine. Try it on a board of your own." |

---

## The 60-second cut

Drop segments 6 and 7. The arc still works: hook → wall → **it already knew** →
same files read differently → the thing KiCad cannot see → close. You lose the
enclosure, which is a feature; you keep the argument.

Do not shorten segments 3 or 5 to save time. Shorten segment 4 — it is the one
whose job the other two now partly do.

---

## Lines to avoid

*   **"AI-powered"**, **"leverage"**, **"seamless"**, **"revolutionise"**. A maker
    who has been burned by a bad board order does not want a revolution.
*   **"Never make a mistake again."** It finds some things. Say which.
*   **"Replaces KiCad."** It does not, and claiming it insults the audience.
*   Anything about the model, the provider, or the pipeline. Nobody watching cares
    which model read the datasheet.
*   Do not say **"simply"** or **"just"**. Nothing here is simple; that is why the
    tool exists.

## What to say if it is thirty seconds

Hook, **segment 3**, segment 5, close. Two beats, not one, and the order matters:
the app speaking first buys the attention that the mismatch then rewards.

If it has to be a single beat, it is **segment 3** rather than segment 5 — which
is a change from the previous version of this script, and worth saying why. The
mismatch is the sharper idea, but it needs the viewer to already care about the
difference between "breaks a rule" and "will not work". A screen that answers
before anybody asks needs no setup at all.

Everything else in this product is *better* than the alternative. Those two are
*different*.

---

## Capture notes

*   **Screen Studio**, following its own defaults for cursor smoothing. Turn the
    automatic zoom **off** for segments 2 and 4 — it fights with reading. Turn it
    off for segment 3 as well, and for a different reason: an automatic zoom is a
    movement, and that segment's claim is that nothing moved.
*   Record each segment separately. One continuous take invites a hunt for the
    good thirty seconds.
*   Cursor speed: slow enough that a viewer's eye can follow it to the thing being
    pointed at, and then a beat before anything moves.
*   Redact afterwards with `scripts/redact_screenshots.py` if any frame shows a
    file path — the project header and Settings both do.
*   Export at the platform's native aspect. A 16:9 export letterboxed into a
    vertical feed reads as somebody else's video.
