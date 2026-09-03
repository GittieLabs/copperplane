---
id: SPEC-336
title: "First-Run Onboarding & Launch Experience"
status: Completed
type: Feature
created: 2026-09-02
last_updated: 2026-09-03
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-336-first-run-onboarding-and-launch.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-336: First-Run Onboarding & Launch Experience

## 1. Executive Summary & Goals

*   **High-Level Goal:** A first-time user should be walked to a working configuration, and every
    launch after that should start somewhere deliberate rather than in an arbitrary project.

*   **Business / Technical Value:** Three separate problems, all at the front door.

    **Settings is the onboarding surface, and it is not one.** A new user's first screen is the
    full Settings page: five provider records with API-key fields, provider kinds
    (`anthropic`/`openai_compat`/`google`), two model-role bindings, a GitHub token, a KiCad IPC
    socket path, and connectivity readouts. Every control is legitimate and none of it is a first
    step. As the maintainer put it: *"I think this would feel overwhelming for a user who is trying
    to initially use the app."*

    **Nothing tells the user the app cannot actually work.** KiCad and FreeCAD are hard
    requirements — every check, every measurement and every enclosure runs through them — and a user
    can configure a provider, open the app, and discover their absence only by watching features
    fail one at a time. The fix is *telling them*, clearly and persistently; it is not locking the
    door (see the skip rule below).

    **Launch opens an arbitrary project.** `App.tsx` selects `names[0]` from `list_projects()`,
    which is `sorted(...)` — so it opens the **alphabetically first** project, not the most recently
    used one. Stable, and meaningless. The maintainer's concern is exactly right: *"It's possible
    that the project could have moved, is corrupted, or isn't the project the user expected to
    open."* There is also no way to close a project once opened — only to select a different one.

