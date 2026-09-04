---
title: Find a part
description: Search a part number, disambiguate the result, and save it to your library as a real object.
sidebar:
  order: 1
---

Open a project, go to the **Components** tab, and type a part number.

## What you get back

![A real part search, with five candidates](/copperplane/images/component-search.png)

Ranked candidates, each with its manufacturer, a datasheet link and a confidence
signal. **Nothing is chosen for you.** Open a datasheet link before confirming
if the match is not obvious — that is what it is there for.

If you typed something slightly wrong, you get a *did you mean* card rather than
a silent correction. That is deliberate: a silent substitution that happens to
be right is the same mechanism as one that is wrong, and next time it produces a
part you did not ask for.

Parts already in your library are marked as such, so you do not re-add one you
already own.

## Confirming

Confirming a candidate runs extraction against its datasheet and opens Part
Detail with a real pin table — numbers, names, electrical types.

Every field records where it came from: which source, which model, and a
confidence signal. That record follows the part for its whole life, so months
later you can tell a value read out of a datasheet from one a model inferred.

## Saving

**Save to Library** turns it into a real object on your disk — readable JSON you
can open, diff and commit. It is now available in every project.

Reopen it any time by clicking it in the Library rail. That loads the saved
record directly; it does not re-run extraction or cost you another API call.

## When it goes wrong

**A search that is too broad** returns a short, unhelpful candidate list. Add the
package or the manufacturer.

**A dead datasheet link** happens — manufacturers move files. Confirmation is not
blocked by a failed datasheet fetch, so you can still save the part; you just
will not get design guidance until a datasheet is reachable.

**"Extraction did not return valid JSON"** means the model's response was
malformed or truncated. Retrying often works. If it is reproducible for a
specific part, that is worth
[an issue](https://github.com/GittieLabs/copperplane/issues/new?template=bug_report.yml)
— include the part number.
