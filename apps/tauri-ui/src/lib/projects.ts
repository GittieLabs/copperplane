import { open as openDialog } from '@tauri-apps/plugin-dialog'
import { dispatch } from './ipc'

/** Mirrors `library_store.py`'s Project record shape (SPEC-304). Kept
 * minimal -- this spec's rail only needs enough to list/create/select a
 * project, not a full project-detail schema.
 *
 * CTX-312.1: `directory` is `SPEC-304` §2.1's own long-described but
 * never-built "link to a KiCad project directory on disk" -- optional,
 * since an unlinked project (today's only real kind) has nowhere real
 * to point at yet. `last_results`/`export_history` are the real Save
 * Project manifest fields `library_store.py`'s `save_project` now
 * persists verbatim, keyed by area tab (`"enclosure"` today).
 *
 * CTX-304.3: `parts` is `SPEC-304` §2's own long-described but never-built
 * "component refs" -- real Part-level references into the global Library
 * (many-to-many, never a copy). Optional/absent on a project saved before
 * this context; `library_store.py`'s own `load_project` backfills it to
 * `[]` server-side, but the type stays optional here since a bare
 * `{name}` object (e.g. right after `project.list`) never carries it.
 *
 * CTX-308.9: `footprint_overrides` -- real user feedback found there's
 * no guarantee the same footprint fits a Part in every project it's
 * used in. Keyed by `part_id`; a part with no entry here just uses its
 * own global `footprint_id` (`SavedPart`, `lib/partDetail.ts`) as
 * before -- this never creates a second Footprint record, only a
 * per-project override of which existing one applies. Same optionality
 * reasoning as `parts` above.
 *
 * CTX-318.5: `intent` -- SPEC-318 §2.4's free-text statement of what the
 * user is building, injected verbatim into every agent's context as the
 * user's stated goal, never a verified fact. The backend already
 * validates/backfills it (`library_store.py`'s `_validate_project_intent`/
 * `_backfill_project_intent`, `CTX-206.1`) -- `null`/absent is a normal
 * state, not a degraded one, for every project that predates this field. */
export interface Project {
  name: string
  schema_version?: number
  directory?: string
  last_results?: Record<string, unknown>
  export_history?: ExportHistoryEntry[]
  parts?: string[]
  footprint_overrides?: Record<string, string>
  intent?: string | null
  /** SPEC-325 §2.1: the `.kicad_pro` this project is anchored to. The
   *  schematic and PCB are resolved from it, replacing "whatever board
   *  KiCad currently has open" -- which needed KiCad running, its API
   *  enabled, and the right document focused, for a fact sitting in a
   *  file. `directory` stays for projects with no KiCad files yet. */
  kicad_project_path?: string | null
  /** SPEC-326 §2.5: heights the user supplied for footprints with no 3D
   *  model, keyed by FOOTPRINT rather than reference designator -- ten
   *  identical resistors are one decision, and it survives a schematic edit
   *  that renumbers references. */
  component_heights?: Record<string, number>
}

/** One real, permanent record of an actual `freecad.export_enclosure`
 * call (CTX-311.13's own "keep this" action) -- Generate itself never
 * appends one, matching this app's own established "Generate stays
 * cheap and repeatable" precedent (`CTX-311.2`/`CTX-311.13`). */
export interface ExportHistoryEntry {
  area: string
  dest_path: string
  exported_at: string
}

/** A conversation turn, matching `library_store.py`'s append-only
 * `conversation.jsonl` shape and SPEC-302's own `HistoryTurn`.
 *
 * CTX-313.1: `timestamp` is stamped client-side (`new Date().toISOString()`),
 * matching `ExportHistoryEntry.exported_at`'s own existing convention --
 * `append_conversation_turn` persists whatever dict it's given verbatim, no
 * server clock involved. Optional because turns written before this context
 * shipped have none; the Overview activity feed (`lib/overview.ts`) sorts a
 * missing timestamp to the end rather than assuming every turn has one. */
