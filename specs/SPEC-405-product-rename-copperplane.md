---
id: SPEC-405
title: "Product Rename to Copperplane"
status: Draft
type: Feature
created: 2026-08-25
last_updated: 2026-08-25
target_version: v0.2.0
location: "specs/SPEC-405-product-rename-copperplane.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-405: Product Rename to Copperplane

## 1. Executive Summary & Goals

*   **High-Level Goal:** Rename the product from Hardware Agent Studio to **Copperplane**
    everywhere a person can see it, and ship the new mark and app icon. The application's
    *identity* on disk stays exactly as it is: the same bundle identifier, the same keychain
    service, the same data directories, the same project state folder. A `v0.1.3` user who
    installs the renamed build finds their library, their API keys, and their linked projects
    where they left them.

*   **Business / Technical Value:** "Agent Studio" is the most crowded two-word phrase in software
    right now. Oracle, Google, Automation Anywhere, Workato, Algolia, Cognigy and Siemens all ship
    something by that name, and Orange Logic has a pending USPTO application (serial 99340137) on
    the bare mark in class 42 for AI SaaS. Nothing blocks the old name legally, but the only
    distinctive word in it was "Hardware", which is also the plainest description of the category.
    Copperplane is clean on USPTO, unclaimed on GitHub, and unused by any software product. A
    copper plane is also the solid ground or power layer of a PCB, so the name comes out of the
    user's own vocabulary rather than out of the AI-tooling vocabulary.

*   **Non-Goals:**
    *   **Changing the app's identity or data locations.** Explicitly out of scope, and §2.1 names
        the exact strings that must not move.
    *   **Any migration code.** There is nothing to migrate precisely because nothing moves. If a
        future spec decides to change the bundle identifier, that is a separate piece of work with
        its own user-facing consequences.
    *   **A custom domain for the docs site.** `base` changes from one project path to another;
        moving to `copperplane.dev` is a separate decision.
    *   **Renaming the GitHub organisation.** GittieLabs stays.
    *   **Re-cutting `v0.1.3` under the new name.** The rename lands in the next release.

## 2. System Architecture & Design Choices

### 2.1 Design Rationale: two classes of string, and only one of them moves

Every occurrence of the old name falls into exactly one of two categories, and the whole design of
this spec is the line between them.

**Identity strings must not change.** These five are load-bearing. Each one is a key that existing
user data is filed under, and changing any of them silently orphans that data. They stay verbatim,
including their old spelling.

| Where | String | What breaks if it moves |
| :--- | :--- | :--- |
| `core/tauri-rust/tauri.conf.json` `identifier` | `com.gittielabs.hardware-agent-studio` | Tauri derives `app_data_dir` and `app_config_dir` from it. Moving it hides the user's `storage/` root, which is the project and parts library, and breaks the updater's continuity with installed `v0.1.x` builds. |
| `core/tauri-rust/src/secrets.rs` `SERVICE` | `hardware-agent-studio` | The OS keychain service every API key is stored under. Moving it makes every saved key unreadable, with no error a user could interpret. |
| `services/python-daemon/daemon.py` (data dir) | `hardware-agent-studio` | The daemon's own data directory, resolved independently of Tauri's. |
| `services/python-daemon/library_store.py` `_PROJECT_STATE_SUBDIR` | `.hardware-agent-studio` | **The riskiest one.** This dot-folder is written into the user's own project directories, alongside their KiCad files and quite possibly inside their git repo. Moving it means every already-linked project stops being recognised as linked. |
| `services/python-daemon/library_store.py` `_KICAD_MOD_GENERATOR` | `hardware-agent-studio` | Stamped into the `generator` field of every `.kicad_mod` this app has ever written. Changing it is not destructive, but it makes previously generated footprints indistinguishable from third-party ones. |

Each of these five gets a comment at its declaration site saying it is deliberately the old name
and pointing at this spec. The comment already at `library_store.py:912` is the model to follow.

**Presentation strings change.** Everything else: window titles, menu labels, `productName`,
package names, URLs, prose, issue templates, the About string, the icon set.

### 2.2 Rename inventory

75 tracked files, 177 occurrences. Grouped by what a change actually means:

