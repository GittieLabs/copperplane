---
id: SPEC-211
title: "The Power Path Review"
status: Draft
type: Feature
created: 2026-09-07
last_updated: 2026-09-10
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

*   ~~**Nothing here needs schematic connectivity**, which keeps netlist reading off the critical
    path.~~ **Overtaken 2026-09-10.** `CTX-210.1` shipped netlist reading, so connectivity is
    available and free. The design choice this bullet protected — never depend on it — is no longer
    a cost worth paying: see §2.0, and §2.4 for what it changes.

*   **Non-Goals:**
    *   **Does not size or select components.** It does not pick a regulator, choose a capacitor, or
        specify a protection part. It says what the arithmetic implies and hands the decision back.
    *   **Never edits anything.**
    *   **Not a thermal simulation.** A first-order dissipation number against a datasheet limit,
        with its assumptions stated, is the entire claim.
    *   **Not general absolute-maximum extraction across every part.** v1 is regulators only, for
        the reason in §2.3.

## 2. System Architecture & Design Choices

### 2.0 Measured 2026-09-10: the connectivity premise is stale, and the regulator question has an answer

This spec was drafted on 2026-09-07 around a constraint that no longer holds, and its largest stated
unknown turns out to be a lookup. Both were measured against five real boards before anything was
built, per `CLAUDE.md`'s norm.

**1. Connectivity exists now, so §2.4's premise is false.** `CTX-210.1` added
`kicad_cli.export_netlist()` on 2026-09-09 — one `kicad-cli sch export netlist` command, pin-level,
on a closed file. §2.4 says the app *"cannot prove that the input voltage reaches the part it is
worried about"* and therefore demotes several items to questions. It can now prove exactly that. On
`Hello_World_Blinky`, the rail `+9V` and `U2` pin 8 `VCC_8` are the **same net**, which is item 2's
entire missing fact. **Item 2 is promoted from a question to a finding**, and §2.4's honest-shape
argument survives only for the cases connectivity genuinely cannot settle.

**2. `lib_id` answers §2.3's "largest unknown" — identifying a regulator.** KiCad ships the taxonomy
already: `Regulator_Linear` (1,626 symbols) and `Regulator_Switching` (1,148), as separate
libraries. Library membership is the classifier, the same trick `SPEC-210` used for `Device:LED` and
`is_mounting_hole`. **The split is the part that matters**: the dissipation arithmetic applies to a
linear regulator and is nonsense for a switching one — which is the *fix* this pack recommends, not
the problem. A classifier that could not tell them apart would confidently recommend a switcher to
someone who already had one.

**3. 440 of those 1,626 symbols encode the output voltage in the name** — `AMS1117-3.3`, `AMS1117-5.0`
— so `Vout` needs no datasheet extraction at all for 27% of the library, and the bare `AMS1117`
(adjustable) legitimately yields nothing. That is §3's "unknown must produce silence" case arriving
for free rather than as a special path.

**4. The obvious heuristic is 0% precise, and would have shipped.** Before checking `lib_id` I
tested "a part with a `power_in` pin and a `power_out` pin is a regulator". Across five boards it
returns three parts: `Arduino_UNO_R3`, `Adafruit-Feather-ESP32-S3` and `XIAO_ESP32-S3`. **Every hit
is a dev board module and not one is a regulator.** It is not even wrong in an obvious way — those
modules do contain regulators, which is precisely what makes the false positive convincing.

**5. `pintype` values are compound strings, and equality silently misses pins.** The real values
include `power_out+no_connect`, `bidirectional+no_connect` and `power_in+no_connect`. Any
`type == "power_out"` test drops every unconnected power pin without erroring. Split on `+` and
compare the first field.

**6. The lead case's part does not exist on any board we have.** Zero discrete regulators across all
five: `Copperplane_Blink_LEDs`, `NFC_Reader_ESP32`, `MacroPad`, `Hello_World_Blinky` and
`BB8-Breakout`. Power arrives through a devkit module or a battery cell, every time. **This is the
most important measurement in this section** and §3 now carries it: the headline story cannot be
verified against a board the maintainer owns, and a fixture built for the test is not the same
evidence.

It also *relocates* the story rather than killing it. On `Copperplane_Blink_LEDs` the rail `+5V`
lands on `A1` pin 8, whose `pinfunction` is `VIN_8` — the Arduino's **regulator input**. The §1
arithmetic is the same arithmetic; it just happens inside a module whose datasheet this app does not
hold. Whether that becomes a finding, a question, or nothing is Phase 1's to settle with evidence,
not this section's to assume.

