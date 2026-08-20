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
  /** SPEC-300 §2.2's provenance record, keyed by field name. Real,
   * already returned by library.save_confirmed_part/library.save_part
   * (verified directly against library_store.py -- save_part's own
   * schema validation requires it on every save), but never declared
   * here until CTX-308.2 needed to round-trip it through a re-save
   * (attaching a footprint_id) without silently dropping it. */
  provenance: Record<string, unknown>
  /** CTX-205.3/.4: `null` until a user has ever run "Generate Design
   * Requirements" -- kept distinct from "generated, every category
   * came back empty" (SPEC-205 §5's own "silence must not be readable
   * as no requirements" principle, mirrored on the frontend the same
   * way `library_store._backfill_design_guidance` keeps it on the
   * backend). */
  design_guidance: DesignGuidance | null
}

/** Mirrors library_store.save_part_design_guidance's real, persisted
 * shape (CTX-205.3). `document_revision` is always `null` today -- no
 * extraction step for a human-readable revision string exists yet;
 * left honestly unset rather than a fabricated placeholder. */
export interface DesignGuidanceItem {
  quote: string
  page: number
  category: string
}

export interface DesignGuidance {
  generated_at: string
  content_hash: string
  document_revision: string | null
  categories: Record<string, DesignGuidanceItem[]>
  /** CTX-205.7, SPEC-205 §2.1.1: a real plain-language paragraph per
   * category, generated strictly from that category's own already-cited
   * `categories` items -- never a new citable fact. `null` for a
   * category with no validated items (never called the LLM); absent
   * entirely for a record generated before this field existed (backend
   * backfills to `{}` on read, so a lookup here is simply `undefined`,
   * treated the same as `null` by the UI). */
  category_summaries: Record<string, string | null>
}

export interface SavedSymbol {
  symbol_id: string
  reference_prefix: string
  pins: ExtractedPin[]
}

/** Mirrors component_pipeline.py's connection_guidance response shape
 * (CTX-308.7). */
export interface ConnectionGuidance {
  pin_guidance: { pin_number: string; guidance: string }[]
  general_notes: string
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

/** CTX-308.7: SPEC-308's third named concern (decoupling, protection,
 * power), once a part and its footprint are both real. A real LLM call
 * (kicad.generate_connection_guidance is async-registered), so
 * submitJob -- matching extractPartDetail's own precedent. */
export async function getConnectionGuidance(partId: string): Promise<ConnectionGuidance> {
  const handle = await submitJob<ConnectionGuidance>('kicad.generate_connection_guidance', { part_id: partId })
  return handle.result
}

/** CTX-205.3/.4: SPEC-205's real datasheet-guidance pipeline -- a real,
 * multi-category LLM run (~20-30s+ observed for a real 8-category
 * document), so submitJob like every other real LLM route here.
 * Returns the whole updated Part (datasheet.generate_guidance's own
 * real route persists onto the Part record and returns it, not just
 * the new field), matching attachFootprintToPart/generateFootprintFromPart's
 * own "re-save returns the fresh whole record" shape in footprints.ts. */
export async function generateDesignGuidance(partId: string): Promise<SavedPart> {
  const handle = await submitJob<SavedPart>('datasheet.generate_guidance', { part_id: partId })
  return handle.result
}
