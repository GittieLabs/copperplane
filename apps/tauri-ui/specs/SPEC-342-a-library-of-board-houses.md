---
id: SPEC-342
title: "A Library of Board Houses"
status: Draft
type: Feature
created: 2026-09-08
last_updated: 2026-09-09
target_version: v0.7.0
location: "apps/tauri-ui/specs/SPEC-342-a-library-of-board-houses.md"
parent_spec: "SPEC-340-ordering-this-board-from-a-real-house.md"
child_specs: []
user_facing: true
---

# SPEC-342: A Library of Board Houses

## 1. Executive Summary & Goals

*   **High-Level Goal:** Turn the single per-project capability profile into a library of board
    houses the user keeps, edits, clones and switches between — shipped with real houses, shared
    across projects, and importable from a file so nobody has to retype numbers a maintainer has
    already read off a vendor page.

*   **Business / Technical Value:** `SPEC-340` shipped exactly one profile, stored per project,
    with no way to have a second. That was the right first step and it is not a usable feature:
    a maker who quotes two houses has to retype nine numbers to compare them, and `SPEC-114` §2.9
    already recorded that real numbers for real houses is the largest open question in the family.
    Requested directly after using the shipped version:

    > "do we only want the user to maintain one set of house settings? I don't think there is a way
    > for the user to just switch out the house settings quickly if they want to change houses."

*   **Non-Goals:**
    *   **Not scraping vendor sites at runtime.** `component-data-sources` already set this
        discipline for distributor data and `SPEC-114` §2.7 restated it: do not scrape at runtime,
        and do not redistribute a third party's data as authoritative.
    *   **Not the advanced process parameters.** The nine fields `SPEC-114` §2.6 settled are the
        ones a house publishes and this app can enforce. Impedance control, blind vias and
        controlled-depth drilling are a later question.
    *   **Not automatic updates.** A profile is a historical record of what was checked
        (`SPEC-114` §2.9). Nothing updates itself behind the user.

## 2. System Architecture & Design Choices

### 2.1 The library is global; the choice is per project

Measured requirement, stated directly: *"These settings are a global object that are shared across
projects and should be saved."*

`SPEC-340` stores the whole profile on the project record. That was fine for one, and is wrong for
many: editing a house's numbers should not mean editing them once per project that uses it. So the
library lives beside `library/parts` in `library_store`, and a project stores a **reference** plus
the numbers it was actually last checked against.

That second half matters and is not redundant. A profile is a historical record; if a user edits a
house's minimum drill next month, the finding they are looking at was still produced against the old
number. Storing the reference alone would silently rewrite history.

### 2.2 Save, edit, remove, clone — and clone is the important one

*"I would think a 'clone' option would work, allow for renaming, and then overwriting the settings
they need changed. You could clone the default settings or the settings of a house."*

Clone is what makes the feature usable without a data-entry session: most houses differ from a
standard process in two or three numbers, not nine. Cloning a bundled house, renaming it, and
overriding what differs is a thirty-second job. Typing nine numbers is not, and a user who abandons
it halfway has a profile that is wrong in a way the app cannot detect.

A cloned profile must reset `confirmed_by_user` on every field it did not change, and carry its
own `recorded_on`. Inheriting someone else's confirmation is exactly the attribution failure
`SPEC-114` §2.6 built per-field provenance to prevent.

### 2.3 Real houses ship as an import, not bundled

*"we should provide the settings for the main houses"* — and this is where the family's own rules
bite hardest. `CTX-114.1` Deviation 6 declined to invent numbers for named vendors, because
attributing invented figures to a real business is not a placeholder, it is a fabricated record a
user might order against.

So a house exists only once someone has actually read that vendor's published page. Each entry
carries the source URL, the date it was read, and the process it describes. The app shows all three
before an order, and never presents a recorded number as current.

**They are distributed as a file, not bundled with the app** — `board-houses/board-houses.json`,
four houses read 2026-09-09. Importing is a deliberate act by the user, which keeps the app from
shipping as though it endorses a vendor's numbers, and an updated set is a file rather than a
release. It is also what makes §2.6's read-only question collapse to almost nothing: a house from
a file can always be got back from the file.

### 2.4 JSON, import and export

*"If we save as json, we can make them available in github for a user to save and import."*

The record is already JSON on disk. Export writes one house or the whole library to a file; import
reads one back, and must treat the file as untrusted input — validated through the same
`capability_profile.validate` path as anything else, with a name collision reported rather than
silently overwriting the user's own edits.

Distribution through the repository, and refreshing bundled houses at release time, then costs
nothing extra: the file the user imports and the file the app ships are the same shape.

### 2.5 Settled 2026-09-09: generic is a template, not a house

**"Generic" is not a house and cannot be chosen as one.** It is a starting point that must be
cloned, and the clone is what a project checks against.

The question was *"would the generic option still show and isn't the generic option kicad's default
or something different?"* — and measurement showed it is neither: stricter than KiCad's defaults on
six of nine fields and **looser on two** (track width 0.127mm against 0.2mm, copper-to-edge 0.2mm
against 0.5mm). A plausible standard process; not a floor, not a default, and not anybody's
published capability.

