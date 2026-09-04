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

From the first walkthrough: dark, redacted, in `public/images/`.

| File | What it shows |
| :--- | :--- |
| `settings.png` | The whole Settings surface, keys showing only as "configured" |
| `component-search.png` | A real part search: five candidates with package and confidence |
| `part-detail.png` | The RGB LED footprint card, including the plain-English abbreviations box |
| `schematic-check.png` | The Schematic tab: board components, 3D-model status, the detected `.kicad_sch` |
| `board-check-explained.png` | DRC rewritten in plain English, with the 0.085mm against 0.100mm annular numbers |
| `enclosure.png` | The enclosure form, with the measured "14.1mm needed, set by D1" hint |

## Still needed, all dark

| File | What must be visible |
| :--- | :--- |
| `welcome.png` | The welcome screen: the mark, both paths. **The rail must be absent** -- that fix is in PR #393, so shoot this after it merges |
| `guided-provider.png` | Guided setup step 1, choosing a provider, before a key is typed |
| `guided-tools.png` | Guided setup showing KiCad and FreeCAD detected, with their real paths |
| `guided-done.png` | The final guided step, where setup finishes |
| `no-project.png` | The launch view with no project selected, showing the mark |
| `new-project.png` | Creating a project, at the point of picking the KiCad project to link |
| `project-linked.png` | `Copperplane_Blink_LEDs` linked, the link banner gone |
| `board-check.png` | The PCB check result list itself: four annular width errors and the unconnected GND, severities visible |
| `design-guidance.png` | Datasheet-derived guidance with its citations. The old one was deleted -- it showed the pre-rename product name |
| `library.png` | The library with a few real parts. Deleted for the same reason |
| `ask-the-agent.png` | The chat panel mid-answer about something on the board |
| `hero.png` | Wide, project open, rail and an area tab visible -- the one image that has to look like a product rather than a screenshot |

Three captures from the first walkthrough were rejected, in case the same
thing happens again: the glossary shot cut off mid-entry at `IDC` with other
desktop windows visible behind it; a part search caught mid-request with an
empty body; and an enclosure shot showing `Test Create Project 1` /
`Hello_World_Blinky` instead of the tutorial project.
