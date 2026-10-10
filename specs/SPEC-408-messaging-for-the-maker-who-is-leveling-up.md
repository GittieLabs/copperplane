---
id: SPEC-408
title: "Messaging, Onboarding Content & the Product Video, for the Maker Levelling Up"
status: In-Progress
type: Feature
created: 2026-09-03
last_updated: 2026-10-10
target_version: v0.4.0
location: "specs/SPEC-408-messaging-for-the-maker-who-is-leveling-up.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-408: Messaging, Onboarding Content & the Product Video, for the Maker Levelling Up

> **Status note, 2026-10-09.** This spec read `Draft` while all six of its contexts
> (`CTX-408.1`–`CTX-408.6`) were `Completed` and merged — the README, the docs site, the voice pass,
> the tutorial catch-up, and two passes over the video script have all shipped. It is now
> `In-Progress` rather than `Completed` for one reason: **the product video has not been recorded.**
> `docs/video/product-video-script.md` is a shot list waiting on a camera, and its "Before you
> record" section is addressed to someone who has not yet rolled. Messaging that exists as a script
> is not messaging the audience has received, so this spec is not done.
>
> **2026-10-10:** `CTX-408.7` takes that last item on. It records three short captioned cuts instead
> of one narrated video (§2), and the agent shoots them by driving a production build of the app.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Say who this is for, to the people it is for, in the places they arrive —
    the README, the docs site, a downloadable first project, and three short videos (15s, 30s, ~60s) — so that
    someone moving from Arduino sketches and breadboards to their first custom PCB and enclosure
    tries the app instead of deciding it is not for them.

*   **Who this is actually for**, in the maintainer's words:

    > *"this product is here to help makers that need a copilot to move from arduino sketches and
    > breadboards to creating custom pcb and enclosures for their next level projects. This audience
    > might be intimidated by schematics and pcb layout and/or creating even a simple enclosure."*

*   **What the README says instead.** Its first sentence:

    > *"Copperplane is an open-source, local-first AI assistant for **hardware engineers** — one
    > workspace that bridges PCB design (KiCad) and mechanical CAD (FreeCAD), instead of a pile of
    > disconnected plugins."*

    followed immediately by Tauri, Rust, React, a long-running Python daemon, native IPC, headless
    FreeCAD, and five LLM providers. Every word is true. It addresses **hardware engineers**, opens
    on architecture, and assumes the reader already knows what a plugin pile feels like. A maker
    who has never drawn a schematic reads that and correctly concludes it is not aimed at them.

*   **What the app is actually for**, and the line the messaging has to hold: Copperplane **does
    not replace KiCad or FreeCAD**. It reads what you have, explains what it finds, and helps you
    decide. Every tutorial and every second of video has to demonstrate *aiding*, because a maker
    who expects it to draw the schematic will be disappointed by a product that is doing its job.

*   **The immediate need is users and validators, not contributors.** Stated plainly by the
    maintainer:

    > *"We need to attract Windows and Linux users to help with testing bc I don't have machines to
    > test those. While I do want contributors, I need users and validators more. And users can
    > become contributors."*

    This is not a preference; it is the repo's largest standing risk made concrete. Almost every
    context in this repo ends with a line like *"this ran on exactly one machine, macOS on Apple
    silicon"*, and `SPEC-403` exists precisely because nobody can say what happens on the other two
    platforms. **The messaging is the acquisition channel for the verification this project cannot
    otherwise buy.**

*   **Non-Goals:**
    *   **Not a rewrite of what the product does.** This changes how it is described, what is
        shipped alongside it, and who is addressed — not the app.
    *   **Not `CONTRIBUTING.md`'s job.** That document speaks to contributors and is correct for
        them. This is about the road before that one.
    *   **Not the in-app copy.** `SPEC-336` and `SPEC-337` own what the app says while running.
    *   **Not brand visuals.** `SPEC-338` owns the logo and the palette; this consumes them.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Whether this is one spec or several.** It carries five deliverables that share an audience and
    nothing else: the README, a quick-start project, tutorial projects, the docs site, and the
    video. Held together here because splitting them first is how the tone drifts between them —
    but it will need several contexts, and the first should probably be the README alone, since
    every other artifact quotes it.
*   **What the quick-start project actually is.** *"a quick start project they can download and use
    to create their first project easily."* Decide what it contains — a `.kicad_pro` with a
    schematic and board? a deliberately imperfect one, so the checks have something real to say? —
    where it lives, and how a user gets it. **The strongest version is a project with real, mild
    problems**, because a clean project makes the app look like it does nothing.
*   **Which strengths the tutorials demonstrate**, given they must show aiding rather than
    replacing. The honest candidates are the ones already proven: explaining a DRC or ERC finding in
    plain language, decoding a footprint name, and sizing an enclosure from a real board.
*   **What "approachable with depth underneath" means structurally.** A page that opens gently and
    grows technical, or separate tracks? The maintainer's framing — *"very approachable with depth
    there as they can read as they learn the app"* — suggests one page per task that begins with
    the outcome.
*   ~~**The docs site does not exist.**~~ **Wrong, and corrected 2026-09-03 by `CTX-408.1`.**
    `docs/site` is a real Astro Starlight project with **16 authored pages**, deployed by
    `.github/workflows/docs.yml`, and the README already links it. `SPEC-336` §3 states the
    opposite and this spec inherited it. The work here is therefore **editing an existing site**,
    not standing one up — a materially smaller job. Its current voice has the same problem as the
    README's: `why.md` opens on a reader who already has a microcontroller on a board and a
    230-page datasheet open. **Still open:** which pages get the approachable opening, and whether
    new pages are needed or existing ones re-led.
