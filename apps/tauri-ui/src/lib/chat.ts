import { dispatch, submitJob } from './ipc'

/** SPEC-206 §2.3's real, eight-kind union -- mirrors
 * `services/python-daemon/chat_agents.py`'s own `_RESOLVERS` dict
 * exactly. Every field is optional here (a single flat interface,
 * not a discriminated union of eight separate shapes) because a
 * `SourceRef` crosses the wire as a plain JSON object and the real
 * discriminator is always `kind` -- consumers narrow by checking
 * `kind`, not by TypeScript's own exhaustiveness machinery, matching
 * how the backend itself treats these as plain dicts, not a typed
 * union. */
export interface SourceRef {
  kind: 'datasheet_page' | 'guidance_item' | 'connection_guidance' | 'part_field' | 'project_intent' | 'chat_turn' | 'note' | 'check_finding'
  part_id?: string
  page?: number
  content_hash?: string
  category?: string
  quote?: string
  pin_number?: string
  field?: string
  project_name?: string
  scope?: string
  scope_id?: string
  turn_id?: string
  note_id?: string
  area?: string
  finding_id?: string
}

export interface ChatToolCall {
  name: string
  input: Record<string, unknown>
  result_digest: string
}

/** SPEC-206 §2.2's real, richer turn shape -- what `chat.send`/
 * `chat.load_thread` actually return, mirroring `chat_agents.py`'s own
 * `_make_turn`. Deliberately separate from `lib/projects.ts`'s
 * `ConversationTurn` (the older, narrower SPEC-302 shape backing
 * `project.append_conversation_turn`) -- that's a real, still-used,
 * separate code path this module does not touch. */
export interface ChatTurn {
  turn_id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  agent: string | null
  sources: SourceRef[]
  sources_dropped: number
  general_practice: boolean
  tool_calls: ChatToolCall[]
  provenance: { provider: string; model: string } | null
  promoted_note_id: string | null
}

export type ChatScope = 'project' | 'part'

export interface ContextSearchResult {
  body: string
  source_ref: SourceRef
  kind: string
  score: number
}

function unwrap<T>(response: { error?: { message: string }; result?: unknown }): T {
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as T
}

/** chat.load_thread/chat.list_threads/chat.promote_turn/context.search
 * are all real, cheap local file I/O or SQLite lookups (confirmed
 * directly against daemon.ASYNC_ROUTES -- none of the four are in
 * it), so plain dispatch -- not submitJob. */
export async function loadChatThread(scope: ChatScope, scopeId: string): Promise<ChatTurn[]> {
  return unwrap(await dispatch('chat.load_thread', { scope, scope_id: scopeId }))
}

export async function listChatThreads(projectName: string): Promise<string[]> {
  return unwrap(await dispatch('chat.list_threads', { project_name: projectName }))
}

export async function promoteChatTurn(
  scope: ChatScope,
  scopeId: string,
  turnId: string,
  targetScope: ChatScope,
  targetId: string,
): Promise<{ note_id: string; text: string; sources: SourceRef[] }> {
  return unwrap(
    await dispatch('chat.promote_turn', {
      scope,
      scope_id: scopeId,
      turn_id: turnId,
      target_scope: targetScope,
      target_id: targetId,
    }),
  )
}

export async function searchContext(
  query: string,
  opts: { partId?: string; projectName?: string; limit?: number } = {},
): Promise<ContextSearchResult[]> {
  return unwrap(
    await dispatch('context.search', {
      query,
      part_id: opts.partId,
      project_name: opts.projectName,
      limit: opts.limit,
    }),
  )
}

/** chat.send is a real LLM call (an internal tool-use loop, potentially
 * several seconds), so submitJob -- matching every other real LLM
 * route's own precedent in this codebase (extractPartDetail,
 * generateDesignGuidance). `projectName` is optional context
 * enrichment, not a routing input -- a part-scoped chat opened with no
 * project open is a legitimate state (SPEC-318 §3), not an error. */
export async function sendChatMessage(
  scope: ChatScope,
  scopeId: string,
  area: string,
  message: string,
  projectName?: string,
): Promise<ChatTurn> {
  const handle = await submitJob<ChatTurn>('chat.send', {
    scope,
    scope_id: scopeId,
    area,
    message,
    project_name: projectName ?? null,
  })
  return handle.result
}
