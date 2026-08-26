---
id: SPEC-402
title: "Release, Signing & Auto-Update"
status: Completed
type: Module
created: 2026-08-16
last_updated: 2026-08-17
target_version: v0.1.0
location: "specs/SPEC-402-release-signing-and-auto-update.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: ["SPEC-406-contributor-local-builds.md"]
user_facing: true
---

# SPEC-402: Release, Signing & Auto-Update

## 1. Executive Summary & Goals
*   **High-Level Goal:** A real, tag-triggered GitHub Actions pipeline that builds real installable
    artifacts (`SPEC-401`'s own packaging, unchanged), publishes them as real GitHub Release assets,
    wires the Tauri auto-updater so installed copies can update in place, and generates real release
    notes from the `CTX-*.md` implementation logs this framework already collects. `CTX-402.1`/`.2`
    shipped this **unsigned** first, deliberately, macOS-only; `CTX-402.3` added real code signing
    and notarization once a real GittieLabs, LLC Apple Developer *Organization* account existed
    (Team ID `834C8Q72TG`); `CTX-402.4` added a second, Intel macOS build leg. `CTX-402.5`/`.6` add
    real, unsigned Windows and Linux builds -- explicitly labeled pre-release, asking for community
    testing help rather than waiting on full cross-platform CAD verification (`SPEC-403`) to exist
    first.
*   **Business / Technical Value:** `SPEC-401` solved building a real, working, sidecar-bundled
    `.app`; nothing since has ever produced a downloadable artifact a person outside this repo could
    actually get. This closes that gap now. Signing was initially deferred rather than rushed into a
    personal Apple/Windows identity that would tie future releases to one person indefinitely --
    once a real organization account existed, that concern no longer applied, and signing became
    real, in-scope work rather than a deferred decision.
*   **Non-Goals:**
    *   **Not Windows code signing/notarization, or any Linux equivalent.** No Windows signing
        account or dev environment exists yet -- the cost and process for one (options include a
        traditional OV/EV certificate or Azure Trusted Signing) remain a real, separate, not-yet-made
        decision. Linux has no equivalent OS-level signing concept for this kind of distribution.
    *   **Not a claim that Windows/Linux builds are as verified as macOS's.** `CTX-402.5`/`.6` add
        real, unsigned Windows/Linux builds explicitly labeled **pre-release**, with release notes
        asking for community help testing them -- `SPEC-403`'s own full cross-platform verification
        of the live KiCad/FreeCAD integration paths still hasn't happened (every real live-CAD test
        in this repo's history has run on exactly one Mac). This is a deliberate, named tradeoff:
        real builds exist and can be tried, but "pre-release, please help test" is the honest framing
        until `SPEC-403` (or equivalent real usage) closes that gap -- not a silent "it works" claim
        the original Non-Goal here was written to avoid making.
    *   **Not a semantic-versioning or release-branch policy.** The version bump and tag push that
        trigger a release remain a real, manual, human action in this first slice -- not
        `release-please`-style automation.

## 2. System Architecture & Design Choices
*   **A real, tag-triggered workflow, not a manual local build.** `.github/workflows/release.yml`
    triggers on a `v*` tag push, checks out that exact commit, and fails loudly (rather than
    publishing a mismatched artifact) if the pushed tag doesn't match the version already recorded
    in `core/tauri-rust/Cargo.toml` -- the same single source of truth
    `get_app_version_matches_this_crates_own_cargo_toml` (an existing, real test) already enforces
    internally. `apps/tauri-ui/package.json` carries no version field of its own today, confirmed by
    reading it directly -- Cargo.toml's stays the one real source, not a second one to keep in sync.
*   **Builds via the real Tauri CLI, on `macos-latest`, as a real two-architecture matrix
    (`CTX-402.4`).** `npm run build` (frontend) then `cargo tauri build --target <triple>`, run twice
    -- once for `aarch64-apple-darwin` (Apple Silicon), once for `x86_64-apple-darwin` (Intel),
    cross-compiled from the same arm64 runner rather than a separate hosted Intel runner (GitHub's
    hosted Intel macOS runners are gated behind the paid Larger Runners offering, confirmed directly
    against `actions/runner-images`' current README). Each leg produces `SPEC-401`'s own real `.app`
    with its own architecture-matched frozen Python daemon sidecar already inside it, wrapped in
    Tauri's own default macOS bundle target (`.dmg`). A separate `publish` job, gated on both matrix
    legs finishing, assembles one real GitHub Release carrying both. `cargo-tauri` isn't installed in
    every dev environment today (confirmed directly this session); CI installs it explicitly rather
    than assuming it's present.
*   **Tauri's auto-updater, signed with its own real, maintainer-generated keypair -- not an
    OS-level code-signing certificate.** `tauri-plugin-updater`'s trust model is a standalone
    Ed25519/minisign keypair (`cargo tauri signer generate`), unrelated to Apple/Windows signing: no
    CA, no identity verification, no cost, and nothing that ties a release to a named individual or
    organization the way a Developer ID does. The private key is a real secret, generated once,
    stored only as a GitHub Actions secret -- never committed, never left on a developer's own
    machine longer than generation requires. The public key is plaintext and safe to commit, in
    `tauri.conf.json`'s `plugins.updater.pubkey`.
*   **`latest.json`, Tauri's own real update-manifest format** (version, real per-platform download
    URL, real Ed25519 signature over the built artifact) is generated by the same release workflow
    and published alongside the `.dmg`. The running app checks this against its own current version
    and the embedded public key -- only a manifest whose signature verifies against that key is ever
    offered as a real update, never silently applied without the user's explicit confirmation
    (matching this product's existing "every AI/external step confirmable, never silent" principle).
*   **A real, honest consequence of staying unsigned, stated plainly, not hidden:** macOS Gatekeeper
    will show its "Apple could not verify this app is free of malware" warning on the first launch of
    every unsigned `.dmg` download, requiring a real, documented right-click-Open workaround. This
    spec ships that documentation as a real deliverable (a release-notes/README section), not just
    the binary -- shipping an unsigned app with no explanation of the warning users will hit is the
    actual undocumented-scope failure mode this spec exists to avoid.
*   **Real release notes generated from `CTX-*.md`'s own `Implementation Log & Commit History`
    tables, not hand-written prose.** `ROADMAP.md` itself already names this framework's own
    real, currently-unread asset -- every `CTX-*.md` between the previous tag and the new one
    contributes its own real phase/commit-hash rows to the generated notes.
*   **Cross-Module Impacts:**
    *   Repo root: `.github/workflows/release.yml` (new); a changelog-generation script reading
        every `context/**/CTX-*.md`.
    *   `core/tauri-rust`: `tauri-plugin-updater` dependency; `tauri.conf.json`'s new
        `plugins.updater` config (`pubkey`, real update-check endpoint URL); `tauri.windows.conf.json`
        and `tauri.linux.conf.json` (`CTX-402.5`), the same real externalBin-override pattern
        `tauri.macos.conf.json` already established, now extended to the two new platforms.
    *   Documentation: a real, committed Gatekeeper-bypass doc, linked from release notes; extended
        by `CTX-402.5` with a real SmartScreen-bypass doc and the Windows/Linux "pre-release, please
        help test" framing.

## 3. Known Constraints & Risks
*   **Gatekeeper's real unsigned-app warning is the direct, accepted cost of this spec's own scope
    decision.** Named explicitly here, with a real mitigating doc shipped alongside the binary, not
    glossed over as a minor detail.
*   **The updater's entire trust model depends on the private signing key never leaking.** A real,
    single point of failure -- anyone holding that key could sign a malicious update the app would
    trust and silently offer to every installed copy. Stored only as a GitHub Actions secret,
    generated once, never persisted anywhere else.
*   **A real, one-time, disruptive re-key when code signing eventually arrives.** Once real
    Apple/Windows certificates exist under a real project entity, Gatekeeper/SmartScreen reputation
    for that *newly signed* identity starts from zero -- it does not inherit any trust the unsigned
    era built up with users. Named honestly now, not left as a later surprise.
*   **Windows/Linux builds (`CTX-402.5`/`.6`) are real but explicitly pre-release.** Unsigned, and
    not backed by the same depth of real live-CAD verification the macOS build has accumulated over
    `CTX-402.1`-`.4` -- shipped anyway, labeled honestly, in exchange for real community testing
    feedback rather than waiting on `SPEC-403` to exist first.
*   **A version/tag mismatch is a real, easy human mistake** (Cargo.toml bumped, tag forgotten or
    wrong) -- this spec's own CI check exists specifically to fail loudly on that, rather than
    silently publish a mismatched artifact under a misleading version number.

## 4. Module Map & Reference Links
```text
[Root Spec](../../specs/SPEC-000-architecture-overview.md)
   └── [This Spec](SPEC-402-release-signing-and-auto-update.md)
          └── [Context 402.1](../context/CTX-402.1-subfeature.md)
```
*   [SPEC-401](SPEC-401-python-sidecar-packaging.md) -- the real, already-shipped `.app`/sidecar
    build this spec's release pipeline packages and publishes, completely unchanged.
*   [SPEC-403](../specs/SPEC-403-cross-platform-verification-matrix.md) -- still unspecced; its real
    cross-platform CAD verification is what would let Windows/Linux builds graduate out of
    "pre-release, please help test," not a hard blocker on shipping them at all.
*   [ROADMAP.md](../ROADMAP.md) §3.4 -- where this gap was originally named ("Tagged releases, macOS
    notarization, Windows code signing, Tauri updater, and a changelog derived from the `CTX-*.md`
    implementation logs -- which the framework already collects, and which nothing currently
    reads"), now explicitly rescoped here to defer signing.

## 5. User & Interaction
*   **Product Stage:** mostly outside the app's own UI -- release/download happens before install;
    auto-update is a real in-app moment once installed.
*   **What the user is trying to accomplish:** get a working build of the app without building from
    source, and learn about new versions without manually checking or re-downloading.
*   **What the user sees and does:** downloads a `.dmg`/`.msi`/`.exe`/`.deb`/`.AppImage` from a real
    GitHub Release page; on first launch, macOS users see Gatekeeper's real unsigned-app warning
    (`v0.1.0` only) and Windows users see SmartScreen's real unsigned-app warning (`CTX-402.5`
    onward, until Windows signing exists), each with a documented one-time workaround. Windows/Linux
    downloaders also see, in the README and release notes, an explicit "pre-release, please help
    test" framing -- a real, honest signal that these builds haven't accumulated the same real usage
    depth the macOS build has, not a hidden caveat. After install, the running app checks for updates
    (a real UI surface -- notification or button, exact placement resolved during implementation) and
    can apply one with explicit confirmation, never silently -- consistent with every other
    AI/external action this product already exposes for confirmation, not automatic application.
