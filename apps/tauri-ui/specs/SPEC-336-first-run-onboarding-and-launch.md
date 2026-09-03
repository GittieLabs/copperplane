---
id: SPEC-336
title: "First-Run Onboarding & Launch Experience"
status: Draft
type: Feature
created: 2026-09-02
last_updated: 2026-09-02
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

    **Nothing checks that the app can actually work.** KiCad and FreeCAD are hard requirements —
    every check, every measurement and every enclosure runs through them — and a user can configure
    a provider, open the app, and discover that only by watching features fail one at a time. There
    is no gate.

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
        path picker — they are frequently installed elsewhere. If genuinely absent, state that both
        must be installed and **halt**: no progression to the main app, and no visible bypass.
    6.  **Then the main app.**

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

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **What "recommended settings" means concretely.** Guided setup promises to configure them.
    Today the defaults come from `llm_providers`' own seeded records, and both model roles point at
    one provider. Decide which provider is recommended and what each role binds to.
*   **How onboarding completion is recorded**, and what re-opens it. A config flag, or inferred
    from state (a usable provider plus both tools found)? Inferred is self-healing but can re-trigger
    on a transient failure; a flag can say "done" about a broken setup.
*   **What "no visible bypass" means in practice.** The Settings screen is reachable from the rail,
    and the native menu has its own entries. Halting means those cannot become an escape hatch.
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
*   **Halting on missing tools is a hard gate**, and hard gates strand people. A user whose KiCad
    lives somewhere unusual must be able to reach the path picker without first getting past the
    gate. Verify the picker itself cannot be blocked by the thing it exists to fix.
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
    FreeCAD are found) or the full Settings screen. On every later launch, a landing view describing
    the app with links to the repo and docs, and buttons to create or open a project — never an
    arbitrary project opened on their behalf.
