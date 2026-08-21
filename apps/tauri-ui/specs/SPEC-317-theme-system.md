---
id: SPEC-317
title: "Theme System: Light, Dark, and System Mode"
status: Draft
type: Feature
created: 2026-08-20
last_updated: 2026-08-20
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-317-theme-system.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-317: Theme System: Light, Dark, and System Mode

## 1. Executive Summary & Goals
*   **High-Level Goal:** Let the user choose Light, Dark, or System appearance instead of being
    locked into the current dark-only design, with System following the OS preference live.
*   **Business / Technical Value:** Real, user-stated starting point: "Not everyone will want the
    dark mode design." A hardcoded-dark-only UI is a real accessibility/preference gap for any user
    whose OS or eyes prefer a light interface; this closes it with a semantic token layer that also
    pays down the "every color is a raw Tailwind literal" debt found during the pre-planning audit.
*   **Non-Goals:**
    *   Not syncing native Tauri window chrome (titlebar) to the theme choice — confirmed with the
        user, out of scope for this pass. `core/tauri-rust`/`tauri.conf.json` are untouched.
    *   Not persisting the preference through the Rust-owned config store (`SPEC-106`) — confirmed
        with the user: this is a pure UI concern with no secrecy or daemon need, so it lives in
        `localStorage` only, not `app_config_dir()`/`daemon.configure`.
    *   Not making the 3D enclosure viewer's canvas background theme-reactive — `EnclosureViewer.tsx`'s
        `VIEWER_BACKGROUND_COLOR` was tuned for material contrast against the mesh, independent of
        app chrome; left theme-inert this pass (see §3).

## 2. System Architecture & Design Choices
*   **Design Rationale:** Confirmed via a pre-planning audit (grep + direct file reads, not
    assumed): all 13 non-test component files in `apps/tauri-ui/src` hardcode dark-only Tailwind
    color classes directly in JSX (~470 occurrences total), zero `dark:` variant usage anywhere,
    zero CSS custom properties, and no `tailwind.config.*` at all — this is Tailwind **v4.3.3**,
    CSS-first (`index.css` was a single `@import "tailwindcss";` line before this spec). **Decided:
    CSS custom properties defined via Tailwind v4's `@theme` block in `index.css`, swapped at
    runtime via a `data-theme` attribute on `<html>` plus a `prefers-color-scheme` media-query
    fallback for System mode.** `@theme`'s base values are the existing dark palette (so no visual
    change until a user opts into something else); a light override block layers on top under
    `:root[data-theme="light"]`, and a `@media (prefers-color-scheme: light)` block guarded by
    `:not([data-theme="dark"])` handles System mode following the OS live. This is the natural fit
    for a v4 CSS-first project with no JS config to hook a `darkMode` setting into, and avoids
    hand-adding a `dark:` twin to every one of the ~470 existing class occurrences.
*   **Data Flow / Interactions:** The preference (`'light' | 'dark' | 'system'`) is read/written in
    `localStorage` only (see Non-Goals) via a new `apps/tauri-ui/src/lib/theme.ts`. A small inline
    blocking script in `index.html`, run before the React root mounts, reads the stored preference
    synchronously and sets `data-theme` immediately to avoid a flash of the wrong theme. A
    `useThemePreference()` hook then takes over reactive control — applying the preference on
    change and subscribing to `matchMedia('(prefers-color-scheme: dark)')`'s change event so System
    mode updates live while the app is open, with no reload needed.
*   **Cross-Module Impacts:**
    *   `apps/tauri-ui` only — every component with hardcoded color classes gets its class names
        remapped to the new semantic tokens; `SPEC-303`'s Settings UI gains the actual Light/Dark/
        System control.
    *   No impact on `core/tauri-rust` (native chrome sync is a confirmed non-goal) or
        `services/python-daemon` (the preference never reaches the daemon).

## 3. Known Constraints & Risks
*   **Known Issues / Technical Debt:** The sweep is large but mechanical — 13 files, ~470 hardcoded
    class occurrences, all drawn from a finite, already-inventoried palette (11 neutral shades + 5
    accent tokens). One pre-existing inconsistency found during the audit (`text-green-400` used
    once where every other success color is `text-emerald-400`) gets folded into the same semantic
    `success` token as part of this sweep, fixing it as a side effect.
*   **Gotchas & Hazards:**
    *   **`apps/tauri-ui/src/components/ViolationsList.tsx`** has a `_SEVERITY_COLOR` object mapping
        severity strings to Tailwind class *strings* (not JSX literals) — a JSX-only codemod would
        miss it; the sweep must cover it as plain text, same class-name mapping.
    *   **`apps/tauri-ui/src/components/EnclosureViewer.tsx`**'s `VIEWER_BACKGROUND_COLOR` is a raw
        hex fed directly into the Three.js canvas background, outside Tailwind's class system
        entirely — explicitly left theme-inert this pass (Non-Goals above), not silently forgotten.
    *   **Flash of wrong theme on load** is a real risk without the `index.html` inline script,
        since React/JS-driven theme application only happens after hydration.
    *   Exact light-mode hex values need picking during implementation, not invented in this spec —
        keep contrast ratios reasonable against the same relative scale (surface lighter than base,
        borders readable, danger/success/warning legible on a white surface).

## 4. Module Map & Reference Links
```text
[SPEC-300](SPEC-300-product-ia-interaction-model.md)
   └── [SPEC-317](SPEC-317-theme-system.md)
```
*   [SPEC-300: Product IA & Interaction Model](SPEC-300-product-ia-interaction-model.md)
*   [SPEC-303: Settings UI](SPEC-303-settings-ui.md) — the real home for the new Appearance control.
    `SPEC-106`'s config store is deliberately not used (see §1 Non-Goals) — the preference is
    `localStorage`-only.

## 5. User & Interaction
*   **Product Stage:** Settings, per `SPEC-303` — a new "Appearance" section alongside its existing
    sections.
*   **What the user is trying to accomplish:** Real, user-stated starting point — use the app in a
    light appearance, or follow their OS's own light/dark preference automatically, rather than
    being forced into the current dark-only design.
*   **What the user sees and does:** Opens Settings, finds a new "Appearance" section with a 3-way
    Light / Dark / System control. Selecting one takes effect immediately across the whole app (no
    restart); System tracks the OS appearance live, including if the OS setting changes while the
    app is still open. The choice persists across app restarts (`localStorage`) and the app never
    flashes the wrong theme on load.
