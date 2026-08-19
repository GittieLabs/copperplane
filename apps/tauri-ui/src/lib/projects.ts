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
 * persists verbatim, keyed by area tab (`"enclosure"` today). */
export interface Project {
  name: string
  schema_version?: number
  directory?: string
  last_results?: Record<string, unknown>
  export_history?: ExportHistoryEntry[]
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
