import { submitJob } from './ipc'

/** Mirrors component_pipeline.py's search_components response shape
 * (SPEC-306) -- a ranked candidate, never a committed schema. `confidence`
 * is a closed enum (matching component_extraction.prompt.md's own
 * electrical_type pattern), not a raw float the model might return
 * inconsistently. */
export interface ComponentCandidate {
  part_number: string
  manufacturer: string
  package: string
  datasheet_url: string
  confidence: 'high' | 'medium' | 'low'
  rationale: string
}

/** Real, ranked candidates from the LLM-driven search agent -- never a
 * single auto-selected result, even when there's exactly one candidate
 * (SPEC-306 §2's own rule). Both routes are async-registered on the
 * daemon (a real LLM call / a real network fetch), so this goes through
 * submitJob, not a plain dispatch. */
export async function searchComponents(query: string): Promise<ComponentCandidate[]> {
  const handle = await submitJob<ComponentCandidate[]>('component.search', { query })
  return handle.result
}

/** Fetches and caches a confirmed candidate's datasheet, returning the
 * real local path -- closes the gap library_store.py named as "not
 * managed by this module yet." */
export async function cacheDatasheet(partNumber: string, datasheetUrl: string): Promise<string> {
  const handle = await submitJob<{ path: string }>('component.cache_datasheet', {
    part_number: partNumber,
    datasheet_url: datasheetUrl,
  })
  const { path } = await handle.result
  return path
}
