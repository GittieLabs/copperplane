---
id: SPEC-318
title: "In-Context Agent Chat, Project Intent & AI Review"
status: Completed
type: Feature
created: 2026-08-21
last_updated: 2026-08-24
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-318-in-context-agent-chat-and-review.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs:
  - "../../../services/python-daemon/specs/SPEC-206-agent-context-store.md"
user_facing: true
---

# SPEC-318: In-Context Agent Chat, Project Intent & AI Review

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give every working area of a project its own scoped agent chat, grounded in
    what that area actually knows, and give the project itself a stated purpose those agents can
    read. `SPEC-305` re-housed the original floating chat into a per-project Overview tab and
    `SPEC-313` gave Overview a dashboard around it, but the chat itself has never had a defined job:
    it is still `SPEC-302`'s `generate`/`inject` command recognizer with a plain-chat fallback,
    grounded in nothing about the project it sits inside. This spec replaces it with five scoped
    surfaces -- Overview (the project), Components (a selected Part), Schematic, PCB, Enclosure --
    each backed by an agent with a declared tool allow-list and a declared retrieval scope, each
    rendering the sources behind every answer, and each collapsible so it never costs an area its
    screen. It also defines the seam a later, proactive **AI Review** action plugs into, so the
    reactive and proactive halves share one agent and one tool layer rather than being built twice.
*   **Business / Technical Value:** The app already produces the three things an engineer would most
    want to ask questions about -- `SPEC-205`'s cited design guidance, `SPEC-308`'s per-pin
    connection guidance, and `SPEC-309`'s ERC/DRC findings -- and then leaves the user alone with
    them. A user who reads "brown-out detection prevents EEPROM corruption" and wants to know *what
    that means for my board* has nowhere to ask. Worse, the knowledge is stranded: guidance
    generated for a Part in one project is invisible when the same Part is used in the next one, and
    a question resolved in conversation is resolved again from scratch a week later. Scoping chat to
    an area and grounding it in stored, cited records turns a pile of generated artifacts into
    something that compounds. Stating the project's purpose -- "I want to build a macropad from
    scratch" -- is what lets an agent answer *for this board* instead of in general.
*   **Supersedes:** `SPEC-302` (Chat & Command Surface), already re-scoped to "Project Conversation"
    by `PRODUCT-PLAN.md` §5.2 and re-housed by `CTX-305.1`. That re-scope was only ever partially
    shipped -- `parseCommand` survives -- and this spec finishes it. See §2.6.
*   **Non-Goals:**
    *   **Any editing of a schematic or board.** `PRODUCT-PLAN.md` §2.3's framing -- "The product is
        an advisor with hands, not a replacement CAD tool. That framing is what keeps stages 3 and 4
        tractable" -- is unchanged. These agents read, explain and cite. The single write they may
        propose is adding a component to the library, and that goes through `SPEC-204`'s existing
        confirmation gate like every other write.
    *   **The AI Review buttons themselves.** This spec defines the seam -- the typed finding shape,
        the shared tool layer, where the button lives -- and deliberately does not ship the buttons.
        Designing the seam alongside the chat that shares its tools is the point; building both at
        once is not.
    *   **Chat as a router.** `PRODUCT-PLAN.md` §3.2 is unchanged and this spec depends on it: the
        tab the user is on selects the agent, deterministically, before any model is called. Typing
        into the Schematic chat can only ever produce a schematic answer. No text input in this app
        chooses a destination.
    *   **Token-by-token streaming.** `gittielabs-agentflow==0.9.0` has no streaming of any kind
        (verified by reading the installed source, not assumed -- see §3). Answers arrive whole.
    *   **Cross-project chat**, a global assistant, or any surface that spans projects. The Projects
        rail owns cross-project navigation; `SPEC-313` already settled that Overview is per-project.
    *   **The enclosure ambitions named in discussion** -- suggesting USB cutout locations, latching
        or fastener methods, or detecting missing mounting holes. Real and wanted; each needs
        geometry work this spec does not do. The Enclosure agent in v1 advises on the parameters
        that already exist using the board data `kicad.get_component_heights` already returns.
    *   **Semantic/vector retrieval.** See `SPEC-206` §2.6 -- deliberately deferred behind an
        interface, not designed out.

