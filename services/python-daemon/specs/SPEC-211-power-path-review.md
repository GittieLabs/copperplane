---
id: SPEC-211
title: "The Power Path Review"
status: Draft
type: Feature
created: 2026-09-07
last_updated: 2026-09-08
target_version: v0.7.0
location: "services/python-daemon/specs/SPEC-211-power-path-review.md"
parent_spec: "SPEC-210-design-considerations-model.md"
child_specs: []
user_facing: true
---

# SPEC-211: The Power Path Review

## 1. Executive Summary & Goals

*   **High-Level Goal:** From two questions the user can answer in fifteen seconds, plus the part
    records the project already holds, check the board's power chain and show the arithmetic. This
    is the second pack under `SPEC-210` and the one that carries the *"this would have cooked"*
    story.

*   **The lead case is linear regulator dissipation, and the real numbers are better than the ones
    this spec was drafted with.** Measured 2026-09-08 against the AMS1117 datasheet: SOT-223 thermal
    resistance **88 degC/W** junction-to-ambient, operating junction temperature **-40 to +125 degC**,
    on-chip **thermal shutdown at 150 degC**, absolute maximum input **18V**, rated **1A**.

    A maker's first board runs one of these from a 12V wall adapter, because that is what the
    tutorial they followed did. From 12V to 3.3V at half an amp the part throws away
    `(12 - 3.3) x 0.5 = 4.35W`, and `4.35W x 88 degC/W` is a **383 degC rise above ambient**. It does
    not get there; it shuts down.

    **The sentence to actually put in front of the user is the ceiling, not the wattage.** Staying
    inside the datasheet's own 125 degC maximum junction temperature at 25 degC ambient allows
    `100 / 88 = 1.14W`, and at an 8.7V drop that is about **130mA**. So on a 12V supply, the "1A
    regulator" everyone believes they have is a 130mA regulator. That is arithmetic a maker can
    follow in one line, it explains something they have physically experienced, and the fix is real
    and teachable: drop the input voltage, or use a switching regulator.

    **The caveat travels with the number.** 88 degC/W is the datasheet's own figure and real thermal
    resistance depends heavily on the copper the tab is soldered to, so this is a first-order
    estimate and the UI must label it as one. It is also a *conservative* direction of error, which
    is the right direction for this audience.

*   **Why this pack rather than "input protection", which was the obvious candidate.** Reverse
    polarity has a hit-rate problem on exactly the audience this is for. A first board is usually
    fed from a devkit or a USB connector, both keyed, so the reversal mostly cannot happen and the
    story does not fire often enough to carry the proof. Reverse polarity survives as one
    consideration *inside* this pack rather than as the headline.

*   **Everything here hangs off two questions**, which is the second reason to build it early: it
    makes `SPEC-210`'s question mechanism prove itself on a real feature instead of being bolted on
    later. What feeds this board, and roughly how much current does it need.

*   **Nothing here needs schematic connectivity**, which keeps netlist reading off the critical
    path. That constraint also shapes the output, honestly and severely, and §2.4 says how.

*   **Non-Goals:**
    *   **Does not size or select components.** It does not pick a regulator, choose a capacitor, or
        specify a protection part. It says what the arithmetic implies and hands the decision back.
    *   **Never edits anything.**
    *   **Not a thermal simulation.** A first-order dissipation number against a datasheet limit,
        with its assumptions stated, is the entire claim.
    *   **Not general absolute-maximum extraction across every part.** v1 is regulators only, for
        the reason in §2.3.

## 2. System Architecture & Design Choices

### 2.1 What is in the pack

1.  **Linear regulator dissipation.** `(Vin - Vout) x Iout` against the part's package thermal
    limit. The lead case.
2.  **Stated input voltage against a part's absolute maximum rating.** This is the literal fry case:
    a 12V input and a part rated to 6V. Constrained by §2.4.
3.  **Current budget against what the source can actually supply.** Twelve LEDs off a USB port.
4.  **Trace width against current**, per §2.5.
5.  **An unkeyed two-pin power input with nothing protecting it.** The reverse-polarity
    consideration, computed from the connector's own footprint (a two-pin screw terminal or bare
    header is reversible in a way a keyed connector is not) and gated on the user having said this
    is the power input.

### 2.2 The current number, and why a guess is fine

A novice does not know their current draw. The app asks, offers "I do not know", and on that answer
estimates from the parts on the board. **Every finding states which number it used and where that
number came from**, so a finding built on the user's guess says so and a finding built on the app's
estimate says so. A wrong estimate that is labelled is honest; an unlabelled one is the kind of
confidently-wrong output that spends this family's credibility.

A maker made to think about their current budget for thirty seconds has learned something even when
the number they produce is wrong, which is a real part of the value and not a consolation.

### 2.3 Regulators only, in v1

A regulator's input voltage, output voltage, output current and package thermal resistance are among
the most reliably extractable numbers on a datasheet, and the regulator is where the money shot is.
General absolute-maximum extraction across every part on a board inherits the whole reliability
problem `SPEC-205` owns, and a wrong thermal or maximum-rating claim is precisely the confidently
wrong case §3 warns about. Widening the net is a later phase with its own measurement.

Identifying *which* parts are regulators, from records the library already holds, is an open question
and probably the largest unknown in this spec.

### 2.4 What not having connectivity actually costs, stated plainly

