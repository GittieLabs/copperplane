# Product Plan: from capability demo to product

**Status:** Approved 2026-08-11 · **Date:** 2026-08-08 · **Supersedes:** ROADMAP.md §3.3 and §4
(M2–M3)

This is a plan, not a spec. It proposes the product model, the navigation, the stage machine, and
which specs need to exist in what order. Approved as of 2026-08-11 — `ROADMAP.md` §3.3 and §4 now
point here. The child specs in §5.1 are not yet written; those, not this document, are the real
commitment per spec, following the usual spec/context loop.

---

## 1. What actually went wrong

Three failures are visible in the current build. Only one of them is cosmetic.

**Intent is inferred from prose, so the same box does three unrelated things.**
`lib/commands.ts` string-matches the input to pick between component generation, board injection,
and open-ended chat. Typing *"looking for esp32-s3"* doesn't match `generate <part>`, so it falls
through to the chatbot — which answers by asking the user what they're trying to do, after the user
already said it. Typing *"generate atiny85"* — misspelled, one `t` — does match, and the pipeline
silently produces a correct ATtiny85. It was right by luck, and nothing surfaced that a correction
had occurred. A silent substitution that happens to be right is not better than one that's wrong;
it's the same mechanism, and next time it produces a footprint for a part the user didn't ask for.

**There are no product objects.** The output is a raw JSON dump into a message bubble. Nothing is
saved. `latestSchema` is a single variable, so generating a second component discards the first.
There is no component, no library, no project — only the transient result of the last call.

**And the cosmetic tell:** markdown renders as literal `##` and `**` in a wall of collapsed text,
and the enclosure panel is three unlabeled number inputs. Those are symptoms, not the disease.

**Root cause.** Every spec written so far answers *"can the machine do X."* None answers *"what is
the user doing."* The UI is the sum of per-capability test harnesses, each bolted on as its
capability landed. That was the right way to get here — the backend is real and verified — but it
has no organizing model, and adding a fourth capability the same way makes it worse, not better.
The backend is not the problem and almost none of it is wasted. What's missing is a layer above it.

---

## 2. The product model

### 2.1 Objects

Persisted as files, per the storage decision in §4.

| Object | What it is | Lifetime |
| :--- | :--- | :--- |
| **Project** | A named workspace grouping work toward one board. Holds *references* to library parts, its own artifacts, and a link to a KiCad project directory. | User-created, long-lived |
| **Part** | The part-number-level object: manufacturer, package name, pins, datasheet URL + cached PDF, **provenance**. References one symbol and one footprint. | Outlives any project |
| **Symbol** | The schematic representation of a part. Mirrors a KiCad symbol (`.kicad_sym`). | Global |
| **Footprint** | The PCB land pattern. Mirrors a KiCad footprint (`.kicad_mod`). **Many parts share one footprint.** | Global |
| **Artifact** | A generated file bound to a project and a stage: `.glb`, `.stl`, `.step`, an advisor report. | Per project |
| **Conversation** | Per-project chat history. | Per project |

**Symbols and footprints are separate libraries, exactly as KiCad models them, and we follow that
split rather than inventing a mapping.** This is not a storage detail — it's the correct cardinality.
SOIC-8 is one footprint shared by hundreds of unrelated parts; a part is one symbol plus a
*reference* to a footprint. Collapsing them into a single "component" object would duplicate
footprint geometry per part, make footprint reuse impossible, and produce an export that doesn't
map onto KiCad's own two libraries.

A consequence worth stating early: creating a part and creating a footprint are **separate user
actions with separate flows**. "Find or create the footprint for this part" is its own step, and it
can be skipped — a part with pins and a datasheet is useful before any footprint exists.

### 2.2 Provenance is not optional

Every field on a Component records where it came from: which source (datasheet PDF, supplier API,
model inference), which model and version, when, and a confidence signal. Without this, a component
is "an LLM said so," and no hardware engineer will trust it enough to put it on a board.

With it, three things the current build cannot do become possible: showing the user *why* a value
is what it is; letting the user correct a field and having the correction stick and outrank the
inference; and refusing to proceed when confidence is too low, with a specific reason.

The "closest matches with links for the user to view" flow only works if candidates carry their
sources. Provenance is what makes that honest rather than decorative.

### 2.3 The stage machine

Stages form a DAG, not a wizard. Every stage is enterable directly, and every stage accepts an
import as an alternative to inheriting from the previous one.

```text
   import part # / datasheet PDF                import .kicad_sch      import .kicad_pcb
              |                                        |                   |       |
              v                                        v                   v       v
   [1] Component Discovery ---> [2] Component Detail ---> [3] Schematic ---> [4] PCB ---> [5] Enclosure
        search, rank,               pins, guidance,           Advisor          Advisor      profile -> body
        disambiguate                footprint, export             |                 |
              ^                          |                        |                 |
              |                          v                        |                 |
              +----- repeat per part --  Library  <---------------+-----------------+
```