| Group | Files | Nature |
| :--- | :--- | :--- |
| User-visible strings | `apps/tauri-ui/index.html`, `core/tauri-rust/src/menu.rs` (2), `apps/tauri-ui/src/lib/settings.ts`, `tauri.conf.json` window `title` | Straight replacement. `settings.test.ts` asserts the About string and moves with it. |
| Bundle naming | `tauri.conf.json` `productName` | See §3.2. Also a capitalisation fix: the current value is `hardware-agent-studio`, so the shipped bundle is literally `hardware-agent-studio.app`. New value is `Copperplane`. |
| Package names | `core/tauri-rust/Cargo.toml` (`name`, `description`, `authors`, `repository`), `docs/site/package.json` | Internal. `Cargo.lock` regenerates. |
| Sidecar binary name | `core/tauri-rust/src/daemon.rs` (4), `tauri.macos.conf.json`, `tauri.linux.conf.json`, `tauri.windows.conf.json`, `.github/workflows/release.yml` (3), `services/python-daemon/scripts/verify_sidecar.py` | **Atomic or nothing.** See §3.3. |
| Repository URLs | `.github/ISSUE_TEMPLATE/*` (3), `core/tauri-rust/src/menu.rs` `GITHUB_REPO_URL`, `tauri.conf.json` updater endpoint, `Cargo.toml`, `docs/site/astro.config.mjs` (2) | Must land in the same change as the GitHub repo rename. |
| Docs site | `docs/site/astro.config.mjs` `base` and `title`, 15 content pages, `public/images/NEEDED.md` | See §3.1. |
| Update manifest | `scripts/generate_update_manifest.py` docstring, `scripts/tests/test_generate_update_manifest.py`, `scripts/tests/test_check_release_version.py` | Test fixtures encode the old artifact names. |
| Network courtesy | `services/python-daemon/community_libraries.py` (2), `library_store.py` (1) | `User-Agent` sent to community library hosts. Safe, and worth doing so hosts see the real name. |
| Framework docs | `README.md`, `ROADMAP.md`, `PRODUCT-PLAN.md`, `CONTRIBUTING.md`, `SECURITY.md`, `NOTICE`, and 14 `CTX-*.md` / `SPEC-*.md` files | Prose. See §3.5 on the historical records. |

### 2.3 The mark and the icon set

The identity is drawn as a single copper trace routed into a C: an 8-unit grid inside a 64x64
board, a 45-degree miter at every corner, and a plated through-hole drilled at each terminal. The
app icon inverts it, so the tile is the copper plane and the routed channel exposes the substrate
underneath. Primary green is `#10743F`, the green of solder mask, at 5.85:1 on white.

Below about 20px the trace and the counter both fall under two pixels and the C fills in, so there
is a second drawing for small sizes with a wider mouth and a heavier trace. The generated icon set
already uses it for every asset at or below 48px. Do not regenerate small sizes by downscaling the
full mark.

Assets are pre-generated in `brand/app-icons/` and drop straight into
`core/tauri-rust/icons/`, replacing all 16 files, which are currently the stock Tauri placeholder.
The macOS `.icns` insets the tile to 80.5% of its canvas per Apple's icon grid; the Windows and
Linux assets are full bleed, matching what `tauri icon` would produce.

Source SVGs, the palette, the usage rules and the generator scripts are in `brand/`. Every asset
is generated by `brand/tools/build.py`, so a colour or size change is a script edit and a re-run,
never a hand edit of an asset.

### 2.4 Cross-Module Impacts

*   `core/tauri-rust` — window title, menu labels, `productName`, Cargo metadata, sidecar
    resolution, updater endpoint, the full icon set.
*   `apps/tauri-ui` — document title, About string, and the test asserting it.
*   `services/python-daemon` — `User-Agent` strings only. **The two data-path constants in
    `library_store.py` and `daemon.py` are frozen.**
*   `docs/site` — base path, site title, every content page, every image URL.
*   `.github` — issue templates, release workflow artifact names.
*   `scripts` — update manifest generator and its tests.

**Upstream dependency:** the GitHub repository rename must happen in the same change window as the
URL edits, or the links ship broken. GitHub redirects the repo web and git URLs after a rename, so
existing clones keep working, but see §3.1 for the one thing it does not redirect.

## 3. Known Constraints & Risks

### 3.1 GitHub Pages does not redirect

Renaming the repository redirects `github.com/GittieLabs/hardware-agent-studio` to the new path.
It does **not** redirect `gittielabs.github.io/hardware-agent-studio`. That URL simply stops
resolving, and it is the URL printed in the `README.md` of every release published so far.

Consequences to accept or address in the context file:

*   `docs/site/astro.config.mjs` `base` becomes `/copperplane`.
*   Every screenshot reference changes from `/hardware-agent-studio/images/<name>.png` to
    `/copperplane/images/<name>.png`. `public/images/NEEDED.md` documents the old pattern and must
    be updated, or the next person to add a screenshot will follow the stale instruction.
*   The old docs URL is dead. If that matters, the mitigation is a custom domain, which is a
    separate decision and out of scope here.

### 3.2 A `productName` change renames the bundle

`productName` determines the `.app` bundle name on macOS and the binary name on Windows and Linux.
Going from `hardware-agent-studio` to `Copperplane` means:

*   The release artifacts change name, and `scripts/generate_update_manifest.py` plus
    `.github/workflows/release.yml` match artifacts by name. Both must be updated together with
    their test fixtures.
*   A user who installs the new `.dmg` by hand gets `Copperplane.app` sitting next to their
    existing `hardware-agent-studio.app`. Two apps, one bundle identifier, sharing one data
    directory. That is untidy but not destructive, and it is worth a line in the release notes.

