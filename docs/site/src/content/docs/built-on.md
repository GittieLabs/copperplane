---
title: Built on KiCad and FreeCAD
description: How this app talks to KiCad and FreeCAD, what it needs from each, and what it owes them.
---

This tool does no PCB or mechanical engineering of its own. **KiCad and FreeCAD
do the actual work.** What this app contributes is a layer above them — reading
datasheets, holding a library, connecting the two programs — and that is only
worth anything because both are excellent and both are open.

If you find this app useful, the projects worth supporting are
[KiCad](https://www.kicad.org/donate/) and
[FreeCAD](https://www.freecad.org/donate.php).

## Not affiliated

**KiCad and FreeCAD are trademarks of their respective owners. This project is
independent — not affiliated with, endorsed by, or sponsored by either.** It is
not a plugin, not a fork, and not a distribution of either program. It bundles
neither; you install them yourself.

## How it talks to KiCad

Over **KiCad's own IPC API**, the Protocol Buffer interface that became stable
in KiCad 9. That is why 9 is the minimum. The app connects to a running KiCad
instance as a client, the same way any other API consumer would.

You have to switch that API on — it is off by default. **Preferences → Plugins →
Enable KiCad API**.

What that connection is used for:

- Reading the footprint libraries configured on your machine, including the
  ~150 that ship inside KiCad itself
- Reading a board's outline and mounting holes
- Injecting a footprint into an open board, as a real transaction that either
  commits or rolls back, and only after you confirm

Separately, the app shells out to **`kicad-cli`**, the command-line tool inside
your KiCad installation, for ERC and DRC and for exporting board geometry. Live
IPC has no ERC/DRC call at all — confirmed by reading the API definitions, not
assumed — so the CLI is the real path.

### One real limitation

KiCad's live API can resolve the path of an open **board**, but has no
equivalent for an open **schematic** — the call simply is not implemented. So
DRC can target whatever board you have open, while ERC needs you to pick the
schematic file yourself. That is a genuine upstream gap, not a shortcut here.

## How it talks to FreeCAD

Headlessly, via `freecadcmd`, for one job: generating a parametric enclosure.
The app writes a script, FreeCAD executes it without a GUI, and the result comes
back as STEP and GLB for the in-app 3D preview.

FreeCAD 0.20 or newer, and it is only needed for enclosures. Everything else
works without it.

## What the app never does

It does not modify KiCad's or FreeCAD's installations, alter their libraries,
install plugins into them, or change their configuration. It reads what is
there, and — for the one confirmed write path — asks KiCad to make a change
through KiCad's own transaction API.

If you uninstall this app, both are exactly as they were.

## Licences

Component data obtained through this app stays under its own licence, and KiCad
library terms are not this app's terms. See
[Attribution and licences](/hardware-agent-studio/attribution/) — particularly if
you plan to publish a design that uses imported community footprints.
