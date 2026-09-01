---
title: What it is, and what it is not
description: The scope boundary, stated plainly — what the app does, what it refuses to do, and what is simply not built yet.
---

Two minutes here will save you an install if this is not the tool you are
looking for.

## It is an advisor with hands

It reads things — datasheets, your installed KiCad libraries, your board file,
ERC and DRC output — and explains them, with sources. When you explicitly ask,
it writes one reviewed thing: a footprint into your open board, a symbol into a
`.kicad_sym` library, an enclosure into a file.

That is the whole shape. Everything below follows from it.

## What it does

| | |
| :--- | :--- |
| **Find a part** | Search a part number, get ranked candidates with sources and a confidence signal. A misspelling produces a *did you mean* card you confirm — never a silent substitution. |
| **Extract its pins** | Pin numbers, names and electrical types, with a record of which model produced them and when. |
| **Explain what it needs** | Cited design guidance from the real datasheet, grouped by concern, each item traceable to a page. |
| **Find or make a footprint** | Search your installed KiCad libraries, your own saved library, and curated community libraries. Generate one from datasheet package dimensions when nothing fits. |
| **Guide connections** | Per-pin notes on decoupling, protection and power for a part you have saved. |
| **Explain checker output** | Run ERC or DRC through KiCad's `kicad-cli` and translate the results into plain language with suggested fixes. |
| **Build an enclosure** | Generate a printable body with standoffs and an optional lid from your board's real outline and mounting holes. Preview in 3D, export STEP or GLB. |
| **Ask, with sources** | A scoped chat panel on every area, grounded in that area's real state — cited datasheet pages, real ERC/DRC findings, your own stated project intent. Save a good answer as a durable note instead of losing it in a transcript. |
| **Keep all of it** | Projects, parts, symbols and footprints as readable files on your disk, reusable across projects. |

## What it will not do

These are decisions, not gaps. They are not on the roadmap.

**It does not draw your schematic.** No net creation, no wiring, no symbol
placement. The Schematic area shows you a part and tells you how to connect it;
you do the connecting in KiCad.

**It does not place or route.** No autoplacement, no autorouting, no push-and-
shove. Both are explicitly out of scope.

**It does not edit your board.** It reads a board and explains what is wrong.
The one write it performs is injecting a footprint you asked for, after showing
you exactly what it will write and waiting for you to confirm.

**It does not decide what screen you are on.** Typing into a search box searches.
Typing into a chat asks a question. No text input in this app is a command line
that guesses at your intent — an earlier version worked that way, it was wrong,
and it was deleted rather than improved.

**It does not silently correct you.** Ambiguity surfaces as a choice you make,
with sources attached, even when the app is fairly confident. A silent
substitution that happens to be right is the same mechanism as one that is
wrong.

**It does not claim a source it cannot produce.** Guidance that cannot be traced
to a real page in your real datasheet is dropped rather than kept and softened.

## What is not built yet

Different from the list above — these are real gaps, and some are being worked
on.

- **Schematic symbol injection into a live KiCad session.** Footprint injection
  into an open board works; symbols need a KiCad version whose IPC API supports
  schematic documents, which does not exist yet. Symbol *export* to a
  `.kicad_sym` library works today.
- **Reading your schematic's contents.** KiCad's live IPC has no path-resolution
  call for schematic documents at all — confirmed against the real API, not
  assumed. ERC therefore needs you to pick the file; DRC can target whatever
  board you have open.
- **Windows and Linux builds.** They compile and their test suites run in CI on
  all three platforms, but no release publishes them yet, and the live CAD
  integration has never been verified anywhere but one Mac.
- **Enclosure refinements** like cutouts for connectors, fastener and latch
  suggestions, or telling you that your board is missing mounting holes. All
  wanted; none built.

## Who it is for

Someone who designs boards in KiCad, prints or machines a case for them, and
would rather spend the afternoon on the design than on scrolling a PDF and
retyping coordinates. It assumes you know what a decoupling capacitor is for. It
does not assume you have memorised where in a 230-page document this particular
manufacturer chose to mention the brown-out threshold.

If you want something that designs the board for you, this is not it, and it is
not trying to become it.

[Install →](/copperplane/install/)
