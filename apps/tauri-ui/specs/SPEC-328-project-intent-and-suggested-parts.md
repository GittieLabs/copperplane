---
id: SPEC-328
title: "Project Intent & Suggested Parts"
status: Draft
type: Feature
created: 2026-09-05
last_updated: 2026-09-05
target_version: v0.6.0
location: "apps/tauri-ui/specs/SPEC-328-project-intent-and-suggested-parts.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-328: Project Intent & Suggested Parts

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give the Overview tab the job `SPEC-313` deliberately left undecided: a
    place to say what you are building, before you have anything, that the rest of the app then
    knows about.

*   **The user this is for arrives with nothing.** Every other surface assumes a KiCad project
    already exists. The audience `SPEC-408` describes — someone moving from breadboards to a first
    PCB — often arrives with an idea and no files. Today the app has nothing for them but a
    project-creation wizard that immediately asks for a `.kicad_pro`.

*   **A general parts list, not a vendor search.** "10K resistor, 100µF capacitor, ESP32-S3 devkit"
    is the useful answer. The user then searches for real parts through the flow that already
    exists. What this adds is not procurement — it is knowing what kind of thing you need before
    you know which one.

*   **Intent is already stored and already underused.** A project record carries `intent`, and the
    tutorial's own project holds *"a blinking led controlled by a pushbutton with logic from Arduino
    UNO"*. Nothing downstream consults it. Carrying it forward so the library, schematic, PCB and
    enclosure stages know what the project is *for* — does it need a lid, will a connector exit the
    case — is most of this spec's value and costs nothing new to store.

*   **Non-Goals:**
    *   **Not part selection.** It suggests categories; the user chooses parts.
    *   **Not a schematic.** Nothing here draws or wires anything.
    *   **Not a supplier integration.** `SPEC-203` covers that ground and found it mostly closed.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **What the clarifying conversation actually is.** "The app asks clarifying questions" can mean
    a form, a chat, or a wizard step. The app already has a chat surface per area and a four-step
    project wizard; adding a fifth shape would be a mistake.

*   **What a suggested part *is*, as data.** A string, or a record with a category and a rationale
    that the search flow can consume directly? The second is more useful and much more work, and
    determines whether a suggestion can become a real part in one click or is only prose.

*   **How intent reaches the other stages.** It is stored on the project today. Whether downstream
    surfaces read it directly, or it is summarised into something narrower (needs a lid, has an
    off-board connector), decides whether this is a data model change or a prompt change.

*   **What happens when the description is vague.** "a robot" is a plausible first answer and
    yields nothing useful. Whether the app pushes back, offers examples, or accepts it and moves on
    is a product decision that sets the tone of the whole surface.

*   **Whether it survives contact with a linked project.** Once a real KiCad project is attached,
    the parts list is at best advisory and at worst contradicts what is actually on the board. The
    Overview tab has to age gracefully from "what I intend" to "what I have".

## 3. Known Constraints & Risks

*   **This is the surface most able to invent plausible nonsense.** A parts list is exactly the
    output a language model produces fluently and wrongly. Unlike datasheet guidance, there is no
    document to cite — which means the honest framing is "a starting point to check", and the UI
    has to carry that without becoming an apology.

*   **`SPEC-302` is the cautionary tale.** A user-facing surface that was mechanically correct and
    the wrong thing to build, because nobody asked what the user was doing. This spec is a §5-first
    spec or it should not be built.

*   **An empty Overview tab is not a crisis.** The current tab is thin, but thin and honest beats a
    surface that generates conversation for its own sake. If the answer is a text field and a
    stored sentence, that is a legitimate outcome.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/specs/SPEC-300-product-ia-interaction-model.md` — parent; owns what each tab is
    for.
*   `apps/tauri-ui/specs/SPEC-313-*.md` — left the Overview tab's purpose open on purpose.
*   `services/python-daemon/specs/SPEC-206-*.md` — the agent surface a clarifying conversation
    would run through.
*   `services/python-daemon/library_store.py` — `intent` on the project record, stored today and
    read by nothing.
*   `apps/tauri-ui/specs/SPEC-335-new-project-wizard.md` — the existing four-step flow this must
    not duplicate.
