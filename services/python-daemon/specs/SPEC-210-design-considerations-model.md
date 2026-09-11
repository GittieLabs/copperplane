---
id: SPEC-210
title: "Design Considerations: Model & Discipline"
status: Draft
type: System
created: 2026-09-07
last_updated: 2026-09-07
target_version: v0.6.0
location: "services/python-daemon/specs/SPEC-210-design-considerations-model.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs:
  - "SPEC-114-fabrication-capability-profiles.md"
  - "SPEC-211-power-path-review.md"
user_facing: true
---

# SPEC-210: Design Considerations: Model & Discipline

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give the app one reusable way to raise the things a maker does not know to
    ask about, each one keyed to something real in their own project, so that adding a second and
    third subject area is a data file and a trigger rather than a rebuild. `SPEC-113` proved the
    principle on one rule. This generalises it and stops there.

*   **The principle being generalised, in `SPEC-113`'s own words:** *"The model's job should be to
    explain a finding, exactly as it already does for ERC and DRC output, never to notice it."*
    Everything below exists to make that enforceable across a category instead of true by accident
    in one place.

*   **Three classes of claim, and only the third is an opinion.** A **computed** claim comes off
    files on disk and is true or false (a symbol has two pins, its footprint has four numbered
    pads). A **cited** claim relays something with a source (what `power_pin_not_driven` means,
    what page 12 of a datasheet requires, what a board house lists as its minimum annular ring). A
    **judgement** claim is the app's opinion about a design (these parts are too close to solder
    comfortably). The repo already splits on this line without naming it: `SPEC-113` is the
    computed half and `SPEC-327` is the judgement half. This spec names the taxonomy both assume
    and requires every consideration to declare which one it is.

*   **The initiative rule that follows.** The app may raise a computed or cited claim unprompted.
    A judgement waits to be asked. `SPEC-113` raises D1 without being asked and that is correct,
    because the underlying claim is falsifiable; the same surface volunteering *"you should use a
    switching regulator here"* would not be.

*   **Two output shapes, and the second one is the interesting one.** A **finding** is computed and
    true or false. A **question** is raised by a trigger and answered by the user, and the answer
    becomes part of the project's stated intent, which then unlocks computation that was not
    possible before. *"You are powering this from USB and you have twelve LEDs. What is your total
    current budget?"* is not a finding. It is the mechanism by which the app comes to know enough
    about a board to say something specific about it, and it is how the app can know more than the
    user without ever modelling the user.

*   **Scope is chosen by the user's declared goal for this board, not by an assessment of their
    skill.** A board built for yourself does not get warned about a connector nobody else will
    touch. The same board, once the user says they are sending it to five friends, brings ESD,
    reverse polarity, connector keying and mechanical abuse into scope, and the app can say plainly
    that those arrived *because that answer changed*. This is the only stage model in the product
    and it is declared by the user, never inferred about them.

*   **Non-Goals:**
    *   **Not a curriculum.** No lesson ordering, no progress tracking, no skill-level model, no
        quizzing. Each of those is a claim about what a maker should know and where they currently
        are, and the product does not make either claim.
    *   **Not a new surface.** Considerations appear where the user already is, in the reviews and
        the area chat. A tutor tab is explicitly the wrong answer and `SPEC-302` is the cautionary
        tale for building a surface nobody asked for.
    *   **Never edits.** Every output is a sentence or a question. `SPEC-329` owns writing to a
        design; `SPEC-114` owns the one write in this family, and it writes a sidecar file the app
        creates rather than anything the user authored.
    *   **Not a replacement for ERC, DRC or schematic parity.** Findings from this family must stay
        visually distinguishable from KiCad's own, exactly as `SPEC-113` requires.

## 2. System Architecture & Design Choices

### 2.0 Measured 2026-09-10: there is enough to compute on, and the netlist is why

