# Screenshot shot list

Not published — this file is documentation for whoever is holding the camera, not
for a reader of the site. Images themselves go in `public/images/` and are
referenced from a page as `/copperplane/images/<name>.png`.

## Status, 2026-09-12

**Seventeen of eighteen images are the 2026-09-11 re-shoot.** Two remain from 2026-09-04 because
nothing in that session captured them, and they are named below rather than left to be discovered.

### Still from 2026-09-04

| File | Why it was not replaced |
| :--- | :--- |
| `new-project-review.png` | The wizard's steps 1-3 were captured; **step 4 of 4, "Reviewing your project"**, was not. That step is the shot — the wizard's own check pass, with parity, component count and the ERC/DRC counts. |
| `settings.png` | Not captured, and **probably does not need to be**. `Settings.tsx` last changed 2026-09-03 and `ProviderConfigEditor` on 2026-08-31, both before the capture, so nothing that screen renders has moved since. Worth an eye before the next release; not a retake. |

> **A correction, recorded because it was asserted twice.** An earlier version of this file said the
> board-house library had moved into Settings and that `settings.png` was therefore wrong about the
> screen's contents. **It is not in Settings.** `HouseLibrary` renders inside `FabricationProfile`,
> which renders inside `BoardAdvisor` — the **PCB tab**. The contact sheet used to triage these shots
> showed "Board houses" under the PCB tab, and the claim was written anyway.

### Never captured, and not yet referenced by any page

These surfaces were photographed on 2026-09-11 and are sitting in the capture folder, but adding
them means **editing a page to reference them** — `test_docs_images.py` fails an image nobody uses,
in both directions. That is a docs change rather than a screenshot change, so it is listed and not
done.

*   The suggested-parts card populated, with real suggestions against the tutorial project.
*   The board-house library, and a house selected with the comparison table showing what differs
    from KiCad's own defaults.
*   The footprint glossary — *"What the abbreviations mean"* — expanded on a real part.
*   KiCad's own footprint libraries appearing in search results beside saved parts.
*   Overview at `board_only` and `both_checked`, if the guided path ever wants its own page.

### The hero

Retaken 2026-09-12 at 00:29, showing Overview at the `complete` state — a reading that was
unreachable until `CTX-343.3` fixed the card going stale, and whose evidence line was a word-for-word
copy of its own heading until the same branch fixed that. Both are right in this capture.

## The pipeline the raw captures need

Recorded because the raw captures do **not** match the set already here, and finding that out costs
an hour.

1.  **Redact first, at full resolution.** `scripts/redact_screenshots.py` needs `pytesseract`, which
    is in none of this repo's virtualenvs — and must not be added to `.build-venv`, which is what
    freezes the shipped sidecar. Make a throwaway venv outside the repo. Of the fifteen shots
    processed on 2026-09-12, **six** carried the username.
2.  **Crop away the drop shadow.** `Cmd+Shift+4` + Space captures a soft shadow and a transparent
    surround; nothing already in `public/images/` has either. The window is where alpha is fully
    opaque — crop to that bounding box, then flatten onto black.
3.  **Resize to 2560 wide**, which is what the existing images are.
4.  **Save as a palette PNG.** A flat dark UI loses nothing visible. 256 colours suits most shots;
    text-dense screens need fewer to come down — 128 for `schematic-erc`, 96 for `design-guidance`,
    64 for `ask-the-agent`. Check the small grey body text at 1:1 for banding before accepting it;
    at 64 colours it was still crisp.

`ask-the-agent.png` is the extreme case: a full agent answer, so nearly the whole frame is small
text. Retaken 2026-09-12 with the answer fitting in one window, and it needs **48 colours** to come
in at 379KB. Checked at 1:1 — the text is still crisp there, and a dark UI with light text has far
fewer distinct colours than the palette count suggests.

## Dark theme, everywhere

Decided, not a per-shot preference: **the docs use the dark theme only.** The
app is dark-first, the mark reads better on dark, and a page whose images
alternate theme looks careless. Light captures exist in the first walkthrough
and are deliberately unused.

Set the theme explicitly in Settings rather than relying on the OS, so a
capture taken next week matches one taken today.

## How to capture

*   **Use the tutorial project**, `Copperplane_Blink_LEDs`, for everything
    except the Settings and Library shots.
*   **One window size throughout.** Roughly 1400x900.
*   Capture the **whole window**, title bar included. Several shots in the first
    walkthrough were cropped mid-page, which reads as a fragment rather than a
    screen.
*   Watch the bottom edge: a card clipped halfway looks like a bug in the app
    rather than the end of a screenshot.
*   PNG, ideally under 400 KB.

## The file path no longer needs your attention

`scripts/redact_screenshots.py` blurs it out afterwards:

```bash
python scripts/redact_screenshots.py <capture-dir> --secret <username>
```

It OCRs each capture, blurs every match, reads the result back, and fails if
the string survived. It also reports any image it could barely read, so
"nothing found" cannot quietly mean "could not look". **API keys it does not
know about** -- check those yourself.

Raw captures are gitignored wherever they land. The chosen ones get cropped
into `docs/site/public/images/`.

## What each existing image shows

Eighteen images, every one dark, every one from the tutorial project with a
clean rail. Read this with the status section at the top — several of these are
now historical records rather than current screens.

| File | Shows |
| :--- | :--- |
| `hero.png` | The Overview tab: the KiCad link, the plain-English build description, the ask box |
| `welcome.png` | First launch: the mark, both paths, no rail |
| `guided-provider.png` | Guided setup step 1, provider chosen, key field empty |
| `guided-tools.png` | Guided setup step 2, KiCad and FreeCAD found with their real paths |
| `no-project.png` | The launch view with nothing selected |
| `new-project.png` | The wizard linking a `.kicad_pro` |
| `new-project-review.png` | The wizard's own check pass -- parity, component count, ERC and DRC counts |
| `schematic-check.png` | Board components with per-part 3D-model status |
| `schematic-erc.png` | The schematic check reporting power_pin_not_driven, which the example project ships with |
| `board-check.png` | The board check result list -- **five** findings, three explaining DRC and two symbol/footprint mismatches |
| `board-check-explained.png` | DRC rewritten in plain English |
| `ask-the-agent.png` | The agent answering the tutorial's own D1 question, sources visible |
| `component-search.png` | Ranked candidates with confidence |
| `part-detail.png` | A footprint card with the abbreviations box |
| `design-guidance.png` | Guidance with expandable citations |
| `enclosure.png` | The generation form with the measured height hint |
| `enclosure-3d.png` | The generated enclosure with the board seated inside |

## One capture was rejected (2026-09-04 session)

The Components tab shot (23:11:19) shows an empty search field, no results, and a leftover
NE555 as the only project part -- which contradicts the eight components the wizard had just
counted. It demonstrates nothing about searching. The earlier `component-search.png`, with five
ranked candidates, is kept instead.

## Known and deliberate

The enclosure 3D preview does not draw the Arduino or the switch. Both *reference* a KiCad 3D
model and neither `.step` file is in KiCad's macOS package, so there is nothing to draw. The
tutorial and the enclosure guide both say so rather than leaving a reader to wonder -- and it is
the same reason the height summary reads "6 still unknown".
