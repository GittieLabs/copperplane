---
id: SPEC-406
title: "Contributor Local Builds & Signing Defaults"
status: Completed
type: Feature
created: 2026-08-26
last_updated: 2026-08-27
target_version: v0.1.4
location: "specs/SPEC-406-contributor-local-builds.md"
parent_spec: "SPEC-402-release-signing-and-auto-update.md"
child_specs: []
user_facing: true
---

# SPEC-406: Contributor Local Builds & Signing Defaults

## 1. Executive Summary & Goals
*   **High-Level Goal:** Make an unsigned, installable local build the **default** outcome of
    `tauri build` in a fresh clone, and document the contributor build path in `CONTRIBUTING.md`,
    which today describes only `tauri dev`. `createUpdaterArtifacts: true` moves out of the
    committed `core/tauri-rust/tauri.conf.json` and into a release-only config overlay that
    `.github/workflows/release.yml` merges explicitly. Nothing about what CI produces changes.
*   **Business / Technical Value:** Today every contributor's first `tauri build` fails, at the end
    of a full release-mode compile, because `createUpdaterArtifacts: true` makes the bundler demand
    `TAURI_SIGNING_PRIVATE_KEY` -- a secret that by design exists only as a GitHub Actions secret
    (`SPEC-402` §3: "never persisted anywhere else"). The failure is correct behaviour applied to
    the wrong audience: the one setting that is release-only is the one setting living in the file
    everyone shares. This was hit for real by the maintainer on 2026-08-26 while trying to check
    the macOS app menu bar, which only exists in a bundled `.app`, not under `tauri dev`.
    `CONTRIBUTING.md` §"Setting up" stops at `npx @tauri-apps/cli@2 dev` and never mentions
    bundling, so a contributor has no documented way to reach the surface they need to test --
    while the same file explicitly *asks* for Windows and Linux platform reports, which cannot be
    produced without an installable build.
*   **Non-Goals:**
    *   **Not a way for contributors to produce signed or update-capable builds.** Neither key can
        be shared, and neither has a useful local substitute. The Apple Developer ID belongs to the
        GittieLabs, LLC org account (Team `834C8Q72TG`) and is non-transferable. The updater
        keypair's entire purpose is to prove an update came from the project; the public half is
        pinned in `tauri.conf.json`'s `plugins.updater.pubkey`, so a contributor generating their
        own keypair produces artifacts the shipped app correctly rejects. **CI stays the only path
        to a distributable build, for maintainers too.**
    *   **Not Windows or Linux code signing.** Unchanged from `SPEC-402` §1 -- still a real,
        separate, not-yet-made decision.
    *   **Not making the frozen Python daemon a prerequisite of a local build.** `SPEC-401`'s
        committed placeholder sidecars already let the Rust crate compile and bundle without
        PyInstaller. This spec documents that boundary honestly; it does not move it.
    *   **Not a `Makefile`, `just` file, or wrapper script.** A documented one-line command is the
        deliverable. A wrapper is a second thing to keep in sync with `release.yml`.
        **Superseded by [SPEC-407](SPEC-407-sidecar-build-integrity.md) §2.3 on 2026-08-27.** The
        first half was falsified by evidence: the documented one-line command produces a broken
        app, seven different ways in one session. The second half is answered rather than
        overruled -- `release.yml` calls the same script, so it is the only implementation, not a
        second one. Left in place rather than deleted: the reasoning was sound when written, and
        what changed is the evidence, not the argument.

## 2. System Architecture & Design Choices
*   **Invert the default, don't document the override.** The alternative considered first was
    leaving `tauri.conf.json` untouched and telling contributors to pass
    `--config '{"bundle":{"createUpdaterArtifacts":false}}'`. Rejected: it keeps the shared config
    describing a state no contributor can reach, and it makes correct local behaviour depend on
    every contributor reading a doc before their first build rather than on the repo's own
    defaults. The committed config should describe the common case; the release pipeline is where
    release-only behaviour already lives.
