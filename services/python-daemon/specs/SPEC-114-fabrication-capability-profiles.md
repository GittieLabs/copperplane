---
id: SPEC-114
title: "Fabrication Capability Profiles & Design Rules"
status: Draft
type: Feature
created: 2026-09-07
last_updated: 2026-09-08
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

### 2.1 Measured 2026-09-08: `kicad-cli` DOES honour a `.kicad_dru` sidecar

Run against a copy of `examples/Copperplane_Blink_LEDs`, KiCad **10.0.3**, macOS, on the maintainer's
machine. The original in the repo was not modified; every run used a copy under `/tmp`.

**Baseline, no sidecar:** 4 violations, all `annular_width`, plus 1 unconnected item and 5 ignored
checks. This reproduces `SPEC-113`'s own measurement exactly.

**Controls, both of which held.** A sidecar named `not_the_project_name.kicad_dru` changed nothing
(4 violations), so the file genuinely must be `<project>.kicad_dru`. Deleting the sidecar returned
the count to 4. Per the repo norm, the check can fail, so the positive result is evidence.

**Constraint classes, one rule per run, each set to a deliberately absurd value:**

| Constraint written | Violation type KiCad reported | Result |
| :--- | :--- | :--- |
| `track_width` | `track_width` | 12 |
| `clearance` | `clearance` | 44 |
| `annular_width` | `annular_width` | 43 |
| `hole_size` | `drill_out_of_range` | 43 |
| `hole_to_hole` | `hole_to_hole` | 75 |
| `text_height` | `text_height` | 24 |
| `text_thickness` | `text_thickness` | 24 |
| `edge_clearance` | `copper_edge_clearance` | 5 |
| `silk_clearance` | `silk_overlap` + `silk_over_copper` | 63 + 25 |
| `physical_clearance` | `clearance` | 270 |
| `courtyard_clearance` | `courtyards_overlap` | 11 |
| `connection_width` | `connection_width` | 4 |
| `via_diameter` | — | **untested: board has 0 vias** |
| `thermal_spoke_width` | — | **untested: board has 0 zones** |

Twelve of fourteen confirmed working. The last two are untested rather than unsupported, and the
distinction was earned: `courtyard_clearance` produced nothing at 1mm and looked broken, then
produced 11 findings at 20mm. The board simply has no parts within 1mm of each other. That is
exactly the trap `CLAUDE.md` names, and it would have gone into this spec as "unsupported" without
the second run.

### 2.2 Two hard limits, both measured, both shape the scope

**Limit 1: a sidecar rule cannot resurrect a check the project has set to `ignore`.** With
`rule_severities.track_width` set to `ignore` in the `.kicad_pro`, the same `track_width` rule
produced **nothing** — and still nothing with an explicit `(severity error)` inside the rule itself.
The project's severity table is a hard gate sitting above the sidecar.

*Consequence, and it is the good outcome:* **v1 stays sidecar-only.** The app writes
`<project>.kicad_dru` and never touches a file the user authored. Where one of its rules is gated
off, it reads the `.kicad_pro` severity table — or simply the DRC report's own `ignored_checks`,
which already carries this and which `SPEC-332` already renders — and says so. That is a read and an
honest sentence, not a write. Writing `.kicad_pro` becomes an optional, confirmation-gated
escalation for a later phase, not a v1 requirement. This board ships with 5 checks ignored by
default: `missing_courtyard`, `track_not_centered_on_via`, `tuning_profile_track_geometries`,
`footprint_filters_mismatch`, `footprint_type_mismatch`.

**Limit 2: a malformed sidecar is discarded ENTIRELY and SILENTLY.** This is the most important
result of the experiment and it is a hazard, not a detail.

*   One valid rule alone: 6 violations.
*   The same valid rule **plus** one rule with a misspelled constraint name: **4** — the baseline.
    The good rule was discarded along with the bad one.
*   Identical behaviour for an unclosed parenthesis, and for an unparseable unit (`0.2furlongs`).
*   In every case: nothing on `stderr`, unchanged exit code, and a normal-looking report.

*Consequence:* the app may never write a `.kicad_dru` and assume it took effect. **Generation must
be followed by a verification run**: write the file, run DRC, and confirm the rules actually fired.
This is cheap because each violation's own description names the rule that produced it, e.g.
`Annular width (rule 'min-annular-ring' min annular width 0.1300 mm; actual 0.0850 mm)`. Without
that step a single typo silently *weakens* the user's board check while the UI reports that it was
strengthened, which is the worst failure this feature could have.

### 2.3 A rule can carry its own severity, and that is worth using

`(severity warning)` inside a rule is honoured: a run returned `{'error': 4, 'warning': 12}`, the
errors being KiCad's own and the warnings being the sidecar's. So the app's added rules can be
warnings while KiCad's defaults stay errors, and the review gets a free, honest visual separation
between *"your fab would not build this"* and *"KiCad's own rules"* without inventing a marker.

### 2.4 The wall-of-violations question, answered: 27, not hundreds

A plausible 2-layer profile (0.127mm track and clearance, 0.13mm annular ring, 0.3mm drill, 0.5mm
hole-to-hole, 0.15mm silk clearance, 1.0mm text height, 0.15mm text thickness, 0.2mm copper-to-edge)
against the tutorial board returns **27 violations**: `silk_overlap` 14, `annular_width` 4,
`hole_to_hole` 3, `text_thickness` 2, `text_height` 2, `silk_over_copper` 2. Those profile numbers
are illustrative and not yet sourced to a real house; the count is what was being measured.

