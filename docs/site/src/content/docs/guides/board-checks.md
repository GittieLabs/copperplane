---
title: Check a schematic or board
description: Run ERC and DRC through KiCad's own tooling and get the results explained in plain language.
sidebar:
  order: 4
---

The app does not implement its own rule checker. It runs **KiCad's** — via
`kicad-cli`, the command-line tool inside your KiCad installation — and then
explains what came back.

## DRC, on a board

Open the **PCB** tab. If you have a board open in KiCad, the app finds it
automatically. Otherwise pick a `.kicad_pcb` file.

You get KiCad's real violations, each with a plain-language explanation of what
the rule means, why it fired on your board, and what would typically fix it.

## ERC, on a schematic

Open the **Schematic** tab and **pick the schematic file**. You have to choose it
explicitly, every time.

That is not laziness. KiCad's live API can resolve the path of an open board but
has no equivalent call for an open schematic — the API returns "no handler
available", confirmed by testing against the real thing. Until KiCad adds it,
there is no way to know which schematic you are looking at.

## Reading the results

Explanations are generated from the violation KiCad reported plus what the app
knows about the parts involved. They are a translation layer, not a second
opinion — **the authority is KiCad's own checker.**

Two things to keep in mind. A suggested fix is a suggestion; you decide whether
it is right for your board. And a clean check means your board passes the rules
KiCad was configured with, which is not the same as the board being correct.

## What this will not do

It will not fix anything. No auto-correction, no rule editing, no writing to
your board. It reads and explains; you edit in KiCad.

There is also no AI review of your schematic yet — nothing that looks at the
whole design and volunteers concerns. That is real planned work, not something
available today.

## If it cannot run

The most common cause is that `kicad-cli` was not found. It lives inside your
KiCad installation, and on some platforms it is not on your `PATH`. Set the path
override in Settings, and use **Copy Diagnostics** if you need to report it.
