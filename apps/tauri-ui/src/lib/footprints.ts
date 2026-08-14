import { dispatch } from './ipc'
import type { SavedPart } from './partDetail'

export interface FootprintCandidate {
  library: string
  footprint_name: string
}

function unwrap<T>(response: { error?: { message: string }; result?: unknown }): T {
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as T
}

/** CTX-308.1's kicad.search_footprints is deliberately synchronous --
 * local filesystem I/O (a fp-lib-table read plus directory listings),
 * not a kipy round trip -- so this uses plain dispatch, not submitJob
 * (which would throw: "did not return a job_id"). */
export async function searchFootprints(query: string): Promise<FootprintCandidate[]> {
  return unwrap<FootprintCandidate[]>(await dispatch('kicad.search_footprints', { query }))
}

/** Links a found footprint to an already-saved Part. No new backend
 * route needed -- library.save_footprint and library.save_part
 * (SPEC-304/CTX-304.1) already accept exactly this shape; this just
 * calls them in the right order. The footprint_id uses KiCad's own real
 * "library:name" reference convention (confirmed against kipy's
 * LibraryIdentifier shape, not invented) so it reads the same way a
 * footprint reference does inside KiCad itself. */
export async function attachFootprintToPart(
  part: SavedPart,
  library: string,
  footprintName: string,
): Promise<SavedPart> {
  const footprintId = `${library}:${footprintName}`

  await unwrap<unknown>(
    await dispatch('library.save_footprint', {
      footprint: { footprint_id: footprintId, library, footprint_name: footprintName },
    }),
  )

  const updatedPart: SavedPart = { ...part, footprint_id: footprintId }
  await unwrap<unknown>(await dispatch('library.save_part', { part: updatedPart }))

  return updatedPart
}
