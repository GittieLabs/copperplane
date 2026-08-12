import { dispatch, submitJob } from './ipc'
import type { ComponentCandidate } from './components'

/** Mirrors component_pipeline.py's SPEC-202 extraction schema. Re-run
 * for real from Part Detail (SPEC-307) -- Discovery's ranking call
 * (SPEC-306) never returns pin data itself. */
export interface ExtractedPin {
  number: string
  name: string
  electrical_type: string
}

export interface ExtractedSchema {
  part_number: string
  package: string
  pins: ExtractedPin[]
}

export interface SavedPart {
  part_id: string
  manufacturer: string
  package: string
  pins: ExtractedPin[]
  datasheet_url: string
  symbol_id: string
  footprint_id: string | null
}

export interface SavedSymbol {
  symbol_id: string
  reference_prefix: string
  pins: ExtractedPin[]
}

function unwrap<T>(response: { error?: { message: string }; result?: unknown }): T {
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as T
}

/** kicad.generate_component is a real, async-registered LLM call (SPEC-202)
 * -- this is a second, real re-run for pin data, not a reuse of
 * Discovery's own ranking call. */
export async function extractPartDetail(partNumber: string): Promise<ExtractedSchema> {
  const handle = await submitJob<ExtractedSchema>('kicad.generate_component', { part_number: partNumber })
  return handle.result
}

/** library.save_confirmed_part is real, fast file I/O (not a network/LLM
 * call), so this goes through plain dispatch, matching library.save_part's
 * own precedent -- not submitJob. */
export async function saveConfirmedPart(
  candidate: ComponentCandidate,
  extraction: ExtractedSchema,
): Promise<{ part: SavedPart; symbol: SavedSymbol }> {
  return unwrap(await dispatch('library.save_confirmed_part', { candidate, extraction }))
}

export async function exportSymbol(symbolId: string): Promise<string> {
  const result = await unwrap<{ path: string }>(await dispatch('library.export_symbol', { symbol_id: symbolId }))
  return result.path
}
