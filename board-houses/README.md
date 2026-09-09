# Board house capability profiles

Numbers read off each vendor's own published capability page, recorded with the URL and the date
they were read. Import `board-houses.json` through **PCB → Board houses → Import from clipboard**.

## What these are, and what they are not

*   **Read from the vendor's page, not from anyone's memory.** Every value here has a `source_url`
    and a `recorded_on`. Nothing is inferred, averaged or filled in from a similar house.
*   **A field a vendor does not publish is absent, not guessed.** An absent field produces no rule,
    so the app checks nothing for it rather than checking against a number nobody stated. PCBWay
    publishes four of the nine; that is what PCBWay's entry contains.
*   **Every field arrives unconfirmed.** `confirmed_by_user` is false on all of them, because you
    have not checked them and we cannot check them on your behalf. The app says so on screen.
*   **They go stale.** Board houses change what they publish. The recorded date is shown next to
    every number, and the app warns when a set is over a year old.
*   **They are not a quote.** They are what the vendor says it can build, on the process named in
    each entry. A different process — heavier copper, more layers, a different finish — has
    different numbers, and these will be the wrong ones to check against.

## Process each entry describes

| House | Process as published |
| :--- | :--- |
| JLCPCB | 2-layer FR4, 1 oz copper |
| PCBWay | Standard PCB, 1–14 layers (not 2-layer specific) |
| OSH Park | Two-layer service |
| AISLER | 2-layer, 1.6 mm, 35 µm copper, HASL |

## Two things the nine-field schema cannot express

Recorded here rather than smoothed over, because both cost accuracy:

1.  **Vendors publish separate annular ring and drill minimums for vias and for plated through
    holes.** AISLER, for instance, requires 300 µm annular on a PTH but 200 µm on a via, and a
    0.5 mm PTH drill against a 0.3 mm via drill. The profile has one field for each, mapped to
    KiCad's via-oriented board setup key, so each entry records the value that field maps to and
    notes the other. Where they differ, the note is the accurate half.
2.  **Silkscreen-to-copper clearance is rarely published.** None of the four state one, so
    `min_silk_clearance` is absent from every entry — even though it is the rule that produced the
    largest single group of findings on the tutorial board.

## What these four say about the tutorial board

Measured 2026-09-09 against `examples/Copperplane_Blink_LEDs`, each house imported and run through
the real check:

| Checked against | Findings | Of which "would be built, quietly wrong" |
| :--- | :--- | :--- |
| KiCad's own defaults | 4 | 4 |
| PCBWay | 4 | 4 |
| OSH Park | 4 | 4 |
| AISLER | 6 | 4 |
| JLCPCB | 11 | 7 |
| **Bundled "Standard 2-layer process" template** | **27** | 7 |

### The template is far stricter than any real house, and one number explains most of it

The bundled template reports **27** findings where the strictest real house reports **11** and two
report nothing beyond KiCad's own four. That gap is not a rounding difference, and it is the exact
failure `SPEC-114` §3 named in advance:

> "A too-strict profile is worse than none. If a bundled profile is more conservative than the
> house's real capability, the app manufactures findings and spends the credibility this family
> runs on."

**Sixteen of the template's twenty-seven findings — 59% — come from `min_silk_clearance: 0.15`**
(fourteen `silk_overlap`, two `silk_over_copper`). **None of the four houses publishes a
silkscreen-to-copper clearance at all.** The single largest group of findings the feature produces
comes from a limit no board house states.

That is a product decision to take deliberately, not a bug to quietly patch: dropping it changes the
headline number `SPEC-114` §2.4 measured and the pitch is built on. It is recorded here so the
decision is made against the measurement rather than against the demo.
