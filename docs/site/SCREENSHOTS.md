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

## How to capture

*   **Use the tutorial project**, `Copperplane_Blink_LEDs`, for everything except
    the Settings and Library shots. A reader following the tutorial should see
    what the tutorial shows.
*   **Dark theme, for all of them.** The app is dark-first, the mark on dark is
    the stronger of the two, and a docs page that alternates themes shot to shot
    reads as carelessness. Set it explicitly in Settings rather than relying on
    the OS, so a later capture matches.
*   **One window size throughout.** Roughly 1400×900 is enough for the rail plus
    a content area without the text becoming unreadable when scaled down.
*   Save as PNG, ideally under 400 KB.

## Before saving, check every frame for

*   API keys, including partially visible ones.
*   **File paths containing your username.** `/Users/<you>/repos/PCBs/...` appears
    in the project header and in Settings. Black it out, or move the project
    somewhere neutral before shooting.
*   Client or employer project names in the projects rail.
*   Anything in a background window, if the capture is not window-cropped.

## Where to put raw captures

Drop unedited captures in `screenshots/raw/`. They are reviewed there, then the
chosen ones are cropped, renamed and moved into `docs/site/public/images/`.
Nothing in `screenshots/` is committed.

## The list

`Page` names the page that will reference the image. A blank page means the
image is wanted but its page is still being written.

### Onboarding — the two paths a new user can take

| File | What must be visible | Page |
| :--- | :--- | :--- |
| `welcome.png` | The welcome screen: the Copperplane mark, and both paths offered | first-run |
| `guided-provider.png` | Guided setup choosing an AI provider, before a key is entered | first-run |
| `guided-tools.png` | Guided setup showing KiCad and FreeCAD detected, with their real paths | first-run |
| `guided-done.png` | The final guided step, the point where setup is finished | first-run |
| `settings.png` | The Settings screen, as the manual path reaches it. **Retake** | first-run |

### Getting a project in

| File | What must be visible | Page |
| :--- | :--- | :--- |
| `no-project.png` | The launch view with no project selected, showing the mark | first-run |
| `new-project.png` | Creating a project, at the point of picking the KiCad project to link | tutorial |
| `project-linked.png` | A project with `Copperplane_Blink_LEDs` linked and the link banner gone | tutorial |

### The checks — the tutorial's core

| File | What must be visible | Page |
| :--- | :--- | :--- |
| `board-check.png` | The PCB check on `Copperplane_Blink_LEDs`: the four annular width errors and the unconnected GND, with severities showing. **Retake** | board-checks, tutorial |
| `board-check-explained.png` | One annular width violation with its explanation open — the "what does this actually mean" moment | board-checks, tutorial |
| `schematic-check.png` | The schematic check after the two `PWR_FLAG` symbols are removed: `power_pin_not_driven` and `pin_not_connected` | board-checks, tutorial |

### The rest of the features

| File | What must be visible | Page |
| :--- | :--- | :--- |
| `component-search.png` | A part search with real results. **Retake** | find-a-part |
| `part-detail.png` | A footprint's detail view, with the package glossary visible | footprints |
| `design-guidance.png` | Datasheet-derived guidance with its citations. **Retake** | design-guidance |
| `enclosure.png` | A generated enclosure in the 3D preview. **Retake** | enclosure |
| `library.png` | The library with a few real parts in it. **Retake** | library / first-run |
| `ask-the-agent.png` | The chat panel mid-answer about something on the board | ask-the-agent |
| `hero.png` | Wide, project open, rail and an area tab visible — the one image that has to look like the product | index |