**8. Measured 2026-09-10, and it costs this spec its headline sentence: there is no thermal data
anywhere in this app, for any part.** §1 says *"the sentence to actually put in front of the user is
the ceiling, not the wattage"* — the 130mA figure — and a ceiling needs a thermal resistance to
divide by.

`SPEC-205`'s design guidance is **quotes and page numbers**, not numbers: an item is
`{"quote", "page", "category"}`. `datasheet_structure.CATEGORY_PATTERNS` has eight categories and
none of them is thermal, and neither datasheet module parses a numeric value at all — there is not a
single `float()` call between them. Nothing else in the daemon holds a junction temperature, a
package thermal resistance, or an absolute maximum as a number.

So §2.6's open question — *"what happens to a part record that has no thermal data at all"* — turns
out to describe **every part there is**, and the choice it offered decides the matter: *"silence, or
an explicit 'cannot compare', never an assumed value."* A package-typical figure inferred from a
footprint would be an assumed value wearing a citation's clothes, and §3 names a wrong thermal claim
as the worst output this pack can produce.

**What ships instead is the watts, which are real.** `(Vin - Vout) x Iout` over three stated numbers
— output voltage from the symbol name, input voltage from the rail the netlist proves reaches the
part, current from the user's own answer — each labelled with where it came from, per §2.2. Then one
sentence saying plainly that whether that wattage is survivable depends on the package and the
copper, and that this app does not hold that figure.

That is less than §1 promised and it is the honest version of it. The ceiling becomes reachable the
day a part record carries a thermal resistance with provenance, and nothing here has to change for
it to: the arithmetic is already in the record's `arithmetic` field.


**7. The two questions are already built.** `input_supply` (with `source`, `nominal_volts`) and
`current_budget` (with `milliamps`) landed in `library_store.INTENT_FIELD_VALIDATORS` under
`CTX-343.1`, both accepting `unknown` as a first-class value distinct from never-asked. §2.2 does
not need a mechanism; it needs a consumer.

And the supply is often **derivable**, which `SPEC-343` §2.5.2 says must be checked before asking:
four of the five boards name their own rail — `+5V`, `+9V`, `/5V`, `VCC`. Asking a user to type a
number their schematic already states is the kind of question that teaches them the app is not
paying attention.

### 2.1 What is in the pack

> **Status 2026-09-10.** All five ship, plus a sixth case this list did not anticipate. Kept as a
> table rather than deleted, because knowing *which context built what* is the thing a later session
> needs and the item numbers alone do not say.
>
> | Item | State |
> | :--- | :--- |
> | 1. Linear regulator dissipation | **Ships**, as watts rather than §1's ceiling — see §2.0 item 8 |
> | 2. Input voltage against an absolute maximum | **Ships** — `CTX-211.3`, and the quote travels with the number |
> | 3. Current budget against the source's capability | **Ships**, for USB only — `CTX-211.2` |
> | 4. Trace width against current | **Ships**, cited to IPC-2221 |
> | 5. Unkeyed two-pin power input | **Ships**, and needed no question — see §2.4 |
> | *(unlisted)* A module fed the voltage it makes | **Ships.** The case that speaks about the boards this project actually has |
>
> **Item 2 was the one to be careful about, and §2.3's warning was exactly right.** A naive parse of
> the ATTINY85's absolute-maximum section returns **13.0V** — a `RESET` pin rating — for a part whose
> supply maximum is **6.0V**, which would call a 12V rail safe on a 6V part. `CTX-211.3` keys the
> parse on the row's own label, and makes a wrong parse harmless by emitting a claim **only on
> exceedance**: too low is a visible false positive shown beside the quote that contradicts it, too
> high is silence. Neither reaches a false reassurance, which is the failure §3 forbids.


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

~~Identifying *which* parts are regulators, from records the library already holds, is an open question
and probably the largest unknown in this spec.~~ **Closed 2026-09-10**: it is library membership on
`lib_id`, and KiCad's own split between `Regulator_Linear` and `Regulator_Switching` is exactly the
distinction the arithmetic needs. §2.0 item 2, and item 4 for the heuristic this replaced.

### 2.4 What not having connectivity actually costs — largely repaid 2026-09-10

