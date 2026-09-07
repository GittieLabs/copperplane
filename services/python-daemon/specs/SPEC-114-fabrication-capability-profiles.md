---
id: SPEC-114
title: "Fabrication Capability Profiles & Design Rules"
status: Draft
type: Feature
created: 2026-09-07
last_updated: 2026-09-07
target_version: v0.6.0
location: "services/python-daemon/specs/SPEC-114-fabrication-capability-profiles.md"
parent_spec: "SPEC-210-design-considerations-model.md"
child_specs: []
user_facing: true
---

# SPEC-114: Fabrication Capability Profiles & Design Rules

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let the user name the board house and process they are actually going to
    order from, record that house's published capability numbers as a first-class object with
    provenance, and turn them into design rules KiCad's own DRC enforces. The explanation layer
    that already exists then does the teaching.

*   **Today the app checks a board against nobody's process.** `kicad_cli.run_drc` runs KiCad's own
    DRC, which enforces whatever constraints the project happens to carry. On a first board those
    are KiCad's defaults, which are permissive and are not any manufacturer's numbers. A clean DRC
    result currently means "you did not violate a rule you never set".

*   **The value is the silent acceptance, not the rejection, and this needs saying plainly because
    the obvious pitch is weaker than it looks.** JLCPCB and PCBWay both run their own DFM check on
    upload and will reject or query the gross violations, so "we catch what nobody catches" is not
    the claim. Two things are: the round trip is saved before any money or two weeks are spent, and
    the terse rejection line is replaced by an explanation. But the class that actually matters is
    what a fab **accepts without comment**: silkscreen over a pad is clipped silently, text below
    the minimum height comes back an unreadable smudge, a solder mask sliver below the minimum dam
    simply is not printed so two fine-pitch pads share one opening and bridge on assembly, and an
    annular ring at the very edge of tolerance builds fine and yields an intermittent connection
    that costs an evening to find. None of that is rejected. It arrives looking like a real board.

*   **This is the lowest-bar proof in the product for a novice.** It fires on very nearly every
    first board, it needs no schematic connectivity, every claim is computed or cited, and the
    surface that explains findings already exists and works.

*   **There is already a fixture.** `SPEC-113` measured the tutorial board at 4 DRC violations, all
    `annular_width`, with 0 schematic parity issues. Annular ring minimums are exactly a fab
    capability number, so the demo board already sits on the boundary this spec is about.

*   **Non-Goals:**
    *   **Not an order form and not a quote.** No layer/thickness/finish selection, no pricing, no
        upload, no vendor account.
    *   **Not panelisation, v-scoring, castellations or controlled-impedance stackups.** Those are
        real capability questions and they are a later pack, if ever.
    *   **No writes to the user's board file in v1.** See §2.1; the entire v1 write path is a
        sidecar file the app creates.
    *   **Not a DFM guarantee.** The app is not the fab, and the profile is a record of what the
        fab published, not a promise about what they will build.

## 2. System Architecture & Design Choices

### 2.1 The gating experiment, to be run before any implementation

**Does `kicad-cli pcb drc` honour a `.kicad_dru` sidecar file, and which constraint classes does it
actually apply from one?** This single question decides the shape of the whole feature and it has
not been measured.

*   If **yes**, v1 writes only `<project>.kicad_dru`, a file the app creates and owns, never
    touching the `.kicad_pcb` or `.kicad_pro` the user authored. That is by a distance the safest
    first write path in a product that has deliberately kept writes last, and it is what this spec
    assumes.
*   If **no**, or if only some constraints are expressible there, the remainder live in Board Setup
    inside the `.kicad_pcb` and in net classes inside the `.kicad_pro`, and the feature acquires a
    real write-to-the-user's-files path with a confirmation gate. That is a materially bigger spec
    and the decision must be recorded before implementation, not discovered during it.

Run it against the tutorial board: a deliberately strict `.kicad_dru`, then `kicad_cli.run_drc`,
then compare violation counts against the same board with no sidecar. Per the repo norm, a check
that cannot fail is not evidence: confirm the *absence* of the sidecar produces the smaller number.

### 2.2 The parser question, also measured rather than assumed

