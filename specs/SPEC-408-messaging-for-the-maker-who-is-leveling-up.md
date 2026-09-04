---
id: SPEC-408
title: "Messaging, Onboarding Content & the Product Video, for the Maker Levelling Up"
status: Draft
type: Feature
created: 2026-09-03
last_updated: 2026-09-03
target_version: v0.4.0
location: "specs/SPEC-408-messaging-for-the-maker-who-is-leveling-up.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-408: Messaging, Onboarding Content & the Product Video, for the Maker Levelling Up

## 1. Executive Summary & Goals

*   **High-Level Goal:** Say who this is for, to the people it is for, in the places they arrive —
    the README, the docs site, a downloadable first project, and a 60-90 second video — so that
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
*   **The docs site does not exist.** `SPEC-336` §3 already records this as a live constraint:
    *"The only external URL in the app today is `GITHUB_REPO_URL`"*, and guided setup links to
    provider docs precisely because a Copperplane docs page would 404. Settle where it is hosted
    and how it is built before writing pages for it.
*   **What the 60-90 second video shows, in order.** Ninety seconds is roughly 200 spoken words and
    perhaps five screens. Decide the single story before writing the script; the failure mode is a
    feature tour that shows eight things and lands none.
*   **How images and GIFs are produced and kept current.** Screen Studio on macOS is the chosen
    tool. A screenshot of a UI that has changed is worse than no screenshot, and this repo changes
    its UI weekly — so settle what gets captured, at what size, and how a stale one is noticed.

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
    to a download without a paragraph about IPC. A 60-90 second video showing one real project going
    from a schematic they did not draw to a check they can understand and an enclosure that fits. A
    quick-start project they can open in one click, with something mildly wrong in it, so the app
    has something true and useful to say the first time they press a button. Docs whose first
    screen of every page is the outcome, with the depth below it for when they want it. And, for
    the Windows and Linux user particularly, a clear invitation that says what is unverified on
    their platform and that a report is the most valuable thing they can send back.
