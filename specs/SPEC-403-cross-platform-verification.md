---
id: SPEC-403
title: "Cross-Platform Verification: Turning One Machine Into Three"
status: Draft
type: Module
created: 2026-09-05
last_updated: 2026-09-05
target_version: v0.5.0
location: "specs/SPEC-403-cross-platform-verification.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: false
---

# SPEC-403: Cross-Platform Verification: Turning One Machine Into Three

## 1. Executive Summary & Goals

*   **High-Level Goal:** Establish what "this works on Windows" and "this works on Linux" actually
    mean for this project, get evidence for both, and record it somewhere that stays true.

*   **The gap, stated exactly.** Every automated suite runs on macOS, Linux and Windows on every
    pull request — 1,143 daemon tests and 837 frontend tests, all three platforms. What those
    suites do not touch is the only part that is genuinely platform-specific: **finding and driving
    KiCad and FreeCAD.** Locating a KiCad install, connecting to its IPC socket, resolving
    `kicad-cli`, driving `freecadcmd` headlessly, and every path assumption underneath. Nearly
    every context file in this repository ends with a sentence admitting it ran on exactly one
    machine, macOS on Apple silicon, and each of those sentences is true.

*   **Why now.** `v0.4.0` publishes six installers across four targets, every one checksummed and
    provenance-attested, with an install page that tells a person how to verify what they
    downloaded. The distribution problem is solved. The verification problem is untouched, and the
    two are no longer coupled — anybody can now get the app onto a Windows machine in under a
    minute.

*   **Why it has been cited before it existed.** `README.md` says "`SPEC-403` tracks turning that
    gap from a hope into a checked fact." `ROADMAP.md` names it three times, `CTX-407.3` defers to
    it, and `SPEC-408` was written to feed it. It has been load-bearing in prose while being
    nothing at all. That is its own small lesson about traceability.

*   **Non-Goals:**
    *   **Not buying hardware.** The maintainer has no Windows or Linux machine and this spec does
        not assume one appears. If it did, this would be a checklist rather than a spec.
    *   **Not CI coverage.** More tests on more runners do not help: a GitHub runner has no KiCad
        install, no IPC server, and no FreeCAD. The gap is precisely what CI cannot reach.
    *   **Not a support process.** This is about obtaining evidence, not about answering users.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **What counts as verified.** "It worked" is not evidence. The unit is probably a named path —
    *KiCad discovered without an override*, *IPC connected*, *DRC ran and returned findings*,
    *FreeCAD generated an enclosure* — each with a platform, a version, and a person attached. The
    list of paths has to be written down before anyone is asked to walk it, or every report answers
    a different question.

*   **Where the answers live.** A closed issue is not a record; nobody reads issue history to find
    out whether Linux works. Candidates: a table in the docs, a file in the repo, or a generated
    page. Whatever it is, an unverified path must be as visible as a verified one — the value is in
    the empty cells.

*   **Who is asked, and how.** `.github/ISSUE_TEMPLATE/platform_report.yml` already exists and is
    linked from four documentation pages. Whether that template asks the right questions, given the
    named-path list above, is part of this spec rather than assumed.

*   **What the app can tell us itself.** Settings already has **Copy Diagnostics**, and
    `daemon.ready` already reports what it found for KiCad, `kicad-cli` and FreeCAD with the exact
    paths checked. A report that carries that output is worth several that describe it in prose.
    Whether to make that one click from a failure is a real design question.

*   **What to do with a partial answer.** Someone reporting "KiCad found, IPC connects, FreeCAD not
    found" has given genuinely useful evidence for two paths and none for the third. The record has
    to hold that without either discarding it or rounding it up to "Linux works".

*   **Whether the machines can be rented rather than found.** `ROADMAP.md`'s own entry names three
    routes this spec should weigh rather than skip: self-hosted runners with real CAD installs, a
    documented manual checklist, and containerised KiCad. The first two are plausible; containerised
    KiCad reaches `kicad-cli` and the file-based paths but not the IPC server or a real desktop
    install's discovery, which is most of what is unverified. A route that exercises the easy half
    and reports success would be worse than no route.

*   **Whether a virtual machine counts.** A Windows VM on the maintainer's Mac could exercise most
    of this. It is not the same as a real user's machine — different graphics stack, different
    install locations, no accumulated cruft — but it is available today and nobody has tried it.
    Deciding whether VM evidence is recorded as equal, lesser, or separate is a decision, not a
    detail.

## 3. Known Constraints & Risks

*   **The maintainer cannot verify this spec's own subject.** Every other spec here was closable by
    the person who wrote it. This one is not, which makes it the only spec whose completion depends
    on strangers.

*   **A report is a snapshot, and versions move.** Evidence that KiCad 9 on Windows 11 worked in
    September says nothing about KiCad 10, and this project already discovered mid-session that the
    maintainer's own machine had moved to KiCad 10 while the docs said 9+. Any record needs the
    versions in it or it decays into folklore.

*   **Silence is ambiguous.** Nobody reporting a Windows problem could mean it works, or that
    nobody has tried. The record must distinguish "verified working" from "no evidence either way",
    and the second is the honest default for everything today.

*   **The paths most likely to break are the least likely to be reported.** A user whose KiCad is
    not found may conclude the app is broken and uninstall it rather than file anything. The
    reporting route has to be reachable *from the failure*, not only from the docs.

## 4. Module Map & Reference Links

*   `services/python-daemon/kicad_cli.py`, `kicad_bridge.py`, `freecad_bridge.py` — the discovery
    and driving code whose platform branches have never run outside macOS.
*   `services/python-daemon/daemon.py` — `daemon.ready`, which already reports what was found and
    which paths were checked.
*   `.github/ISSUE_TEMPLATE/platform_report.yml` — the existing reporting route.
*   `apps/tauri-ui/src/components/Settings.tsx` — **Copy Diagnostics**.
*   `specs/SPEC-408-messaging-for-the-maker-who-is-leveling-up.md` — written explicitly to feed this
    spec: the acquisition channel for the people who can close it.
*   `specs/SPEC-402-release-signing-and-auto-update.md` — the distribution this depends on, now
    delivering checksummed and attested builds for all four targets.
