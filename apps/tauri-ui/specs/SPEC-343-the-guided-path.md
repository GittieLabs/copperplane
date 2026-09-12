---
id: SPEC-343
title: "The Guided Path"
status: Completed
type: Feature
created: 2026-09-10
last_updated: 2026-09-10
target_version: v0.7.0
location: "apps/tauri-ui/specs/SPEC-343-the-guided-path.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-343: The Guided Path

## 1. Executive Summary & Goals

*   **High-Level Goal:** One place that always answers *where am I, and what would move this
    forward* — without hiding anything, interrupting anyone, or deciding for them.

*   **The gap, stated by the maintainer:** every vertical slice of this product is strong on its
    own, and nothing joins them. *"We are making the assumptions that a project exists with a
    schematic that adheres to the goal that also has a matching pcb with components connected ready
    for an enclosure. This isn't wrong. We can be helpful at any of these tasks independently by
    design. But we also need to provide an option that would start from scratch, understand the
    goal, provides real guidance to get started and remembers where we left off."*

*   **The audience this is for, and the failure it exists to prevent.** A maker, not a professional.
    *"The maker wants to finish a project and not get discouraged or confused enough to say our app
    is not helpful bc they got lost."* Every decision below is answerable against that sentence.

*   **The flow is not linear and the design must not pretend otherwise.** Reviewing the PCB can send
    someone back to the schematic; teaching about either can change both; a project's considerations
    change when its schematic does. `SPEC-300` already calls the stage machine *"a DAG, not a
    wizard"*. This spec's job is to make the DAG legible, not to straighten it.

*   **Non-Goals:**
    *   **Not hiding views.** Ruled out explicitly by the maintainer, and it contradicts
        `SPEC-300`'s *"every stage is enterable directly"*. A novice who cannot find what someone
        told them about, in an app that decided for them, is a worse outcome than a busy tab bar.
    *   **Not a wizard.** No step lock, no forced order, no blocked stage.
    *   **Not chat.** See §2.1 — `SPEC-300` forbids it, and that constraint is the shape of this
        whole spec rather than an obstacle to it.
    *   **Not new knowledge.** Everything shown here is already computed by `SPEC-210`,
        `SPEC-328`, `SPEC-113`, `SPEC-339` and the check surfaces. This is where it is joined, not
        where it is invented.

## 2. System Architecture & Design Choices

### 2.0 Measured 2026-09-10: the reading is unambiguous, and the action is the thin part

`CTX-343.1` Phase 1 tested §2.4's claim before anything was built on it, on two halves that fail
differently: is the reading unambiguous, and is there a real next action.

**The reading is unambiguous almost everywhere.** Enumerating the state space — intent, linked
project, schematic checked, board checked, enclosure, staleness — **2 of 64 combinations** are
ambiguous, and they are the same state: *nothing has been checked at all*, where both "check the
schematic" and "check the board" are equally defensible. Every other state has one defensible
reading.

**The next action is thin, and that is the finding.** Four of the six actions are *"go to the tab
this points at and press the button already on it"*: check the schematic, check the board, generate
an enclosure, re-run what is behind. Only two — say what you are building, and link a KiCad project —
are things the user could not already be looking at.

**But the reading is not thin, and that is where the value is.** *"Your schematic changed after the
PCB check"* is something **no tab can say**, because no tab knows about two stages at once. Overview
is the only surface positioned to know it.

So the honest shape is the reverse of what §5 implies: **a "where am I" line is the feature, and
"what's next" is a convenience attached to it.** That is smaller than a guided path and it is the
part that could not be built anywhere else.

**One ordering problem this exposed, and it is `SPEC-343` §2.6's open question made concrete.**
Staleness reaches 32 of 64 combinations — half the space — because a stale check currently outranks
everything. That is wrong at least once: a project where the user never said what they are building
*and* has a stale check should say the first, not the second. Ranking is a real decision, not a
detail, and `SPEC-210` §2.6 left the same question open. Answer both together.

