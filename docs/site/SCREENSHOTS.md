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

## All slots are filled

Fifteen images, every one dark, every one from the tutorial project with a clean rail.

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
| `schematic-erc.png` | ERC after the two `PWR_FLAG` symbols were removed |
| `board-check.png` | The DRC result list |
| `board-check-explained.png` | DRC rewritten in plain English |
| `ask-the-agent.png` | The agent answering the tutorial's own D1 question, sources visible |
| `component-search.png` | Ranked candidates with confidence |
| `part-detail.png` | A footprint card with the abbreviations box |
| `design-guidance.png` | Guidance with expandable citations |
| `enclosure.png` | The generation form with the measured height hint |
| `enclosure-3d.png` | The generated enclosure with the board seated inside |

## One capture was rejected

The Components tab shot (23:11:19) shows an empty search field, no results, and a leftover
NE555 as the only project part -- which contradicts the eight components the wizard had just
counted. It demonstrates nothing about searching. The earlier `component-search.png`, with five
ranked candidates, is kept instead.

## Known and deliberate

`guided-provider.png` reads "A provider is already configured (anthropic, google, perplexity)",
which a genuinely fresh install would never show. The key field is empty and nothing is exposed.
Reshoot only if the wording bothers you; the screen itself is the one a new user sees.

The enclosure 3D preview does not draw the Arduino or the switch. Both *reference* a KiCad 3D
model and neither `.step` file is in KiCad's macOS package, so there is nothing to draw. The
tutorial and the enclosure guide both say so rather than leaving a reader to wonder -- and it is
the same reason the height summary reads "6 still unknown".
