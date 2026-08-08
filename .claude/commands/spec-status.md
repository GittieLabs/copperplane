---
description: Report the state of the spec/context graph and the unspecced roadmap backlog
---

Walk the Spec & Context graph and report status. This command is **read-only** — it reports what
it finds; it does not edit any file, even to fix an obviously broken link.

1. **Find every spec.** Search for `SPEC-*.md` under `specs/`, `apps/*/specs/`, and
   `services/*/specs/` (exclude `SPEC-TEMPLATE.md`). For each, read its YAML frontmatter (`id`,
   `status`, `parent_spec`, `child_specs`).

2. **Check context coverage.** For each spec, search every `context/` directory in the repo for a
   `CTX-<id>.*.md` file. If none exists, list the spec under "no context yet."

3. **Check bidirectional links.** For each spec with a non-null `parent_spec`, open the file it
   points to and confirm that file's own `child_specs` array includes this spec's path back. Flag
   any link that only goes one direction — this exact mistake has happened twice already in this
   repo (`ROADMAP.md` §1.3).

4. **Find open contexts.** Search for every `CTX-*.md` file. For each whose `status` is not
   `Completed`, list it with its `branch` field.

5. **Find unspecced backlog items.** Read `ROADMAP.md`'s spec backlog section. For each `SPEC-nnn`
   entry mentioned there that has no corresponding `specs/**/SPEC-nnn-*.md` file on disk, list it as
   unspecced.

6. **Report.** Print four short sections: **Specs with no context**, **One-directional links**,
   **Open contexts** (with branch names), **Unspecced roadmap items**. Cite real file paths, not
   just IDs — the report should let a human jump straight to the file.

If you find a broken link or a stale status while walking the graph, report it in the output. Do
not fix it as a side effect of running this command — a mechanical fix belongs in its own reviewed
commit, and comprehensive mechanical detection of this class of problem is `SPEC-902`'s job once it
exists, not this command's.