The app cannot see how a `.kicad_sch` is wired. Its own chat prompts say so. So it **cannot prove
that the input voltage reaches the part it is worried about**, and several items in §2.1 are
therefore not findings at all. They are questions:

> You said this board is fed 12V, and U2 is rated to 6V maximum. Is there a regulator between them?

That is the honest shape, and it is a better interaction than a false certainty in both directions.
If the answer is no, the user has just been saved. If the answer is *"yes, the AMS1117"*, the app has
learned the topology from the user without reading a netlist, and that answer persists as project
intent under `SPEC-210` §2.3.

Which items in §2.1 are findings and which are questions must be settled item by item in this spec
and not left to the implementation. Item 1 is a finding when the regulator's own record supplies both
voltages. Item 2 is a question. Item 5 is a question until the connector's role is confirmed, then a
finding.

### 2.5 Trace width: the citation question, settled 2026-09-08

**Settled: name the standard, implement the formula, never reproduce the tables. The item stays in
v1.** The precedent is KiCad itself. Its PCB Calculator ships a Track Width tool, and KiCad's own
documentation says it *"calculates the trace width for printed circuit board conductors for a given
current and temperature rise. It uses formulas from IPC-2221 (formerly IPC-D-275)."* A GPL tool in
this exact domain names the standard and implements the relationship without republishing the
standard's charts. Copperplane can do the same. What it must not do is reproduce IPC's tables or
ship the document.

**Two corrections that came out of checking, and both belong in the user-facing copy.** IPC-2152,
published in 2009, supersedes IPC-2221's trace-sizing charts: it is based on modern thermal testing,
accounts for board construction, copper weight and proximity to planes, and generally permits
*narrower* traces for the same current. IPC-2221 is the older and more conservative one, and it is
built on a single stackup from decades ago.

For a maker's first board, conservative is the correct direction to be wrong in, and IPC-2221 is
also the basis KiCad's own calculator uses, so a user cross-checking against KiCad will get the same
answer. That makes IPC-2221 the defensible choice here. But the app must **say which standard it
used and that a newer one exists**, rather than implying IPC-2221 is current. Presenting a
superseded standard as the current one is exactly the kind of confidently-wrong output this family
cannot afford.

### 2.6 Open questions

*   **Identifying a regulator** among the project's parts, and what happens to a part record that
    has no thermal data at all. Silence, or an explicit "cannot compare", never an assumed value.
*   **Showing the arithmetic inline or on demand.** The sum is the teaching, so inline is likely
    right, but four sums in one review is a wall.
*   ~~**The AMS1117 numbers in §1 are illustrative and unverified.**~~ **Closed 2026-09-08**: read
    off the datasheet and recorded in §1, including the copper-area caveat, which is now a UI
    requirement rather than an open question. The framing changed as a result — the ceiling (about
    130mA on a 12V supply) is the teachable number, not the 4.35W.
*   **Where the two questions are asked.** They belong with `SPEC-328`'s intent surface rather than
    as a prompt inside the PCB tab, but that depends on `SPEC-210` §2.6's answer about what a
    question is.

## 3. Known Constraints & Risks

*   **A wrong thermal claim is the worst output this pack can produce.** It is confident, numeric,
    and about the user's own board. Every number must trace to a datasheet field or a stated user
    input, and an unknown must produce silence rather than a default.
*   **The dissipation check inherits `SPEC-205`'s extraction reliability.** If the regulator's
    datasheet numbers are wrong, this is wrong with arithmetic-flavoured authority. Consider
    requiring user confirmation of the two voltages before the finding is emitted at all.
*   **Estimating current from a parts list is weak.** It cannot know duty cycle, brightness, or what
    a module does when its radio transmits. The estimate is a starting point for a conversation and
    must never be presented as a measurement.
*   **Half of §2.1 degrades to questions without connectivity.** That is the honest state of the
    product today, and it is the strongest argument for netlist reading being the next platform
    investment after these two packs land.
*   **One machine, one board.** As everywhere else in this repo.

## 4. Module Map & Reference Links

*   `services/python-daemon/datasheet_guidance.py` — `SPEC-205`'s extracted guidance, the source of
    the regulator numbers.
*   `services/python-daemon/library_store.py` — `Part` records and their provenance.
*   `services/python-daemon/structural_checks.py` — the computed-finding pattern to follow.
*   `services/python-daemon/kicad_board.py` — the board reader, for the connector footprint in
    §2.1 item 5.
*   [SPEC-210](SPEC-210-design-considerations-model.md) — parent; the record, the trigger discipline
    and the question mechanism.
*   [SPEC-205](SPEC-205-datasheet-design-guidance.md) — datasheet guidance, and the reliability
    this pack inherits.
*   [SPEC-114](SPEC-114-fabrication-capability-profiles.md) — sibling pack, shipped first.
*   [SPEC-328](../../../apps/tauri-ui/specs/SPEC-328-project-intent-and-suggested-parts.md) — where
    the two questions most likely live.

## 5. User & Interaction

*   **Product Stage:** Overview and PCB. The two questions belong with project intent; the findings
    appear in the review alongside everything else.

*   **What the user is trying to accomplish:** Finding out whether the board will survive being
    plugged in, having never had to think about where the heat in a regulator goes.

*   **What the user sees and does:** They are asked what feeds this board and roughly how much
    current it draws, with "I do not know" always available. The review then carries power findings
    that show their arithmetic in one line, say which number came from the user and which from a
    datasheet, and ask rather than assert wherever the app cannot see how the board is wired.