**Sample weakness, stated rather than discovered later.** Only three real projects exist on the
maintainer's machine and two are in near-identical states, so the state space was enumerated rather
than sampled. Enumeration proves the reading is *decidable*; it does not prove the states occur in
the proportions a real user would hit.

### 2.1 Inherited from `SPEC-300`, not re-decided here

Two of that spec's rules settle most of this one, and both are load-bearing:

> *"A conversation surface can only ever produce an answer, never advance a stage, mutate a record,
> dispatch a flow step, or change which screen the user is on."*

**So the guided path cannot be chat.** This is why the existing per-area chat reads as user-initiated
rather than guiding: it was built that way deliberately. Any design where the agent walks someone
through stages violates a rule that exists to stop the app doing things nobody asked for.

> *"The stage machine is a DAG, not a wizard. Every stage is enterable directly."*

**So nothing is hidden and nothing is locked.** The guided path is a *reading* of the project, laid
beside the tabs, never in front of them.

### 2.2 The trigger is the timing

The maintainer's question, and the one this spec turns on: *"how/when do we tell the user anything
that we know they could be missing and that we know they need. Is that only done when they describe
their project?"*

**No — and description time is the worst moment for most of it.** `SPEC-210` §2.2 already settles
the timing without a new rule: a consideration cannot exist before its trigger is true, and once the
trigger is true it is as specific as it will ever be. So:

> **Say it when the trigger becomes true, not when the topic becomes relevant.**

The same knowledge legitimately arrives twice, at different specificity, because different triggers
fire. Measured on the maintainer's own board:

| moment | trigger | what it can say |
| :--- | :--- | :--- |
| intent stated | *"a blinking led controlled by a pushbutton"* | *"current-limiting resistor — without one in series, the LED will draw too much current from the Arduino pin"* |
| schematic saved | net `+5V` carries `D1`'s anode and no resistor | *"D1's anode is on +5V, and nothing on that net is a resistor"* |

Neither is redundant, and **the second could not have been said at description time** — there was no
`+5V` to point at. This is the argument against front-loading: saying everything at intent time means
saying all of it in its vaguest form, before any of it is actionable, which is exactly the
fourteen-things-on-day-one that makes a maker close the app.

### 2.3 Three trigger sources, and only one involves the user describing anything

*   **Intent.** What they said they are building (`SPEC-328`).
*   **A file.** The schematic or board changed, so the netlist changed, so packs re-run
    (`SPEC-210`, `CTX-210.1`). Nobody described anything; the app read a file.
*   **An answer.** A structured intent field changed what is in scope. `board_stage: being_sold`
    brings ESD, reverse polarity and connector keying into scope without the board changing at all
    — and `SPEC-210` §1 requires the app to be able to say those arrived *because that answer
    changed*.

### 2.4 Stage is computed, never declared

The project record already holds enough to say where someone is, with no new storage and nothing for
the user to set. Measured against the maintainer's three real projects:

| record state | what it means |
| :--- | :--- |
| no `intent` | never said what this is for |
| `intent`, no `kicad_project_path` | a goal and no files yet |
| both, no `last_results` | a design nothing has checked |
| `last_results` present, `stale_reason` set | **went back a stage** — the check is behind the file |

**The cycling is observable rather than asked about.** `CTX-210.1` Phase 4 reuses `SPEC-339`'s
staleness so a consideration set carries its source and goes stale when that file changes. *"You
edited the schematic, so the PCB check is behind"* is computed. A user never tells this app which
stage they are in, which is the only way a non-linear flow stays honest.

### 2.5 What may be volunteered is already decided

`SPEC-210` §1's initiative rule is the boundary between guidance and conversation, and it needs no
extension here:

*   **Computed and cited** claims may be raised unprompted. That is the guided path's content.
*   **A judgement** waits to be asked. That is chat's content.

So the two surfaces divide on a principle rather than on taste, and a new pack cannot accidentally
make the app opinionated — the rule is enforced in `considerations.py`, not in this spec's prose.

### 2.5.1 A description the user skipped, and a caveat that is not a nag

*"It is completely plausible that the user doesn't give much thought to the project description or
skips entirely. It's a hindrance that could make us less effective."*

