---
id: SPEC-108
title: "KiCad Write Path: Footprint & Symbol Injection"
status: Completed
type: Feature
created: 2026-08-09
last_updated: 2026-09-04
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs:
  - "SPEC-112-placing-a-part-through-kicads-own-libraries.md"
  - "../../../apps/tauri-ui/specs/SPEC-329-assisted-authoring-adding-a-part.md"
user_facing: true
---

# SPEC-108: KiCad Write Path: Footprint & Symbol Injection

## 1. Executive Summary & Goals

*   **High-Level Goal:** Take `SPEC-202`'s validated component schema and actually write it into the
    board KiCad already has open, via `kipy`'s real board-mutation API — the follow-through
    `CTX-103.1` explicitly deferred when it built the read-only `kicad.get_version` connection.
*   **Business / Technical Value:** This is the last unwritten link on M1's critical path
    (`ROADMAP.md` §4) — the step that turns "the AI extracted a plausible component" into "the board
    actually has it." Everything upstream of this spec (`SPEC-201`/`202`) produces data; this is
    where that data becomes a real, irreversible-feeling change to a user's open work.
*   **Non-Goals:**
    *   **Not the confirmation gate.** `SPEC-204`'s "confirmation gate on all writes" (`ROADMAP.md`
        §6 risk register) is the human-in-the-loop approval step *before* this spec's write path
        runs. This spec's own job starts once approval has already happened; it does not itself
        decide whether to ask the user.
    *   **Not board-outline/mounting-hole extraction.** `SPEC-109`'s enclosure generator reads
        geometry *out of* an existing board; this spec only writes a component *into* one. The two
        specs touch the same `kipy.Board` object but move data in opposite directions.
    *   **Not schematic/symbol-library authoring UI.** This spec injects into whatever library
        target it's told to use (board-local footprint vs. project library — an open question, see
        §3); it does not build a library manager.
    *   **Not multi-component placement/auto-routing.** One component in, at a caller-supplied
        position. Placing several components sensibly relative to each other, or routing between
        them, is out of scope.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Built on real, already-verified `kipy.Board` API — not invented.** `kipy.KiCad.get_board()`
        returns a live `Board` with `begin_commit() -> Commit`, `push_commit(commit, message)`,
        `drop_commit(commit)`, and `create_items(items) -> List[Wrapper]`. This is a real
        transaction/undo-grouping primitive already in the installed `kipy` package — it directly
        satisfies the "a half-applied footprint is worse than none" requirement `ROADMAP.md` §3.1
        raised for this spec, without this spec inventing its own rollback mechanism.
    *   **The write is one commit, always.** `begin_commit()` → `create_items([footprint_instance])`
        → `push_commit(commit, message)` on success, `drop_commit(commit)` on any failure — a
        partial write (footprint placed but a downstream step, e.g. reference-field assignment,
        throws) must never leave the board in a half-applied state.
    *   **Reuses `SPEC-202`'s schema as the sole input contract.** The `part_number`, `package`,
        `pins`, `package_dimensions`, and `courtyard` fields that pipeline already validated are
        this spec's only input — no second extraction, no second validation. `electrical_type`'s
        deliberate alignment with KiCad's own pin-type vocabulary (`SPEC-202` §2) is what makes the
        translation to a real `kipy` footprint/pad object mechanical rather than another inference
        step.
    *   **Reuses `kicad_bridge.py`'s held-open connection (`SPEC-103`/`CTX-103.1`).** No second
        connection lifecycle — `get_client()` already handles lazy-connect, the `FutureVersionError`
        soft-warning, and `SPEC-106`'s socket-path/timeout override. This spec adds a write
        operation on top of that same client, not a parallel one.
