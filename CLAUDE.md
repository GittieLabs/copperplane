# CLAUDE.md

Operating manual for any Claude Code session in this repo. Read this file fully before touching
anything. For the human-facing contract CI actually enforces — directory layout, spec numbering,
the gatekeeper rules — read [CONTRIBUTING.md](CONTRIBUTING.md). This file does not restate it.

## The loop

1. Pick the next item from `ROADMAP.md`'s backlog, or pick up an existing open `SPEC-*.md`.
2. `/spec-status` — see what's specced, what has an open context, what's still unspecced. Read
   this before choosing anything; don't rediscover the graph by grepping.
3. No spec yet for this work? `/new-spec <id> <title>`.
4. Spec exists and you're ready to plan implementation? `/new-context SPEC-xxx`.
5. Implement phase by phase, committing as you go. Verify against the real thing when it's
   available — see Norms below.
6. `/close-context` when the phases are done: commit hashes, status, Plan Drift, validator, PR.

Full sequence diagram, including why each command is scoped the way it is:
[SPEC-901](specs/SPEC-901-agent-operating-manual.md) §2.

## Norms (non-negotiable)

- **Verify against the real thing when it's available, not just mocks.** If KiCad or FreeCAD (or
  whatever the next dependency is) is actually installed, run the integration test for real and
  have it skip itself cleanly when it isn't — don't mock something you could have exercised.
  `CTX-103.1` and `CTX-104.1` both found real bugs this way that mocks would have hidden.
- **Record Plan Drift honestly, including your own wrong predictions.** A Plan Drift entry that
  says "I predicted X, it turned out to be Y, here's why" is the single most useful artifact in
  this repo — it is not an admission of failure. Write it even when it makes you look wrong.
- **Wire `parent_spec` and `child_specs` in both directions, in the same edit.** This has been
  missed twice already (`ROADMAP.md` §1.3: SPEC-102, then SPEC-103/104) by a careful,
  human-prompted session. Don't rely on a second pass to catch it.
- **State what was not verified.** "This ran on exactly one machine" is worth more than a green
  checkmark with no caveat. Say so explicitly in the Testing Requirements Matrix or Plan Drift.
- **`stdout` in the Python daemon is sacred.** No `print()`, ever, anywhere in
  `services/python-daemon`. It is the JSON-RPC wire; a stray line corrupts the frame. Use `stderr`
  or `logging` for anything diagnostic.

## Three traps that will bite you

1. **Testing Requirements Matrix paths are relative to the repo root, not to the `CTX-*.md` file's
   own directory.** `scripts/validate_spec_context.py` checks each path with `os.path.exists(path)`
   exactly as written, run from the repo root. Write `core/tauri-rust/src/daemon.rs`, never
   `../core/tauri-rust/src/daemon.rs` or a path relative to `context/`.
2. **A literal `|` inside any Testing Matrix cell — even inside a code span — breaks the
   validator's column parsing.** It splits each table row on every `|` character with
   `line.split('|')` and does not understand Markdown's `\|` escape. One stray pipe in a Test
   Description shifts every column after it, and the file-existence check silently validates the
   wrong cell. Rephrase around it; don't try to escape it.
3. **A scaffolding command must fail loudly on a name collision, never overwrite.** `/new-spec` and
   `/new-context` create new files. If the target ID already exists — a typo, a re-run, a stale
   argument — stop and report the conflict instead of clobbering an in-progress spec or context.

## Commands

Defined in `.claude/commands/`: `spec-status.md`, `new-spec.md`, `new-context.md`,
`close-context.md`. Each file is the authoritative instructions for that command — this section is
a pointer, not a copy.

- `/spec-status` is read-only. It reports; it does not fix what it finds.
- `/new-spec` and `/new-context` are where a bad link or a hallucinated path actually gets created
  in this repo — read them before assuming a command "just scaffolds."
- `/close-context` fetches `origin/develop` before running the validator. Local branch refs in this
  repo have drifted mid-session before; never trust one without fetching first.
- None of the four commands merge a PR. Opening one is as far as any of them go.
