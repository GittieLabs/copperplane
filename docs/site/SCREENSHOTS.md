# Screenshot shot list

Not published — this file is documentation for whoever is holding the camera, not
for a reader of the site. Images themselves go in `public/images/` and are
referenced from a page as `/copperplane/images/<name>.png`.

## Status, 2026-09-11

Eighteen images, all captured **2026-09-04**. Eleven are dead, four are probably
fine, and the app has grown surfaces since that have never been photographed at
all. Each claim below is tied to the commit that invalidated the shot, so this
section can be re-derived rather than trusted.

### Dead: the component behind them changed

| File | Invalidated by |
| :--- | :--- |
| `hero.png` | `SPEC-343` — Overview is a different screen now: the reading of where the project stands, the considerations callout, what you got right, the intent editor |
| `welcome.png` | `CTX-338.1` — the Copperplane mark on the launch screen |
| `no-project.png` | `CTX-338.1` — the same mark on the no-project landing |
| `board-check.png` | `SPEC-340` — the board-house picker and the fabrication summary banner |
| `board-check-explained.png` | `SPEC-340` — same, plus `ViolationsList` changes |
| `schematic-erc.png` | `SPEC-340` — `SchematicAdvisor` and `ViolationsList` |
| `component-search.png` | `SPEC-334` (KiCad's own libraries in results) and `SPEC-306` (a dead datasheet link became a live search) |
| `part-detail.png` | `SPEC-334.2` glossary, `CTX-339.1` review persistence |
| `enclosure.png` | `SPEC-326` — the labelled bounding solids |
| `enclosure-3d.png` | `SPEC-326` — same |
| `settings.png` | `SPEC-342` — the board-house library lives here now |

**`welcome.png` and `no-project.png` are worth a note.** They were captured at
**23:26** on 2026-09-04; `CTX-338.1`, the commit that put the mark on those two
exact screens, landed at **23:39**. Thirteen minutes. The shots are of the
screens the commit was about, taken just before it.

### Probably fine — check, do not assume

`guided-provider.png`, `guided-tools.png`, `new-project.png`,
`new-project-review.png`, `schematic-check.png`, `design-guidance.png`,
`ask-the-agent.png`. No component behind them has changed since the capture.
Compare against the running app before keeping them.

### Never captured: surfaces that did not exist on 2026-09-04

These are the gap that matters, because the site cannot show the app's most
distinctive feature at all.

| Needed | What to set up |
| :--- | :--- |
| **Overview with considerations** | Link `Copperplane_Blink_LEDs`. It raises R1's placeholder value and the `+5V`-on-`VIN` finding with no setup at all. The most important missing shot on the list. |
| **What you got right** | Same screen — D1's series resistor, with the "checked here" line visible underneath. Frame both together if they fit. |
| **The guided-path toggle** | Same screen, showing that it can be turned off. |
| **The intent editor** | Overview, with the supply and current-budget fields. Leave them empty; empty is the honest default state. |
| **Board-house picker** | PCB tab with a house selected, so the banner shows what changed against the generic profile. |
| **The board-house library** | Settings. Show more than one house, so the picker reads as a library rather than a setting. |
| **KiCad's own libraries in search** | Components tab. A query returning both your saved parts and KiCad's own footprints, so the merge is visible. |

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

## One capture was rejected

The Components tab shot (23:11:19) shows an empty search field, no results, and a leftover
NE555 as the only project part -- which contradicts the eight components the wizard had just
counted. It demonstrates nothing about searching. The earlier `component-search.png`, with five
ranked candidates, is kept instead.

## Known and deliberate

The enclosure 3D preview does not draw the Arduino or the switch. Both *reference* a KiCad 3D
model and neither `.step` file is in KiCad's macOS package, so there is nothing to draw. The
tutorial and the enclosure guide both say so rather than leaving a reader to wonder -- and it is
the same reason the height summary reads "6 still unknown".