> **This section was written when the app could not read a netlist. It now can** (§2.0 item 1), so
> the specific cost below is repaid: the app **can** prove the input voltage reaches the part, and
> item 2 is a finding rather than a question. What survives, and is worth keeping, is the *shape* —
> a question is the honest output wherever the app genuinely cannot see something, and asking is
> better than false certainty in either direction. The remaining cases are the ones connectivity
> does not settle: what a module does internally, and what role a connector plays.

The app could not see how a `.kicad_sch` is wired. Its own chat prompts said so. So it **could not
prove that the input voltage reaches the part it is worried about**, and several items in §2.1 were
therefore not findings at all. They were questions:

> You said this board is fed 12V, and U2 is rated to 6V maximum. Is there a regulator between them?

That is the honest shape, and it is a better interaction than a false certainty in both directions.
If the answer is no, the user has just been saved. If the answer is *"yes, the AMS1117"*, the app has
learned the topology from the user without reading a netlist, and that answer persists as project
intent under `SPEC-210` §2.3.

Which items in §2.1 are findings and which are questions must be settled item by item in this spec
and not left to the implementation. Item 1 is a finding when the regulator's own record supplies both
voltages. ~~Item 2 is a question.~~ **Item 2 is a finding as of 2026-09-10**, because the netlist
proves the rail and the part's supply pin are one net; it degrades to a question only when the
supply voltage itself is unknown. ~~Item 5 is a question until the connector's role is confirmed, then
a finding.~~ **Item 5 is a finding as of 2026-09-10, and nobody is asked.** The netlist confirms the
connector's role on its own: on `BB8-Breakout`, `Net-(J4-Pin_1)` carries J4 pin 1 and `X1`'s `5V`
power-in pin while J4 pin 2 sits on ground, which is what "this is the power input" means. The
confirmation §2.4 expected to need a user turns out to be readable.

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

*   ~~**Identifying a regulator** among the project's parts~~ — **closed 2026-09-10**, §2.0 item 2.
*   ~~**What happens to a part record that has no thermal data at all.**~~ **Closed 2026-09-10**:
    every part is that part, because this app holds no thermal data of any kind (§2.0 item 8). The
    answer is the explicit "cannot compare" rather than silence — the pack states the watts and says
    in one sentence why it is not stating a temperature.
*   ~~**Trace width: which items cite and which compute.**~~ Settled in §2.5 and **implemented
    2026-09-10**: `trace_too_narrow_for_current` is the family's first `cited` claim. The arithmetic
    is ours and the relationship is IPC's, so it carries `source` naming IPC-2221, states that
    IPC-2152 supersedes it, and says that 1oz copper is an assumption — no board measured states a
    copper weight. Verified to agree with KiCad's own Track Width calculator, which is the point of
    having chosen IPC-2221.

*   **Showing the arithmetic inline or on demand.** The sum is the teaching, so inline is likely
    right, but four sums in one review is a wall. Still open, and now with something concrete behind
    it: a consideration carries its calculation in `arithmetic`, so the surface can choose.
*   ~~**The AMS1117 numbers in §1 are illustrative and unverified.**~~ **Closed 2026-09-08**: read
    off the datasheet and recorded in §1, including the copper-area caveat, which is now a UI
    requirement rather than an open question. The framing changed as a result — the ceiling (about
    130mA on a 12V supply) is the teachable number, not the 4.35W.
*   ~~**Where the two questions are asked.**~~ **Closed 2026-09-10**: they are intent fields, they
    exist, and `CTX-343.1` built them — `input_supply` and `current_budget`, both with `unknown` as
    a first-class value (§2.0 item 7). The open part is narrower and better: **derive before
    asking**, per `SPEC-343` §2.5.2, since four of five boards name their own supply rail.

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
*   ~~**Half of §2.1 degrades to questions without connectivity.**~~ **Resolved 2026-09-10** — the
    argued-for investment was made first. `CTX-210.1` shipped netlist reading, so item 2 is a
    finding and only the module-internal and connector-role cases stay questions.

*   **No board available to this project contains a discrete linear regulator.** Measured across all
    five (§2.0 item 6): power arrives through a devkit module or a battery, every time. The lead
    case — the one carrying the whole *"this would have cooked"* story — can therefore be exercised
    only against a schematic authored for the test. That is a real KiCad file read by real
    `kicad-cli`, which is worth something, but it is **not** evidence that the pack fires correctly
    on a board a user drew, and it must not be reported as if it were.
*   **One machine.** Five boards rather than one, which is better than this repo usually manages —
    but all five are the same maintainer's, and three are devkit-carrier boards of the same shape.

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