**On Overview.** Overview already says *"Not stated yet — agents answer generically until you add
one"*, which states the fact and does not make the case. §2.4 computes `no_goal` as the earliest
state, so the guided path's one sentence **is** the callout — it needs to argue the benefit rather
than note the gap, and it must be **dismissible**, because a user who has decided not to describe
their project should not be asked forever. A callout that cannot be dismissed becomes furniture, and
furniture is not read.

**On a response.** *"We might even consider adding a message to a chat response ... that could have
given a better response if we knew what they are trying to build."*

Permitted, and the reason matters: `SPEC-300` says a conversation surface may only produce an answer,
and a caveat **about the basis of that answer** is still an answer. It advances nothing and moves
nobody. It is the same class as `SPEC-306`'s `view datasheet (unverified)` — an honest note about
what the answer rests on.

Two disciplines stop it becoming a scold, and both are enforceable rather than editorial:

*   **Only when it is true.** `chat_agents` resolves `project_intent` and passes it to four call
    sites, so the app knows whether an answer was produced without it. Never said on a response that
    would not have changed.
*   **Once per conversation, not once per turn.** Repetition turns an honest caveat into nagging, and
    the nagging is what makes a user stop reading the caveats that matter — including
    `unverified` and *not confirmed*, which this product depends on being read.

**And the rule that governs all of it:** we do not guess. *"I would have answered better knowing what
you are building"* is honest. *"This looks like an LED blinker, shall I assume that?"* is the
inference this family refuses to make, however confident it could be.

### 2.5.2 When a field is unknown *and* underivable

`SPEC-210` §2.5 says an explicit "I do not know" on `current_budget` *"triggers an estimate from the
parts on the board, labelled as an estimate everywhere it is used."* **Measured 2026-09-10: on the
maintainer's own board that estimate is not computable at all.**

The schematic carries `R1` with `value='R'` and `D1` with `value='LED'` — the placeholder values
KiCad ships, never set. With no resistance there is no current, and deriving one means inventing the
value, which is the guess this family exists not to make. So *"the user does not know"* and *"the app
cannot derive it"* are simultaneously true, on the board every other spec in this family is written
about. That state is currently assumed away.

**Four fallbacks, in order, and the app takes the first that works:**

1.  **Ask, and let `unknown` be a real answer.** Built — `CTX-328.1` Phase 2 stores `unknown` as a
    value distinct from never-asked, which is the whole reason that distinction exists.
2.  **Bound it from the supply, which survives when the current does not.** `power:+5V` is a real
    symbol on the schematic, so the rail voltage is a file fact, and a supply source bounds the
    current a board can draw. That is enough for a worst-case trace-width check **stated as worst
    case**. The bound itself is a `cited` claim and its numbers must be **read** from the USB
    specification, never recalled — the same discipline §2.0.1 states for IPC-2221.
3.  **Estimate from the parts, when the parts say anything.** Where values are set this works and
    shows its arithmetic (`SPEC-210` §2.0.1). Where they are not, it must fail rather than assume.
4.  **Say what would unblock it.** *"`R1` has no value"* is an absence that names something real, so
    it is a legitimate consideration under §2.2 — and it converts *"we cannot help"* into *"set
    `R1`'s value and this becomes answerable."* This is the first concrete case for §2.6's
    absence-shaped triggers, and it is real on an actual board rather than hypothetical.

**When all four fail, the honest answer is not a number.** A maker with a breadboard can measure the
current. Telling them so is the app distinguishing what it can compute from what only the bench can
say, which earns more trust than a figure with invented inputs — and is the same judgement `SPEC-212`
made when it declined to guess a datasheet URL.

### 2.6 Telling, when the app may not interrupt

Given §2.1, *telling* reduces to **it is there when they look, and something makes them look.** The
only mechanism that violates nothing is a count on the Overview tab: a signal that something changed,
which the user may ignore entirely. No modal, no redirect, no chat message arriving unbidden, no
stage advanced on their behalf.

Which reframes the design question usefully — not *when do we tell them*, but *what makes Overview
worth returning to*. It changes when their project changes, without them asking.

