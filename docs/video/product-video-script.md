# Copperplane product video — script

**Length:** 75 seconds (target), 90 hard ceiling.
**Capture:** Screen Studio, macOS. **Voice:** one narrator, unhurried.
**Audience:** a maker whose breadboard works and who has not yet made a PCB.

## The one story

A person has a board. Something is wrong with it, and KiCad has told them so in a language they do
not read. Copperplane translates, shows them where, and then sizes a case around the same board.

**Everything else is cut.** Ninety seconds is roughly 200 spoken words and five screens; a tour of
eight features lands none of them. Component search, the parts library, the community-library
import and provider settings are all real and all absent from this video.

## Script

| Time | On screen | Voiceover |
| :--- | :--- | :--- |
| 0:00-0:07 | The example project open in **KiCad**, schematic visible. Slow, no cursor movement. | "You built the circuit. It works on the breadboard. Now you want a real board — and a case to put it in." |
| 0:07-0:14 | KiCad's own DRC dialog, raw findings visible. Hold long enough to feel unhelpful. | "This is the part where a lot of projects stop." |
| 0:14-0:22 | Cut to **Copperplane**, project already linked. Click the **PCB** tab, then **Run Review**. | "Copperplane reads the same files KiCad does." |
| 0:22-0:38 | The finding list appears. Cursor rests on one finding; its plain-language explanation and the component it names are on screen. | "It runs the same checks — and then tells you what they mean. Which pad, on which part, and why it matters. Not 'unconnected item'." |
| 0:38-0:46 | Expand the switched-off-tests disclosure. | "It also tells you which tests were switched off, so a clean result can't quietly mean 'we didn't look'." |
| 0:46-0:56 | **Schematic** tab. Click a footprint name; the detail view opens with the plain-language reading. | "It reads the names, too. This one is a single row of four pads, two and a half millimetres apart, standing up off the board — which is why its height counts against your case." |
| 0:56-1:08 | **Enclosure** tab → Generate. The 3D viewer fills with a case around the board. | "And it measures your actual board — outline, mounting holes, component heights — to size an enclosure that fits it." |
| 1:08-1:15 | Cut back to KiCad, unchanged, both windows side by side. | "It doesn't replace KiCad or FreeCAD. It reads what you've made, explains what it finds, and hands the decisions back to you." |
| 1:15-1:20 | Copperplane's launch screen with the logo. URL on screen. | "Everything stays on your machine. It's free, it's early, and it's open." |

**Word count:** ~150. At an unhurried 130 wpm that is ~70 seconds of speech inside a 75-second cut,
which leaves room to breathe on the two silent beats (0:07 and 1:08).

## Lines to avoid

*   *"AI-powered"* anywhere. The audience cares that the answer is right, not how it was produced.
*   Naming the stack. No Tauri, no Rust, no daemon, no IPC. That belongs in the README's lower half.
*   *"Just"* — "just link your project", "just click generate". Nothing about this is *just* for
    someone who has never done it.
*   Any claim the app authors a schematic or a board. It does not, and the video must not imply it.

## What the recording needs

The demo depends on a project that has **real, mild problems**. A clean project produces "No
violations found", which makes the app look like it does nothing — and this is not hypothetical: the
maintainer's own schematic is clean, which is why nobody could tell whether the ERC explanation
worked until a broken one was made deliberately.

See [`example-project.md`](example-project.md) for exactly what that project must contain and how to
produce the defects, with measured results.

## Capture notes

*   **Two windows, one story.** KiCad appears at the start and the end. The middle is Copperplane
    alone.
*   **Slow the cursor.** Screen Studio's automatic zoom follows the pointer; a cursor that darts
    makes the zoom lurch. Move deliberately and pause before each click.
*   **Record at the window size the app is used at**, not full screen. Text has to be legible at
    whatever size the video ends up embedded.
*   **Dark or light, pick one and stay.** The app themes both ways; switching mid-video reads as a
    glitch.
*   **No API keys on screen.** The Settings screen is not in this video, and the provider name is
    not mentioned.
*   Capture each numbered row as its own take. Cutting between takes is easier than re-recording
    ninety unbroken seconds, and the two silent beats are natural seams.
