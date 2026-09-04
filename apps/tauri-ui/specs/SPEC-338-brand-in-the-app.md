---
id: SPEC-338
title: "The Brand Inside the App: Logo and the Copperplane Green"
status: Draft
type: Feature
created: 2026-09-03
last_updated: 2026-09-03
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-338-brand-in-the-app.md"
parent_spec: "SPEC-317-theme-system.md"
child_specs: []
user_facing: true
---

# SPEC-338: The Brand Inside the App: Logo and the Copperplane Green

## 1. Executive Summary & Goals

*   **High-Level Goal:** Make the app look like the product it is. The logo appears where a person
    first meets Copperplane, and the brand green earns a real, small job in the interface — enough
    to tie the app to its own identity, not enough to repaint it.

*   **Business / Technical Value:** A complete brand kit already exists and ships in the repo —
    `brand/`, Rev A, drawn 2026-08-25, with generated SVG lockups, app icons, a favicon, and a
    palette documented down to contrast ratios. **The application uses none of it.**

    Two specific gaps, both verified rather than asserted:

    1.  **The logo appears nowhere in the UI.** Nothing under `apps/tauri-ui/src` references
        `brand/`, a lockup, or a mark. The icons wired into `core/tauri-rust/icons` give the app a
        Dock and taskbar identity; the moment the window opens, that identity disappears.
    2.  **The brand green appears nowhere either — but a *different* green does.**
        `index.css` defines `--color-success: #34d399`, Tailwind's emerald-400. The brand's greens
        are Solder mask `#0B5C34`, Copperplane green `#10743F`, Signal `#178F4E`, and Bright
        `#4FC17E`. So the one green a user does see is not the product's green, which is worse
        than having no green at all: it reads as a palette nobody chose.

*   **This is partly unbuilt `SPEC-336`, not new scope.** That spec's §1 says the first screen is a
    *"**Welcome screen** — app logo, and two paths"*, and its §5 repeats *"a welcome screen with
    the app logo"*. `CTX-336.1` shipped a text `<h1>` and nobody noticed, because a heading that
    says "Welcome to Copperplane" satisfies every test that could be written about it.

*   **Where it belongs, per the maintainer:** the first-run wizard, and the home screen when no
    project is selected. Both are moments with room and nothing else competing.

*   **Non-Goals:**
    *   **Not a redesign.** `SPEC-317`'s neutral greyscale is deliberate and stays. This adds an
        accent and a mark; it does not restyle surfaces, text, or the rail.
    *   **Not brand asset work.** `brand/tools/build.py` generates everything from script, and
        `brand/README.md` is explicit that files are not edited by hand. If a size or variant is
        missing, it is generated there, not drawn here.
    *   **Not marketing copy.** `SPEC-408` owns what the app *says*; this owns what it looks like.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Which green, for what.** The brand documents four, with contrast ratios and explicit
    warnings: Signal and Copper "both fall under 4.5:1 on white ... fine for fills, rules, and
    large display type, and wrong for body text", and Bright `#4FC17E` is specified for "mark and
    links on dark surfaces". The app is dark-first with a light mode, so this is at least a pair of
    tokens, not one — and `SPEC-317`'s own rule is that every colour is defined for both themes.
*   **What the green is actually *for*.** Candidates, in increasing order of risk: the focus ring;
    links; the primary button (`--color-accent`, currently near-white/near-black). Repainting every
    primary button green is the largest visible change in the app and the easiest to get wrong,
    and `CTX-336.1` already records what happens when an accent's foreground is not thought
    through — an invisible button in both themes.
*   **Whether `--color-success` should become a brand green.** Tempting, and probably wrong:
    success/warning/danger are a semantic set, and making one of them the brand colour means a
    green check and a green button carry different meanings in the same interface.
*   **Which lockup, where.** `svg/lockup-horizontal.svg` and its `-on-dark` variant, `stacked`, and
    the bare `mark`. The theme can be light, dark, or system — so this needs the same treatment as
    every other themed asset, and a mark that is invisible in one theme is the `text-on-accent`
    failure again in a different medium.
*   **How an SVG gets into the app at all.** Nothing in `apps/tauri-ui` imports one today. Vite can
    inline or serve it; a Tauri build must not reach outside its own bundle. Settle the mechanism
    once, because the docs site (`SPEC-408`) will need the same assets.

## 3. Known Constraints & Risks

*   **`brand/` is generated, and lives outside `apps/tauri-ui`.** Referencing it across the module
    boundary, or copying files in, is a decision with a maintenance consequence either way: a copy
    goes stale silently when Rev B is generated.
*   **A colour that only exists in one theme is a shipped defect, and this repo has one on record.**
    `CTX-336.1` Deviation 9: `text-on-accent` was not a token, so a button rendered black-on-black
    in light and white-on-white in dark. `apps/tauri-ui/tests/themeTokens.test.ts` now guards that
    class, and any new token must be defined in **both** blocks or it will fail.
*   **Contrast is a real constraint, not a preference.** The brand's own table rules Signal and
    Copper out for body text. Using one anyway would be choosing brand over legibility for the
    audience `SPEC-408` describes as most likely to give up.
*   **The logo is the one thing on screen a user cannot act on.** It costs vertical space on two
    screens whose whole job is to get someone moving. Big enough to be identity, small enough not
    to be a splash screen.

## 4. Module Map & Reference Links

*   `brand/README.md` — the palette, the contrast table, and the rule that assets are generated.
*   `brand/svg/` — `lockup-horizontal`, `lockup-horizontal-on-dark`, `lockup-stacked`, `mark`,
    `mark-on-dark`, and small variants.
*   `apps/tauri-ui/src/index.css` — the token blocks, defined once per theme.
*   `apps/tauri-ui/src/components/Welcome.tsx` — `SPEC-336`'s first screen, where §1 already said
    the logo goes.
*   `apps/tauri-ui/src/components/NoProjectLanding.tsx` — the launch view.
*   `apps/tauri-ui/tests/themeTokens.test.ts` — the guard any new token has to satisfy.
*   `apps/tauri-ui/specs/SPEC-317-theme-system.md` — parent; owns the token model.

## 5. User & Interaction

*   **Product Stage:** First run, and every launch without a project open.
*   **What the user is trying to accomplish:** Nothing, at that instant — which is the point. These
    are the two moments where the app is asking them to begin, and the only two where it has their
    attention without a task competing for it.
*   **What the user sees and does:** The mark, at a size that reads as identity rather than
    decoration, on the welcome screen and the launch view. Elsewhere the app is unchanged except
    that its accent is finally the product's own green — visible enough to connect the app to its
    icon, its README and its docs site, and quiet enough that nobody notices it as a colour scheme.
