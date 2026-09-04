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

Download `Copperplane_Blink_LEDs` and open it in KiCad first. Look at the
schematic and the board for a minute before Copperplane sees them — it is worth
having your own impression to compare against.

## Link it

In Copperplane, make a new project and point it at the `.kicad_pro` file.

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

KiCad's own DRC reports five errors on this board. Here is one of them, as KiCad
puts it:

> Annular width (board setup constraints min annular width 0.1000 mm; actual
> 0.0850 mm)

That sentence is completely accurate and tells a beginner almost nothing.

![A DRC finding, explained](/copperplane/images/board-check-explained.png)

What it means: a plated through-hole pad is a ring of copper around a drilled
hole. The *annular ring* is the copper left between the hole edge and the pad
edge. Yours is 0.085 mm where the board's own rules ask for 0.1 mm. Drill
placement varies by a few thousandths of a millimetre in manufacturing, so a ring
this thin can be **broken through** by the drill — leaving a pad connected to
nothing, on a board that looked fine in CAD.

All four of these are on D1, the RGB LED. Same footprint, four pads, same
shortfall.

The fifth error is different, and it is the one every beginner makes:

> Missing connection between items: Track [GND] on F.Cu — PTH pad 7 [GND] of A1

A ground connection that was drawn but never finished. On a board this small you
would probably catch it by eye. On a board with two hundred nets you would not.

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

## Break the schematic on purpose

The schematic passes ERC cleanly as shipped. To see the schematic check do
something, give it something to find.

In KiCad, delete the two **PWR_FLAG** symbols and save. Then run the schematic
check in Copperplane. You should get four errors of two kinds:

| What ERC says | What it means |
| :--- | :--- |
| `power_pin_not_driven` ×2 | Nothing in the schematic tells KiCad this power net is actually fed from somewhere |
| `pin_not_connected` ×2 | The pins those flags were sitting on are now dangling |

`power_pin_not_driven` is the single most confusing error in KiCad for anyone
starting out, because **the board is fine**. Your 5 V rail really does come from
the Arduino. KiCad simply cannot tell the difference between "power arrives here
from off-sheet" and "you forgot to connect this", so it asks you to say which,
and `PWR_FLAG` is how you say it.

Put the flags back when you are done and the errors go away.

## Fit an enclosure

Open the **Enclosure** tab.

![Generating an enclosure from the board](/copperplane/images/enclosure.png)

The height field is pre-filled with the 14.1 mm from earlier, and repeats the
caveat: six components have no measurable height, so the real minimum may be
taller. Generate, and you get a box sized to your actual board outline with the
PCB seated inside it for a visual fit check.

The mounting holes are the reason this is worth doing before you order anything.

## What you have learned

Five real errors, one non-error that would have cost you a board, and an
enclosure that fits. More usefully: a way of reading check output that does not
depend on already knowing what an annular ring is.

Take the same pass over a board of your own. If something goes wrong — and on
Windows or Linux especially, it might —
[tell us what happened](https://github.com/GittieLabs/copperplane/issues/new?template=platform_report.yml).
