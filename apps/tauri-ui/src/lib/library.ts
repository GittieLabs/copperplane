import { dispatch } from './ipc'

function unwrap<T>(response: { error?: { message: string }; result?: unknown }): T {
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as T
}

/** CTX-315.1's real registry entry shape -- Default's own real counts
 * are computed across *every* real Part/Symbol/Footprint (implicit
 * membership), a custom library's counts only across what's actually
 * been tagged into it. */
export interface LibrarySummary {
  id: string
  name: string
  part_count: number
  symbol_count: number
  footprint_count: number
}

/** All real, local disk I/O (`library_store.py`'s own O(n)-scan shape,
 * `SPEC-304`'s `.index/` cache explicitly out of scope) -- plain
 * `dispatch`, matching `listLibraryParts`'s own established convention,
 * not `submitJob`. */
export async function listLibraries(): Promise<LibrarySummary[]> {
  return unwrap(await dispatch('library.list_libraries', {}))
}

export async function createLibrary(name: string): Promise<{ id: string; name: string }> {
  return unwrap(await dispatch('library.create_library', { name }))
}

export type LibraryObjectKind = 'part' | 'symbol' | 'footprint'

/** SPEC-315 §5's own real "Add to library..." shape -- a user picks the
 * full real set for one object at a time; Default is force-included by
 * the daemon route regardless of what's passed here. */
export async function tagObject(
  kind: LibraryObjectKind,
  objectId: string,
  libraryIds: string[],
): Promise<Record<string, unknown>> {
  return unwrap(await dispatch('library.tag_object', { kind, object_id: objectId, library_ids: libraryIds }))
}

export async function listParts(libraryId?: string): Promise<string[]> {
  return unwrap(await dispatch('library.list_parts', { library_id: libraryId ?? null }))
}

export async function listSymbols(libraryId?: string): Promise<string[]> {
  return unwrap(await dispatch('library.list_symbols', { library_id: libraryId ?? null }))
}

export async function listFootprints(libraryId?: string): Promise<string[]> {
  return unwrap(await dispatch('library.list_footprints', { library_id: libraryId ?? null }))
}

/** CTX-315.2: a real, previously-missing gap -- nothing before this
 * slice ever needed to fetch one already-saved Part/Symbol/Footprint's
 * own record just to display it (every existing caller only ever
 * listed ids or saved). Minimal, real display shapes -- not the full
 * schema, just enough for a library's own detail view to show
 * something identifiable per item. */
export interface LibraryPartSummary {
  part_id: string
  manufacturer?: string
  package?: string
}
export async function loadPart(partId: string): Promise<LibraryPartSummary> {
  return unwrap(await dispatch('library.load_part', { part_id: partId }))
}

export interface LibrarySymbolSummary {
  symbol_id: string
  symbol_name?: string
}
export async function loadSymbol(symbolId: string): Promise<LibrarySymbolSummary> {
  return unwrap(await dispatch('library.load_symbol', { symbol_id: symbolId }))
}

export interface LibraryFootprintSummary {
  footprint_id: string
  footprint_name?: string
  library?: string
  provenance?: { license?: string; repo?: string }
}
export async function loadFootprint(footprintId: string): Promise<LibraryFootprintSummary> {
  return unwrap(await dispatch('library.load_footprint', { footprint_id: footprintId }))
}
