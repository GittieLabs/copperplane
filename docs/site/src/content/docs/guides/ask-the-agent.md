---
title: Ask the agent
description: A scoped, sourced chat panel at the foot of every area — grounded in what that area actually knows, never a command line.
sidebar:
  order: 6
---

Every area — Overview, Components, Schematic, PCB, Enclosure — has a
collapsible chat panel at the foot of the screen. Collapsed by default, so it
never costs the area its width; the app remembers whether you left it open,
per area.

## It is five agents, not one

The tab you are on picks the agent, deterministically, before any model is
called. There is no router reading your words to guess where to send them —
the area key is real, typed state the app already has. Typing a question into
the Schematic chat can only ever produce a schematic answer.

Each agent is grounded in different real state, and can call different tools:

| Area | Grounded in | Can call |
| :--- | :--- | :--- |
| **Overview** | Project intent, your last check results, export history, the parts this project references | Search, library lookups |
| **Components** | The selected part's design guidance, connection guidance, pins, package, datasheet | Search, datasheet reading, library lookups |
| **Schematic** | Parts your project uses, plus real ERC findings | Search, datasheet reading, ERC results, part search |
| **PCB** | Real DRC findings, component heights | Search, DRC results, component-height lookups |
| **Enclosure** | Board outline, mounting holes, component heights | Search, component-height lookups |

On Components, the chat is scoped to the **part**, not the project — a Part is
a real object you own (see [Find a part](/hardware-agent-studio/guides/find-a-part/)),
so its history follows it everywhere, into every project it is used in. Every
other chat is scoped to the project.

## Every answer carries its sources, or says it does not

The same contract [design guidance](/hardware-agent-studio/guides/design-guidance/)
already makes: an answer renders clickable source chips beneath it. A datasheet
chip opens your cached PDF at the exact page. Content the model is offering as
general engineering practice — not something your specific datasheet says — is
visually marked as such, never blended in with a cited fact.

Nothing here is described as "verified." The chip is one click from the real
page precisely so your own eye can be the last check, in about five seconds —
the same discipline [design guidance](/hardware-agent-studio/guides/design-guidance/)
uses.

## Answers arrive whole, not token by token

There is no streaming. While the agent is working — reading a datasheet page,
checking a search result — you see what it is doing, not a typing-indicator
animation implying a token stream that is not actually happening.

## Save as note

Found an answer worth keeping? **Save as note** promotes it to a durable,
cited record on the part or the project — the same kind of real object the
[library](/hardware-agent-studio/guides/find-a-part/) already is, not
something you have to scroll back through a transcript to find again. The next
conversation starts from it instead of re-deriving the same answer.

## Project intent

From the Overview tab, you can state what you are building — "a macropad from
scratch," "a battery-powered soil sensor" — in a plain-text field, editable any
time. Entirely optional; every project works exactly the same with it empty.

It is injected verbatim into every agent's context as your stated goal, never
treated as a verified fact about the design. It is what lets an answer be about
*your* board instead of a generic one.

## What replaced the old command box

An earlier version of Overview's chat recognized two typed commands —
`generate <part>` and `inject` — alongside plain questions. That design is
gone; see [What it is, and what it is not](/hardware-agent-studio/what-it-is/)
for why. The capabilities moved to where they actually belong:

- **Generating a component directly from a part number**, for when search
  cannot find it, is now a real fallback next to search on the **Components**
  tab — it lands you in the same review-before-save flow as a real search
  result, rather than a raw, unreviewable JSON block in a chat message.
- **Injecting a component into the board KiCad has open** is now a real action
  on a saved part's own Part Detail page, behind the same explicit
  confirmation step as before — nothing writes to your board without you
  reading exactly what it is about to do first.