Twenty-seven is reviewable. Ranking still matters, but the feature does not drown a first board.

And the findings read the way the pitch requires, unedited:

*   `Silkscreen clipped by solder mask (rule 'min-silk-clearance' clearance 0.1500 mm; actual 0.1200 mm)` → *Arc of D1 on F.Silkscreen*
*   `Text height out of range (min height 1.0000 mm; actual 0.8000 mm)` → *Footprint text of D1*
*   `Annular width (min annular width 0.1300 mm; actual 0.0850 mm)` → *PTH pad 1 [GND] of D1*

Every one of those is a build-silently-wrong case rather than a rejection, which is precisely §1's
claim. All three land on **D1**, already the tutorial's hero component from `SPEC-113`. The
manufacturability pack and the structural pack tell the same story about the same part, from two
independent directions.

### 2.5 The parser question, now narrower

`kiutils` ships a `dru.py`, and `kicad_bridge` already uses `kiutils` for `.kicad_mod` footprints.
It remains the obvious candidate for *reading* a user's existing `.kicad_dru`. For *writing*, the
grammar is small enough that generating text directly is defensible and avoids depending on the
library whose `Board().from_file()` raises `IndexError` on real boards from this machine
(`CTX-314.1`, and `kicad_pcb_import.py`'s own docstring). Given §2.2's Limit 2, whichever route is
chosen is verified by re-running DRC, not by trusting the writer.

### 2.6 The capability profile as an object

A `CapabilityProfile` is a real record on disk in the same sense `Part` is, with **per-field
provenance**: value, source URL, the date it was recorded, and whether the user has confirmed it.
This mirrors the provenance `Part` already enforces at schema level, for the same two reasons: trust
and attribution.

Fields, using the correct names for what board houses publish: minimum trace width; minimum
clearance; minimum annular ring; minimum drill and minimum via diameter; minimum solder mask dam and
mask expansion; minimum silkscreen line width and text height; copper-to-board-edge clearance; and
the build context those numbers belong to (layer count, copper weight, board thickness). Every field
is optional, and an absent field produces no rule rather than a guess.

Note from §2.1 that mask dam and mask expansion have **no** matching DRC constraint class in the
list that was measured, so those fields are recorded and shown but cannot be enforced through the
sidecar. Saying so is better than quietly dropping them.

### 2.7 Where the numbers come from

Bundled starter profiles for the handful of houses makers actually use, each carrying the date its
numbers were recorded and a link to the published page, and each editable. The app shows the source
and the date before the user orders, and never presents a bundled number as current.

This follows the discipline `component-data-sources` already set for distributor data: do not scrape
at runtime, and do not redistribute a third party's data as authoritative. A user pointing the app at
their fab's spec page and confirming each extracted value is the honest path if fetching is ever
wanted; it is out of scope for v1.

### 2.8 The proof surface

A **before and after**: this board passes with KiCad's defaults, here is what it looks like against
the house you actually chose. On the tutorial board that is 4 findings becoming 27, all of the new
ones being things a fab would build without comment. Cheap to construct, and it is the whole argument
in one screen.

### 2.9 Open questions that remain

*   **Ranking.** 27 findings is reviewable but not self-organising. "Would this have built silently
    wrong" first, "would be rejected" second, cosmetic last, is the ordering this spec proposes, and
    it needs to be settled against a real reading rather than asserted.
*   **Where the user chooses a profile.** Project wizard, Settings, or the PCB tab. A profile is per
    project, not per install, since the same design may go to two houses.
*   **No linked KiCad project.** A profile can be chosen before a board exists; that is an honest
    empty state, not an error.
*   **Versioning.** When a house changes its published numbers, an existing project's profile is a
    historical record of what was checked, not something to silently update.
*   **Net classes.** Per-net-class track widths and clearances live in `.kicad_pro`, outside the
    sidecar, and are therefore outside v1 by §2.2's Limit 1.
*   **Real numbers for real houses**, which is now the largest unknown in this spec and is a
    research task rather than an engineering one.

## 3. Known Constraints & Risks

*   **A malformed sidecar silently disables every rule in it** (§2.2, Limit 2). Measured, not
    feared. The mitigation is a mandatory verification run after every write, and this is the single
    most important implementation requirement in this spec.
*   **A rule the project has set to `ignore` will not run**, and the app must say so rather than
    reporting a clean result. `SPEC-332` already built the surface for exactly this.
*   **The numbers go stale and they belong to someone else.** Per-field provenance and a visible
    recorded-on date are the whole mitigation; the failure mode is a user ordering against numbers
    the app implied were current.
*   **A too-strict profile is worse than none.** If a bundled profile is more conservative than the
    house's real capability, the app manufactures findings and spends the credibility this family
    runs on. Prefer published standard-process numbers and name the process they describe.
*   **The app must never be the reason a board comes back wrong.** Anything reading as "you are good
    to order" is out of scope. The output is "here is what your chosen house publishes, and here is
    where your board sits against it".
*   **Mask dam and mask expansion cannot be enforced** through the sidecar (§2.6). They are recorded
    and displayed, never checked.
*   **Measured on one machine, one KiCad (10.0.3), one board.** `SPEC-403` owns closing that gap,
    and the constraint-class table above is the first thing that should be re-run on Windows and
    Linux.

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
