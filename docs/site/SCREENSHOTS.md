# Screenshot shot list

Not published — this file is documentation for whoever is holding the camera, not
for a reader of the site. Images themselves go in `public/images/` and are
referenced from a page as `/copperplane/images/<name>.png`.

## Every existing image has to be retaken

All six images currently in `public/images/` were captured on 2026-08-24 and are
unusable, for two independent reasons:

1. **The window title bar reads "Hardware Agent Studio".** That is the superseded
   product name, live on the docs site right now. `test_readme_claims.py` fails
   the build if that string appears in any page's prose; it cannot read a PNG,
   which is exactly how this survived the rename.
2. **They predate the brand colour** (`CTX-338.1`). Every primary button in them
   is the old near-white/near-black accent, not Copperplane green, and the app
   now shows the mark on its launch and welcome screens.

They also show a different project (`test 1`, an NFC reader) rather than the
tutorial project.

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

## Already placed

| File | Source | Notes |
| :--- | :--- | :--- |
| `hero.png` | tutorial capture | The Schematic tab on the real project, full window |
| `board-check.png` | tutorial capture | The DRC result list with its findings |
| `schematic-erc.png` | tutorial capture | ERC after the two `PWR_FLAG` symbols were removed |
| `ask-the-agent.png` | tutorial capture | The agent answering the tutorial's own D1 question, sources visible |
| `design-guidance.png` | tutorial capture | Guidance with expandable citations |
| `new-project.png` | tutorial capture | Linking a KiCad project |
| `component-search.png` | tutorial capture | Ranked candidates with confidence |
| `settings.png` | first walkthrough | Whole Settings surface, keys only as "configured" |
| `part-detail.png` | first walkthrough | RGB LED footprint card with the abbreviations box |
| `schematic-check.png` | first walkthrough | Schematic tab, board components, detected `.kicad_sch` |
| `board-check-explained.png` | first walkthrough | DRC rewritten in plain English |
| `enclosure.png` | first walkthrough | Enclosure form with the measured 14.1mm hint |

## Two things to fix before these are final

**Scratch projects are in the rail on 9 of 24 captures**, `hero.png` included: `Test`,
`Test Create Project 1`, `Test No Project`, and a second `Blink LED Tutorial` beside the real
`Copperplane Blink LEDs`. It reads as a developer's machine rather than a product. Removing them
("Remove from list") and re-shooting the affected screens is the fix; nothing else can reach it,
because the rail is in the pixels.

**One project is named inconsistently.** `board-check.png` shows `Blink LED Tutorial` while the
tutorial prose and every other shot say `Copperplane Blink LEDs`. A reader following along will
notice.

Both are cosmetic and neither blocks publishing. They are the difference between "screenshots of
the app" and "screenshots of the product".

## Still needed, all dark

Five slots remain, all of them onboarding, which needs `onboarding_completed` reset to reach:

| File | What must be visible |
| :--- | :--- |
| `welcome.png` | The welcome screen: the mark, both paths, **no rail** |
| `guided-provider.png` | Guided setup step 1, choosing a provider, before a key is typed |
| `guided-tools.png` | Guided setup showing KiCad and FreeCAD detected, with their real paths |
| `no-project.png` | The launch view with no project selected, showing the mark |
| `library.png` | The library with a few real parts |

`first-run.md` carries `<!-- screenshot pending -->` markers where the first three go, so the
guard stays green and the gap stays visible.