*   **A release-only overlay merged by `--config`, matching a pattern this repo already uses.**
    `core/tauri-rust/tauri.conf.json` sets `"createUpdaterArtifacts": false`. A new
    `core/tauri-rust/tauri.release.conf.json` carries `{"bundle": {"createUpdaterArtifacts": true}}`
    and nothing else. All three build legs in `release.yml` (`build-macos`, `build-windows`,
    `build-linux`) append `--config tauri.release.conf.json` to their existing `tauri build`
    invocations. Tauri v2's CLI reference states configs "are merged in the order they are
    provided," and that `--config` accepts a file path as well as an inline JSON string -- verified
    directly against the current published reference, not assumed. The automatic
    `tauri.macos/windows/linux.conf.json` platform merge is unaffected and still applies alongside
    an explicit `--config`.
*   **`plugins.updater` stays exactly where it is.** `active`, `endpoints` and `pubkey` are the
    *runtime* half of the updater and are unrelated to artifact generation. A contributor's local
    build keeps a working update-check code path; it simply does not emit a signed
    `.app.tar.gz`/`.sig` pair of its own. Conflating these two halves is the same mistake
    `SPEC-402` §2 was careful to avoid between the updater keypair and the Developer ID.
*   **The failure direction inverts, and that is the main safety argument.** Today CI is green and
    every contributor is broken -- a failure nobody with commit rights encounters routinely. After
    this change, a CI leg that lost the `--config` flag would produce no `.sig`, and the existing
    `if-no-files-found: error` on each leg's `upload-artifact` step fails the release loudly at the
    tag. The regression that matters becomes the one that is already guarded.
*   **Three honest tiers of local build, to be stated as such in `CONTRIBUTING.md`.** The current
    doc implies one mode (`dev`) and the release pipeline implies another (fully signed); the
    useful middle tier is undocumented and is what contributors actually need.
    *   **Tier 1 -- `tauri dev`.** What `CONTRIBUTING.md` documents today. Fast. Does **not**
        exercise the macOS app menu bar, `Info.plist` identity (app name, icon, bundle-ID-keyed TCC
        permission prompts), or `SPEC-401`'s `Contents/Resources` sidecar resolution, because the
        running process is not a bundle.
    *   **Tier 2 -- unsigned bundle, placeholder daemon.** `npx @tauri-apps/cli@2 build
        --bundles app` in `core/tauri-rust`. After this spec, works in a fresh clone with no keys
        and no Python toolchain, because `CTX-401.2`'s placeholder sidecars are committed and
        satisfy `tauri-build`'s existence check. Correct tier for UI, menu, window-chrome and
        installer-shape work. `--bundles app` skips DMG creation and is meaningfully faster than a
        full `build`; `--bundles dmg` is the tier for testing the install experience itself.
    *   **Tier 3 -- unsigned bundle, real daemon.** Tier 2 plus a real `pyinstaller daemon.spec`
        freeze in `services/python-daemon`, which on macOS requires a **python.org framework build**
        of Python 3.11, not Homebrew's -- the constraint `CTX-401.1` established and `release.yml`
        still honours by installing the official universal2 `.pkg` rather than using the runner's
        own Python. Required for anything touching daemon behaviour end-to-end.
*   **"Unsigned" must be documented as "runs fine locally," because contributors assume otherwise.**
    A `.app`/`.dmg` produced on the contributor's own machine never receives the
    `com.apple.quarantine` extended attribute, so Gatekeeper shows no warning and no right-click-Open
    dance is needed. The friction `SPEC-402` §2 documents for released `.dmg` downloads applies to
    *downloaded* artifacts, not locally built ones. Stating this plainly is a real deliverable: a
    contributor who believes an unsigned build will not launch does not attempt Tier 2 at all.
*   **Cross-Module Impacts:**
    *   `core/tauri-rust`: `tauri.conf.json` (`bundle.createUpdaterArtifacts` -> `false`);
        `tauri.release.conf.json` (new).
    *   Repo root: `.github/workflows/release.yml` -- `--config tauri.release.conf.json` added to
        three `tauri build` steps; `CONTRIBUTING.md` -- a new local-build section.
    *   `services/python-daemon`: none. The placeholder sidecars and `daemon.spec` are referenced
        by the new documentation but not modified.
    *   No Rust, TypeScript or Python source changes. No test-suite changes.

## 3. Known Constraints & Risks
*   **A manual, out-of-CI release build would now silently produce no updater artifacts.** The real
    mitigation is that releases are tag-triggered and CI-only by `SPEC-402` §2's own design, and
    that `if-no-files-found: error` catches the CI case. The residual risk is a maintainer building
    a release by hand and publishing it without a `.sig`, breaking auto-update for everyone who
    installed it. `scripts/check_release_version.py` is the existing precedent for guarding a
    release-time human mistake; whether to extend that pattern here is a real decision for the
    implementing context, not something this spec should pre-answer.
