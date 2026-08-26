---
title: Read design guidance
description: Get what a datasheet says a part needs around it, with the page it came from.
sidebar:
  order: 2
---

This is the feature the project exists for. On a saved part, click **Generate
design requirements**.

## What it does

It does not hand a 230-page PDF to a model and hope. It runs two passes.

First it **locates** the relevant sections — finding the real numbered headings
for each concern and narrowing to a handful of candidate pages. Then it
**extracts** from those pages only, and every extracted item must quote text
that genuinely appears on the page it claims.

**An item whose quote cannot be found is discarded, not repaired.** That is the
contract that makes the rest trustworthy.

## What you see

Per concern — power, decoupling, reset, clock and oscillator, absolute maximum
ratings, recommended operating conditions, layout, typical application — a short
plain-language summary, with the underlying verbatim quotes collapsed beneath.

The summary is written strictly from those already-verified quotes. It never
introduces a fact that is not in them, and it is never generated for a concern
with no valid items.

Click a page citation and your cached copy of the datasheet opens at that page.
That round trip — claim to source in about five seconds — is the point.

![Design requirements on Part Detail](/copperplane/images/design-guidance.png)

## How to actually use it

Read the summary. For anything you are going to act on, **open the citation**.
The summary is a reading aid; the datasheet page is the authority. The app is
built so checking is cheap precisely because you should check.

Empty concerns are normal. Not every datasheet discusses every category, and an
empty section means nothing citable was found — which is the honest answer.

## Limitations worth knowing

**Guidance only appears if the datasheet says it in prose.** Information that
exists only inside a schematic diagram or an unlabelled table is not extracted
today.

**Citations resolve to a page, not a section.** You get "page 31", not "§7.2 of
revision C". There is no document-revision extractor yet, so if you regenerate
against a newer datasheet the page numbers change with it.

**Multi-variant datasheets are not scoped per variant.** A document covering
several part numbers may yield guidance that applies to a sibling.

**A generated summary is not a review of your board.** It tells you what the
datasheet requires. Whether your design meets it is still your call.