export interface ConversationTurn {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

function unwrap<T>(response: { error?: { message: string }; result?: unknown }): T {
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as T
}

/** Real project list from SPEC-304's storage -- never a value only held
 * in React state. */
export async function listProjects(): Promise<string[]> {
  return unwrap(await dispatch('project.list', {}))
}

export async function saveProject(project: Project): Promise<Project> {
  return unwrap(await dispatch('project.save', { project }))
}

export async function loadProject(name: string): Promise<Project> {
  return unwrap(await dispatch('project.load', { name }))
}

/** CTX-312.3: the real reverse of `pickProjectDirectory` + `saveProject`
 * with a `directory` -- restores a project from a real, already-linked
 * folder (e.g. copied from another machine), the actual payoff of
 * `CTX-312.1`'s own portability work. Thin `dispatch` wrapper, mirroring
 * `loadProject`'s own shape; throws the real, clean
 * `ProjectNotLinkedError` message when the folder has no real state
 * file, never silently creating a new project from its basename. */
export async function openProjectFromDirectory(directory: string): Promise<Project> {
  return unwrap(await dispatch('project.open_from_directory', { directory }))
}

/** CTX-312.1: a real native "choose a folder" dialog -- `openDialog`
 * already supports `directory: true` (confirmed against the installed
 * `@tauri-apps/plugin-dialog` types before writing this; no new Rust
 * command needed, unlike `EnclosureViewer`'s save-location picker which
 * needed the newer `save()` capability). Returns `null` on cancel, not
 * an error -- matching `pickPcbFile`'s own convention in `lib/enclosure.ts`. */
export async function pickProjectDirectory(): Promise<string | null> {
  const selected = await openDialog({ directory: true })
  return typeof selected === 'string' ? selected : null
}

/** The Library rail entry's count -- real, from SPEC-304's storage, zero
 * on a fresh install rather than a placeholder number. */
export async function listLibraryParts(): Promise<string[]> {
  return unwrap(await dispatch('library.list_parts', {}))
}

/** Overview's persisted conversation history for one project (SPEC-305
 * §2: re-houses SPEC-302's chat, now scoped per-project instead of one
 * global React variable that's lost on reload). */
export async function loadConversation(projectName: string): Promise<ConversationTurn[]> {
  return unwrap(await dispatch('project.load_conversation', { project_name: projectName }))
}

export async function appendConversationTurn(
  projectName: string,
  turn: ConversationTurn,
): Promise<void> {
  const response = await dispatch('project.append_conversation_turn', {
    project_name: projectName,
    turn,
  })
  unwrap(response)
}

/** CTX-304.3: adds a real Part-level reference from a Project onto a
 * Library Part -- idempotent server-side (`library_store.py`'s
 * `add_project_part_reference`), so calling this twice for the same
 * part is always safe. Returns the updated Project record. */
export async function addProjectPartReference(
  projectName: string,
  partId: string,
): Promise<Project> {
  return unwrap(
    await dispatch('project.add_part_reference', { project_name: projectName, part_id: partId }),
  )
}

/** CTX-318.5: sets a project's `intent` on its own, via `project.set_intent`
 * (`library_store.set_project_intent`, `CTX-206.1`) -- a dedicated route
 * rather than a full `saveProject(project)` round-trip, so editing the
 * intent from Overview can't race a stale in-memory copy of `last_results`
 * or `export_history` into the saved record. */
export async function setProjectIntent(projectName: string, intent: string): Promise<Project> {
  return unwrap(await dispatch('project.set_intent', { name: projectName, intent }))
}

/** CTX-308.9: sets (or, with `footprintId: null`, clears) this
 * project's own override of which Footprint a Part resolves to here --
 * the Part's own global `footprint_id` is untouched either way. Real,
 * fast local file I/O (`library_store.set_project_footprint_override`),
 * so plain `dispatch`, matching `addProjectPartReference`'s own
 * precedent -- not `submitJob`. */
export async function setProjectFootprintOverride(
  projectName: string,
  partId: string,
  footprintId: string | null,
): Promise<Project> {
  return unwrap(
    await dispatch('project.set_footprint_override', {
      project_name: projectName,
      part_id: partId,
      footprint_id: footprintId,
    }),
  )
}

/** SPEC-319 §2.1's named prerequisite.
 *
 *  `chat_agents._check_status_note` feeds the chat and review agents a
 *  project's real ERC/DRC findings from `Project.last_results[area]`. Only
 *  `enclosure` was ever written to it: the schematic and PCB checks kept
 *  their results in local React state and dropped them, so the PCB review
 *  agent was told "No DRC check result is available this session" every
 *  time — on a board with real errors. It had no tool to run DRC itself, so
 *  it had nothing to review and honestly found nothing.
 *
 *  A dedicated route rather than a full `saveProject`, matching
 *  `setProjectIntent`: saving a whole in-memory project to record one field
 *  races a stale copy of every other field into the manifest. */
export async function setProjectCheckResult(
  projectName: string,
  area: 'schematic' | 'pcb' | 'enclosure',
  result: Record<string, unknown>,
): Promise<Project> {
  return unwrap(
    await dispatch('project.set_check_result', {
      project_name: projectName,
      area,
      result,
    }),
  )
}