*   **The committed placeholder sidecars fail loudly, but only at runtime.** A Tier 2 bundle
    contains `CTX-401.2`'s shell-script placeholder, which prints its own explanation to `stderr`
    and exits 1 when the supervisor tries to launch it. This is the designed behaviour and is
    better than a silent fake -- but a contributor who has not read the Tier 2/Tier 3 boundary will
    read it as a bug in their change. The documentation must name it before they hit it.
*   **A hand-renamed sidecar is a real, latent architecture footgun.** Tauri's `externalBin`
    convention appends the *target* triple, so a contributor unblocking a build by copying
    `...-aarch64-apple-darwin` to `...-x86_64-apple-darwin` gets a bundle that builds cleanly and
    then fails at runtime on the wrong architecture. `CTX-402.4`'s Plan Drift already recorded the
    CI-side version of this exact mistake. The documentation should say "re-freeze," never "rename."
*   **Real Apple signing material currently sits in the working tree at `developer-key/`** -- an
    App Store Connect `.p8` and a `.p12` certificate bundle, observed on the maintainer's machine on
    2026-08-26. `.gitignore` covers `developer-key/`, `*.p8` and `*.p12`, so this is not an exposure
    through git, but it does contradict `SPEC-402` §3's own stated rule that this material lives
    "only as a GitHub Actions secret ... never in the repo itself, not even briefly." Named here
    honestly rather than left unrecorded; relocating it outside the checkout is a maintainer action,
    not an implementation task, and is not in this spec's scope.
*   **This spec was written without running a single Tauri build.** The failure it fixes was
    observed for real by the maintainer; the `--config` merge semantics were verified against
    Tauri's current published CLI reference; the config, workflow, `.gitignore` and placeholder
    sidecar states were all read directly from the repo. But **no build of any tier has been
    executed to confirm the fix**, on any platform. The implementing context owns that verification
    and should record which tiers it actually exercised and on which architecture -- per
    `CLAUDE.md`, "this ran on exactly one machine" is worth more than an uncaveated green check.

## 4. Module Map & Reference Links
```text
[Root Spec](SPEC-000-architecture-overview.md)
   └── [SPEC-402](SPEC-402-release-signing-and-auto-update.md)
          └── [This Spec](SPEC-406-contributor-local-builds.md)
                 └── [Context 406.1](../context/CTX-406.1-unsigned-local-build-default.md)
```
*   [SPEC-402](SPEC-402-release-signing-and-auto-update.md) -- the parent. Its release pipeline,
    its two independent trust mechanisms, and every `TAURI_SIGNING_*`/`APPLE_*` secret stay exactly
    as they are; this spec only changes which config file the updater-artifact switch lives in.
*   [SPEC-401](SPEC-401-python-sidecar-packaging.md) -- the placeholder-sidecar and framework-Python
    constraints that define the Tier 2 / Tier 3 boundary documented here.
*   [CONTRIBUTING.md](../CONTRIBUTING.md) §"Setting up -- only as much as you need" -- the section
    the new local-build documentation extends, and §"Platform reports are a contribution", which
    asks for exactly the artifacts this spec unblocks.

## 5. User & Interaction
*   **Product Stage:** before the product's own workflow -- this surface is the contributor's build
    loop, not an in-app screen.
*   **What the user is trying to accomplish:** see their change running in a real installed app --
    the menu bar, the window chrome, the installer -- without needing keys they cannot have, and
    know which parts of the app will genuinely work in that build and which will not.
*   **What the user sees and does:** in a fresh clone with no secrets configured, they run
    `npx @tauri-apps/cli@2 build --bundles app` in `core/tauri-rust` and get a working, launchable,
    unsigned `.app` (no Gatekeeper prompt -- it was never quarantined). `CONTRIBUTING.md` tells them,
    before they try it, which of the three tiers they are in, that the bundled daemon is a
    placeholder that will exit with a message if the app tries to start it, and that signed and
    update-capable builds come only from CI -- so an unsigned local build reads as the expected
    outcome rather than as something they failed to configure.