*   **Data Flow / Interactions:**

    ```text
    kicad.inject_component (new async route, real multi-second board mutation)
       │  validated component schema (SPEC-202 output) + target position
       ▼
    kicad_bridge.get_client().get_board()
       │
       ├─> board.begin_commit()
       ├─> translate schema -> kipy FootprintInstance + pads (electrical_type -> kipy pad type)
       ├─> board.create_items([footprint_instance])
       │
       ├─ success ─> board.push_commit(commit, message) ─> board.save()
       └─ failure ─> board.drop_commit(commit) ─> clean error, board unchanged
       ▼
    Result: board now contains the component, or a specific error naming what
    failed, with the board provably unchanged (no half-applied state)
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: `kicad_bridge.py` gains the write path (a new function, not a
        rewrite of the existing read-only `get_client()`/`check_version()` logic); `daemon.py` gains
        a new async route (`SPEC-105`'s pattern, since a real board mutation plus save is
        multi-second, same reasoning as every other real route this product has added).
    *   `apps/tauri-ui`: needs a way to trigger this route with a position (even a hardcoded
        board-origin default for M1's demo) and render success/failure — likely the same
        `submitJob`/`JobHandle` pattern `App.tsx` already uses for `kicad.generate_component`.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   None yet — there is no existing write path to KiCad today; this spec closes a real gap
        (`CTX-103.1`'s explicitly deferred follow-through), not a broken existing behavior.
*   **Gotchas & Hazards:**
    *   **`CTX-103.1`'s `FutureVersionError`-as-warning decision is untested against a real
        breaking protocol change, and a write is where that assumption gets expensive.** A read that
        returns stale/garbage data is annoying; a write against a board whose IPC wire protocol
        actually changed underneath `kipy`'s declared API version could corrupt the board. This
        context needs to decide whether writes should re-check version compatibility more strictly
        than the existing read-only warning-only path does.
    *   **Board-local footprint vs. project library target is an open question this context must
        resolve, not default into silently.** `create_items` places a `FootprintInstance` on the
        board directly; whether that footprint should also be saved into a project or global
        library (so it's reusable, and so KiCad's own footprint-library-table bookkeeping stays
        consistent) is a real design decision with real consequences for a user's library hygiene —
        not a detail to leave implicit.
    *   **Where does the "confirmation gate" boundary actually sit?** `SPEC-204` owns the human
        approval UI, but this spec's route is the thing that actually mutates a board the instant
        it's called — this context needs to state plainly whether `kicad.inject_component` is safe
        to call directly (i.e., the caller — eventually `SPEC-204`'s gate — is solely responsible for
        only calling it after approval) or whether this spec's own route should carry some
        additional safety check of its own.
    *   **Undo/commit semantics interacting with a user's own concurrent edits.** `begin_commit`/
        `push_commit` are KiCad's own transaction primitives, but this spec runs inside a daemon
        process separate from the KiCad GUI a human may simultaneously be editing in — what happens
        if the user's own unsaved GUI edit and this spec's programmatic commit land at the same time
        is worth stating explicitly, even if the honest answer for M1 is "not handled, documented as
        a known risk."

## 4. Module Map & Reference Links

*   [ROADMAP.md](../../../ROADMAP.md) §3.1, §4, §6 — this spec's backlog entry, the M1 critical path
    it completes (the last unwritten link), and the risk register entries (`FutureVersionError`
    assumption; hallucinated-footprint consequence) it directly interacts with.
*   [SPEC-103](SPEC-103-kicad-ipc.md) / [CTX-103.1](../context/CTX-103.1-kicad-ipc.md) — the
    connection lifecycle and version-gate this spec's write path reuses, and the follow-through it
    explicitly deferred.
*   [SPEC-202](SPEC-202-component-intelligence-pipeline.md) / [CTX-202.1](../context/CTX-202.1-component-intelligence-pipeline.md) —
    the validated component schema this spec's sole input contract.
*   [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) — the async job
    pattern this spec's real (multi-second) board-mutation call should very likely use.
*   [SPEC-109](#) (not yet written) — the enclosure generator that reads geometry back out of a
    board this spec writes into; opposite data direction, same `kipy.Board` object.
*   [SPEC-204](#) (not yet written) — the human confirmation gate upstream of this spec's write.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-108] KiCad Write Path: Footprint & Symbol Injection
          └── [Context 108.1] (not yet written)
```

## 5. User & Interaction

*Filled in for real by `CTX-108.4`, the first time this surface actually changed since the TODO
below was written — not invented after the fact; the confirmation step it describes is real,
shipped behavior.*

*   **Product Stage:** Overview's chat surface, after a component has already been generated
    (`kicad.generate_component`) and the user is deciding whether to commit it to their real,
    currently-open board.
*   **What the user is trying to accomplish:** place a validated footprint onto their live PCB
    without an LLM's mistake — or their own typo in the chat box — silently mutating a board they
    didn't mean to touch yet.
*   **What the user sees and does:** types `inject` → sees an explicit, real confirmation prompt
    ("This will write into the board KiCad currently has open. Confirm?") with **Confirm**/**Cancel**
    buttons, before anything happens to the board → clicking **Confirm** actually performs the write
    and shows success/error exactly as before; **Cancel** leaves the board untouched and requires no
    second daemon call.
