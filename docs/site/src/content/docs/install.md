---
title: Install
description: How to install Copperplane, what you need alongside it, and what to expect on each platform.
---

## What is published

Every release publishes a build for all four targets:

| Platform | Download | Signed? |
| :--- | :--- | :--- |
| **macOS**, Apple Silicon | `_aarch64.dmg` | ✅ Signed and notarized |
| **macOS**, Intel | `_x64.dmg` | ✅ Signed and notarized |
| **Windows** | `_x64-setup.exe` | ❌ Not signed |
| **Linux** | `.AppImage` or `.deb` | ❌ Not signed |

All of them are on the
[Releases page](https://github.com/GittieLabs/copperplane/releases).

Signed means macOS can confirm who built the app before running it. The Windows
and Linux builds have no equivalent yet, so each release also publishes a
`SHA256SUMS.txt` — see [Verify your download](#verify-your-download).

## macOS

1. Download the `.dmg` — `_aarch64.dmg` for Apple Silicon, `_x64.dmg` for Intel.
2. Open it and drag **Copperplane** into `/Applications`.
3. Launch it. It should open normally.

Not sure which Mac you have? **Apple menu → About This Mac**. Anything with an
M-series chip is Apple Silicon; if you bought it in 2020 or later it almost
certainly is. Taking the wrong one is not dangerous — it simply will not run.

The build is signed and notarized under a real GittieLabs, LLC Apple Developer
identity, so there should be no Gatekeeper warning. If you get one, that is a
bug worth [reporting](https://github.com/GittieLabs/copperplane/issues/new?template=bug_report.yml).

:::note[Very early releases were unsigned]
The first release was deliberately unsigned, and macOS refuses a normal
double-click on it. If you have one of those, download the newest release
instead — every recent one is signed and notarized, and opens normally.
:::

## Windows

Download the file ending in `_x64-setup.exe` and run it.

**Windows will stop you the first time.** You will get a blue "Windows protected
your PC" box saying the publisher is unknown. That is SmartScreen doing its job:
this installer is not code-signed, because the project does not have a
certificate yet. To continue, click **More info**, then **Run anyway**.

You should not take that step on faith. Before running it, you can confirm the
file is exactly what our build server produced — see
[Verify your download](#verify-your-download). If you would rather not run an
unsigned installer at all, that is a reasonable position:
[build from source](#build-from-source) instead.

There is also an `.msi`. Take the `_x64-setup.exe` unless you specifically need
an MSI for managed deployment — the `.exe` is what the built-in updater installs,
so staying on it keeps future updates working the ordinary way.

## Linux

**AppImage** — one file, no install:

```bash
chmod +x Copperplane_*_amd64.AppImage
./Copperplane_*_amd64.AppImage
```

**Debian / Ubuntu** — if you would rather have it installed properly:

```bash
sudo apt install ./Copperplane_*_amd64.deb
```

If the AppImage exits immediately complaining about FUSE, install `libfuse2`
(`sudo apt install libfuse2`) — recent Ubuntu releases dropped it, and it is the
usual cause. If something else happens,
[tell us](https://github.com/GittieLabs/copperplane/issues/new?template=platform_report.yml);
that report is worth a great deal here.

## Verify your download

Every release publishes `SHA256SUMS.txt` alongside the installers. It lets you
confirm the file you have is byte-for-byte the one our build server produced.

Download it into the same folder as your installer, then:

**macOS**

```bash
shasum -a 256 -c --ignore-missing SHA256SUMS.txt
```

**Linux**

```bash
sha256sum -c --ignore-missing SHA256SUMS.txt
```

**Windows**, in PowerShell:

```powershell
Get-Content SHA256SUMS.txt | ForEach-Object {
  if ($_ -match '^([0-9a-f]{64})\s+(.+)$') {
    $expected = $Matches[1]
    $name = $Matches[2]
    if (Test-Path -LiteralPath $name) {
      $actual = (Get-FileHash -LiteralPath $name -Algorithm SHA256).Hash
      if ($actual -eq $expected) { "$name : OK" } else { "$name : FAILED" }
    }
  }
}
```

You want to see `OK` next to the file you downloaded. `--ignore-missing`
matters: without it, every one of the five installers you *did not* download is
reported as `FAILED`, which looks alarming and means nothing.

:::caution[What this does and does not prove]
A checksum published next to the file it describes proves **integrity**: your
download is complete, uncorrupted, and identical to what the build produced. It
does not prove **authenticity** — anyone who could replace the installer on the
releases page could replace the checksum too. It is a useful check, not a
replacement for code signing, and we would rather say so than let it look like
more than it is.

The same run's hashes are also printed into the
[build log](https://github.com/GittieLabs/copperplane/actions) for the release
tag, which is a separate record that editing a release asset does not reach.
:::

Automatic updates are a different matter, and stronger: the updater verifies an
Ed25519 signature over every update on all platforms, including Windows and
Linux, and refuses anything that does not match. That check is cryptographic and
it is not optional. It is only this very first download that has no signature
behind it.

## Build from source

You never have to — every platform has a published build — but this is the path
if you would rather not run an unsigned installer, you want to change something,
or you are on a platform or architecture we do not ship (32-bit ARM Linux, say).

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
The app builds, installs and launches on both — CI proves that much on every
pull request. What has never been verified by a person is whether the *live CAD
integration* works there: finding your KiCad install, connecting to its IPC
server, locating `kicad-cli`, driving FreeCAD headlessly. Path resolution on
those platforms is the least-exercised code in the project. The install steps
above have not been walked through on a real Windows or Linux desktop either.

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
