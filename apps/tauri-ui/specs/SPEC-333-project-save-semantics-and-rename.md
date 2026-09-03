---
id: SPEC-333
title: "Project Lifecycle: Save Semantics, Rename & Removal"
status: Draft
type: Feature
created: 2026-09-02
last_updated: 2026-09-02
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-333-project-save-semantics-and-rename.md"
parent_spec: "SPEC-312-application-shell-project-portability-persistence.md"
child_specs: []
user_facing: true
---

# SPEC-333: Project Lifecycle: Save Semantics, Rename & Removal

## 1. Executive Summary & Goals

*   **High-Level Goal:** Make the three things a person does to a project record — save it, rename
    it, remove it from the list — real, supported actions rather than ways to end up with two
    projects, one wrong one, or no way to tidy up.

> **The save half is resolved, 2026-09-02.** The Save Project button was deleted rather than fixed:
> *"I still don't believe we need a Save project button. We should save the project at project
> creation time and have all other edits update as things change."* Every field now persists at the
> moment it changes, so there is no stale snapshot left to write. §1's save analysis is kept as the
> record of why. **Rename and removal remain.**

*   **Business / Technical Value:** Both problems are reproduced, not predicted, and one of them
    got materially worse this week.

    **Save Project silently discards newer data.** `handleSaveProject` writes the whole
    `currentProject` React snapshot through `project.save`, and `save_project` replaces the record
    wholesale. Anything a dedicated route wrote since that snapshot was loaded is erased.
    Reproduced directly:

    ```
    09:55  the UI loads the project into React state
    10:00  a DRC check runs; project.set_check_result records it   -> last_results.pcb present
    10:05  the user clicks Save Project (writing the 09:55 copy)   -> last_results.pcb GONE
    ```

    `SPEC-312` already knew about this shape — `setProjectIntent`'s own docstring says a dedicated
    route exists precisely "so editing the intent from Overview can't race a stale in-memory copy
    of `last_results` or `export_history` into the saved record." The dedicated routes avoid the
    race; the Save button still has it. `CTX-326.3` then made it much easier to hit by writing
    `last_results` on every check and every enclosure generate, so the window between load and save
    now routinely contains real data.

    **Rename is not implemented, and doing it by hand forks the project.** There is no rename route.
    Saving under a new name writes a *second* pointer record and leaves the first, so:

    ```
    list_projects()      -> ['New', 'Old']      # one folder, two projects
    load_project('Old')  -> name 'Old'          # still resolves
    the folder's manifest -> name 'New'         # and disagrees
    ```

    A user who renames gets a duplicate in their project list, and an old entry that loads with a
    name its own folder contradicts.

*   **Removing a project from the list, without deleting anything.** Requested by the maintainer
    on 2026-09-03: *"I believe we need a way to 'soft delete' a project. All this should do is
    remove from the project list in the app."* Today a project is in the list if and only if a
    folder holding `project.json` sits in `<storage_root>/projects/` — `library_store.list_projects`
    is exactly that `os.listdir`. There is no way to tidy an experiment out of the list short of
    deleting files by hand outside the app, which is both destructive and invisible to it.

*   **Non-Goals:**
    *   **Deleting a user's files.** "Soft" is the whole request. Nothing this spec adds removes a
        board, an export, or a project folder from disk.
    *   Multi-user or concurrent editing. One person, one machine; the race here is between two
        code paths in the same app, not two people.
    *   A general undo/version history for projects. `export_history` records exports and is not
        being turned into a journal.
    *   Renaming the project *folder* on disk. The folder is the user's, and moving it is theirs to
        do — `load_project`'s "moved, renamed, or deleted" error already covers the aftermath.

## 2. System Architecture & Design Choices

*Open questions removal must settle:*

*   **Where "removed" is recorded.** A flag in the project's own `project.json` keeps one record in
    one place and travels with the folder, which is consistent with `SPEC-312`'s portability. A
    list in `config.json` keeps the user's own files untouched but makes the state machine-local,
    so a project hidden on one machine reappears on another.
*   **How it comes back.** `project.open_from_directory` already exists for restoring a project
    from a folder (`CTX-312.3`), which is a natural undo if removal is a flag: pointing at the
    folder again clears it. Settle whether that is the whole story or whether the list needs its
    own "show removed" view.
*   **What the confirmation says.** It must state plainly that nothing is deleted, because the word
    a user brings to this is "delete" and being wrong about that in either direction is bad: a user
    who thinks files are gone loses trust, and one who thinks they are safe when they are not loses
    work.

*Open questions this spec must settle, before implementation:*

*   **What "Save Project" should mean now.** Most of what it once saved is now written the moment
    it changes (intent, check results, footprint overrides, export history). Options to weigh: make
    it a merge rather than a replace; narrow it to the fields it is genuinely the author of; or
    remove the button and let every edit persist on its own. Consider which of these leaves a user
    able to answer "is my work saved?" without thinking about it.
*   **Whether a whole-record write should exist at all.** If `project.save` stays, decide whether
    it merges server-side, or takes a version/etag so a stale write is refused rather than applied.
*   **What rename does to the pointer.** Rewrite it, or key projects by something stable that a
    name is merely a label for. `SPEC-312`'s pointer/manifest split is the constraint to design
    within.
*   **What the name is for.** It is currently both the display label and the storage key, which is
    why renaming forks the record.
*   **Whether existing duplicates need repairing.** At least one machine may already have forked
    entries.

## 3. Known Constraints & Risks

*   `save_project`'s pointer/manifest routing (`CTX-312.1`) is load-bearing for portability — a
    linked project's manifest travels with its folder. Any change here must keep that intact.
*   A merge-on-save has its own failure mode: a field the user genuinely cleared could be revived
    by a stale copy that still carries it. Deleting must stay possible.
*   `list_projects()` scans the storage root's own directories, so a stale pointer is not just an
    orphaned file — it is a visible, clickable project.
*   The storage root can equal the parent of a project's own directory (it does on the
    maintainer's machine: root `~/Desktop`, project `~/Desktop/projects/test 1`). Any repair pass
    must not assume the two are distinct.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/src/App.tsx` — `handleSaveProject`, the whole-snapshot write.
*   `apps/tauri-ui/src/lib/projects.ts` — `saveProject`, and the dedicated routes that already
    avoid the race (`setProjectIntent`, `setProjectCheckResult`, `setProjectFootprintOverride`).
*   `services/python-daemon/library_store.py` — `save_project`, `load_project`, `list_projects`,
    `_project_pointer_path`, `_project_state_path`.
*   `services/python-daemon/daemon.py` — the `project.*` routes.
*   `apps/tauri-ui/specs/SPEC-312-application-shell-project-portability-persistence.md` — the
    persistence model this corrects.

## 5. User & Interaction

*   **Product Stage:** Every stage — this is the workspace itself, not one area of the workflow.
*   **What the user is trying to accomplish:** Keeping their work, and calling their project what
    they want to call it. Neither is a task they should have to think about.
*   **What the user sees and does:** *To be settled in §2.* Today they click **Save Project** in
    the header and are told "Project saved." — which is true of the snapshot written and not
    necessarily of the work done since. Rename has no surface at all.