Stage 2 loops back to stage 1 — adding components one at a time is the common path, not an edge
case. Stages 3–5 each read from the library and can each be entered cold by importing a file.

**We are not building a schematic editor or a PCB editor.** Stage 3 shows a component with its pins
and tells you how to connect it. Stage 4 reads errors from a board the user already has and
explains them. The product is an advisor with hands, not a replacement CAD tool. That framing is
what keeps stages 3 and 4 tractable.

---

## 3. Navigation and the interaction rule

### 3.1 Shell

```text
+----------------+------------------------------------------+
|  PROJECTS      |                                          |
|   > Weather PCB|   [ Overview ] [ Components ] [ Schematic ] [ PCB ] [ Enclosure ]
|     Doorbell   |                                          |
|                |   ( the selected area's own surface )    |
|  LIBRARY       |                                          |
|   Components   |                                          |
|   Footprints   |                                          |
+----------------+------------------------------------------+
```

*Overview* is the project summary plus the freeform conversation with history. Chat belongs
here — as a **place**, not as a router. The library sits outside any project, because components
are reusable across projects by design.

### 3.2 The rule that fixes the reported bug

> **A text input inside a stage is a parameter to that stage's function. It is never a command
> line.**

In Component Discovery, typing is a search query and can only ever produce candidate components. In
Overview, typing is conversation and can only ever produce a reply. The same widget, two
unambiguous meanings — because *the surrounding context disambiguates, not a parser*. `parseCommand`
is deleted, not improved.

### 3.3 Where AI is allowed to act

| AI does | AI does not |
| :--- | :--- |
| Search for a part and rank candidates | Decide which screen the user is on |
| Extract structure from a datasheet | Silently correct the user's input |
| Ask for clarification when confident matching fails | Write to a board without explicit confirmation |
| Explain an ERC/DRC error and suggest a fix | Return prose where a typed result is expected |
| Converse, in Overview | Apply a change the user didn't see first |

Two disciplines follow. **Every AI step inside a deterministic flow returns a typed result**, not
prose — prose is confined to Overview. And **ambiguity surfaces as a structured choice**: "atiny85"
produces a *did you mean* card listing ATtiny85 with its datasheet link and a confidence note, which
the user confirms. It does not produce a silent substitution.

---

## 4. Storage: files as truth, index as cache

```text
~/HardwareAgentStudio/            # user-chosen root
  library/
    parts/ATtiny85.part.json      # references a symbol and a footprint by id
    symbols/                      # exportable as a KiCad .kicad_sym library
    footprints/                   # exportable as a KiCad .pretty library
    datasheets/ATtiny85.pdf       # cached alongside its URL
  projects/
    weather-pcb/
      project.json                # metadata, KiCad project link, component refs
      conversation.jsonl
      artifacts/enclosure_*.glb
  .index/                         # SQLite — rebuildable, never authoritative
```

Readable JSON that a user can inspect, diff, and commit; a shared library folder that is
independently useful; and a SQLite index that exists only to make search fast and can be deleted
and rebuilt at any time. This matches how KiCad itself works, survives app corruption, and makes the
library exportable to KiCad without a translation layer.

The cost is honest: cross-project queries need the index to be correct, so index-rebuild has to be
cheap and has to run on startup when the file tree is newer than the index.

---

## 5. Spec plan

### 5.1 New specs

| Spec | Scope | Depends on |
| :--- | :--- | :--- |
| **SPEC-300** Product IA & Interaction Model | Parent for the whole 3xx tree: the domain model in §2, the stage machine, the navigation rule in §3.2, the AI boundary in §3.3, and provenance. Everything else hangs off this. | — |
| **SPEC-304** Project & Library Storage | The §4 layout, the Component/Project/Artifact schemas, index rebuild, import/export. | SPEC-300 |
| **SPEC-305** App Shell & Navigation | Project list, area tabs, empty and not-built states, routing. | SPEC-300, SPEC-304 |
| **SPEC-306** Component Discovery | Search, candidate ranking, the *did you mean* disambiguation surface, datasheet link + local cache, confidence gating. | SPEC-300, SPEC-202 |
| **SPEC-307** Part Detail & Library Export | Pin diagram with selectable pins, pin table, per-pin guidance, save to the parts library, export symbol to a KiCad `.kicad_sym` library. | SPEC-306, SPEC-304 |
| **SPEC-308** Footprints & Schematic Advisor | Footprint as a first-class object: find in installed KiCad libraries, or create from datasheet dimensions; export to a `.pretty` library; link to parts. Plus connection guidance (decoupling, protection, power). | SPEC-307 |
| **SPEC-309** Board Advisor | Read ERC/DRC results from a connected schematic or board, explain, suggest. | SPEC-103 |
| **SPEC-310** Enclosure from Board Profile | Import a `.kicad_pcb`, take outline and mounting-hole geometry only, produce a starter body. | SPEC-104, SPEC-109 |

