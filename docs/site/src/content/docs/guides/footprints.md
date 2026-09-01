---
title: Find or make a footprint
description: Search everything you already have, pull from community libraries, or generate from datasheet dimensions.
sidebar:
  order: 3
---

A part and its footprint are separate objects, because that is how KiCad models
them and how reality works — SOIC-8 is one land pattern shared by hundreds of
unrelated parts. So finding a footprint is its own step, and you can skip it: a
part with pins and a datasheet is useful before any footprint exists.

## Three sources, ranked

**Your installed KiCad libraries** — everything configured on your machine,
including the ~150 that ship inside KiCad itself. This is the first place to
look and usually the last. Requires KiCad installed and its API enabled.

**Your own saved library** — anything you previously saved or generated. Results
from both sources are merged and tagged so you can see which is which.

**Curated community libraries** — SparkFun and Espressif, searched through
GitHub's API. Optional, and you can supply your own GitHub token in Settings if
you hit rate limits. Imported files are stored **verbatim** rather than
re-derived, so what you keep is what they published.

:::caution[Attribution]
SparkFun's libraries are CC-BY-4.0, which requires attribution if you publish a
design using them. See [Attribution and licences](/copperplane/attribution/).
:::

## Generating one

If nothing fits, the app can build a footprint from the package dimensions in
your part's own datasheet — which extraction already captured, so no extra API
call is needed.

It **fails closed** for any package it does not recognise, rather than guessing
geometry. That is intentional: a plausible-looking wrong footprint costs a board
spin.

:::danger[Generated footprints are unverified]
A generated footprint is marked `verified: false` in your library, and that flag
means what it says: **nobody has checked it against a real part.** Open it in
KiCad's footprint editor and check the pad pitch, pad size and courtyard against
the datasheet's mechanical drawing before you commit it to a board.
:::

## Symbols

Symbols are generated from the extracted pins, laid out on KiCad's own 2.54 mm
grid, and exported to a real `.kicad_sym` library you can add to KiCad.

Parts with the same package and pin count converge on one shared symbol rather
than duplicating.

## Getting it onto a board

With a board open in KiCad and its API enabled, the app can inject a footprint
directly. It shows you exactly what it will write and does nothing until you
click **Confirm**. The write is a real KiCad transaction — it commits fully or
rolls back.

Injecting a **symbol** into a live schematic is not possible yet; KiCad's API
does not support schematic documents. Export to a `.kicad_sym` library and add
it in KiCad instead.
