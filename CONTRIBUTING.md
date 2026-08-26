# Contributing to Copperplane

Thanks for being here. This project is early, actively developed, and genuinely
open to contribution — including from people who have never touched a PCB.

Two things to know before anything else:

*   **Pull requests target `develop`, not `main`.**
*   **There are two lanes.** Small fixes have a light path. Behaviour changes go
    through this repo's Spec & Context framework, which is stricter than most
    projects and is the reason the codebase has stayed coherent. Which lane you
    are in is the first thing to work out.

---

## The two lanes

### Trivial lane

For a small, self-contained fix: a typo, a broken link, a wrong string in the
UI, a misleading error message, an obvious one-liner.

1.  Open the PR against `develop`.
2.  Say in the description that it is a trivial fix.
3.  A maintainer adds the **`trivial-fix`** label, and the Spec & Context check
    stands down. Tests and lint still run — those never stand down.

You do not need a context file, a spec, or any knowledge of the framework below.
If you are not sure whether your change qualifies, open it anyway and ask. The
worst case is that we tell you it needs a context file and help you write one.

**What does not qualify:** anything that changes behaviour, adds a dependency,
touches a data schema, or that you would struggle to describe in one sentence.

### Normal lane

Everything else. Read on.

---

## Setting up — only as much as you need

You do not need the full stack to contribute. Find your row:

| If you are changing… | You need | You do **not** need |
| :--- | :--- | :--- |
| Documentation, specs, or this file | Nothing. Edit on GitHub if you like. | — |
| The React frontend (`apps/tauri-ui`) | Node.js 18+ | Rust, Python, KiCad, FreeCAD |
| The Python daemon (`services/python-daemon`) | Python 3.11+ and [uv](https://github.com/astral-sh/uv) | Rust, Node, KiCad, FreeCAD |
| The Rust supervisor (`core/tauri-rust`) | [Rust](https://rustup.rs/) | KiCad, FreeCAD |
| Running the whole app | Rust, Node 18+, uv | KiCad and FreeCAD are optional to *launch* |
| Anything touching live KiCad | The above, plus **KiCad 9+** with its IPC server enabled | FreeCAD |
| Anything touching enclosures | The above, plus **FreeCAD 0.20+** | — |

**The live CAD tests skip themselves cleanly when the tools are not installed.**
That is deliberate, it is verified in CI on macOS, Linux and Windows, and it
means you can run the full test suite on a machine with neither KiCad nor
FreeCAD and get a green, honest result. A skipped test is reported as skipped,
never as passed.

```bash
# Python daemon
cd services/python-daemon
uv venv && uv pip install -r requirements.txt
python -m unittest discover tests/

# Frontend
cd apps/tauri-ui
npm install && npm test

# The whole app, in dev mode
cd core/tauri-rust
npx @tauri-apps/cli@2 dev
```

### Local builds — three honest tiers

`tauri dev` (above) is fast, but it never runs a real bundle — no macOS app menu bar, no `Info.plist`
identity, no sidecar resolution the way an installed app actually does it. When you need one of
those, here is what a local build in `core/tauri-rust` actually gets you, and what it does not
(SPEC-406):

| Tier | Command | Gets you | Does not |
| :--- | :--- | :--- | :--- |
| 1 — `tauri dev` | `npx @tauri-apps/cli@2 dev` | Fast iteration | App menu bar, bundle identity, sidecar resolution |
| 2 — unsigned bundle, placeholder daemon | `npx @tauri-apps/cli@2 build --bundles app` | A real, launchable, unsigned `.app` — no keys, no Python toolchain needed | Any real daemon behavior — the bundled sidecar is a placeholder that prints an explanation and exits if the app tries to start it |
| 3 — unsigned bundle, real daemon | Tier 2, plus a real `pyinstaller daemon.spec` freeze in `services/python-daemon` first | Everything Tier 2 gets you, plus real daemon behavior end to end | — |

**An unsigned local build runs fine.** It never receives macOS's `com.apple.quarantine` attribute
(that only gets attached to something downloaded from the internet), so there is no Gatekeeper
warning and no right-click-Open dance — the friction described in `SPEC-402` applies to *released*
`.dmg` downloads, not a build you just made yourself.

**Signed, update-capable builds only ever come from CI.** `core/tauri-rust/tauri.conf.json` ships
with `createUpdaterArtifacts: false` for exactly this reason — no local build ever demands
`TAURI_SIGNING_PRIVATE_KEY`, a secret that only exists as a GitHub Actions secret and has no local
substitute. The release pipeline re-enables it explicitly via a `--config
tauri.release.conf.json` overlay on its own three build legs; there is no way to produce a real
update-capable artifact locally, by design — a contributor's own generated updater keypair would
produce artifacts the shipped app's pinned public key correctly rejects.

### Platform reports are a contribution

Every live test against real KiCad and FreeCAD has run on exactly one machine —
the maintainer's Mac. The Windows and Linux builds compile and launch in CI on
all three platforms, but nobody has confirmed the CAD integration actually works
there. If you run it on Windows or Linux and tell us what happened, that is a
real contribution, and there is
[an issue template for it](../../issues/new?template=platform_report.yml).
**Reports that everything worked are as useful as bug reports.**

---

## The Spec & Context framework

Every feature and significant fix is driven by two Markdown files. This is
enforced by CI, so it is worth understanding before you write code.

**`SPEC-*.md` — the what and the why.** Goals, architecture, data contracts,
constraints, and what is explicitly out of scope. Lives next to the code it
describes; cross-cutting specs live in the root `/specs/`.

**`CTX-*.md` — the how and the when.** The implementation plan for one slice of
one spec: execution phases, a Testing Requirements Matrix, the real commit
hashes, and — importantly — a **Plan Drift** section recording what actually
went wrong.

### Spec ID numbering

| Range | Layer | Lives in |
| :--- | :--- | :--- |
| `000` | Root architecture | `specs/` |
| `1xx` | Platform and transport foundation | module `specs/` dirs |
| `2xx` | Intelligence layer — LLMs, datasheets | `services/python-daemon/specs/` |
| `3xx` | Product surface — UI, workspace, settings | `apps/tauri-ui/specs/` |
| `4xx` | Distribution and operations | `specs/` |
| `9xx` | The development framework itself | `specs/` |

Pick the next unused number in the matching range. Never reuse one.

### The workflow

1.  **Read or write the spec.** If one does not exist for what you are doing,
    write it from `SPEC-TEMPLATE.md`. If your change is user-facing, the
    `user_facing: true` frontmatter field and a `## 5. User & Interaction`
    section are both required and CI checks for them.
2.  **Create the context file** from `CONTEXT-TEMPLATE.md`, in the relevant
    `context/` folder. Fill in the frontmatter and the Testing Requirements
    Matrix. **The test file paths in that matrix must exist on disk** — CI
    verifies every one.
3.  **Branch**, matching your context ID: `feat/CTX-101.1-my-feature`.
4.  **Record your commit hashes** in the `commit_hashes` frontmatter array as
    you go. CI verifies that newly added hashes resolve to real, reachable
    commits — so do not `git commit --amend` a commit after recording its hash,
    which silently orphans it.
5.  **Open a PR against `develop`.**

Run `/spec-status` in Claude Code, or read `ROADMAP.md`, to see what is specced,
what is in flight, and what is an open idea.

### Plan Drift is not embarrassing

Context files have a Plan Drift section, and it is meant to be used. If your
first approach failed, if the spec turned out to be wrong, if you discovered
the library does not do what its documentation claims — write that down. This
repo has a real history of specs being corrected mid-implementation because
somebody checked instead of assuming, and those records are among the most
valuable things in it.

A PR that says "the obvious approach did not work, here is why" is worth more
than one that presents a tidied narrative.

---

## What gets a PR merged

*   **Scoped to one context.** One slice, one PR.
*   **Tests exist, and their paths are real.** CI checks the paths; a reviewer
    checks whether the tests are meaningful.
*   **Verified against the real thing, not only mocks.** This project has found
    genuine bugs that mocks hid — a CAD library raising on a benign version lag,
    a headless process hanging on stdin, a coordinate convention silently
    mirrored. If your change touches a bridge, exercise it against real KiCad or
    FreeCAD, and say so.
*   **For anything user-facing: somebody used it as a user would.** Not "the
    route returns the right value" — somebody opened the app, clicked the thing,
    and wrote down what they saw. This is the standard that has caught the most
    real bugs here, including several that a fully green test suite missed
    entirely.
*   **Gaps stated, not hidden.** Could not test on Windows? No API key for that
    provider? Could not verify the click-through? Say so in the PR. An honest
    gap is completely acceptable. A silent one is the problem.

---

## AI-assisted contributions

**This codebase is largely written with AI assistance**, under the framework
described above, with human review and real verification at every step. It would
be incoherent to forbid you from doing the same.

So: **use whatever tools you like.** There is no ban here and no penalty.

There is one rule, and it is about accountability rather than authorship:

> **You must understand every line you submit and be able to defend it in
> review.** If a reviewer asks why a function handles a case the way it does,
> "the model wrote it" is not an answer.

The PR template asks whether you used an AI assistant. That is so reviewers know
where to look more carefully — not to filter anyone out, and it will never be
held against a PR.

What this actually rules out is the thing those bans exist to stop: a
plausible-looking patch, generated in bulk, that nobody has read, for a bug
nobody confirmed. Every verification norm above applies identically whether a
human or a model typed the code. In practice the norms are the filter, and they
are a much better one than a policy about tools.

If you want to see how this works in earnest, read any `CTX-*.md` file — the
Plan Drift sections are unedited, and several of them record the AI being
confidently wrong and being caught by real verification.

---

## Licensing

This project is Apache-2.0. **By contributing, you agree that your contributions
are licensed under the same terms.** There is no CLA and no copyright assignment
— your contribution stays yours.

Note that third-party data licences do not follow this repo's licence. KiCad's
libraries, community footprint libraries and generated geometry each carry their
own terms; see the attribution documentation before adding a new data source.

---

## Where to ask

*   **A question, or unsure whether something is a bug** →
    [Discussions](../../discussions)
*   **A confirmed defect** → [file an issue](../../issues/new?template=bug_report.yml)
*   **A security issue** → **not** a public issue. See [SECURITY.md](SECURITY.md).
*   **Not sure where to start?** Look for
    [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

Everyone here is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
