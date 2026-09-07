# Copperplane product video — script and shot list

**75 seconds.** A 60-second cut is marked at the end: drop segments 6 and 7.

Rewritten after the tutorial was written and the app was photographed, so every
number here is one the camera will actually show. The first version of this
script was written before any of that existed and guessed at all of them.

---

## The one story

A maker has a working breadboard. They draw a real PCB. KiCad tells them what is
wrong in a language they do not speak — and stays silent about the one thing that
would actually cost them a board order.

Everything below serves that. If a shot does not, cut it.

**The strongest ten seconds in this product is segment 5**, and it is the one no
competitor can copy by adding a feature: the part that is wired correctly, passes
every check, and was never going to work. Do not rush it.

It also got materially easier to shoot. Until `SPEC-113` the app only surfaced
that mismatch if the viewer thought to ask for it, so the segment needed a
question typed on camera. Now it is a finding in the list the previous segment
already ran, and the beat is a scroll.

---

## Before you record

*   Use `examples/Copperplane_Blink_LEDs` — the same project the tutorial ships,
    so a viewer can download it and follow. Its numbers are recorded in
    `examples/README.md`.
*   **Dark theme**, one window size, the rail showing only `Copperplane Blink LEDs`.
*   Have both windows pre-arranged. Never record a window being dragged.
*   Run each check once before recording so nothing shows a spinner you have to
    cut around.
*   Quit anything with notifications.

---

## The script

Each segment lists what to capture, what must be legible, and the line. The
**on-screen text** column matters more than the voiceover: most people will watch
this muted.

### 1 — The hook (0:00–0:06)

| | |
| :--- | :--- |
| **Capture** | The example board in KiCad's PCB editor, zoomed so the Arduino shield fills frame. No cursor. Hold still. |
| **Must be legible** | Nothing in particular. This is a picture, not information. |
| **On screen** | `Your breadboard works.` then `Now make it real.` |
| **Voiceover** | "Your breadboard works. Now you want a real board — and a case to put it in." |

Six seconds is generous for a hook. If the board does not read as *a real thing
somebody made* in the first two, reframe tighter.

### 2 — The wall (0:06–0:14)

| | |
| :--- | :--- |
| **Capture** | KiCad's own DRC dialog, run on the example board. Its raw violation list. Let it sit two beats too long. |
| **Must be legible** | `Annular width (board setup constraints min annular width 0.1000 mm; actual 0.0850 mm)` — the exact sentence. |
| **On screen** | *(nothing — let the dialog speak)* |
| **Voiceover** | "This is where a lot of projects stop." |

The discomfort is the point. Do not cut away early to be kind.

### 3 — The same files, read differently (0:14–0:24)

| | |
| :--- | :--- |
| **Capture** | Cut to Copperplane, project already linked, **PCB** tab. Click **Run Review**. Let the findings appear. |
| **Must be legible** | The first finding's heading: *Four pads on D1 have too little copper ring around their drill holes*. |
| **On screen** | `Same files. Same checks.` |
| **Voiceover** | "Copperplane reads the same files. Runs the same checks. Then tells you what they mean." |

KiCad reported that violation four times. Copperplane shows it once — that
compression is what this segment has to land, and the first finding's heading is
what carries it.

**Do not put a findings count on screen.** The list is five findings now: three
that explain DRC and two the next segment is about. Naming a number here sets up
"three findings from five violations", which segment 5 then contradicts.

### 4 — What it means (0:24–0:36)

| | |
| :--- | :--- |
| **Capture** | Cursor rests on the annular finding. Slow scroll through the explanation. |
| **Must be legible** | `0.085 mm` against `0.100 mm`, and the phrase about the plating cracking or the hole breaking loose. |
| **On screen** | `0.085 mm of copper. The rule says 0.100.` |
| **Voiceover** | "A plated hole needs a ring of copper around it. Yours is 0.085 millimetres where the rule says 0.100 — thin enough that the drill can break through it, on a board that looked fine in CAD." |

This is the segment that earns trust: it is specific, it names the part, and it
says what physically goes wrong.

### 5 — The thing KiCad cannot see (0:36–0:50)

