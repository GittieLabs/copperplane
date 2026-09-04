---
title: Why this exists
description: What happens between a working breadboard and a board you can order — and which parts of it this tool takes off you.
---

Your circuit works on the breadboard. The jumper wires are a mess, but it does
what you wanted, and the obvious next step is to make it real: a board you can
order, and a case you can print.

That step is where a lot of projects stop. Not because it is beyond you — the
tools are free and the tutorials exist — but because the amount you have to
learn before your first board is *correct* is larger than it looks, and most of
it is not the interesting part. A checker tells you `power_pin_not_driven` and
means "add a marker KiCad wants". A footprint is called
`PinHeader_1x04_P2.54mm_Vertical` and nobody tells you that is a sentence. Your
case has to fit a board you would have to measure by hand.

None of that is design work. It is translation, and it is where the afternoons
go.

## The afternoon this was built for

Here is what that looks like a little further along, once you are past the first
board and into a real part.

You are putting a microcontroller on a board. You have its datasheet open — two
hundred and thirty pages of it. Somewhere in there is the answer to what that
part actually needs around it to work: how much decoupling and where, whether
the reset line needs a pull-up, what load capacitance the crystal wants, what
the brown-out behaviour does to your EEPROM if the supply sags.

That information exists. It is written down, precisely, by the people who made
the part. And finding it means scrolling.

So you scroll. You find the power section, read three paragraphs, and go back
to KiCad. Twenty minutes later you need the reset section, and you scroll again.
By the end of the afternoon you have made four correct decisions and cannot
remember which page any of them came from — which matters, because in six weeks
when someone asks why there are two capacitors on that pin, "I read it
somewhere" is not an answer you want to give.

Then the board is done and it needs a case. Your enclosure is a separate
program, with a separate model, that has never heard of your board. So you read
your own mounting-hole coordinates off the PCB editor and type them into
FreeCAD by hand. If the board outline changes, you do it again.

**None of this is hard. All of it is slow, and all of it is the kind of slow
that produces mistakes** — a transposed coordinate, a decoupling value
remembered from a different part, a standoff in the wrong place discovered after
the print.

## What we thought was worth building

Three things, in the order they hurt.

**Answers that carry their source.** The value is not that a model can tell you
about decoupling — it is that you can check. Every piece of design guidance in
this app is extracted from your part's real datasheet and stored with the page
it came from. Click the citation, the PDF opens at that page. An item whose
quote cannot be found on the page it claims is discarded rather than repaired.
That contract is the whole feature; the plain-language summary on top is just
what makes it readable.

**One library, across projects.** A part you looked up once should be a real
object you own — with its pins, its package, its datasheet, and a record of
where each field came from — not a chat message you scroll back to find. Save it
once and it is there in every project after, along with the footprint, which is
shared rather than duplicated, exactly as KiCad models it.

**Geometry that comes from the actual board.** Your enclosure should be built
from your board's real outline and real mounting holes, read from the file, not
from numbers you retyped.

## The thing we deliberately did not build

Every few months something appears that claims to generate a schematic from a
prompt. We are not that, on purpose.

The failure mode of a confident wrong answer in hardware is expensive and
delayed: a hallucinated footprint that looks plausible costs a PCB spin, and you
find out weeks later. So the app validates before anything reaches a board —
pin count against the package, pad pitch for sanity, courtyard actually
enclosing the pads — and refuses rather than guessing when a package is not
recognised. Writing to a board you have open in KiCad happens only after you
have seen exactly what will be written and clicked confirm.

The honest framing is that this is **an advisor with hands**. It reads, explains,
cites, and — when you tell it to — writes one specific reviewed thing. It is not
trying to design your board, and the moment it started trying, you would stop
being able to trust the parts that work.

[What it is, and what it is not →](/copperplane/what-it-is/)
