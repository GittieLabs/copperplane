import { dispatch } from './ipc'

/** Mirrors `library_store.py`'s Project record shape (SPEC-304). Kept
 * minimal -- this spec's rail only needs enough to list/create/select a
 * project, not a full project-detail schema. */
export interface Project {
  name: string
  schema_version?: number
}

/** A conversation turn, matching `library_store.py`'s append-only
 * `conversation.jsonl` shape and SPEC-302's own `HistoryTurn`. */
export interface ConversationTurn {
  role: 'user' | 'assistant'
  content: string
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