`CTX-210.1` Phase 1 asked the question this whole family stands on before modelling anything: does a
real project hold enough computable signal to trigger a consideration at all? If it does not, every
consideration is a `judgement`, a judgement may not be raised unprompted (§1's initiative rule), and
this is the chat surface that already exists wearing a framework's clothes.

**It does, decisively — but not from the sources this spec assumed.** Measured against the
maintainer's own board.

What the app holds today, from the real routes:

| source | carries | connectivity |
| :--- | :--- | :--- |
| `kicad_list_board_components` | reference, footprint, value, position, rotation, courtyard, has_model, dnp | **none** |
| `kicad_list_schematic_components` | the above plus `lib_id` and `pin_count` | **none** |
| `structural_checks` | pin count against pad count | n/a |
| `intent_fields` (`CTX-328.1`) | `board_stage`, `input_supply`, `current_budget`, `environment` | n/a |
| ERC / DRC / `fabrication_profile` | existing findings and limits | indirect |

Two findings change the shape of this spec.

**First: `lib_id` is a functional taxonomy and nobody was using it as one.** The eleven symbols on
that board read `Device:LED`, `Device:R`, `Switch:SW_Push`, `power:+5V`, `power:GND`,
`MCU_Module:Arduino_UNO_R3`, `Mechanical:MountingHole`. That is KiCad's own classification of what a
part *is*, sitting in a file the app already parses. It is a **computed** fact in §2.1's sense —
read, not inferred — and it makes presence-and-count triggers available immediately. §1's own worked
example needs exactly two facts, *"you are powering this from USB"* and *"you have twelve LEDs"*, and
**both are computable today**: the second from `lib_id`, the first from `input_supply`.

**Second, and larger: full pin-level connectivity is one command away, and nothing in the app uses
it.** `kicad-cli sch export netlist --format kicadxml` returns every net with its `ref.pin` nodes —
33 nets on that board, including `Net-(D1-A)` joining `D1.2` to `R1.1`. That is precisely the *"does
this LED have a series resistor"* fact, and it is a file fact rather than a model's opinion.

The app does not read it. `kicad_cli.py` has no netlist function, and neither the board reader nor
the schematic reader carries a net. So topology-class considerations are **not blocked, they are
unbuilt** — one `kicad-cli` call and an XML parse, not a research problem.

**What this settles.** The `computed` class is real and much wider than presence-and-count. It
reaches connectivity, which is what `SPEC-211`'s power path needs and what would otherwise have made
that spec unbuildable. Nothing here is descoped; the netlist read becomes a prerequisite this
context did not know it had.

### 2.0.1 Measured 2026-09-10: the board carries geometry, and the calculators are the bridge

Raised by the maintainer while looking at KiCad's own Calculator Tools: *"kicad offers a series of
calculators, that i don't understand, that seem useful to a user if they understand how to use them
and when. and useful if the app needs them as well. would these tie into what we get from the
netlists?"*

They do, and the answer changes what a pack is.

**The board file carries more than connectivity.** Each routed segment is
`(width …) (layer …) (net "…")` with real endpoints, so per-net width, layer and length are all
computed facts. Measured on the maintainer's board:

| net | routed | width |
| :--- | ---: | :--- |
| `GND` | 21.50 mm | 0.2 mm |
| `Net-(A1-D3)` | 38.99 mm | 0.2 mm |
| `Net-(D1-A)` | 16.59 mm | 0.2 mm |
| `Net-(A1-D2)` | 5.46 mm | 0.2 mm |

**What is missing is current, and it is missing from the files, not from the parser.** Nothing in the
schematic or the board says how much current flows anywhere. That is not a gap to close with better
reading; it is a fact nobody has written down yet.

**KiCad's calculators are the standards formulas that turn geometry into an answer** — track width
and electrical spacing from IPC-2221, via current, fusing current, the regulator divider. They are
deterministic and they have a citable source, which makes them precisely this spec's `cited` class,
and they belong in §2.1's `arithmetic` field: *"where a claim rests on a calculation, the calculation
itself, shown."*

So the loop closes, and the shape of it is the argument for this whole family:

1.  **Netlist** — `+5V` reaches these pins. *computed*
2.  **Board** — routed at 0.2 mm on `F.Cu`, 21.5 mm long. *computed*
3.  **Question** — how much current does this board draw? *the user answers, and the answer becomes
    stated intent*
4.  **Calculator** — the standard's minimum width for that current and temperature rise. *cited*
5.  **Comparison** — a claim about this board, with its arithmetic shown.

**Step 3 is why the question mechanism is not decoration.** §1 already says the question is the
interesting output shape; this is the concrete reason. The calculators cannot run without a current,
the files do not contain one, and asking is the only honest way to get it. §1's own worked example —
*"You are powering this from USB and you have twelve LEDs. What is your total current budget?"* — is
exactly step 3, and it exists to unlock exactly step 4.

**A pack is therefore three things, not two:** a trigger, a formula, and a shown calculation. That is
a correction to the shape §2.1 implies, where `arithmetic` reads as an optional extra rather than
the point.

**One constraint, stated before anyone builds on this.** A trace-width number is a `cited` claim and
its constants must be read from the standard, never recalled. §3 says the first time this app is
confidently wrong about a board the user understands better than it does, the whole family is spent
— and a plausible-looking formula with a misremembered exponent is the most likely way to spend it.

### 2.1 The record

A **consideration** is the unit. The proposed shape, to be settled during implementation:

*   `id` and `domain` (`manufacturability`, `power`, …), so a pack is addressable.
*   `claim_class` — `computed` | `cited` | `judgement`. Required. Decides whether it may be raised
    unprompted.
*   `trigger` — what in *this project* raised it, named concretely: a part, a net, a stated intent
    field, a stage declaration, a capability-profile value.
*   `source` — for a cited claim, where the fact came from, with the same rigour `Part` provenance
    already enforces. Empty is only legal for a computed claim.
*   `explanation` — maker-level prose. Written by hand for the pack, or generated from the record
    by the model, never invented by the model.
*   `arithmetic` — where a claim rests on a calculation, the calculation itself, shown. See
    `SPEC-211`, where showing the two-term sum is most of the value.
*   `state` — see below.

### 2.2 The trigger discipline

**No consideration exists without a trigger that names something real in the project.** If the
trigger cannot be named, the consideration is not raised. This is the whole safety property: it is
what prevents the family from degenerating into a generative best-practices essay, which is
precisely the output a language model produces fluently and wrongly (`SPEC-328` §3 names the same
hazard for suggested parts).

### 2.3 State, and why reinforcement needs it

A consideration is `raised`, `answered`, `satisfied`, or `dismissed` with a reason, persisted with
the project rather than lost with the chat. This buys three things:

1.  **Honest reinforcement.** Telling a user their design is good is worthless unless the app knows
    what the bad version would have been. *"You put a 100nF cap within 3mm of every VCC pin, and
    here is what that prevents"* is only sayable against a baseline. Generic praise is worse than
    silence.
2.  **Not asking twice.** A question answered stays answered.
3.  **Accumulation.** The project gets better understood the longer it is worked on, which is the
    actual mechanism behind *"talk me through my board"*.

### 2.4 Where it plugs in

`chat_agents._check_status_note` already reads `Project.last_results[area]` and feeds real ERC and
DRC findings into the review prompt, and `library_store.set_project_check_result` already persists
them. `SPEC-113` established `structural_checks.py` as a third source and the `copperplane.` type
prefix that marks a finding as this app's own rather than KiCad's. Considerations are the
generalisation of that third source, and they inherit the prefix convention.

### 2.5 Intent fields this family depends on

`SPEC-328` already stores a project `intent` string that nothing downstream reads. This family needs
a small number of structured fields alongside it, and every one of them must accept **unknown as a
first-class value** rather than a blank:

*   `board_stage` — for me / for others / being sold. The scope selector in §1.
*   `input_supply` — nominal voltage and what it comes from (USB, wall adapter, battery, host
    board).
*   `current_budget` — with an explicit "I do not know" that triggers an estimate from the parts on
    the board, labelled as an estimate everywhere it is used.
*   `environment` — indoor bench, enclosure, outdoors. Cheap to ask, gates several later packs.

Whether these live on the `Project` record or in a sibling object is an open question below. What
is settled is that they are structured fields, not prose to be re-parsed on every request.

### 2.6 Open questions this spec must settle

*   **Storage.** Do considerations live under `Project.last_results` alongside check results, or in
    their own store? `SPEC-113` left the same question open for structural findings and the two
    should be answered together, not separately.
*   **What a question *is*, as a surface.** The app already has a per-area chat and a project
    wizard. A third shape would repeat `SPEC-328`'s own warning about adding a fifth surface. The
    likeliest answer is that questions surface in the review as answerable cards and in chat as
    turns, sharing one record.
*   **Staleness of a dismissal.** A consideration dismissed as irrelevant may become relevant when
    the design changes. `SPEC-339` already owns review persistence and staleness; this must reuse
    that mechanism rather than inventing a second one.
*   **Who authors a pack, and in what format.** A Python module, a JSON/YAML data file, or a prompt
    fragment. The answer decides whether a contributor can add domain knowledge without touching
    the daemon, which matters for an Apache-2.0 project asking for help.
*   **Ordering.** With two packs live, a review could carry a dozen considerations. Ranking by
    claim class, by severity, or by "would this have built silently wrong" are different answers and
    the third is probably right.

## 3. Known Constraints & Risks

*   **A false positive costs more here than anywhere else in the product.** `SPEC-113` states this
    for one rule and it scales with the category: the first time the app is confidently wrong about
    a board the user understands better than it does, the whole family is spent. Every pack clears
    the same bar `SPEC-113` set, which is measurement against a real board with its false positives
    counted, not plausibility.

    **Measured 2026-09-10, and the rate is the point: three packs were written from plausibility and
    all three failed on first contact with a real board.**

    | pack | what the plausible rule did on a *correct* board |
    | :--- | :--- |
    | `led_series_resistor` | fired on `GND` — the LED's cathode sits on ground and no resistor does |
    | `power_pin_without_decoupling` | could not tell a supply rail from ground; KiCad marks both `power_in`. Withdrawn |
    | `component_without_value` | matched **all eleven symbols**, including a net name, four mounting holes and the Arduino's part number |

    Two of the three were salvaged by finding another **file fact** to key on — `pinfunction` naming
    `A_2` and `K_1`, a closed list of symbols whose value is an electrical parameter. The third had
    no fact to rest on and was removed.

    So this is not a bar that packs usually clear and occasionally miss. **It is a bar that a rule
    written from plausibility fails by default**, and the measurement that catches it is one command
    against one board. Any pack that has not been run against a real design has not been written yet,
    however reasonable it reads — and the reviewer's question is not *is this rule sound* but *what
    did it do on a board that is fine*.
*   **The person being taught is the person least able to check the teaching.** With a DRC finding
    the user can go and look. With an explanation of *why* something matters they have no
    independent check, which is why `general_practice` needs to become visible to the user rather
    than staying a machine-only field in the citation block.
*   **Verification needs boards that are broken on purpose.** Every pack needs fixtures with known
    defects, committed to the repo, in the way `parity_match.kicad_sch` already serves ERC. This is
    a real work item with real effort attached and not a footnote; without it a pack can only be
    tested when a user happens to have the bug.
*   **This is a category, not a feature, and the maintainer is one person.** The named domains
    beyond the first two (grounding and return paths, thermal, signal integrity, assembly
    ergonomics) are a multi-year backlog. They stay named and unbuilt in `ROADMAP.md`. Shipping two
    packs well is the goal; shipping six badly is the failure mode.
*   **Everything here has been designed on one machine with one board.** Stated now rather than
    discovered later, per the repo norm.

## 4. Module Map & Reference Links

*   `services/python-daemon/structural_checks.py` — `SPEC-113`'s computed findings, the pattern
    this generalises.
*   `services/python-daemon/chat_agents.py` — `_check_status_note`, `_REVIEW_PROMPT`.
*   `services/python-daemon/library_store.py` — `set_project_check_result`, `Project`.
*   [SPEC-113](SPEC-113-structural-consistency-checks.md) — the first computed finding, and the
    principle this spec generalises.
*   [SPEC-205](SPEC-205-datasheet-design-guidance.md) — datasheet-grounded guidance, the source of
    most cited claims.
*   [SPEC-114](SPEC-114-fabrication-capability-profiles.md) — first pack.
*   [SPEC-211](SPEC-211-power-path-review.md) — second pack.
*   [SPEC-319](../../../apps/tauri-ui/specs/SPEC-319-ai-review.md) — the review that surfaces these.
*   [SPEC-327](../../../apps/tauri-ui/specs/SPEC-327-design-advice-layout-and-clearance.md) — the
    judgement-class sibling.
*   [SPEC-328](../../../apps/tauri-ui/specs/SPEC-328-project-intent-and-suggested-parts.md) — owns
    the intent record §2.5 extends.
*   [SPEC-339](../../../apps/tauri-ui/specs/SPEC-339-review-persistence-and-staleness.md) — owns
    staleness; dismissals reuse it.

## 5. User & Interaction

*   **Product Stage:** Review, wherever ERC, DRC and structural findings already appear, and the
    per-area chat that discusses them.

*   **What the user is trying to accomplish:** Finding out what they should be thinking about on
    this board before they spend money on it, without knowing the vocabulary well enough to ask.

*   **What the user sees and does:** Nothing new to click. The review they already run carries
    additional items marked as coming from Copperplane rather than from KiCad. Some are findings
    with an explanation and, where relevant, the arithmetic behind them. Some are questions with an
    "I do not know" answer that is always acceptable, and answering one both sharpens what the app
    can compute and is remembered for the rest of the project.