*Open questions this spec must settle:*

*   **What the callout says, and when it stops.** §2.5.1 settles that it must be dismissible; it does
    not settle whether dismissal is per project or forever, or whether a project that later gains a
    schematic should ask once more now that there is something to be specific about.
*   **Absence-shaped triggers, and this is where the value probably is.** §2.5.2 gives the first
    concrete case — a component with no value, blocking a current estimate — which is real on the
    maintainer's board rather than hypothetical. What a novice is missing is
    usually a part that is not there, so the trigger is an empty set rather than a present thing.
    `CTX-210.1` withdrew `power_pin_without_decoupling` because it could not distinguish a supply
    rail from ground — but the *shape* is legitimate and unresolved. An absence still has to name
    something real (§2.2): *"no capacitor on `+5V`"* names `+5V`. Settle what makes an absence
    nameable, because the alternative is the app staying silent about exactly the class of thing a
    beginner most needs.
*   **What "off" means.** Quiet entirely, or still *where am I* without the teaching? Those are
    different products for someone returning to a half-finished board.
*   **Whether a new project defaults it on.** Defaulting on and being dismissible means the novice
    gets it without choosing and the second-time user turns it off once; defaulting off means the
    people who need it most never see it.
*   **Ordering when several things are true at once.** `SPEC-210` §2.6 left the same question and
    named *"would this have built silently wrong"* as probably the right ranking. Answer both
    together.
*   ~~**What the one sentence says when nothing is wrong.**~~ **Settled 2026-09-10 — see §2.7.**

### 2.7 Settled: a silent pack is the reinforcement

The state where nothing is wrong was left open because `SPEC-210` §2.3 sets a bar generic praise
cannot clear:

> *"Telling a user their design is good is worthless unless the app knows what the bad version would
> have been."*

**It does know. That is exactly what a silent pack is.** `led_series_resistor` stays quiet on the
maintainer's board for a computed reason — `D1`'s anode is on `Net-(D1-A)` and `R1` is on it too —
and that reason is calculated and then thrown away. So:

> **"D1's anode reaches R1 — that resistor is what stops the LED drawing more current than the
> Arduino pin can give."**

Not praise. A computed fact about *their* board, naming *their* parts, teaching the thing they got
right and why it mattered. The baseline §2.3 demands is the finding that was not raised.

**Why this rather than "nothing is wrong":**

*   **"Nothing is wrong" is a claim this app cannot support.** It checked what it can check. A
    beginner reads that sentence as *my board is good*, and a board can pass every check here and
    still not work. Saying it would be the confidently-wrong-once §3 says spends the family.
*   **It teaches at the cheapest moment.** Someone who believes they are finished is relaxed and
    about to order. That is when an explanation costs them nothing to read.
*   **It is computed, not generated.** No model, so no invented compliment.

**Three constraints, or it becomes the noise it replaced:**

1.  **One at a time.** A wall of *"here is everything that is fine"* is its own overload, and the
    `complete` state is where a finished project sits forever.
2.  **Only where the pack genuinely cleared something.** A pack that was silent because its trigger
    was absent — no LEDs on this board — has taught nothing and must say nothing. *"Your board has no
    LEDs without resistors"* is true, useless, and faintly absurd.
3.  **Paired with what was not checked.** The `complete` state is exactly where a novice mistakes
    *checked* for *correct*, so the honest boundary belongs beside the reinforcement rather than
    instead of it.

**The cost, stated because it is a contract change and not a string.** Packs currently return only
what they raised. Reporting silence means each pack also returns what it **cleared** and why, which
every future pack must then do. Accepted deliberately: a pack that can explain its silence is a pack
whose reasoning can be read back, which is worth having whatever this surface does with it.

## 3. Known Constraints & Risks

*   **A guided surface that is wrong once is worse than none.** It speaks with the app's whole voice
    rather than one stage's. `SPEC-210` §3 already says the first confidently wrong claim spends the
    family; this surface is where that spending happens fastest.
*   **Legibility is not the same as progress.** A user can be told exactly where they are and still
    be stuck. The measure is whether they take the next action, not whether the sentence is accurate.
