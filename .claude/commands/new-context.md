---
description: Draft a new CTX-*.md implementation plan from an existing SPEC, and create its branch
argument-hint: SPEC-xxx
---

Draft the next context file for spec `$1` (e.g. `SPEC-105`). This is the highest-leverage of the
four commands — a hallucinated test path or a missing link has actually happened at this step
before, not at `/new-spec` or `/close-context`.

1. **Locate the spec.** Find `specs/**/$1-*.md`. If it doesn't exist, stop and say so — do not
   fabricate a context for a spec that isn't written yet. Suggest `/new-spec` instead.

   Derive `NUM` by stripping the `SPEC-` prefix from `$1` (e.g. `$1 = SPEC-901` → `NUM = 901`).
   Every context ID in this repo drops the `SPEC-` prefix and uses just the number — `CTX-101.1`,
   `CTX-102.1`, `CTX-103.1`, `CTX-104.1`, never `CTX-SPEC-101.1`. Use `NUM`, not `$1`, everywhere
   below that builds a `CTX-*` id or branch name.

2. **Pick the next context number.** Search every `context/` directory for existing `CTX-NUM.*.md`
   files and use the next unused `.n` suffix, starting at `.1`.

3. **Pick the target directory.** Same module as the spec: a root spec (`specs/`) gets a root
   `context/`; `apps/tauri-ui/specs/` gets `apps/tauri-ui/context/`;
   `services/python-daemon/specs/` gets `services/python-daemon/context/`. Create the directory if
   it doesn't exist yet (`CONTRIBUTING.md` §3 documents a root `context/` that may not exist on disk
   until the first root-level context needs one) — do not assume it's already there.

4. **Read the spec in full**, then decompose its §1-§3 into discrete, reviewable phases, following
   `CONTEXT-TEMPLATE.md`'s structure exactly (frontmatter fields, phase checklists, the four
   numbered sections).

5. **Draft the Testing Requirements Matrix carefully — this is where it goes wrong:**
   - Every path in the "Test File Location" column is relative to the **repo root**, never to this
     new `CTX-*.md` file's own directory.
   - Each path must be a file you are about to create, or one that already exists. Never write a
     plausible-looking path you haven't verified. If a test doesn't exist yet, either create an
     empty stub for it now or leave that row for a later commit — but the cell must always name a
     real file, because `scripts/validate_spec_context.py` checks `os.path.exists()` on it verbatim
     and CI fails otherwise.
   - **Never put a literal `|` character in any cell**, including inside inline code spans like
     `` `a | b` ``. The validator splits each row on every `|` with no escape handling; one stray
     pipe shifts every column after it and the file check silently validates the wrong cell.
     Rephrase around it.

6. **Fill frontmatter:** `id: CTX-NUM.<n>`, `spec_ref` (relative path to the spec), `title`,
   `status: Planned`, `branch: feat/CTX-NUM.<n>-<slug>`, `created`/`last_touched` (today),
   `version_included`, `commit_hashes: []`.

7. **Create the branch.** Fetch first — do not trust a local `develop` ref without checking; this
   repo's branches have drifted mid-session before, more than once. Then:
   `git fetch origin && git checkout -b feat/CTX-NUM.<n>-<slug> origin/develop`.

   **Immediately re-check that the spec is still there** (`git show HEAD:specs/**/$1-*.md` or
   equivalent). Checking out `origin/develop` replaces your working tree with develop's — if the
   spec you just read in step 1 only existed on a different, unmerged branch or PR (e.g. it was
   approved in conversation but its PR hasn't merged yet), it disappears here. This has happened in
   this exact repo. If it's gone, STOP: do not recreate the spec from memory. Report that the spec's
   own PR needs to land on `develop` first, and name it if you know which one.

8. **Report** the new file's path and the branch name.