*   ~~**What the 60-90 second video shows, in order.** Ninety seconds is roughly 200 spoken words
    and perhaps five screens.~~ **The story is settled; the format changed on 2026-10-10
    (`CTX-408.7`).**
    - `CTX-408.6` settled the single story: the app speaks first (segment 3), then shows the part
      that breaks no rule and was never going to work (segment 5). That still holds, and the
      warning against a feature tour that shows eight things and lands none still applies.
    - What changed is the format. Instead of one narrated 60-90s screen recording, there are
      **three cuts — 15s, 30s and ~60s — from one shot list.** They have **captions and no
      sound**: no voiceover, no music.
    - Each finding is **pulled out of the real UI** as a card, rather than left in a full window
      for the viewer to find. A muted viewer scrolling a feed does not hunt for a warning.
    - The "200 spoken words" budget no longer applies. Captions are read, not heard, so it becomes
      about one short line every 2-3 seconds.
    - **Captions carry the whole argument, so they are part of the design.** They are burned into
      the frame at a size that reads on a phone, and each one stays up long enough to be read.
      Each cut also ships an `.srt` file for platforms that want one.
    - Every number in a caption is read off the captured frame it comes from, never copied from
      the script.
    - The 15s cut is hook, segment 3, segment 5, close: the two beats the script already ranked
      first.
*   **How images and GIFs are produced and kept current.** ~~Screen Studio on macOS is the chosen
    tool.~~ **Changed 2026-10-10 (`CTX-408.7`).**
    - The agent drives a production build of the app itself and captures stills with
      `screencapture -l`, which works while the window is covered.
    - Cap records only the few shots with real motion, with the screen cleared for each take.
    - Pullouts are composited from those real captures, never redrawn.
    The staleness concern stands, and has already bitten: the first test take showed a saved board
    check from before the SPEC-340 fix. So every saved result is re-run on the build being filmed,
    and every number in a caption is read off the captured frame it came from. Still open: how
    docs screenshots, which are dark, and the video, which is light UI on a dark background, are
    kept consistent.

## 3. Known Constraints & Risks

*   **The app is honest about being early, and the messaging must stay honest.** The README's
    current status line — *"early, under active daily development"* — is the right kind of claim.
    Softening the pitch for a less technical audience must not become overpromising to it, and this
    week alone produced five user-visible defects.
*   **Tutorials and screenshots rot.** Every one of them is a claim about a UI that is still
    moving. `SPEC-337` renamed two things in the header this week; any screenshot of that header is
    now wrong.
*   **A quick-start project ships someone else's files.** Licensing, provenance, and whether it
    must open cleanly in the reader's KiCad version are real questions, and KiCad file formats
    change between majors.
*   **Attracting non-technical users raises the cost of every rough edge.** The audience this spec
    targets is the audience least able to distinguish "this app is broken" from "my configuration
    is wrong" — which is exactly what `SPEC-336`'s banners and `SPEC-407` §5's degraded-build
    notice exist to address. Both landed this week; neither has been seen by a stranger.
*   **The maintainer cannot verify the platforms he is recruiting for.** Windows and Linux
    instructions will be written by someone who cannot run them. They must be written as such, and
    the first reports will be about the instructions rather than the app.

## 4. Module Map & Reference Links

*   `README.md` — the first thing anyone reads; currently addressed to hardware engineers.
*   `CONTRIBUTING.md` — the contributor path, deliberately unchanged.
*   `brand/` — lockups and palette for the site and video (`SPEC-338`).
*   `docs/video/product-video-script.md` — the segment-by-segment shot list all three cuts draw
    from, and the record of every number it has got wrong.
*   `context/CTX-408.7-motion-cuts.md` — how the cuts are captured and composited.
*   `apps/tauri-ui/specs/SPEC-336-first-run-onboarding-and-launch.md` — the first-run experience a
    new user meets, and the record that no docs site exists.
*   `specs/SPEC-406-contributor-local-builds.md` — the contributor build path, and the platform
    reports it asks for.
*   `ROADMAP.md` — `SPEC-403` Cross-Platform Verification Matrix, which this feeds.

## 5. User & Interaction

*   **Product Stage:** Before the app is installed, and the first hour after.
*   **What the user is trying to accomplish:** Find out, quickly, whether this thing will help them
    turn a working breadboard into a board they can order and a case they can print — without first
    having to learn what a courtyard, a netlist or a DRC rule is.
*   **What the user sees and does:** A README that opens with their problem in their words and gets
    to a download without a paragraph about IPC. Short, muted, captioned videos showing one real
    project going from a schematic they did not draw to a check they can understand and an
    enclosure that fits. A
    quick-start project they can open in one click, with something mildly wrong in it, so the app
    has something true and useful to say the first time they press a button. Docs whose first
    screen of every page is the outcome, with the depth below it for when they want it. And, for
    the Windows and Linux user particularly, a clear invitation that says what is unverified on
    their platform and that a report is the most valuable thing they can send back.
*   **The video viewer specifically** (added 2026-10-10, `CTX-408.7`):
    - They are scrolling a feed, usually with the sound off, and decide within about two seconds
      whether to stop.
    - They will not read a full app window to find the one line that matters, and they will not
      wait out a spinner.
    - So each cut opens on its strongest image, pulls each finding out of the UI and holds it until
      its caption can be read, and never shows waiting.
    - The 15s cut has to work for someone who watches only that. The longer cuts are for someone
      who stopped scrolling.