## 2. System Architecture & Design Choices

### 2.1 The one settled decision this spec deliberately amends

**`PRODUCT-PLAN.md` §3.3 and `SPEC-300` §2 currently confine prose to Overview.** The exact wording:
"Every AI step inside a deterministic flow returns a typed result, not prose -- prose is confined to
Overview," and in `SPEC-300` §2, the AI "converses (in Overview only)." A prose chat panel in
Components, Schematic, PCB and Enclosure contradicts that on its face, and this spec is not entitled
to slide past it -- `PRODUCT-PLAN.md` §3 is one of the decisions that cost real work to establish.

Stated plainly, then, with the argument rather than an assertion. That rule bundles two claims, and
only one of them is load-bearing:

*   **"Every AI step inside a deterministic flow returns a typed result."** Untouched, and this spec
    depends on it. Search, extraction, guidance generation, footprint generation, ERC/DRC
    explanation and AI Review findings all still return typed results. Nothing in a flow starts
    returning prose.
*   **"Prose is confined to Overview."** This is a proxy, not the principle. What made the original
    text box dangerous was never that it emitted prose -- it was that prose was *consumed*: a
    parser read the user's words and chose between three unrelated functions. `PRODUCT-PLAN.md` §1's
    failure is an input failure, and "keep prose in one room" was the cheapest way to contain it
    while the product had no other structure.

The replacement invariant is narrower than the location rule and strictly stronger where it counts:

> **Prose is confined to conversation surfaces, and a conversation surface can only ever produce an
> answer.** It cannot advance a stage, mutate a record, dispatch a flow step, or change which screen
> the user is on. Every action it proposes becomes a separate, explicitly confirmed step.

Under the old rule, Overview was safe because of where it was. Under this one, every chat surface is
safe because of what it is permitted to do -- which is why Overview's own chat, which today still
routes `generate` and `inject` through `parseCommand`, is the *least* compliant surface in the app
and is fixed by §2.6 rather than grandfathered.

This requires real amendments to `PRODUCT-PLAN.md` §3.3 and `SPEC-300` §2, in the documents
themselves, following the precedent `PRODUCT-PLAN.md` §10 set when the `user_facing` gate was added.
Those edits are part of this spec's first context, not a follow-up.

**A second, smaller amendment:** `PRODUCT-PLAN.md` §2.1's object table gives Conversation the
lifetime "Per project." Part chats under this spec are global, following the Part (§2.2). That
column widens to "follows the scope of its subject" -- consistent with how `SPEC-315` already
refused to make library membership project-scoped, and with Footprints being shared rather than
duplicated per Part.

### 2.2 Design rationale

*   **Five agents, one per area, selected by the tab -- not by a model.** The area key already exists
    as real, typed state: `apps/tauri-ui/src/lib/areas.ts`'s `Area` union
    (`'overview' | 'components' | 'schematic' | 'pcb' | 'enclosure'`), held in `App.tsx`'s `view`
    discriminated union. That value is passed to the daemon as an explicit parameter and is the
    entire routing decision. `SPEC-206` §2.5 records that AgentFlow's `RuleEvaluator` matches on
    caller-supplied context keys with **no LLM on the rule path**, so this is a lookup, not an
    inference. No prose is ever consulted to choose an agent.
*   **The component chat is Part-scoped and global; every other chat is project-scoped.** A Part is
    a `SPEC-304` global object and a Footprint is shared across many Parts. A conversation about an
    ATtiny85's brown-out behaviour is a fact about the ATtiny85, not about the macropad, and should
    be there the next time that Part is opened from any project. This is a single-user desktop app,
    so the usual objection -- seeing someone else's history on a shared part -- does not apply.
    Storage follows the scope, not the screen: `SPEC-206` §2.2.