**Unverified, and it needs to be verified before release:** whether Tauri's macOS updater handles a
`productName` change across versions cleanly, in place, at the existing install path. The updater
replaces the bundle at its current location; what it does when the incoming bundle has a different
name is not something this spec should assert without someone watching it happen. The context file
should carry a real `v0.1.3` install being auto-updated to the renamed build on a real machine, and
record what actually occurred, including if it turns out to be wrong about this.

### 3.3 The sidecar binary name is atomic or nothing

`hardware-agent-studio-daemon` appears in six places across three languages and two build systems:
the Rust resolver in `daemon.rs` (dev and release branches, four occurrences), all three
platform-specific `tauri.*.conf.json` `externalBin` entries, three `mv` commands in
`release.yml`, and `verify_sidecar.py`. Rename any subset and the app builds fine, then fails at
runtime when the supervisor cannot find its daemon.

Renaming this at all is optional. It buys nothing at runtime and carries this risk. A defensible
alternative is to leave the sidecar name alone and note it in the same place as the §2.1 identity
strings. The context file should make that call explicitly rather than defaulting into it.

### 3.4 A global find-and-replace will break this

This is the central hazard of this spec. `grep -rl` plus `sed -i` across the repo is the obvious
way to do a rename, it will appear to work, CI will very likely stay green, and it will orphan
every existing user's keys, library and linked projects.

Mitigation, in the context file:

*   A test in the Rust suite asserting `SERVICE == "hardware-agent-studio"`.
*   A test in the Python suite asserting `_PROJECT_STATE_SUBDIR == ".hardware-agent-studio"` and
    the daemon data directory name.
*   A test asserting `tauri.conf.json` `identifier` is unchanged.

Those three tests are the durable artifact here. They outlive the rename and stop a future
well-intentioned cleanup from doing the damage this spec is designed to avoid.

### 3.5 Historical records should not be rewritten

14 `CTX-*.md` and `SPEC-*.md` files mention the old name. Those are dated records of work that
happened under that name, and this repo's whole argument for its framework is that the records are
honest. Rewriting them to say Copperplane makes them say something that was not true at the time.

Recommendation: leave the body of every completed `CTX-*.md` alone, and add the rename to
`ROADMAP.md` §3.4 as this spec's entry so the graph explains itself. `README.md`,
`PRODUCT-PLAN.md`, `CONTRIBUTING.md`, `SECURITY.md` and `NOTICE` are living documents and do get
updated.

### 3.6 Sequencing

The repo rename and the URL edits must land together. Suggested order:

1.  Land the code, docs and icon changes on a branch, with the URLs already pointing at the new
    repo path (they will 404 until step 2).
2.  Rename the repository on GitHub.
3.  Merge.
4.  Confirm the docs site publishes at the new base path and every screenshot resolves.

Note that `develop` currently has uncommitted work on `feat/CTX-319.6-review-design-menu` plus four
untracked spec files. This rename touches 75 files and should start from a clean tree.

## 4. Module Map & Reference Links

```text
[Root Spec](SPEC-000-architecture-overview.md)
   └── [This Spec](SPEC-405-product-rename-copperplane.md)
          ├── [CTX-405.1](../context/CTX-405.1-rename-app-and-icons.md)     (proposed)
          ├── [CTX-405.2](../context/CTX-405.2-rename-docs-site.md)         (proposed)
          └── [CTX-405.3](../context/CTX-405.3-identity-guard-tests.md)     (proposed)
```

Related: [SPEC-402](SPEC-402-release-signing-and-auto-update.md) owns the release pipeline and the
updater this spec's `productName` change touches. [SPEC-106](../services/python-daemon/specs/SPEC-106-configuration-secrets-store.md)
owns the keychain service name frozen in §2.1.

Brand assets and the identity sheet live in `brand/`, with `brand/README.md` as the usage rules.

## 5. User & Interaction

*   **Product Stage:** Every stage. This is the frame around the whole product rather than one
    surface inside it: the icon in the Dock, the name in the menu bar, the title of the window, the
    About box, and the docs site the user lands on before they ever install anything.

*   **What the user is trying to accomplish:** Recognising and finding the thing they installed.
    An existing user needs to open the app after updating and find their library and keys intact,
    with no sense that something was taken from them. A new user needs to search for the product
    and land on it rather than on Oracle's or Google's Agent Studio.

*   **What the user sees and does:** The app in the Dock shows a green routed-C icon instead of the
    stock Tauri placeholder. The menu bar, window title and About box read Copperplane. Nothing
    else about their workflow changes: the same projects open, the same parts library loads, the
    same API keys are already in Settings. Per `CONTRIBUTING.md`, this is verified by a person
    updating a real `v0.1.3` install and confirming exactly that, not by a route returning the
    right string.
