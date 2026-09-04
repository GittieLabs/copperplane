<p align="center">
  <img src="brand/svg/lockup-horizontal.svg#gh-light-mode-only" alt="Copperplane" width="360">
  <img src="brand/svg/lockup-horizontal-on-dark.svg#gh-dark-mode-only" alt="Copperplane" width="360">
</p>

<p align="center">
  <strong>A co-pilot for your first real circuit board.</strong>
</p>

---

Your breadboard works. The next step — a real PCB, and a case to put it in — is where a lot of
projects stop.

Not because it is impossible. Because KiCad opens onto a blank schematic and a hundred menus,
because the design-rule checker reports *"Pin not connected"* and *"power_pin_not_driven"* without
saying what to do about it, and because measuring your own board so an enclosure actually fits is
fiddly, error-prone work that has nothing to do with the thing you set out to build.

**Copperplane sits beside KiCad and FreeCAD and explains what they are telling you.** It reads the
files you already have, checks them, says what each finding means in plain language, and sizes an
enclosure from your board's real outline and mounting holes.

## What it does not do

It **does not replace KiCad or FreeCAD**, and it does not draw your schematic for you. Those are
good tools and you will still use them. Copperplane reads what you have made, tells you what it
finds, and hands the decisions back to you.

If you are looking for something that designs the board itself, this is not that.

## What it does

*   **Explains the checks instead of just running them.** Real ERC and DRC through `kicad-cli`, then
    a plain-language explanation of each finding, where it is on your board, and which tests were
    switched off — so a clean result cannot quietly mean "we did not look".
*   **Tells you what a footprint name means.** `PinHeader_1x04_P2.54mm_Vertical` is a sentence once
    someone reads it to you: a single row of four pads, 2.54mm apart, standing up off the board so
    its height counts against your enclosure. It also says whether a 3D model exists, which decides
    whether the part can be measured at all.
*   **Sizes an enclosure from your actual board.** Outline, mounting holes, and per-component
    heights, read from the board file. No live KiCad connection needed.
*   **Looks up parts and cites where the answer came from.** Every field records its source — a
    datasheet page, a model inference — so you can tell a verified value from a guess.
*   **Keeps everything on your machine.** Your parts library, your board files, your API keys
    (stored in your OS keychain, never in a file).

You bring your own AI provider — Anthropic, OpenAI, Google, Perplexity, or a local Ollama model.

## Try it

> **This is early software, under daily development.** It is genuinely useful today and it is not a
> polished install-and-go product. Things will be rough, and hearing about it is the most useful
> thing you can do — see below.

**macOS (Apple Silicon):** grab the newest `.dmg` from [Releases](../../releases), open it, and drag
**Copperplane** into `/Applications`. Recent releases are signed and notarised, so it should open
normally.

**Windows and Linux:** there is no published build yet — you can [build from
source](#build-from-source), and an issue saying you want one genuinely affects whether it gets
built.

To get the most out of it you will want **KiCad 9+** installed, and **FreeCAD 0.20+** if you want
enclosures. The app will tell you if either is missing and what stops working without it.

📚 **[Documentation](https://gittielabs.github.io/copperplane/)** — installing, first run, and a
guide per feature.

## The most useful thing you can do

**Tell us what broke.** Especially on **Windows or Linux**.

Every automated test suite runs on macOS, Linux and Windows. But the parts that talk to KiCad and
FreeCAD have only ever been verified end-to-end on one machine — a Mac — because that is the only
machine the maintainer has. Nearly every design document in this repo ends with a line admitting it.

So if you run Windows or Linux, **you can find things nobody here can find**, and an issue that says
"I clicked this and it did nothing" is worth more to this project right now than a pull request.
`SPEC-403` tracks turning that gap from a hope into a checked fact.

Contributions are welcome too, and there is a real workflow for them below — but users come first,
and users become contributors.

## Under the hood

A [Tauri](https://tauri.app/) desktop app (Rust + React) driving a long-running Python daemon over
JSON-RPC. The daemon talks to KiCad through `kicad-cli` against files on disk — no running KiCad
required for most features — and to FreeCAD headlessly. An LLM you choose does the explaining, and
every AI-assisted write to your board is gated behind an explicit confirmation.

*   Projects, Parts, Symbols and Footprints are real objects on disk — readable JSON plus a
    rebuildable SQLite index — not a chat transcript.
*   A live KiCad IPC bridge exists as well, for the operations that genuinely need a running
    instance; component injection is transactional and confirmation-gated.
*   The Rust core owns the Python daemon's lifecycle at the OS level (Job Objects on Windows,
    `prctl` on Linux), so closing the app kills everything it started, CAD engines included.
*   The daemon and frontend suites run on macOS, Linux and Windows on every PR, including live
    integration tests that skip themselves cleanly when the machine has no KiCad or FreeCAD.

### Build from source

You will need [Rust](https://rustup.rs/), [Node.js](https://nodejs.org/) 18+, and
[uv](https://github.com/astral-sh/uv).

```bash
# 1. Python daemon dependencies
cd services/python-daemon
uv venv && uv pip install -r requirements.txt
cd ../..

# 2. Frontend dependencies
cd apps/tauri-ui
npm install
cd ..

# 3. Run the app in dev mode (starts the frontend dev server and the daemon for you)
cd core/tauri-rust
npx @tauri-apps/cli@2 dev
```

See [`services/python-daemon/README.md`](services/python-daemon/README.md) for daemon-only setup and
test details.

## Where this is heading

The product model is in [`PRODUCT-PLAN.md`](PRODUCT-PLAN.md); `ROADMAP.md` has the detail, and
`/spec-status` prints what is specced, in progress, or still an idea.

The read-only half is built: reading your project, checking it, explaining the results, and
generating an enclosure from real geometry. What is deliberately still ahead is the part where the
app helps you *change* things — assisted authoring — kept last on purpose, because a tool that
writes to your board before it has earned your trust is a tool you stop using.

## Contributing

This repo runs a **spec → context → implement → verify** workflow: every feature has a `SPEC-*.md`
saying what and why, and a `CTX-*.md` recording how it was built, what was tested, and what went
wrong — the honest mistakes included. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first; it is short,
and CI enforces it.

Where help is most useful, in order:

1.  **Anyone on Windows or Linux**, telling us what breaks.
2.  **Anyone with a real board**, telling us where the checks or the enclosure got it wrong.
3.  **Developers** — the project shell and 3D viewer (React/Three.js), and the LLM tool-calling
    layer (`SPEC-204`, Python).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
