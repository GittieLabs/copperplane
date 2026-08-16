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

/** CTX-308.5: the shape kicad.generate_footprint_from_part returns --
 * mirrors what library_store.py actually persists (pads/courtyard from
 * kicad_write.generate_pad_layout, a real provenance record marking it
 * generated and unverified). The UI only reads footprint_id/provenance
 * from this; pads/courtyard exist purely for a future real board-write
 * path (out of this spec's own scope -- SPEC-308 §1's non-goal). */
export interface GeneratedFootprint {
  footprint_id: string
  footprint_name: string
  provenance: { source: string; generated_from_part_id: string; verified: boolean }
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

/** SPEC-308's third footprint source (PRODUCT-PLAN.md §8 item 3,
 * CTX-308.5): generates a footprint from the part's own already-saved
 * datasheet dimensions -- no new search, no LLM call here (the daemon
 * route reuses the extraction this part was already saved with). Like
 * kicad.search_footprints, this is real but cheap local computation, so
 * plain dispatch -- not submitJob. */
export async function generateFootprintFromPart(part: SavedPart): Promise<SavedPart> {
  const footprint = await unwrap<GeneratedFootprint>(
    await dispatch('kicad.generate_footprint_from_part', { part_id: part.part_id }),
  )

  const updatedPart: SavedPart = { ...part, footprint_id: footprint.footprint_id }
  await unwrap<unknown>(await dispatch('library.save_part', { part: updatedPart }))

  return updatedPart
}

/** CTX-308.6: SPEC-308 §1's "export it to a real .pretty library" --
 * only meaningful for a footprint with real pad geometry (one
 * generateFootprintFromPart produced). A found footprint (installed
 * KiCad library or your own saved library) is already a real
 * .kicad_mod file; the daemon route itself returns a clear error for
 * that case rather than writing a meaningless pad-less file. */
export async function exportFootprint(footprintId: string): Promise<string> {
  const result = await unwrap<{ path: string }>(
    await dispatch('library.export_footprint', { footprint_id: footprintId }),
  )
  return result.path
}