*   **The flow, as specified by the maintainer:**

    1.  **Welcome screen** — app logo, and two paths.
    2.  **Managed** — API keys and model choices maintained by the hosted service. **Shown but
        disabled, marked "coming soon"**: `SPEC-320` and `SPEC-404` are both still Draft and the
        backing service is unfinished. Visible because it is the intended default, disabled because
        it does not yet exist.
    3.  **Self / local** — the user maintains providers and models. Offers **guided** or **manual**
        (which is today's Settings screen, unchanged).
    4.  **Guided: add a provider.** Choose one of the four supported providers, enter its API key,
        with a link to the docs page for obtaining a key *for that provider*. Guided setup applies
        the recommended settings rather than exposing every control.
    5.  **Guided: check KiCad and FreeCAD.** If either is missing from its default location, offer a
        path picker — they are frequently installed elsewhere. If genuinely absent, say so plainly
        and **let the user continue anyway**.
    6.  **Then the main app.**

*   **Every step is skippable, and the wizard never blocks entry.** This reverses the first draft of
    this spec, which halted on missing tools with "no visible bypass". The maintainer reconsidered,
    and the reasoning is decisive:

    > *"Blocking the user may not be the answer. We could replace this with banner messages to let
    > the user know about missing requirements and still let the user get to the main app and fix
    > later. A user may also be unsure about providing an api key and really want to see more before
    > deciding... Its really no different than the manual setup where a user still has to setup
    > before using and they do it at their own pace."*

    That last point settles it on consistency alone: **the manual path never gated anyone.** A user
    who chooses "manual setup" lands in Settings with no key and no tools configured and the app
    lets them proceed. Gating only the guided path would punish precisely the user who asked for
    help, and would make "guided" the more restrictive choice — the opposite of what it is for.

    Hesitancy about an API key is also a legitimate reason to look around first, not a state to be
    trapped in.

*   **Missing requirements are surfaced as persistent banners instead**, naming what is missing,
    what it stops working, and how to fix it — with a way back into the guided setup at any time. A
    banner that can be dismissed forever is the same failure as no banner; see §2.

*   **Also in scope:**
    *   **A no-project landing view** — what the app is, links to the repo and docs, and actions to
        create a new project or open an existing one. This becomes the launch view.
    *   **Stop auto-opening a project** on launch.
    *   **A close-project action**, which does not exist today.

*   **Non-Goals:**
    *   Building the managed service. `SPEC-404` owns that; this only renders the door and keeps it
        shut.
    *   Installing KiCad or FreeCAD. Detect, let the user point at them, or stop.
    *   Rewriting Settings. Manual setup goes there; guided setup is a different, narrower path.

> **Delivered in [CTX-336.1](../context/CTX-336.1-first-run-onboarding.md)** on 2026-09-03: the
> welcome screen with a disabled Managed path, guided setup, requirement banners, the landing view,
> and Close project. All seven §2 questions below are settled — five from evidence in the repo, two
> by the maintainer (pre-selected provider: `anthropic`; key links: each provider's own docs, no
> Copperplane docs site). §3's "the docs site does not exist" is therefore answered by *not linking
> one*, not by building it.
>
> The click-through found two defects no test could: a primary button using an invented colour
> token, invisible in both themes, and a config clobber that silently reverted the provider guided
> setup had just bound. Both are worth reading in that context's Plan Drift before building another
> surface that writes `config.json`.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **What "recommended settings" means concretely.** Guided setup promises to configure them.
    Today the defaults come from `llm_providers`' own seeded records, and both model roles point at
    one provider. Decide which provider is recommended and what each role binds to.
*   **How onboarding completion is recorded**, and what re-opens it. A config flag, or inferred
    from state (a usable provider plus both tools found)? Inferred is self-healing but can re-trigger
    on a transient failure; a flag can say "done" about a broken setup.
*   **How a banner persists, and what dismissing one means.** Per-session, until fixed, or
    collapsible-but-never-gone? The requirement is that a user can always find their way back to
    the guided setup; the mechanism is open.
*   **Where "finish setting up" lives** once the wizard has been skipped — the rail, a banner
    action, the menu, or all three.
*   **How a provider's docs link is chosen.** One page per provider, or one page with anchors.
*   **Whether the no-project view replaces or precedes the rail.** It is the launch view, but the
    rail also lists projects.
*   **What closing a project does** — return to the no-project view, and whether anything is
    persisted on the way out.

## 3. Known Constraints & Risks

*   **The docs site does not exist.** The only external URL in the app today is
    `GITHUB_REPO_URL` (`core/tauri-rust/src/menu.rs:85`). Every link this spec describes needs a
    placeholder that is honest about not being written yet, and its own context to create the pages
    — a link that 404s on first run is worse than no link.
*   **The risk moved when the gate was removed, it did not disappear.** A user can now reach the
    main app with no provider and no tools, where most features fail. The banners are the only thing
    standing between that and the "watching features fail one at a time" experience this spec exists
    to end — so they carry real weight and must be specific ("KiCad not found, so board checks and
    the enclosure cannot run"), not a generic "setup incomplete".
*   **A dismissible banner is the trap in a different costume.** Dismiss-forever returns the user to
    an unexplained broken app with no route back. Whatever dismissal exists must keep a way back to
    the guided setup permanently visible.
*   **A disabled "Managed" path invites clicking.** It must say *why* it is disabled and roughly
    when, or it reads as broken rather than forthcoming.
*   `SPEC-305`'s "visible-but-empty beats hidden" applies to the managed option and argues for
    showing it; it does **not** license showing a control that silently does nothing.
*   Detection is per-platform. `find_kicad_cli` and `freecad.get_version` are verified on macOS
    only; Windows and Linux paths are unverified, and onboarding is the worst place to discover that.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/src/App.tsx` — the launch view selection, and where the gate must sit.
*   `apps/tauri-ui/src/components/Settings.tsx` — the manual path, unchanged.
*   `apps/tauri-ui/src/components/Rail.tsx` — project list, and where a close action would live.
*   `services/python-daemon/llm_providers.py` — the seeded provider records and their kinds.
*   `services/python-daemon/daemon.py` — `freecad.get_version`, `kicad.get_version`,
    `daemon.get_capabilities`.
*   `services/python-daemon/kicad_cli.py` — `find_kicad_cli`, and its `configure(path_override=...)`.
*   `apps/tauri-ui/specs/SPEC-320-managed-account-signin-and-usage.md` — Draft.
*   `specs/SPEC-404-managed-hosted-access.md` — Draft; the service behind the disabled path.
*   `apps/tauri-ui/specs/SPEC-335-new-project-wizard.md` — takes over the moment a project is
    created; this spec ends where that one begins.

## 5. User & Interaction

*   **Product Stage:** Before any stage — installing, configuring, and opening the app.
*   **What the user is trying to accomplish:** Getting from a freshly installed app to one that can
    actually do something, without needing to know what a provider kind or a model role is.
*   **What the user sees and does:** On first run, a welcome screen with the app logo and two
    choices; then either a short guided sequence (pick a provider, paste a key, confirm KiCad and
    FreeCAD are found) or the full Settings screen. **Any step can be skipped** — a user who wants
    to look around before handing over an API key can, and lands in the app with a banner naming
    what is missing and what it stops working, plus a way back into setup whenever they are ready.
    On every later launch, a landing view describing the app with links to the repo and docs, and
    buttons to create or open a project — never an arbitrary project opened on their behalf.
