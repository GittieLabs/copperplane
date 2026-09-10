import { submitJob } from './ipc'

/** SPEC-328 Phase 3's record. A suggestion is data, not prose, because §5
 *  requires each entry be carried straight into the existing part search. */
export interface PartSuggestion {
  category: string
  search_term: string
  why: string
}

export interface SuggestionResult {
  /** False when the brief was too vague to answer, or was not a hardware
   *  project. `question` is then the answer and `suggestions` is empty --
   *  the daemon empties it rather than trusting callers to check this flag. */
  ready: boolean
  question: string | null
  suggestions: PartSuggestion[]
  /** Entries the daemon dropped, with why. Reported rather than silently
   *  removed: a caller that cannot see what was dropped cannot tell a clean
   *  answer from a filtered one. */
  rejected: { value: string; reason: string }[]
  /** SPEC-328 §3's honest framing, carried on the record rather than left to
   *  UI copy, so a second caller cannot drop it by not knowing about it. */
  caveat: string
}

/** SPEC-328: what KINDS of component this project needs.
 *
 * Async-registered on the daemon (a real LLM call), so this goes through
 * submitJob rather than a plain dispatch. */
export async function suggestParts(projectName: string): Promise<SuggestionResult> {
  const handle = await submitJob<SuggestionResult>('project.suggest_parts', { name: projectName })
  return handle.result
}