Listing it beside real vendors would have made it answer a question it cannot answer — *which house
is this?* — and every field in it would have carried `confirmed_by_user: false` forever, because
there is no page for a user to check it against. Making it clone-only says what it actually is: the
numbers you start from before you have your own.

Three consequences, each enforced rather than documented:

*   A template is refused by `save_house`. The library holds houses, and a template is not one.
*   A template is refused as a project's choice. `set_project_fabrication_profile` will not take
    one, so a board is never checked against numbers that name no house.
*   `clone` clears the template flag. A clone is always a real house, which is the only way one
    comes into existence from the bundled starting point.

The user-visible flow is unchanged in effort: "start from standard 2-layer numbers" still takes one
click. It now produces a house of their own, which they can rename and edit, rather than silently
adopting a set of numbers attributed to nobody.

### 2.6 One read-only thing: the template

*"Read only would just be reserved for our generic import included template. and everything else
would be editable which is fine bc you could always reimport a house file."*

Houses ship as an **importable file**, not bundled with the app. That single decision collapses the
whole read-only question: any house can be got back by importing it again, so locking one protects
nothing and costs the user the ability to fix a number.

So the rule is one sentence. **The template is read-only; every house is editable.**

| | Clone | Edit | Remove |
| :--- | :--- | :--- | :--- |
| The standard-process template | yes | **no** | **no** |
| Every board house | yes | yes | yes |

The template is the exception because it is not a house at all. It names no vendor, so it cannot be
saved to the library or checked against — §2.5 — and cloning is the only thing that can be done with
it. That is the entire rule, and it is enforced in `capability_profile` and `library_store` rather
than described here.

An earlier draft had a second concept: houses shipped *with the app*, read-only so that a mistake in
one stayed recoverable. It was removed, not because it was wrong in itself but because distributing
by import makes it unnecessary — and a concept that protects nothing is one more thing to reason
about. Nothing ever set the flag, which was the first sign.

### 2.7 A collision is never resolved silently

Importing a house you already have is a real fork and the app does not guess which way. Nothing that
collides is imported on the first pass; the user is told what clashed and picks:

*   **Keep both** brings the incoming one in under a free id, leaving what they had.
*   **Replace mine** overwrites, which is destructive and only ever happens after they say so.

The reason to ask rather than default: only the user knows whether the copy they have is one they
edited. Replacing an edited house discards work on numbers a board gets judged against, and doing
that quietly to save a click is the wrong trade.

## 3. Known Constraints & Risks

*   **A looser limit can switch off a check.** Measured: a sidecar rule REPLACES the board's own
    constraint rather than adding to it, so a house limit looser than the user's own setting hides
    real violations — four genuine errors went to zero in testing. `CTX-340.2` fixed this by never
    writing a rule the project's own setting already beats. **Any house the library ships or imports
    is subject to the same hazard**, and the protection lives in one place; a future path that
    writes rules without going through it reintroduces the bug.
*   **Editing a house changes what other projects will check against.** That is the point of a
    shared library and it is also a way to surprise someone. The per-project record of what was
    actually checked is the mitigation, not a nicety.
*   **Imported files are untrusted.** A profile is numbers a board is judged against; a malformed or
    hostile one is a wrong answer with a confident face.
*   **Bundled numbers go stale, and they belong to someone else.** Unchanged from `SPEC-114` §3.
    Shipping more of them multiplies the exposure rather than reducing it.
*   **Nine fields is a deliberate floor, not a starting point for growth.** Every field added is one
    more number a user must find, and `SPEC-114` §2.6 measured that mask dam and mask expansion
    cannot be checked at all.

## 4. Module Map & Reference Links

*   `services/python-daemon/capability_profile.py` — the record, its provenance rules, and
    `BOARD_SETUP_KEYS`, which is what stops a house weakening a check.
*   `services/python-daemon/library_store.py` — where a global library belongs, beside parts.
*   `apps/tauri-ui/src/components/FabricationProfile.tsx` — today's single-profile surface.
*   [SPEC-340](SPEC-340-ordering-this-board-from-a-real-house.md) — parent; the one-profile version.
*   [SPEC-114](../../../services/python-daemon/specs/SPEC-114-fabrication-capability-profiles.md) —
    the capability, §2.6's field list, §2.7's do-not-scrape rule, §2.9's open questions.
*   [SPEC-315](SPEC-315-library-browsing-and-organization.md) — the existing library surface whose
    save/edit/remove patterns this should follow rather than invent.

## 5. User & Interaction

*   **Product Stage:** PCB, and Settings — the library outlives any one project.

*   **What the user is trying to accomplish:** Comparing what two board houses will actually build,
    and keeping their own house's numbers somewhere they do not have to retype.

*   **What the user sees and does:** A list of houses they can pick from per project, ship-with
    entries alongside their own. Any of them can be cloned, renamed and edited; their own can be
    removed. Each shows where its numbers came from and when they were read. Switching a project to
    a different house is one choice, and the board check says plainly that existing findings were
    produced against the previous one until it is re-run.

*   **How we will know it worked:** Someone quotes two houses for the same board, switches between
    them, and can say which one their design already satisfies — without typing nine numbers twice.