### 5.2 Re-scoped

*   **SPEC-302 Chat & Command Surface → Project Conversation.** The command-parsing half is
    removed, not refactored. CTX-302.x should record this as plan drift — it was a real design
    mistake found by real use, which is exactly what the Plan Drift section is for. The chat half
    survives intact and moves into Overview.
*   **SPEC-301 3D Viewer.** Survives as-is. Becomes a component of the Enclosure area rather than a
    floating panel.
*   **SPEC-202 Component Intelligence Pipeline.** Its output becomes the Component object. Needs
    provenance and per-field confidence added — currently it returns a bare schema with no record
    of where anything came from.
*   **SPEC-108 KiCad Injection.** Becomes an action on a Component within a Project, behind the
    confirmation gate. Not a bare button that mutates a live board on click.
*   **SPEC-204 Agent Tool Registry.** Its confirmation-gating policy is now load-bearing and should
    be written before, not after, injection gets a real UI.

### 5.3 Unaffected

The entire 1xx platform layer and the AgentFlow-based provider work stand. SPEC-105's job protocol,
SPEC-106 config, SPEC-107 logging, SPEC-201 providers, SPEC-103/104 bridges — all correct, all
reusable, none of it touched by this.

---

## 6. Milestones

### M2 — Shell, Projects, Components *(next)*

The smallest thing that turns this from a demo into a product.

1.  **SPEC-300** — write first; everything else depends on the model being settled.
2.  **SPEC-304** — storage, because objects that don't persist aren't objects.
3.  **SPEC-305** — the shell, with PCB / Schematic / Enclosure areas present and explicitly marked
    not built. Visible-but-empty beats hidden: it tells the user what's coming.
4.  **SPEC-306** — discovery, including the disambiguation card. This is the flow whose absence
    produced the reported bug.
5.  **SPEC-307** — detail view and library export.

The existing enclosure panel moves into the Enclosure area unchanged. It works; it just needs
labels and a home.

**Done means:** create a project, search for a part, disambiguate it, see its pins with sources,
save it to the parts library, reopen the app and it's still there, use it in a second project.
Footprints are explicitly out of M2 — a part is useful with pins and a datasheet before any
footprint exists, and footprints get their own flow in SPEC-308.

### M3 — Schematic stage ✅ done 2026-08-16

SPEC-308: footprint search and creation into the KiCad library (all three ranked sources real --
`CTX-308.1`/`.3`/`.4`/`.5`), export to a real `.pretty` library (`CTX-308.6`), and per-pin connection
guidance -- decoupling, protection, power -- via a real LLM call once a part and its footprint are
both real (`CTX-308.7`).

### M4 — Advisors

SPEC-309: connect a schematic or board, read ERC/DRC, explain and suggest. Deliberately after M3 —
it depends on file access patterns M3 will have already established.

### M5 — Enclosure from geometry, then ambition

SPEC-310 first (low stakes, high usefulness). Auto-layout and assisted routing stay explicitly out
of scope until everything above is solid.

---

## 7. What happens to the shipped UI

| Code | Disposition |
| :--- | :--- |
| `lib/commands.ts` (`parseCommand`) | **Delete.** The premise is wrong. |
| `App.tsx` | Becomes the shell. Its chat half moves to Overview; its generate/inject halves move to Components. |
| `EnclosurePanel` | Moves into the Enclosure area, with labels. |
| `EnclosureViewer`, `lib/ipc.ts` job client | Keep unchanged. |
| Daemon routes, 1xx/2xx backend | Keep. Right capability layer, wrong surface. |

Nothing in the daemon gets rewritten. This is a re-housing, not a rebuild.

---

## 8. Open questions

1.  **`kicad-cli` specifically.** KiCad itself is confirmed installed and launching. The board
    advisor (SPEC-309) plausibly shells out to `kicad-cli sch erc` / `kicad-cli pcb drc` for
    machine-readable reports rather than parsing files or driving the IPC API. `kicad-cli` is a
    *separate binary shipped inside the app bundle*, not the app — KiCad 9+ ships it, so it is very
    likely present, but confirm before SPEC-309 is written:
    `ls /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli && … kicad-cli pcb drc --help`
