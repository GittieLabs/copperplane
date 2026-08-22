import { dispatch, submitJob } from './ipc'
import type { SavedPart } from './partDetail'
import { setProjectFootprintOverride, type Project } from './projects'

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
/** Persists a found footprint as a real library_store Footprint record
 * (idempotent -- re-saving the same id is harmless) and returns its id.
 * Split out of `attachFootprintToPart` so `attachFootprintToProjectOverride`
 * below can reuse the exact same persistence step without also
 * rewriting the Part's own global `footprint_id`. */
async function saveFootprintRecord(library: string, footprintName: string): Promise<string> {
  const footprintId = `${library}__${footprintName}`
  await unwrap<unknown>(
    await dispatch('library.save_footprint', {
      footprint: { footprint_id: footprintId, library, footprint_name: footprintName },
    }),
  )
  return footprintId
}

export async function attachFootprintToPart(
  part: SavedPart,
  library: string,
  footprintName: string,
): Promise<SavedPart> {
  const footprintId = await saveFootprintRecord(library, footprintName)

  const updatedPart: SavedPart = { ...part, footprint_id: footprintId }
  await unwrap<unknown>(await dispatch('library.save_part', { part: updatedPart }))

  return updatedPart
}

/** CTX-308.9: real user feedback -- the same Part may need a different
 * footprint in a different project. Persists the found footprint the
 * same way `attachFootprintToPart` does, but records it as *this
 * project's own override* instead of overwriting the Part's global
 * default -- the Part's own `footprint_id` is left untouched. */
export async function attachFootprintToProjectOverride(
  project: Project,
  part: SavedPart,
  library: string,
  footprintName: string,
): Promise<string> {
  const footprintId = await saveFootprintRecord(library, footprintName)
  await setProjectFootprintOverride(project.name, part.part_id, footprintId)
  return footprintId
}

/** SPEC-308's third footprint source (PRODUCT-PLAN.md §8 item 3,
 * CTX-308.5): generates a footprint from the part's own already-saved
 * datasheet dimensions -- no new search, no LLM call here (the daemon
 * route reuses the extraction this part was already saved with). Like
 * kicad.search_footprints, this is real but cheap local computation, so
 * plain dispatch -- not submitJob. */
/** Real, cheap local generation (the daemon route reuses the part's own
 * already-saved extraction, no new LLM/network call) -- split out of
 * `generateFootprintFromPart` so `generateFootprintForProjectOverride`
 * below can reuse it without also rewriting the Part's global
 * `footprint_id`. */
async function generateFootprint(part: SavedPart): Promise<GeneratedFootprint> {
  return unwrap<GeneratedFootprint>(
    await dispatch('kicad.generate_footprint_from_part', { part_id: part.part_id }),
  )
}

export async function generateFootprintFromPart(part: SavedPart): Promise<SavedPart> {
  const footprint = await generateFootprint(part)

  const updatedPart: SavedPart = { ...part, footprint_id: footprint.footprint_id }
  await unwrap<unknown>(await dispatch('library.save_part', { part: updatedPart }))

  return updatedPart
}

/** CTX-308.9: the generate-from-datasheet counterpart to
 * `attachFootprintToProjectOverride` above -- same "generate, then
 * record as this project's own override" shape. */