*   **Overview's chat becomes the project agent rather than being deleted.** Confirmed directly with
    the user rather than assumed. It is the only surface that can answer "what should I do next,"
    "does this part fit what I'm building," or "which area has a problem" -- and it is the natural
    owner of the project intent this spec introduces. `SPEC-313`'s dashboard (status summary,
    activity feed) is untouched. The agent may *name* a destination ("your ERC results are on the
    Schematic tab"); it may not navigate there. Suggesting is not routing.
*   **Every answer carries its sources, or is marked as not having any.** `SPEC-205` established the
    contract -- an item whose page or quote does not check out is dropped, never repaired -- and
    `CTX-205.7`/`CTX-205.8` established the reading surface: plain language first, citations
    collapsed beneath in a native `<details>` element, available on demand as proof. Chat inherits
    both. An answer renders a validated `SourceRef[]` (`SPEC-206` §2.3) as clickable chips; a
    datasheet chip opens the cached PDF at that page, reusing `PartDetail.tsx`'s existing
    `handleOpenCitation`. Content offered as general engineering practice rather than as something
    the datasheet says is visually segregated, the discipline `SPEC-205`'s Class C already describes.
*   **Honest limit, stated here rather than discovered later:** the citation objects are validated
    for resolvability, and the UI renders only validated ones. Nothing mechanically proves the
    surrounding prose faithfully represents the cited page. That is a real gap between this and
    `SPEC-205`'s extraction path, where the quote *is* the payload. It is why the chips must be one
    click from the real page: the user's own eye is the last check, and the UI's job is to make that
    check cost five seconds. Do not describe chat answers as "verified" anywhere in the UI.
*   **Chat is collapsible, and its collapsed state is remembered per area.** Every area already
    fights for width -- `CTX-305.2` and `CTX-305.3` were both real layout bugs about exactly this.
    Default collapsed on first visit to an area, with a persistent expand affordance; the flag is
    per-area UI state, not a project record.
*   **State preservation is a requirement of this spec, not an afterthought.** `CTX-306.2` fixed the
    class of bug where switching tabs discarded in-progress work, using a specific pattern: the four
    area panels are always mounted in `App.tsx` and hidden with the Tailwind `hidden` class rather
    than conditionally rendered, and each resets its own local state in a `useEffect` keyed on
    `projectName` so a *project* switch still starts fresh. Chat panels must follow that pattern
    from the first commit: an in-flight answer must survive a tab switch and land in the right
    thread, and a half-typed question must still be there on return. **Overview is currently the one
    area still conditionally rendered** (`{view.area === 'overview' && ...}`) -- `CTX-306.2` records
    that `ComponentDiscovery` "was simply never included when that fix was made," and Overview was
    likewise never migrated; no behaviour of Overview's own requires it. Giving Overview a chat with
    a draft and an in-flight request means migrating it to the mount-always pattern. That is real,
    named work, not an assumption.

### 2.3 Per-area scope table

Each agent's retrieval scope and tool allow-list is declared, not emergent. `SPEC-206` §2.5 defines
the tools and their registration; this table is the authority on who may call which, and the two
must be kept in agreement.

| Area | Grounded in | May call | Cannot |
| :--- | :--- | :--- | :--- |
| **Overview** | Project intent, `Project.last_results`, `export_history`, the Part records the project references, promoted notes | `context.search`, `library.list_parts` | Read a board or schematic file directly |
| **Components** | The selected Part's `design_guidance` (+ `category_summaries`), `connection_guidance`, `pins`, `package`, `provenance`, its cached datasheet, its own chat history | `context.search`, `datasheet.read_pages`, `library.load_part` | Write to the Part without confirmation |
| **Schematic** | Parts in the library used by this project, all of the above per Part, plus `kicad.check_schematic` findings | `context.search`, `library.load_part`, `datasheet.read_pages`, `kicad.check_schematic`, `component.search`, `library.save_confirmed_part` (**gated**) | Modify a schematic |
| **PCB** | Same Part corpus, plus `kicad.check_board` findings and `kicad.get_component_heights` | `context.search`, `library.load_part`, `datasheet.read_pages`, `kicad.check_board`, `kicad.get_component_heights` | Modify a board |
| **Enclosure** | Board outline and mounting holes, component heights, `last_results.enclosure` parameters | `context.search`, `kicad.get_component_heights` | Generate geometry without an explicit click |

The Schematic agent's central move -- the one worth building the plumbing for -- is: take a component
the user names, resolve it to a library Part via `library.load_part`, read that Part's stored
guidance, and if the guidance does not cover the question, read the cached datasheet with
`datasheet.read_pages`. Three tool calls over records that already exist.

**What is deliberately not in that chain, and must not be implied:** nothing in this app reads a
`.kicad_sch`'s component list. `kicad.check_schematic` shells out to `kicad-cli sch erc` on a
user-picked file and returns ERC findings, not a netlist, and `SPEC-309`/`CTX-309.1` confirmed
directly that KiCad's live IPC has **no schematic path-resolution RPC at all**
(`get_open_documents(DOCTYPE_SCHEMATIC)` raises a real `no handler available` error). So the v1
Schematic agent works from the user's own description plus ERC findings plus the library, not from
walking a schematic. A real schematic-reading tool is a genuine future capability with a real
upstream blocker, and naming it as such here is the point -- an agent prompted to "inspect the
schematic" with no tool that can would hallucinate one.

`AgentConfig.max_tool_rounds` defaults to 6 in AgentFlow, which accommodates these chains; the value
belongs in each agent's `.prompt.md`, chosen per agent.

### 2.4 Project intent

A new, optional free-text field on the Project record (`SPEC-206` §2.1) describing what the user is
building. Captured in two places, neither blocking:

*   **At project creation** -- a single optional textarea beside the name, with skip as a first-class
    outcome. Today `App.tsx` creates a project with `saveProject({ name })` and nothing else; that
    path must keep working unchanged for a user who skips.
*   **Any time afterwards** -- editable from the Overview tab, where `SPEC-313` already put the
    project's own summary surface.

Free text, deliberately. The temptation is to parse it into structured attributes (board type,
target MCU, constraints) with an LLM call; that is a second inference layer whose failures are
invisible and which nothing yet needs. The text is injected into every agent's context verbatim, and
every agent's `.prompt.md` is responsible for treating it as *the user's stated goal*, never as a
verified fact about the design. An empty intent is a normal state, not a degraded one -- every
existing project will have none.

### 2.5 The AI Review seam

Not built here. Defined here so building it later is additive rather than a rewrite.

A review is the same agent, the same tools and the same retrieval scope as that area's chat, invoked
with a fixed internal prompt instead of a user question, and returning a **typed finding list**
rather than prose -- `PRODUCT-PLAN.md` §3.3's typed-result rule applies unchanged, because a review
is a flow step, not a conversation. The shape:

```ts
interface ReviewFinding {
  severity: 'info' | 'suggestion' | 'warning'
  title: string
  detail: string
  sources: SourceRef[]        // same union as chat -- SPEC-206 §2.3
  area: Area
}
```

Two constraints that must hold from the start, because retrofitting either is expensive. A finding is
subject to the same source contract as a chat answer -- an unsourced finding must declare itself
general practice. And a review must never apply anything; it produces findings the user reads,
exactly as `SPEC-309`'s advisor already does. The button belongs in each area's existing action row
and, per `SPEC-316`, in its `Design` submenu.

### 2.6 What happens to `parseCommand`

`PRODUCT-PLAN.md` §3.2 and §7 both ordered `lib/commands.ts`'s `parseCommand` deleted, not improved.
`CTX-305.1` moved the chat half into Overview and recorded the deletion as inherited, unresolved
debt; `App.tsx` still imports `parseCommand` and still string-matches into `generate` / `inject` /
plain chat, holding `latestSchema` in a single `useState`. This spec finishes that deletion, and must
account for what the deletion removes:

*   `parseCommand`, `lib/commands.ts` and `lib/commands.test.ts` are deleted.
*   **Overview's chat is currently the only live UI path to `kicad.generate_component` and to
    `SPEC-108`'s inject flow via `agent.dispatch_tool`.** Removing it without rehoming them silently
    removes a shipped capability. Component generation belongs in the Components area, which already
    owns discovery and Part Detail; injection belongs wherever `SPEC-108`'s confirmation gate is
    surfaced as a real, visible action rather than a typed word. Choosing and building those homes
    is in scope for this spec's contexts and must be done in the same slice that deletes the parser,
    not after it.

### 2.7 Cross-Module Impacts

*   `apps/tauri-ui/src/App.tsx` -- `Overview` (a local function component defined inside `App.tsx`,
    not a file in `components/`) is extracted into its own component and migrated to the
    mount-always pattern; `parseCommand` import and its `generate`/`inject` branches removed;
    project-creation form gains the optional intent field.
*   `apps/tauri-ui/src/components/` -- a new shared `AgentChat` component (collapsible, source chips,
    draft preservation) mounted by the extracted `Overview`, `PartDetail`, `SchematicAdvisor`,
    `BoardAdvisor` and `EnclosurePanel`. `OverviewDashboard.tsx` stays purely presentational as its
    own doc comment requires -- the chat and its state sit in `Overview`, not in the dashboard.
    `PartDetail.tsx`'s `handleOpenCitation` is generalised so the chat reuses it rather than copying
    it.
*   `apps/tauri-ui/src/lib/projects.ts` -- `Project` gains `intent`; `ConversationTurn` is superseded
    by the richer turn shape in `SPEC-206` §2.2, with the existing interface retained for reading
    migrated history.
*   `apps/tauri-ui/src/lib/` -- a new client module for the `chat.*` and `context.*` routes,
    following `lib/components.ts`'s use of `lib/ipc.ts`'s `submitJob` (chat is async: it is an LLM
    call). `lib/commands.ts` deleted.
*   `PRODUCT-PLAN.md` §2.1, §3.3, §7 and `SPEC-300` §2 -- the amendments in §2.1 above.
*   `services/python-daemon` -- everything else, via `SPEC-206`.

## 3. Known Constraints & Risks

*   **No streaming, confirmed against the installed source.** `gittielabs-agentflow==0.9.0` contains
    no `yield`, no `AsyncIterator`/`AsyncGenerator` return type, no `stream=True` argument and no
    delta handling anywhere; every provider is single-shot request/response. A chat UI that cannot
    stream must not look like one that can. Use `SPEC-105`'s existing async job protocol and
    AgentFlow's `EventBus` (`LLM_CALL_STARTED`, `TOOL_CALLED`, `TOOL_RESULT`) to show real progress
    -- "reading the ATtiny85 datasheet" is a better wait state than a token trickle and is achievable
    with what exists. Do not design a typing indicator that implies streaming.
*   **The app must own every transcript.** AgentFlow's `AgentExecutor.run()` takes
    `history: list[Message] | None` and returns only a `NodeOutput` -- it never returns its updated
    message list, so intermediate tool-call turns are unrecoverable from its return value. Its only
    conversation abstraction, `MultiUserHistory`, is in-memory, keyed by `user_id` with no thread
    concept, and its `append(user_id, role, content)` signature **cannot store tool calls at all**;
    `HistoryPersistence` is a `Protocol` with zero implementations. None of it is usable here.
    `SPEC-206` §2.2 specifies the store this app writes instead.
*   **Guidance citations resolve to a page, not a section.** A stored guidance item is exactly
    `{quote, page, category}`; `design_guidance.document_revision` is written but is **always
    `None`** because no revision extractor exists. So a source chip can open the cached PDF at a page
    and cannot say "§7.2 of rev. C." If the user regenerates guidance against a newer datasheet,
    `content_hash` changes and old page numbers may be wrong -- which is why `SPEC-206` §2.3 requires
    a `SourceRef` to carry the `content_hash` it was made against, and the UI to mark a chip stale
    rather than silently opening a page that has moved.
*   **Chat history must survive regenerating design requirements.** It falls out of the storage
    split: `datasheet.generate_guidance` rewrites `part["design_guidance"]` wholesale, while the
    Part's thread is a separate file keyed by `part_id`. The failure mode to guard is not deletion
    but *staleness* -- a thread full of answers citing the previous document's page numbers. Mark
    affected chips stale on `content_hash` mismatch; never clear the thread.
*   **The Enclosure agent may have no parameters to reason about.** `last_results.enclosure` is
    written only by `handleExportSuccess` -- on **export**, never on generate. A user who generated
    an enclosure but did not export it leaves that agent with board geometry and nothing else. Handle
    the empty case explicitly rather than assuming the key exists.
*   **The Components chat has two entry points with different state.** `CTX-315.4` added a second
    door into `PartDetail` -- `initialPart`, hydrating from a saved record and skipping re-extraction
    -- and reaching it from the Library uses a top-level `partDetail` view that requires no project
    at all. A Part chat opened with no project open therefore has no project intent to inject. That
    is a legitimate state, not an error: the agent runs with part scope only. Note also that
    `CTX-315.4` is recorded as **not yet verified live in the running app** -- a manual click-through
    is still owed on the very path this chat mounts on.
*   **`AgentExecutor` dispatches every tool call immediately.** There is no confirmation, pending,
    approval or interrupt mechanism anywhere in AgentFlow (grep-verified across the package). The
    "add this component to my library" action must be routed through the app's own
    `agent.dispatch_tool` gate and added to `CONFIRMATION_REQUIRED_TOOLS`, which today contains only
    `kicad.inject_component`. A write tool handed to a bare `AgentExecutor` will fire unprompted.
*   **Screen real estate is a live, repeatedly-broken constraint.** `CTX-305.2` (every tab stuck at a
    448px content column) and `CTX-305.3` (Enclosure reserving space for a result that did not exist)
    were both found by real click-throughs, not by tests. A collapsible chat panel added to five
    areas is exactly the change that reintroduces them. Verification must include a real human
    click-through of every area at a realistic window size, per `ROADMAP.md` §5.3 norm 9.

## 4. Module Map & Reference Links

```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-318-in-context-agent-chat-and-review.md)
                 ├── [SPEC-206](../../../services/python-daemon/specs/SPEC-206-agent-context-store.md) (context store, retrieval, transcripts, agent layer)
                 ├── supersedes [SPEC-302](SPEC-302-chat-command-surface.md) (the command surface this finishes deleting)
                 ├── depends on [SPEC-205](../../../services/python-daemon/specs/SPEC-205-datasheet-design-guidance.md) (cited guidance + the citation contract)
                 ├── depends on [SPEC-308](SPEC-308-footprints-schematic-advisor.md) (connection guidance -- not persisted today)
                 ├── depends on [SPEC-309](SPEC-309-board-advisor.md) (ERC/DRC findings the agents explain)
                 ├── depends on [SPEC-313](SPEC-313-overview-tab-project-dashboard.md) (the Overview surface this re-scopes)
                 └── depends on [SPEC-204](../../../services/python-daemon/specs/SPEC-204-agent-tool-registry.md) (the confirmation gate)
```

## 5. User & Interaction

*   **Product Stage:** Cross-cutting -- every stage of `PRODUCT-PLAN.md` §2.3's machine (Component
    Discovery, Component Detail, Schematic, PCB, Enclosure), plus the project-level Overview.
*   **What the user is trying to accomplish:** Understand what the app has told them. They have a
    cited power section, a list of pin guidance, or an ERC error, and they want to know what it means
    for the board they are actually building -- and to have that answer still be there, with its
    sources, the next time they use the part.
*   **What the user sees and does:** A collapsible chat panel at the foot of each area, labelled for
    that area's job. They type a question; the answer arrives whole, with source chips beneath it
    that open the exact datasheet page, guidance item or check finding it came from, and with
    anything offered as general practice visibly marked as such. On Components the panel appears once
    a part is selected and its history follows that part everywhere. A "Save as note" action on any
    answer promotes it to a durable, cited note on the Part or Project, so the next conversation
    starts from it instead of re-deriving it.
