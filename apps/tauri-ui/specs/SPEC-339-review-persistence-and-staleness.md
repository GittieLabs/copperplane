---
id: SPEC-339
title: "Review Persistence & Staleness"
status: Draft
type: Feature
created: 2026-09-05
last_updated: 2026-09-05
target_version: v0.6.0
location: "apps/tauri-ui/specs/SPEC-339-review-persistence-and-staleness.md"
parent_spec: "SPEC-319-ai-review.md"
child_specs: []
user_facing: true
---

# SPEC-339: Review Persistence & Staleness

## 1. Executive Summary & Goals

*   **High-Level Goal:** Stop throwing away a review the user already paid for. Keep it, show it,
    and say when the file underneath it has changed -- rather than silently discarding it and
    charging for it again.

*   **The current behaviour, precisely.** `ReviewPanel` holds findings in React state and resets
    them to `null` on every change of `scope`/`scopeId`. Switching from a project to the library
    and back, or between two projects, destroys the review. The next look costs a full ERC or DRC
    run plus a real LLM call, for a file that has not changed. The reset itself is correct -- a
    review from another project must never linger -- but "correct" was implemented as "forget",
    and those are not the same requirement.

*   **The ERC and DRC results are already persisted; only the review is not.**
    `library_store.set_project_check_result` writes `Project.last_results[area]` and has since
    `SPEC-319`. The gap is narrow and has a working precedent sitting next to it.

*   **Never re-run automatically.** A stale review is shown, labelled, and left alone. Re-running
    is the user's decision because it is the user's money and the user's minute. This is the same
    principle as `PRODUCT-PLAN.md` §3.3's rule against applying a change the user did not see
    first, applied to spend rather than to files.

*   **Non-Goals:**
    *   **Not a background watcher.** No file-system watching, no polling loop, no re-running on
        focus.
    *   **Not cross-machine sync.** The cache lives with the project record.
    *   **Not a change to what a review contains.** `SPEC-113` owns adding findings.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **What identifies "the same file".** The maintainer proposed the timestamp. `mtime` alone
    misfires in both directions: KiCad rewriting a file unchanged marks a good review stale, and a
    restored backup can move mtime backwards. The proposed resolution is stat-then-hash -- compare
    size and mtime first, and only when they differ compute `library_store.content_hash_of_file`;
    if the hash matches, quietly refresh the stored stat and keep the review current. Cheap in the
    common case, correct in the uncommon one.

*   **Which file each area is keyed to.** Schematic to the `.kicad_sch`, PCB to the `.kicad_pcb`.
    The enclosure review is measured from the board, so it is stale when the board changes.
    Multi-sheet projects are unresolved -- `SPEC-325` already carries a visible warning that
    hierarchy handling is unverified, and this spec must not quietly assume one file per schematic.

*   **Where it is stored, and how much.** Alongside `last_results`, or under its own key.
    `set_project_check_result` caps stored findings at 25 because the record is read into an LLM
    context window; a stored review is read by a human and by the model, so whether the same cap
    applies is a real question, not a copy-paste.

*   **What the user sees when it is stale.** The maintainer's proposal is a chip or banner beside
    **Run Review**. What it must say is settled: which file changed and when, not merely "stale".
    What is open is whether a stale review's findings are dimmed, marked individually, or left
    exactly as they were with only the header changing -- the last being the most honest, since no
    individual finding is known to be wrong.

*   **What happens when a review has never been run.** A never-run area and a stale one must not
    look the same. Today both show nothing.

## 3. Known Constraints & Risks

*   **A cached review is a claim about a file the app does not own.** KiCad is usually open beside
    this app and may hold unsaved changes, so "current" means current with what is on disk, and the
    surface must not imply more. `kicad.list_schematic_components` already reports `read_at` for
    exactly this reason and the wording here should match it.
*   **A stale review that looks current is worse than no cache at all.** If the staleness signal is
    ever wrong, the feature has made the product less trustworthy while making it cheaper.
*   **Persisting a review means persisting model output.** It will be read back and shown as
    current-looking content long after the model, the provider, or the prompt has changed. Whether
    the record stores which model produced it is an open question with an obvious answer.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/src/components/ReviewPanel.tsx` -- the state reset this spec exists to fix.
*   `apps/tauri-ui/src/lib/projectReview.ts`
*   `services/python-daemon/library_store.py` -- `set_project_check_result`,
    `content_hash_of_file`.
*   `services/python-daemon/chat_agents.py` -- `review`, `_check_status_note`.
*   [SPEC-319](SPEC-319-ai-review.md) -- the review being persisted.
*   [SPEC-325](SPEC-325-kicad-project-integration.md) -- `read_at` and the multi-sheet caveat.
*   [SPEC-113](../../../services/python-daemon/specs/SPEC-113-structural-consistency-checks.md) --
    adds findings this cache will carry.

## 5. User & Interaction

*   **Product Stage:** Review -- the Schematic, PCB and Enclosure tabs of an open project.

*   **What the user is trying to accomplish:** Looking again at what the review said, without
    paying for it twice. Moving between a project, the library, and another project is ordinary
    navigation, not a request to discard work.

*   **What the user sees and does:** Returning to an area shows the review that already ran, with
    when it ran. If the underlying file has changed on disk since, a chip beside **Run Review**
    says so and names the file -- and nothing re-runs until the user clicks. An area that has never
    been reviewed says that, distinctly from one whose review is merely old.
