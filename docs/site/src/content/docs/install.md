---
title: Install
description: How to install Copperplane, what you need alongside it, and what to expect on each platform.
---

## What is actually published today

Being blunt about this, because the alternative is you going to the Releases
page and not finding what you expected:

| Platform | Status |
| :--- | :--- |
| **macOS, Apple Silicon** | ✅ Published, signed and notarized |
| **macOS, Intel** | ❌ Not published. Build from source. |
| **Windows** | ❌ Not published. Build from source. |
| **Linux** | ❌ Not published. Build from source. |

Windows and Linux are real, working CI targets — the daemon and frontend test
suites run on all three platforms on every pull request — they simply are not
attached to a published release yet. If you need one,
[open an issue](https://github.com/GittieLabs/copperplane/issues/new?template=platform_report.yml)
so the demand is visible.

## macOS (Apple Silicon)

1. Download the `.dmg` ending in `_aarch64.dmg` from
   [Releases](https://github.com/GittieLabs/copperplane/releases).
2. Open it and drag **Copperplane** into `/Applications`.
3. Launch it. It should open normally.

Not sure which Mac you have? **Apple menu → About This Mac**. Anything with an
M-series chip is Apple Silicon; if you bought it in 2020 or later it almost
certainly is.

The build is signed and notarized under a real GittieLabs, LLC Apple Developer
identity, so there should be no Gatekeeper warning. If you get one, that is a
bug worth [reporting](https://github.com/GittieLabs/copperplane/issues/new?template=bug_report.yml).

:::note[Very early releases were unsigned]
The first release was deliberately unsigned, and macOS refuses a normal
double-click on it. If you have one of those, download the newest release
instead — every recent one is signed and notarized, and opens normally.
:::

## Build from source

Needed for Intel macOS, Windows and Linux until releases exist.

You will need [Rust](https://rustup.rs/), [Node.js](https://nodejs.org/) 18 or
newer, and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/GittieLabs/copperplane.git
cd copperplane

# Python daemon
cd services/python-daemon
uv venv && uv pip install -r requirements.txt
cd ../..

# Frontend
cd apps/tauri-ui
npm install
cd ../..

# Run it
cd core/tauri-rust
npx @tauri-apps/cli@2 dev
```

:::caution[Windows and Linux are genuinely untested here]
The app builds and launches on both. What has never been verified by anyone is
whether the *live CAD integration* works there — finding your KiCad install,
connecting to its IPC server, locating `kicad-cli`, driving FreeCAD headlessly.
Path resolution on those platforms is the least-exercised code in the project.
Expect rough edges, and please
[tell us what you hit](https://github.com/GittieLabs/copperplane/issues/new?template=platform_report.yml)
— including if it all just worked, which is equally useful.
:::

## What you need alongside it

Neither is bundled. Both are separate programs you install yourself.

**[KiCad](https://www.kicad.org/) 9 or newer** — required for anything involving
a real board: footprint library search, injecting a footprint, ERC and DRC,
reading a board outline. Version 9 is the floor because that is where KiCad's
IPC API became stable.

You also need KiCad's IPC server switched on, which it is not by default:
**Preferences → Plugins → Enable KiCad API**. Without it the app can see KiCad
is installed but cannot talk to it.

**[FreeCAD](https://www.freecad.org/) 0.20 or newer** — required only for
generating enclosures. Everything else works without it.

You can explore the app, search for parts, read design guidance and manage your
library with neither installed. Features that need a tool you do not have report
that clearly rather than failing strangely.

## An AI provider

The app has no model of its own and no bundled key. Pick a provider in Settings
and supply your own key, which is stored in your operating system's keychain —
never in a config file on disk.

Supported: **Anthropic**, **OpenAI**, **Google**, **Perplexity**, and **Ollama**
for a fully local model. Ollama is the option to choose if you would rather
nothing left your machine at all; see [Privacy and your
data](/copperplane/privacy/) for exactly what is sent under each.

[First run →](/copperplane/first-run/)
