---
title: Privacy and your data
description: Exactly where your files live, where your API keys are kept, and what leaves your machine under each provider configuration.
---

"Local-first" is a claim that is worth nothing without specifics, so here are
the specifics.

## There is no telemetry

The app collects no analytics, sends no usage data, phones no home, and has no
crash reporter. Not "anonymised" telemetry, not "opt-out" telemetry — none. We
do not know how many people use this, and the only way we learn anything is when
someone tells us.

That is a deliberate trade. If it ever changes it will be opt-in, documented
here, and announced in a release note — not slipped into a minor version.

## Where your files are

Everything the app creates lives under a storage root you choose, which you can
change in Settings.

```
<your storage root>/
  library/
    parts/           one readable .json per part
    symbols/         schematic symbols
    footprints/      land patterns
    datasheets/      cached PDFs
    libraries.json   your library groupings
  projects/
    <project name>/
      project.json
      chats/
      artifacts/     generated .glb, .step, reports
  .index/            a rebuildable SQLite cache
```

Two properties worth knowing:

**The files are the truth.** Plain, readable JSON you can open, diff, and commit
to your own version control. Not a database you need this app to interpret.

**The index is disposable.** `.index/` exists only to make search fast. Delete
it and the app rebuilds it from the files. It is never the authoritative copy of
anything.

If you link a project to a folder of your own, that project's state — including
its chat history — is written into `<your folder>/.hardware-agent-studio/`, so
copying the folder to another machine brings the work with it.

## Where your API keys are

In your operating system's keychain — Keychain on macOS, Credential Manager on
Windows, the Secret Service on Linux. Never in a config file, never in the
project files, never in a log.

This matters for a specific reason: the app is open source and your project
folder is something you might well commit to git or hand to someone. Nothing you
can accidentally share contains a key.

## What actually leaves your machine

Three things, and nothing else.

**Prompts to the model provider you chose.** When you search for a part, extract
its pins, generate design guidance or ask a question, the app sends text to that
provider's API. That text contains the part number, extracted datasheet text
relevant to the request, and — for design guidance — the actual page contents
being analysed. It does not send your board file, your schematic, your project
names, or your parts library.

**Datasheet PDF downloads.** When you confirm a part, the app fetches its
datasheet from the manufacturer's URL and caches it locally. That is an ordinary
HTTPS GET to whatever host the datasheet lives on.

**Community library searches, if you use them.** Searching community footprint
libraries queries GitHub's public API for the specific repositories on a curated
allowlist. Optional, and only when you use that feature.

Your board files never leave your machine. `kicad-cli` and FreeCAD run as local
processes on your own computer; nothing about your geometry is uploaded to
anything.

## If you want nothing to leave at all

Choose **Ollama** as your provider and point it at a model running on your own
machine. The app treats it exactly like any other provider, and no prompt leaves
your computer.

Two caveats, stated honestly. Datasheet downloads still reach the manufacturer's
server, because that is where the PDF is — you can avoid this by not using
features that fetch one. And local models are generally weaker at the structured
extraction this app leans on, so expect more failed extractions than with a
frontier model. That is a real trade, not a marketing footnote.

## What we cannot promise

The provider you choose has its own data policy, and it governs what happens to
your prompts once they arrive. Whether they train on your requests, how long
they retain them, and who can see them are questions for them, not us. The app
picks the provider you configured; it cannot make privacy guarantees on that
provider's behalf.

Read your provider's terms. If that matters to you, use Ollama.