*   **The DAG has no end state, and the UI will imply one.** Any *what's next* wording risks reading
    as a checklist with a bottom. A board is never finished; it is ordered.
*   **Everything here is designed against one maintainer's three projects**, two of which are the
    same tutorial board. Stated now rather than discovered later.

## 4. Module Map & Reference Links

*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) — parent. Owns the stage machine, the
    navigation rule and the AI boundary this inherits. **Read §2's stage-machine and AI-boundary
    bullets before designing anything here.**
*   [SPEC-210](../../../services/python-daemon/specs/SPEC-210-design-considerations-model.md) — the
    considerations, the trigger discipline, and §1's initiative rule that splits guidance from chat.
*   [SPEC-328](SPEC-328-project-intent-and-suggested-parts.md) — intent, the structured fields, and
    the first trigger source.
*   [SPEC-339](SPEC-339-review-persistence-and-staleness.md) — the staleness mechanism §2.4 reuses
    to detect a stage regression.
*   [SPEC-313](SPEC-313-overview-tab-project-dashboard.md) — the tab this lands on.
*   `services/python-daemon/library_store.py` — the project record §2.4 computes stage from.
*   `apps/tauri-ui/src/components/Overview.tsx` — where it renders.

## 5. User & Interaction

*   **Product Stage:** Overview, across the whole project rather than any one stage.

*   **What the user is trying to accomplish:** Finishing a board without getting lost — knowing at
    any moment whether they are on track, and what one thing would move them forward.

*   **What the user sees and does:** On Overview, one sentence saying where the project stands and
    one action that would advance it, with anything the app has learned since they were last here
    shown beneath. They click the action, which takes them to the tab that already exists, or they
    ignore it entirely and use the tabs directly. Nothing is hidden from them, nothing happens
    without them, and the surface can be turned off for the project and back on at any point.

---

## 6. Shipped 2026-09-10 — and the one thing not verified

Both contexts closed: [CTX-343.1](../context/CTX-343.1-where-am-i.md) built the reading, the
toggle, the skipped description and absence-shaped triggers;
[CTX-343.2](../context/CTX-343.2-what-you-got-right.md) built §2.7's reinforcement.

**What is verified:** every route over real JSON-RPC against a linked project, the packs against a
real board (`SPEC-210` §3 records the three that failed on first contact and why), and the full
suite on both sides.

**§2.6 was designed and never built, found 2026-09-12.** *"A count on the Overview tab: a signal
that something changed"* — the packs computed `needs_attention` on every load and nothing rendered
it. Found while trying to screenshot the guide describing it: there was no such screenshot in 51
captures, because the app had never shown a finding. Built in
[CTX-343.4](../context/CTX-343.4-what-needs-attention.md).

That this spec closed as `Completed` with a settled §2.6 unbuilt is the more useful half of the
lesson. Everything §2.6 asked for was decided; the decision was mistaken for the work.

**Found by use, 2026-09-11, and it is the defect this section predicted.** The reading went stale:
the user was told *"Nothing has been checked yet"*, followed the *"Check the schematic"* action, ran
the review on the Schematic tab, came back, and the card had not moved. The record on disk was
correct and `project_stage.read` computed the right answer from it — every layer above the daemon
was stale, because `App` renders all areas at once and hides the inactive ones with CSS, so Overview
never unmounts and no effect here re-runs. Fixed by re-reading when the tab becomes visible.

It is worth being exact about what this cost. Every route was verified, every pack measured against
real boards, 968 frontend tests green — and the surface was broken in the first minute of somebody
using it, in a way none of that could have caught. `CLAUDE.md`'s *"verify as the user, not just as
the capability"* is not a formality.

**What is not:** nobody has used this surface as a novice would. The norm in `CLAUDE.md` —
*"verify as the user, not just as the capability"* — is satisfied for the capability and not for
the user, and `SPEC-302` is the reason that distinction is written down. §3's second constraint is
the one this leaves open: the measure is whether a user takes the next action, and that cannot be
read off a passing test. It needs the first real novice, which is what the self-managed testing
round is for.