`kiutils` ships a `dru.py` that models `.kicad_dru` files, and `kicad_bridge` already uses `kiutils`
for `.kicad_mod` footprints. That makes it the obvious candidate. It is also the library whose
`Board().from_file()` raises `IndexError` on real boards from this machine, recorded twice already
(`CTX-314.1`, then `kicad_pcb_import.py`'s own docstring). So `kiutils.dru` must be verified against
a real KiCad 9/10 `.kicad_dru` before being relied on, and generating the file as text is a
legitimate fallback given how small the grammar is.

### 2.3 The capability profile as an object

A `CapabilityProfile` is a real record on disk in the same sense `Part` is, with **per-field
provenance**: value, source URL, the date it was recorded, and whether the user has confirmed it.
This mirrors the provenance `Part` already enforces at the schema level and exists for the same two
reasons, trust and attribution.

Fields, as a first cut, using the correct names for what board houses publish:

*   minimum trace width and minimum clearance
*   minimum annular ring
*   minimum drill diameter and minimum via diameter
*   minimum solder mask dam (sliver) and mask expansion
*   minimum silkscreen line width and minimum text height
*   copper-to-board-edge clearance
*   the build context the numbers belong to: layer count, copper weight, board thickness

Every field is optional and an absent field produces no rule, never a guess.

### 2.4 Where the numbers come from

Bundled starter profiles for the handful of houses makers actually use, each one carrying the date
its numbers were recorded and a link to the published page, and each one editable. The app shows
the source and the date before the user orders and never presents a bundled number as current.

This follows the discipline `component-data-sources` already set for distributor data: do not scrape
at runtime and do not redistribute a third party's data as authoritative. A user pointing the app at
their fab's spec page and confirming each extracted value is the honest path if fetching is ever
wanted; it is out of scope for v1.

### 2.5 The proof surface

The demo is a **before and after**: this board passes with KiCad's defaults, here is what it looks
like against the house you actually chose. Cheap to build, and it is the entire argument in one
screen.

### 2.6 Open questions

*   **Findings will arrive in bulk.** Switching a first board from KiCad's defaults to a real
    profile could produce a large number of violations at once, and a wall of findings does not
    teach, it drowns. Ranking matters more here than in any existing review, and the ranking that
    is probably right is "would this have built silently wrong" first, outright rejection second,
    cosmetic last. This must be settled, with the tutorial board's real post-profile count measured
    to know how big the problem actually is.
*   **Where the user chooses a profile.** The project wizard, Settings, or the PCB tab. A profile is
    per project, not per install, since a maker may order the same design from two houses.
*   **No linked KiCad project.** A profile can be chosen before a board exists. What the app does
    with one and nothing to check is an honest empty state, not an error.
*   **Versioning.** When a house changes its published numbers, an existing project's profile is a
    historical record of what was checked, not something to silently update.
*   **Net classes.** Track widths and clearances per net class live in `.kicad_pro`, outside the
    sidecar. Whether v1 says anything about them at all, or defers entirely to `SPEC-211`'s trace
    width work, is open.

## 3. Known Constraints & Risks

*   **The numbers go stale and they belong to someone else.** The provenance and the visible
    recorded-on date are not decoration; they are the whole mitigation, and the failure mode is a
    user ordering against numbers the app implied were current.
*   **A too-strict profile is worse than none.** If a bundled profile is more conservative than the
    house's real capability, the app manufactures findings and spends the credibility this family
    runs on. Prefer the published standard-process numbers and say which process they describe.
*   **The app must never be the reason a board comes back wrong.** Anything that reads as "you are
    good to order" is out of scope. The output is "here is what your chosen house publishes and here
    is where your board sits against it".
*   **One machine, one KiCad, one board.** Every measurement this spec calls for will be made on
    macOS with the maintainer's KiCad, and `SPEC-403` owns closing that gap.

## 4. Module Map & Reference Links

*   `services/python-daemon/kicad_cli.py` — `run_drc`, the subprocess pattern, and where a sidecar
    would have to be honoured.
*   `services/python-daemon/kicad_project.py` — project file locations.
*   `services/python-daemon/kicad_write.py` — the existing write path and its confirmation gate.
*   `services/python-daemon/library_store.py` — record persistence and the provenance schema to
    mirror.
*   [SPEC-210](SPEC-210-design-considerations-model.md) — parent; the record and the discipline.
*   [SPEC-113](SPEC-113-structural-consistency-checks.md) — the measurement of the tutorial board
    this spec reuses.
*   [SPEC-319](../../../apps/tauri-ui/specs/SPEC-319-ai-review.md) — the review that explains the
    resulting findings.
*   [SPEC-403](../../../specs/SPEC-403-cross-platform-verification.md) — the one-machine gap.

## 5. User & Interaction

*   **Product Stage:** PCB, after a board exists and before it is ordered.

*   **What the user is trying to accomplish:** Finding out whether the board they are about to pay
    for will actually come back the way they drew it, without knowing what an annular ring is.

*   **What the user sees and does:** They are asked once, per project, which board house and which
    process they intend to order from, and can accept a bundled profile or enter their own numbers.
    The PCB check then reports against those numbers instead of KiCad's defaults, and shows the
    difference the choice made. Each finding explains what the fab would do with it, separating the
    ones that would be rejected from the ones that would be built silently wrong, which is the class
    they had no way to know about.
