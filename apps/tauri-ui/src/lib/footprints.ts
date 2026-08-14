import { dispatch } from './ipc'
import type { SavedPart } from './partDetail'

/** CTX-308.4: kicad.search_footprints now merges two real sources --
 * KiCad's own installed libraries (CTX-308.1/CTX-308.3) and footprints
 * this app has already saved (CTX-308.2's own attach flow) -- each
 * result tagged with which one it came from, so the UI can tell them
 * apart instead of presenting an undifferentiated list. */
export type FootprintSource = 'kicad_library' | 'your_library'

export interface FootprintCandidate {
  library: string
  footprint_name: string
  source: FootprintSource
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
 * calls them in the right order.
 *
 * footprint_id deliberately does NOT use KiCad's own "library:name"
 * reference syntax (an earlier version of this function did) --
 * footprint_id is also the on-disk filename library_store.py persists
 * it under (`{footprint_id}.json`), and `:` is a reserved character in
 * Windows filenames. Real, live-caught bug: a real footprint saved with
 * a colon-containing id silently failed to round-trip through search on
 * real windows-latest CI. "__" is a safe, still-readable separator on
 * every platform this app ships to. */
export async function attachFootprintToPart(
  part: SavedPart,
  library: string,
  footprintName: string,
): Promise<SavedPart> {
  const footprintId = `${library}__${footprintName}`

  await unwrap<unknown>(
    await dispatch('library.save_footprint', {
      footprint: { footprint_id: footprintId, library, footprint_name: footprintName },
    }),
  )

  const updatedPart: SavedPart = { ...part, footprint_id: footprintId }
  await unwrap<unknown>(await dispatch('library.save_part', { part: updatedPart }))

  return updatedPart
}
