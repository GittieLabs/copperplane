---
title: Attribution and licences
description: The licences covering this app, the software bundled inside it, and — importantly — the component data it helps you obtain.
---

The application is Apache-2.0. **The data it helps you obtain is not**, and the
licences on that data do not become Apache-2.0 by passing through this tool.
That distinction is the reason this page exists.

## The application

Copperplane is licensed under the
[Apache License 2.0](https://github.com/GittieLabs/copperplane/blob/develop/LICENSE).
Copyright 2026 GittieLabs.

## Bundled software

Distributed builds include a frozen Python runtime containing the daemon's
dependencies. Two of them ship `NOTICE` files that Apache-2.0 section 4(d)
requires us to reproduce, and we do, in the
[`NOTICE`](https://github.com/GittieLabs/copperplane/blob/develop/NOTICE)
file at the repository root:

- **[AgentFlow](https://github.com/GittieLabs/agentflow)** (`gittielabs-agentflow`) — Apache-2.0
- **[Requests](https://requests.readthedocs.io/)** — Apache-2.0

The rest are permissively licensed and carry no notice-propagation requirement:
MIT, BSD 2- and 3-Clause, ISC and Apache-2.0 across `pdfplumber`, `kiutils`,
`kicad-python`, `pynng`, `trimesh`, `numpy`, `pydantic`, `httpx` and the model
provider SDKs. **certifi** is Mozilla Public License 2.0 and is bundled
unmodified; its source is at
[certifi/python-certifi](https://github.com/certifi/python-certifi).

## Component data — read this part

This is where obligations can land on **you**, not us.

### KiCad's own libraries

When the app searches the footprint and symbol libraries installed on your
machine, it is reading **KiCad's libraries**, which are licensed
[CC-BY-SA 4.0 with an exception for design outputs](https://www.kicad.org/libraries/license/).

That exception is the important part and it is generous: using a KiCad footprint
or symbol in your own design does **not** make your design a derivative work,
and does not oblige you to license your board under CC-BY-SA. Redistributing the
libraries themselves is a different matter and does carry the share-alike terms.

### Community libraries

The app can search and import from a small, hand-verified allowlist of
GitHub-hosted community libraries:

| Library | Licence |
| :--- | :--- |
| [SparkFun KiCad Libraries](https://github.com/sparkfun/SparkFun-KiCad-Libraries) | CC-BY-4.0 |
| [Espressif KiCad Libraries](https://github.com/espressif/kicad-libraries) | See its `LICENSE.md` |

**CC-BY-4.0 requires attribution.** If you import a SparkFun footprint or symbol
and publish the resulting design, you are expected to credit SparkFun. That
obligation is yours and this tool cannot discharge it for you. The imported
record keeps its source so you can find what came from where.

When the app imports a community footprint or symbol it stores the **original
file content verbatim** rather than re-deriving it into its own format —
deliberately, so the thing you keep is the thing they published, and its
provenance stays honest.

### Generated footprints

Footprints the app generates from datasheet package dimensions are computed from
IPC-style rules and the dimensions in your part's own datasheet. They are marked
`source: datasheet_generation` and `verified: false` in your library, and that
second flag is not decoration — **a generated footprint has not been checked
against a real part by anyone.** Verify it before you commit it to a board.

### Datasheets

Datasheets are the manufacturer's copyrighted documents. The app downloads a
copy to your machine for your own use and shows you passages from it with page
citations. It does not redistribute them, and neither should you without
checking the manufacturer's terms.

### What the app deliberately does not do

It does not integrate with distributor APIs — DigiKey, Mouser, Octopart, Arrow,
element14 and others were researched in depth and ruled out. Partly because they
do not return what this tool needs (no pins, no footprints, no design guidance),
and partly because their terms forbid what a local-first tool does: caching
responses, building a local database, aggregating across sources. The
[full research](https://github.com/GittieLabs/copperplane/blob/develop/docs/research/SPEC-203-supplier-api-exploration.md),
with per-clause citations, is in the repository.

Distributors appear only as links you click.

## KiCad and FreeCAD trademarks

KiCad and FreeCAD are trademarks of their respective owners. **This project is
not affiliated with, endorsed by, or sponsored by either.** It is an independent
tool that talks to both as separate programs, and neither is bundled.

## Getting this wrong

If something on this page is inaccurate, or a licence has changed, that is worth
an issue — licence correctness is not a detail we would rather not hear about.
[Open one](https://github.com/GittieLabs/copperplane/issues/new?template=bug_report.yml).
