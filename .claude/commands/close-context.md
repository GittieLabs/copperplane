---
description: Close out the current CTX-*.md — record commits, flip status, run the validator, open the PR
---

Close out the context file for the branch you're currently on. This command opens a PR; it never
merges one.

1. **Find the active context.** Match the current git branch name (`git branch --show-current`)
   against the `branch:` frontmatter field across every `context/` directory in the repo.

2. **Collect commits.** Fetch first, then diff against the real base:
   `git fetch origin && git log --oneline $(git merge-base HEAD origin/develop)..HEAD`. Add every
   commit as a `"<hash> - <short description>"` entry in the frontmatter's `commit_hashes` array,
   and as a row in the Implementation Log table. Do not skip any commit or paraphrase a hash.

3. **Verify the Testing Requirements Matrix, don't just re-read it.** For each row, actually run the
   test it names. Mark it ✅ Passed only if it just passed in this session. If a row can't be run
   here (missing platform, missing tool, requires CI), leave it ⏳ Pending and say exactly why in
   the Status column — "requires `windows-latest` CI" is a real answer, a blank cell is not.

4. **Write Plan Drift.** Ask: did anything discovered while implementing contradict the spec, the
   plan, or an earlier prediction? If yes, add a numbered Plan Drift entry — what was assumed, what
   turned out to be true instead, and the impact. If an earlier entry predicted something (e.g.
   "this might not compile on Windows"), record whether it was right or wrong. This is the most
   useful artifact this framework produces; a session with nothing to report here should say so
   explicitly rather than leave the section thin by omission.

5. **Set `status: Review`** — not `Completed`. Completed is for after the PR has merged and its CI
   has actually run green.

6. **Run the validator against the real current base**, not a possibly-stale local branch:
   `git fetch origin && python3 scripts/validate_spec_context.py --base origin/develop`.
   Fix everything it reports before continuing. Do not open a PR with a failing local check.

7. **Commit, push, and open the PR.** Commit the frontmatter/matrix/Plan Drift updates, push the
   branch, and run `gh pr create --base develop` with a summary of what changed and an honest test
   plan section — state plainly what was and wasn't verified, and on what machine/OS. Report the PR
   URL. Do not merge it, and do not ask the user if you should merge it — merging is a separate,
   explicit decision made outside this command.
