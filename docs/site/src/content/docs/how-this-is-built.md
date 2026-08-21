---
title: How this codebase is written
description: This project is built with heavy AI assistance under a strict spec-and-context framework. Here is exactly what that means and what it does not.
---

Most of the code in this repository was written with AI assistance, under a
framework designed to constrain it, with human review and real verification at
every step.

That is worth stating plainly rather than leaving you to notice. If you would
rather not use software built this way, better you know now than discover it
from the commit log.

## What the framework actually is

The concern with AI-generated code is not that a model cannot write a function.
It is that it produces plausible code for a problem nobody confirmed, with tests
that assert what the code does rather than what it should do, and nobody
notices.

The answer here is process, enforced by CI rather than by memory.

**Nothing gets built without a spec.** A `SPEC-*.md` states the goal, the data
contracts, the constraints and — the part that matters — what is explicitly out
of scope. Written and reviewed before implementation starts.

**Nothing gets implemented without a context file.** A `CTX-*.md` carries the
plan for one slice: phases, a testing matrix whose file paths CI verifies exist,
and real commit hashes CI verifies resolve to real reachable commits.

**Verification means the real thing.** Live CAD tests run against genuinely
installed KiCad and FreeCAD. That norm exists because mocks hid real bugs: a CAD
library raising on a benign version lag, a headless process hanging on stdin, a
coordinate convention silently mirrored between two export paths.

**User-facing work needs a human to use it.** The strictest norm, added after a
painful lesson. Twelve pull requests once shipped with every capability test
passing, and produced a UI where one text box string-matched prose to pick
between three unrelated functions. Every test passed. Nobody had sat down and
tried to look up a part. A spec is now not satisfied by proving a route returns
the right value — somebody has to open the app, click the thing, and record what
they saw.

**Mistakes get written down.** Every context file has a Plan Drift section, and
it is used honestly. Wrong predictions, failed approaches, specs corrected
mid-implementation — recorded rather than tidied away.

## What that looks like in practice

The public record is the point. A few real examples, all in the repository:

- A spec assumed two gaps existed in a dependency and planned around them.
  Someone checked the actual source before writing code. **Neither gap was
  real.** The spec was corrected the same day and the correction recorded.
- An enclosure generator passed its geometry tests and produced an open-ended
  tube with no floor. A human clicked through and said *"it's a wrapper, no top
  or bottom."* No automated test had caught it.
- A datasheet feature worked on an 8-page test fixture and failed on a real
  234-page one, because a keyword search matched `reset` on 84 pages. Found by
  live use, fixed with heading-based detection, recorded with the real numbers.

Read any `CTX-*.md` file. The Plan Drift sections are unedited.

## What this does not mean

**It does not mean nobody reviewed it.** Every change goes through a human who
can explain it. The framework's whole purpose is to make review possible by
forcing intent to be written down first.

**It does not mean your contributions get second-class treatment.** Human-written
pull requests are reviewed against exactly the same bar.

**It does not mean AI decides anything at runtime in your app.** That is a
separate question, and the answer is deliberate: inside the application, AI acts
within a step you chose, never to decide which step you are on. Ambiguity
surfaces as a choice you confirm. Nothing writes to your board without an
explicit confirmation. See [What it is, and what it is
not](/hardware-agent-studio/what-it-is/).

## Contributing with AI

Use whatever tools you like. There is no ban and no penalty — it would be
incoherent to forbid you from working the way this codebase was built.

One rule, about accountability rather than authorship: **understand every line
you submit and be able to defend it in review.**

The pull request template asks whether you used an assistant. That is so
reviewers know where to look more carefully — not to filter anyone out.

What this rules out is the thing the bans elsewhere exist to stop: a
plausible-looking patch, generated in bulk, that nobody read, for a bug nobody
confirmed. Every verification norm above applies identically whether a human or
a model typed the code — and in practice those norms are a better filter than a
policy about tools.
