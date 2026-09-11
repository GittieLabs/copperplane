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

Mostly it does not. **It reads your files**, with KiCad closed.

Two mechanisms, and the first is the one that matters:

**`kicad-cli`**, the command-line tool inside your KiCad installation, run
against a saved file. ERC, DRC, the netlist that gives pin-level connectivity,
and board geometry export all go this way. Live IPC has no ERC/DRC call at all —
confirmed by reading the API definitions, not assumed — so the CLI was never a
fallback; it is the real path.

Alongside it, the app **parses the `.kicad_pcb` and `.kicad_sch` files
directly** for what the CLI does not expose: the footprints on a board, their
positions, the symbols in a schematic and their library ids.

**KiCad's own IPC API** — the Protocol Buffer interface that became stable in
KiCad 9 — is the second mechanism, and it is optional. It is off by default
(**Preferences → Plugins → Enable KiCad API**) and it is used for the things that
genuinely require a live session:

- Reading the footprint libraries configured on your machine, including the
  ~150 that ship inside KiCad itself
- Resolving a footprint's 3D model file, for the enclosure preview
- Injecting a footprint into an open board, as a real transaction that either
  commits or rolls back, and only after you confirm

### One real upstream gap, and how it is worked around

KiCad's live API can resolve the path of an open **board**, but has no
equivalent for an open **schematic** — the call simply is not implemented.

That used to mean picking the schematic file by hand every time. It no longer
does: linking a KiCad project gives the app the `.kicad_pro` path, and the
schematic is its sibling. The upstream gap is real and still there; it stopped
being the user's problem.

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
[Attribution and licences](/copperplane/attribution/) — particularly if
you plan to publish a design that uses imported community footprints.