2.  **Schematic access.** Live IPC (SPEC-103's stated preference) or reading `.kicad_sch` from disk?
    The advisor arguably needs the file, which reopens a decision SPEC-103 deliberately closed.
3.  **Footprint sources, ranked -- all three real, 2026-08-16.** Now that footprints are their
    own object, "find a footprint" needs a defined corpus: the user's installed KiCad footprint
    libraries first, then the user's own library, then generation from datasheet package dimensions.
    Source one (installed KiCad libraries) is fully real: `CTX-308.1` shipped direct
    `fp-lib-table` entries, `CTX-308.3` added KiCad's own ~100+ built-in libraries behind the
    recursive `(type "Table")` entry (156 real libraries searchable, up from 1). Source two (the
    user's own saved library) is real too, as of `CTX-308.4`: results from both sources are merged
    and tagged (`kicad_library`/`your_library`) in the real UI `CTX-308.2` built. Both `CTX-308.3`
    and `CTX-308.4` found and fixed real Windows-only bugs along the way -- separator/placeholder
    handling and a `:` reserved character in `footprint_id`'s own on-disk filename -- all only
    catchable by real CI (no Windows machine this session). Source three (datasheet generation) is
    real as of `CTX-308.5`: turned out to need no second LLM call at all -- the extraction Part
    Detail already runs (`SPEC-202`) already returns `package_dimensions`/`courtyard`, previously
    silently dropped before being saved; `CTX-308.5` fixed that and reused `kicad_write`'s existing
    pad-layout geometry (the same function `SPEC-108`'s live inject path calls) to turn them into a
    real Footprint, marked `source: "datasheet_generation"`, `verified: false`. Fails closed for any
    package outside `kicad_write.SUPPORTED_PACKAGES`, the same choice `SPEC-202`'s own validation
    already makes for an unrecognized package.
4.  **Project root location.** User-chosen on first run, or a fixed default under the app data dir
    with an override? Affects SPEC-304 and SPEC-106.
5.  **Symbol generation.** SPEC-202 already produces pins with electrical types, which is most of a
    symbol. Whether SPEC-307 generates a real `.kicad_sym` or defers symbol export to a later stage
    is a scoping call for M2.

---

## 9. Risks

| Risk | Why it matters |
| :--- | :--- |
| SPEC-300 becomes a design document nobody implements against | Keep it to the model, the stages, and the two rules. Screen-by-screen detail belongs in the child specs. |
| The library schema is wrong and every stage inherits it | It is the most-depended-on artifact in the plan. Worth over-thinking in SPEC-304, and worth versioning the file format from day one. |
| Provenance is specified but not enforced | If it's optional it will be skipped under time pressure, and the trust argument in §2.2 evaporates. Make the schema require it. |
| M2 grows to absorb stages 3–5 | The areas are visible and empty on purpose. Resist filling them early. |
| Re-housing turns into a rewrite | §7 is deliberately conservative. If a Code session starts rewriting the daemon, it has gone off-plan. |

---

## 10. The process gap that let this happen

Worth separating from the product problem, because it will recur otherwise.

The framework worked exactly as designed. Twelve merged PRs: specs written, contexts derived, tests
real and run against genuinely installed CAD tools, Plan Drift recorded honestly, CI green
throughout. And it still arrived at a product where three unrelated functions share one text box —
because **no section of `SPEC-TEMPLATE.md` asks what the user is doing.** Goals, architecture,
constraints, module map: all mechanism. A capability spec can be perfect and still be the wrong
thing to build. Velocity carried it further off than a slower process would have.

Two amendments close it, and neither is a new spec:

*   **A required `## 5. User & Interaction` section**, gated on a new `user_facing:` frontmatter
    field, stating which product stage the surface belongs to, what the user is trying to
    accomplish, and what they see and do. Mechanically checkable, so SPEC-902's validator enforces
    it rather than a reviewer remembering.
*   **Extend the "verify for real" norm from *the capability fires* to *use it as the user would*.**
    Every capability test for SPEC-302 passed. Nobody sat down and tried to look up a part. Norm 3
    is currently satisfied by proving a route returns the right value; it needs a companion that is
    only satisfied by a human clicking through the actual surface and recording what happened.

These amend SPEC-901's norms, SPEC-902's checks, and `SPEC-TEMPLATE.md`. They apply to SPEC-300 and
everything under it — meaning the very first spec written under this plan is also the first one
subject to the gate.

> **Status note (2026-08-11):** both amendments described in this section are implemented and
> merged — `SPEC-TEMPLATE.md`'s `user_facing` field and `## 5. User & Interaction` section,
> `ROADMAP.md` §5.3 norms 8/9, and the two new `scripts/validate_spec_context.py` hard failures —
> in `CTX-901.2` ([PR #42](https://github.com/GittieLabs/hardware-agent-studio/pull/42)). SPEC-300,
> once written, is already subject to that gate.