| | |
| :--- | :--- |
| **Capture** | Stay on the same findings list and scroll to the bottom two. No typing, no chat panel — they are already there. |
| **Must be legible** | The D1 finding: the symbol `Device:LED` has 2 pins, the footprint `LED_THT:LED_D5.0mm-4_RGB` has 4 numbered pads. |
| **On screen** | `ERC passes.` `DRC passes.` `This part was never going to work.` |
| **Voiceover** | "And then there is this. A two-pin LED symbol, on a four-pin RGB footprint. Two pads connected to nothing, one resistor where three belong. Every check passes. It is not a rule violation — it is a part that was never going to work." |

**The three on-screen lines should land as three separate beats.** This is the
whole argument for the product in fourteen seconds: a checker tells you which
rules you broke; knowing what you actually built is a different question.

**This segment used to require typing a question on camera**, because the app
only surfaced the mismatch if you asked for it. It does not any more — the
finding is in the list you already ran. Shoot it as a scroll, not as a demo of
the chat. Someone who has to know the question in advance is not the person this
argument is for.

There is a **second** mismatch in the list, SW1, and it is deliberately not in the
script. It is the milder case — a tactile switch whose extra legs are internally
paired — and explaining why one is fatal and the other probably is not costs more
seconds than the segment has. Do not crop it out of frame; just do not narrate
it. A viewer noticing a second finding they were not told about reads as
thoroughness.

### 6 — The case (0:50–1:02)

| | |
| :--- | :--- |
| **Capture** | **Enclosure** tab. The pre-filled height. Click **Generate**. The 3D preview fills with the case around the board. |
| **Must be legible** | `14.1mm needed, set by D1` and the caveat that some components have no known height. |
| **On screen** | `Measured from your board.` |
| **Voiceover** | "It measures your actual board — outline, mounting holes, component heights — and sizes a case to fit. And it tells you what it could not measure, instead of guessing." |

That last clause is not filler. It is the difference between a tool you can trust
with a board order and one you cannot.

### 7 — Whose machine (1:02–1:10)

| | |
| :--- | :--- |
| **Capture** | Both windows side by side, KiCad unchanged. Then Copperplane's welcome screen with the mark. |
| **Must be legible** | The Copperplane mark. |
| **On screen** | `It reads your files. It doesn't take them over.` |
| **Voiceover** | "It does not replace KiCad or FreeCAD. It reads what you made, explains what it finds, and hands the decision back to you." |

### 8 — Close (1:10–1:15)

| | |
| :--- | :--- |
| **Capture** | The mark, still, with the URL. |
| **Must be legible** | `gittielabs.github.io/copperplane` |
| **On screen** | `Free. Open. Runs on your machine.` + URL |
| **Voiceover** | "Free, open, and it runs on your machine. Try it on a board of your own." |

---

## The 60-second cut

Drop segments 6 and 7. The arc still works: hook → wall → same files read
differently → what it means → the thing KiCad cannot see → close. You lose the
enclosure, which is a feature; you keep the argument.

Do not shorten segment 5 to save time. Shorten segment 4.

---

## Lines to avoid

*   **"AI-powered"**, **"leverage"**, **"seamless"**, **"revolutionise"**. A maker
    who has been burned by a bad board order does not want a revolution.
*   **"Never make a mistake again."** It finds some things. Say which.
*   **"Replaces KiCad."** It does not, and claiming it insults the audience.
*   Anything about the model, the provider, or the pipeline. Nobody watching cares
    which model read the datasheet.
*   Do not say **"simply"** or **"just"**. Nothing here is simple; that is why the
    tool exists.

## What to say if it is thirty seconds

Hook, segment 5, close. The mismatch is the only segment that is unique to this
product — everything else is *better*, that one is *different*.

---

## Capture notes

*   **Screen Studio**, following its own defaults for cursor smoothing. Turn the
    automatic zoom **off** for segments 2 and 4 — it fights with reading.
*   Record each segment separately. One continuous take invites a hunt for the
    good thirty seconds.
*   Cursor speed: slow enough that a viewer's eye can follow it to the thing being
    pointed at, and then a beat before anything moves.
*   Redact afterwards with `scripts/redact_screenshots.py` if any frame shows a
    file path — the project header and Settings both do.
*   Export at the platform's native aspect. A 16:9 export letterboxed into a
    vertical feed reads as somebody else's video.
