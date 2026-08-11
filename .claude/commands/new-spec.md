---
description: Scaffold a new SPEC-*.md from SPEC-TEMPLATE.md with frontmatter and bidirectional links pre-filled
argument-hint: <id, e.g. SPEC-105> <title>
---

Scaffold a new spec file. `$1` is the spec ID (e.g. `SPEC-105`); everything after it is the title.

1. **Refuse a collision.** Search for `specs/**/$1-*.md` across the whole repo. If a file already
   matches that ID, STOP and report the conflict. Never overwrite an existing spec.

2. **Place it correctly.** Determine the ID's range per `CONTRIBUTING.md` §2 and map it to a
   directory:
   - `000` or `9xx` → root `specs/`
   - `1xx` or `4xx` → root `specs/`, unless the work is clearly scoped to one module already (ask
     if unsure)
   - `2xx` → `services/python-daemon/specs/`
   - `3xx` → `apps/tauri-ui/specs/`

   If the number the human gave you doesn't match the layer their description implies, say so and
   ask before proceeding — don't silently pick a directory that contradicts the ID.

3. **Scaffold from the template's structure, not its placeholder text.** Copy
   `SPEC-TEMPLATE.md`'s section headers (`## 1. Executive Summary & Goals` through `## 4. Module Map
   & Reference Links`) into the new file. Fill frontmatter: `id: $1`, `title`, `created` and
   `last_updated` (today's date), `target_version`, `location` (the real path you just chose),
   `status: Draft`, `type`. Leave the body sections as prompts for the human/agent to fill in
   through conversation — do not invent the spec's actual design content yourself.

4. **Ask whether this spec adds or changes a surface a person directly interacts with, and set
   `user_facing` from the answer — don't default it.** A capability spec can be mechanically
   correct and still be the wrong thing to build if nobody asked what the user is doing with it
   (`ROADMAP.md` §5.3 norm 8; `SPEC-302` is the example that forced this). If `user_facing: true`,
   scaffold a `## 5. User & Interaction` section (copied from `SPEC-TEMPLATE.md`) with its three
   bullets as prompts — product stage, what the user is trying to accomplish, what the user sees
   and does — for the human/agent to fill in through conversation, same as every other section. If
   `user_facing: false`, omit the section entirely; do not scaffold an empty placeholder for a
   surface that doesn't exist. `scripts/validate_spec_context.py` hard-fails a spec missing the
   `user_facing` field at all, and a changed `user_facing: true` spec with no `## 5.` section.

5. **Wire the parent link in both directions, in the same operation.** Ask whether this spec has a
   `parent_spec` (default: `specs/SPEC-000-architecture-overview.md` for anything that's part of
   the product architecture; `null` if it's a parallel root like `SPEC-901`). If there is a parent:
   - Set `parent_spec` in the new file.
   - Open the parent file and append this spec's path to the parent's own `child_specs` array.
   Do both edits before reporting success. A parent link with no matching `child_specs` entry is
   the single most common mistake in this repo's history (`ROADMAP.md` §1.3) — it does not count as
   done until both sides are edited.

6. **Report** the new file's path, and explicitly confirm whether a parent link was wired and both
   sides updated, and whether `user_facing` was set to `true` or `false`.
