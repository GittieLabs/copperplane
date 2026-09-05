---
title: Your first board check
description: Walk a real Arduino shield through Copperplane — find what is wrong with it, understand why, and fit an enclosure around it.
---

This is a real board with real problems. Not a toy: an Arduino UNO shield with an
RGB LED, a resistor, a tactile switch and four mounting holes. It has five errors
on the PCB, and one mistake that **neither KiCad nor Copperplane will flag as an
error** — which turns out to be the most interesting thing in it.

You will need KiCad 9 or newer, and about twenty minutes.

:::note[What you are looking at]
The board is an Arduino shield: it sits on top of an UNO. If you have never made
one, that is fine — nothing here asks you to design anything. You are reading a
board somebody else drew, which is most of what a checking tool is for.
:::

## Get the project

**[Download Copperplane_Blink_LEDs.zip](https://github.com/GittieLabs/copperplane/raw/develop/examples/Copperplane_Blink_LEDs.zip)**
— about 35 KB, three files. Unzip it anywhere and open the `.kicad_pro` in KiCad.

(The same files live in
[`examples/Copperplane_Blink_LEDs/`](https://github.com/GittieLabs/copperplane/tree/develop/examples/Copperplane_Blink_LEDs)
if you would rather browse them or already have the repository.)

Look at the schematic and the board for a minute before Copperplane sees them —
it is worth having your own impression to compare against.

## Link it

In Copperplane, make a new project and point it at the `.kicad_pro` file.

![Linking a KiCad project to a new Copperplane project](/copperplane/images/new-project.png)

The last step of the wizard checks the project as it links it — schematic and board
agreeing, the component count, and what ERC and DRC already have to say. You have not
asked for anything yet and it has already read the design.

![The wizard's own check pass, before you have asked for anything](/copperplane/images/new-project-review.png)

The rail on the left holds your projects, your parts library, and Settings.
Across the top of a project sit five tabs — **Overview**, **Components**,
**Schematic**, **PCB**, **Enclosure** — which is roughly the order you would work
in.

## Read the board

Open the **Schematic** tab.

![The Schematic tab, showing the board's components](/copperplane/images/schematic-check.png)

Eight components. Six of them have **no 3D model**, which is not an error — most
KiCad footprints ship without one — but it matters later, and Copperplane says so
rather than quietly assuming a height of zero.

Notice what it already knows: the enclosure needs at least **14.1 mm** of interior
height, and that figure comes from D1, measured from its 3D model. It also tells
you the number is a floor rather than an answer, because six components could not
be measured at all.

That is the shape of everything here. A number, where it came from, and what it
does not cover.

## Check the PCB

Open the **PCB** tab and run the check.

![The board check result list](/copperplane/images/board-check.png)

**Three findings.** KiCad's own DRC counts five violations here; you are shown
three, and the difference is the point.

**One — four pads, one problem.** KiCad reports the same violation four times,
once per pad of D1. It reads like this:

> Annular width (board setup constraints min annular width 0.1000 mm; actual
> 0.0850 mm)

Four times over, that is accurate and tells a beginner almost nothing. They are
one problem with one cause and one fix, so they arrive as one finding.

![A finding, explained](/copperplane/images/board-check-explained.png)

What it means: a plated through-hole pad is a ring of copper around a drilled
hole. The *annular ring* is the copper between the hole edge and the pad edge.
Yours is 0.085 mm where the board's own rules ask for 0.100 mm. Drill placement
varies by thousandths of a millimetre in manufacturing, so a ring this thin can
be **broken through** by the drill — leaving a pad connected to nothing, on a
board that looked fine in CAD.

**Two — the mistake every beginner makes.**

> Missing connection between items: Track [GND] on F.Cu — PTH pad 7 [GND] of A1

A ground connection drawn but never finished. On a board this small you would
probably catch it by eye. On a board with two hundred nets you would not.

**Three — something KiCad never said.** The last finding is a *suggestion*, not
a violation: this project has the "footprint has no courtyard defined" check
switched off. A courtyard is the keep-out outline marking the space a component
physically occupies, and the Enclosure tab measures board-to-case fit directly
from those outlines. With the check disabled, a part could be missing its
courtyard and DRC would never mention it — which means the enclosure you
generate later could be quietly wrong.

That one is worth dwelling on. Nothing was violated, so no checker would raise
it. It is a consequence of a setting, noticed because something else in the app
depends on it.

## The mistake nothing flags

Look at D1 again.

The **symbol** in the schematic is `Device:LED` — a plain two-pin LED. The
**footprint** on the board is `LED_THT:LED_D5.0mm-4_RGB` — a four-pin RGB LED.

Two pins driving a four-pin part. Pads 3 and 4 have no net at all, and there is a
single resistor where an RGB LED wants three, one per colour channel.

**ERC does not catch this. DRC does not report it as an error.** KiCad mentions
it only obliquely, as pads with no net, buried among other information. It is not
a rule violation — it is a part that was never going to work, described perfectly
consistently.

This is the gap the tool exists for. A checker tells you which rules you broke.
Understanding what you *built* is a different question, and it is the one that
costs you a board order.

:::tip[Try it]
Ask about the board: *"why does D1 have pads with no net?"* The answer should
mention the symbol and the footprint disagreeing. If it doesn't, that is worth
[telling us](https://github.com/GittieLabs/copperplane/issues/new?template=bug_report.yml)
— it is exactly the case this feature is for.
:::

## Check the schematic

Run the schematic check. Two errors, both the same kind:

```
ERROR  power_pin_not_driven — Input Power pin not driven by any Output Power pins
ERROR  power_pin_not_driven — Input Power pin not driven by any Output Power pins
```

This is the single most confusing error in KiCad for anyone starting out,
because **the board is fine**. The 5 V rail really does come from the Arduino.

KiCad cannot tell the difference between "power arrives here from off the sheet"
and "you forgot to connect this". Both look identical to it: a power input with
no power output feeding it. So it asks you to say which, and a **PWR_FLAG** is
how you say it — a symbol whose entire job is to tell ERC "power genuinely
enters the design at this point, stop asking".

The project ships without them so the check has something real to report. To fix
it the way you would on your own board: in KiCad, place a `PWR_FLAG` on the +5V
net and another on GND, save, and run the check again. Both errors go.

That is the whole lesson. The error was never about a broken circuit — it was
KiCad asking a question, and the fix is answering it.

![The schematic check, with the power flags removed](/copperplane/images/schematic-erc.png)

## Fit an enclosure

Open the **Enclosure** tab.

![Generating an enclosure from the board](/copperplane/images/enclosure.png)

The height field is pre-filled with the 14.1 mm from earlier, and repeats the
caveat: six components have no measurable height, so the real minimum may be
taller. Generate, and you get a box sized to your actual board outline with the
PCB seated inside it for a visual fit check.

The mounting holes are the reason this is worth doing before you order anything.

![The generated enclosure, with the board seated inside it](/copperplane/images/enclosure-3d.png)

:::note[Why the Arduino is not in the picture]
The preview draws the parts KiCad has 3D models for. On this board that is the RGB LED
and the resistor — the switch and the Arduino module both *reference* a model in KiCad's
library, and those two `.step` files are not in KiCad's macOS package, so there is nothing
to draw.

That is also why the height reads "6 still unknown". The 14.1 mm floor comes from D1,
the tallest part Copperplane could actually measure, and the app says plainly that the
real minimum may be taller rather than quietly treating an unmeasurable part as flat.
:::

## What you have learned

Five real errors, one non-error that would have cost you a board, and an
enclosure that fits. More usefully: a way of reading check output that does not
depend on already knowing what an annular ring is.

Take the same pass over a board of your own. If something goes wrong — and on
Windows or Linux especially, it might —
[tell us what happened](https://github.com/GittieLabs/copperplane/issues/new?template=platform_report.yml).