export async function generateFootprintForProjectOverride(project: Project, part: SavedPart): Promise<string> {
  const footprint = await generateFootprint(part)
  await setProjectFootprintOverride(project.name, part.part_id, footprint.footprint_id)
  return footprint.footprint_id
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

/** CTX-314.1's real, curated-allowlist search result shape --
 * `community_libraries.search_community_footprints`'s own real return
 * value, unchanged here. A `.kicad_sym` candidate's `path` names a real
 * *library file* that may hold many symbols (SPEC-314 §2's own real,
 * verified finding), not one -- `importCommunityFootprint` reflects
 * that with its own two-step shape below. */
export interface CommunityLibraryCandidate {
  owner: string
  repo: string
  path: string
  kind: 'footprint' | 'symbol'
  license: string
  blob_sha: string | null
  download_url: string
}

/** CTX-314.2: `library.search_community_footprints` is a real GitHub
 * network call (community_libraries.py's own `_github_request`), so
 * it's ASYNC_ROUTES-registered like every other genuinely slow route --
 * `submitJob`, not plain `dispatch` (unlike this app's own installed-
 * library `searchFootprints` above, which is real local disk I/O). */
export async function searchCommunityFootprints(query: string): Promise<CommunityLibraryCandidate[]> {
  const handle = await submitJob<CommunityLibraryCandidate[]>('library.search_community_footprints', { query })
  return handle.result
}

/** A real symbol name and its real pin count, found inside a `.kicad_sym`
 * library file `importCommunityFootprint` fetched and parsed but has not
 * yet imported -- the real "browse" step SPEC-314 §2's own multi-symbol
 * finding requires before a specific one can be chosen. */
export interface CommunitySymbolOption {
  name: string
  pin_count: number
}
export interface CommunitySymbolBrowseResult {
  symbols: CommunitySymbolOption[]
}

/** The real, persisted record `library.import_community_footprint`
 * returns once an import actually commits -- either a footprint
 * (`pad_count`) or one named symbol out of its own library file
 * (`pin_count`), both carrying real provenance back to their GitHub
 * source. */
export interface ImportedCommunityRecord {
  footprint_id?: string
  symbol_id?: string
  pad_count?: number
  pin_count?: number
  provenance: {
    source: string
    owner: string
    repo: string
    path: string
    license: string
    blob_sha: string | null
  }
}

/** CTX-314.2: fetches, real-verifies (kiutils), and persists a
 * candidate `library.search_community_footprints` already found. A
 * `.kicad_mod` candidate imports directly. A `.kicad_sym` candidate
 * needs `symbolName` -- call once with none to get the real browse list
 * (`CommunitySymbolBrowseResult`), then a second time with a real,
 * chosen name to actually import (`ImportedCommunityRecord`). Never
 * silently picks a symbol on the caller's behalf. Real GitHub network
 * fetch + kiutils parse, so `submitJob` like the search above. */
export async function importCommunityFootprint(
  candidate: CommunityLibraryCandidate,
  symbolName?: string,
): Promise<ImportedCommunityRecord | CommunitySymbolBrowseResult> {
  const handle = await submitJob<ImportedCommunityRecord | CommunitySymbolBrowseResult>(
    'library.import_community_footprint',
    {
      owner: candidate.owner,
      repo: candidate.repo,
      path: candidate.path,
      kind: candidate.kind,
      license: candidate.license,
      download_url: candidate.download_url,
      blob_sha: candidate.blob_sha,
      symbol_name: symbolName ?? null,
    },
  )
  return handle.result
}

/** Links an already-imported community footprint or symbol to a saved
 * Part -- mirrors `attachFootprintToPart`'s own real shape, but the id
 * is already final (community_libraries' own `owner__repo__stem`
 * naming), not derived from a library/name pair. */
export async function attachCommunityFootprintToPart(
  part: SavedPart,
  record: ImportedCommunityRecord,
): Promise<SavedPart> {
  const footprintId = record.footprint_id
  if (!footprintId) {
    throw new Error('Only a footprint (not a symbol) can be attached to a Part this way.')
  }
  const updatedPart: SavedPart = { ...part, footprint_id: footprintId }
  await unwrap<unknown>(await dispatch('library.save_part', { part: updatedPart }))
  return updatedPart
}

/** CTX-308.9: the community-import counterpart to
 * `attachFootprintToProjectOverride` above -- the record is already
 * persisted by `importCommunityFootprint`, so this only ever records
 * the project override, no re-save. */
export async function attachCommunityFootprintToProjectOverride(
  project: Project,
  part: SavedPart,
  record: ImportedCommunityRecord,
): Promise<string> {
  const footprintId = record.footprint_id
  if (!footprintId) {
    throw new Error('Only a footprint (not a symbol) can be attached to a Part this way.')
  }
  await setProjectFootprintOverride(project.name, part.part_id, footprintId)
  return footprintId
}

/** CTX-306.7: real user feedback -- a footprint's pad layout and a
 * symbol's pin arrangement are inherently visual; text alone doesn't
 * let a user judge whether a match is right. Both routes shell out to
 * real `kicad-cli sym/fp export svg` (~1-2s observed), so ASYNC_ROUTES
 * + submitJob, matching `searchCommunityFootprints`'s own precedent for
 * "real but not instant." Returns raw SVG markup, safe to render
 * directly -- kicad-cli's own output, never user-supplied text. */
export async function renderSymbolPreview(symbolId: string): Promise<string> {
  const handle = await submitJob<{ svg: string }>('library.render_symbol_preview', { symbol_id: symbolId })
  const result = await handle.result
  return result.svg
}

export async function renderFootprintPreview(footprintId: string): Promise<string> {
  const handle = await submitJob<{ svg: string }>('library.render_footprint_preview', {
    footprint_id: footprintId,
  })
  const result = await handle.result
  return result.svg
}
