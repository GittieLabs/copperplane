---
title: Contribute
description: How to work on this project — including the small-fix path that skips the heavy process.
---

This project is early, actively developed, and open to contribution — including
from people who have never touched a PCB. A meaningful share of the work is
frontend, packaging, docs and platform testing.

The full [`CONTRIBUTING.md`](https://github.com/GittieLabs/hardware-agent-studio/blob/develop/CONTRIBUTING.md)
is the authority. This page is the orientation.

## The most valuable thing you can do right now

**Run it on Windows or Linux and say what happened.**

Every live test against real KiCad and FreeCAD has run on exactly one machine.
The builds compile and their test suites pass on all three platforms in CI, but
nobody has confirmed the CAD integration actually works anywhere else. Until
someone does, "cross-platform" is a claim rather than a fact.

There is [a template for it](https://github.com/GittieLabs/hardware-agent-studio/issues/new?template=platform_report.yml),
and **a report that everything worked is just as useful as a bug report.**

## Two lanes

**Trivial lane** — a typo, a broken link, a wrong string, an obvious one-liner.
Open the PR, say it is a trivial fix, and a maintainer adds the `trivial-fix`
label. The heavier process below stands down. Tests and lint still run.

**Normal lane** — anything that changes behaviour. Goes through the project's
Spec & Context framework, described below.

If you are unsure which you are in, open the PR and ask. Nobody gets bounced for
guessing wrong.

## You do not need the whole stack

| Changing… | You need |
| :--- | :--- |
| Docs or specs | Nothing — edit on GitHub if you like |
| The React frontend | Node.js 18+ |
| The Python daemon | Python 3.11+ and `uv` |
| The Rust supervisor | Rust |
| Live KiCad paths | The above, plus KiCad 9+ |
| Enclosures | The above, plus FreeCAD 0.20+ |

The live CAD tests **skip themselves cleanly** when the tools are not installed
— verified in CI on all three platforms. You can run the full suite on a machine
with neither and get a green, honest result. A skipped test reports as skipped,
never as passed.

## The Spec & Context framework

Every feature is driven by two markdown files, and CI enforces it.

A **`SPEC-*.md`** states what is being built and why, its data contracts, and
what is explicitly out of scope. A **`CTX-*.md`** is the implementation plan for
one slice: phases, a testing matrix whose file paths must actually exist, real
commit hashes, and a **Plan Drift** section recording what went wrong.

That last section is the unusual one, and it is meant to be used. If your first
approach failed, or the spec turned out to be wrong, write it down. This
repository has a real history of specs being corrected mid-implementation
because somebody checked instead of assuming, and those records are among the
most useful things in it. A pull request that says *"the obvious approach did
not work, here is why"* is worth more than a tidied narrative.

## What gets a PR merged

- Scoped to one context — one slice, one PR
- Tests exist and their paths are real
- Verified against real KiCad or FreeCAD, not only mocks, if it touches a bridge
- **For anything user-facing: somebody opened the app and used it.** Not "the
  route returns the right value" — somebody clicked the thing and wrote down
  what they saw. This standard has caught more real bugs here than the test
  suite has.
- Gaps stated rather than hidden. No Windows machine? No API key? Say so. An
  honest gap is fine; a silent one is the problem.

## Using AI to contribute

Allowed, explicitly, and used heavily by the maintainer — see
[How this codebase is written](/hardware-agent-studio/how-this-is-built/).

One rule, about accountability rather than authorship: **you must understand
every line you submit and be able to defend it in review.** "The model wrote it"
is not an answer to "why does this handle that case that way".

## Where to ask

- **A question, or not sure it is a bug** → [Discussions](https://github.com/GittieLabs/hardware-agent-studio/discussions)
- **A confirmed defect** → [file an issue](https://github.com/GittieLabs/hardware-agent-studio/issues/new?template=bug_report.yml)
- **A security issue** → not a public issue; see [SECURITY.md](https://github.com/GittieLabs/hardware-agent-studio/blob/develop/SECURITY.md)
- **Somewhere to start** → [`good first issue`](https://github.com/GittieLabs/hardware-agent-studio/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
