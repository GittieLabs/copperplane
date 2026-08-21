<!--
Thanks for contributing.

Target `develop`, not `main`.

Two lanes, and it matters which one you are in — see CONTRIBUTING.md:

  TRIVIAL LANE  A small, self-contained fix: a typo, a broken link, a wrong
                string, an obvious one-liner. No new behaviour, no new
                dependencies. Ask a maintainer to add the `trivial-fix` label
                and the spec-and-context check will stand down. Tests and lint
                still run.

  NORMAL LANE   Anything that changes behaviour. Needs a CTX-*.md context file
                in the same PR. If you are not sure how to write one, open the
                PR anyway and say so — we will help rather than bounce you.
-->

## What this changes

<!-- One or two sentences. What is different after this merges? -->

## Why

<!-- Link the issue (`Fixes #123`) or the spec this implements. If neither exists, explain. -->

## Lane

- [ ] **Trivial** — small, self-contained, no behaviour change. Requesting the `trivial-fix` label.
- [ ] **Normal** — includes a `CTX-*.md` context file: <!-- path -->

## How I verified this

<!--
Be specific and honest. "Tests pass" is not verification on its own — CI already
says that. What did you actually do?

If this touches anything a person sees, this repo expects someone to have used
the running app as a user would, not just proved a route returns the right
value. Say what you clicked and what you saw. If you could not test something
(no KiCad installed, no Windows machine, no API key), say that plainly — an
honest gap is fine and useful; a silent one is not.
-->

- [ ] Automated tests cover this, and the paths in my Testing Requirements Matrix exist on disk
- [ ] I ran the app and used this change by hand
- [ ] Verified against real KiCad / FreeCAD, not only mocks
- [ ] Not applicable / could not test — explained below

## Anything that went wrong on the way

<!--
Optional, and genuinely welcome. If your first approach failed, or the spec
turned out to be wrong, say so — this project records that in context files on
purpose. A PR that says "the obvious approach did not work, here is why" is
more useful than one that pretends it was clean.
-->

## Tools

- [ ] I used an AI assistant on some or all of this

<!--
Not a problem, and not a gotcha — this codebase is largely written that way. See
the AI-assisted contributions section of CONTRIBUTING.md. The only rule is that
you understand every line you are submitting and can defend it in review. We ask
so reviewers know what to look at more carefully, not to filter anyone out.
-->
