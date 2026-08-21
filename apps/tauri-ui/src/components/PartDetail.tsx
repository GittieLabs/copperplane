import { open } from '@tauri-apps/plugin-shell'
import { useEffect, useState } from 'react'
import { cacheDatasheet, type ComponentCandidate } from '../lib/components'
import {
  attachCommunityFootprintToPart,
  attachFootprintToPart,
  exportFootprint,
  generateFootprintFromPart,
  importCommunityFootprint,
  searchCommunityFootprints,
  searchFootprints,
  type CommunityLibraryCandidate,
  type CommunitySymbolOption,
  type FootprintCandidate,
} from '../lib/footprints'
import { listLibraries, tagObject, type LibrarySummary } from '../lib/library'
import { addProjectPartReference, type Project } from '../lib/projects'
import {
  exportSymbol,
  extractPartDetail,
  generateDesignGuidance,
  getConnectionGuidance,
  loadPart,
  saveConfirmedPart,
  type ConnectionGuidance,
  type DesignGuidanceItem,
  type ExtractedSchema,
  type SavedPart,
  type SavedSymbol,
} from '../lib/partDetail'

/** SPEC-205 §2.2's own real structure-pass category keys
 * (`datasheet_structure.CATEGORY_PATTERNS`) -- not `SPEC-205 §5`'s own
 * friendly Power/Decoupling/Reset-Boot/Clock/Protection/Layout grouping,
 * which doesn't map 1:1 onto what the real backend produces today
 * (`reset` exists, `reset/boot` and `protection` don't). A real,
 * honest label per real key, not a guess at the eventual fuller
 * grouping -- named explicitly as future work in this context's own
 * Plan Drift. */
const DESIGN_GUIDANCE_CATEGORY_LABELS: Record<string, string> = {
  absolute_maximum_ratings: 'Absolute Maximum Ratings',
  recommended_operating_conditions: 'Recommended Operating Conditions',
  power: 'Power',
  decoupling: 'Decoupling',
  reset: 'Reset',
  clock_oscillator: 'Clock / Oscillator',
  layout: 'Layout',
  typical_application: 'Typical Application',
}

type Status = 'extracting' | 'ready' | 'error'
type FootprintSearchStatus = 'idle' | 'searching' | 'error'

/** SPEC-307: replaces SPEC-306's confirmed-candidate dead end with a
 * real pin diagram/table -- a second, real re-run of SPEC-202's
 * extraction for actual pin data (Discovery's own ranking call never
 * returns pins). "Save to Library" assembles provenance from the
 * confirmed candidate plus this extraction and persists a real Part +
 * Symbol; "Export Symbol" then writes a real, KiCad-openable
 * .kicad_sym file. */
/** CTX-315.4: a Part opened from the Library (`App.tsx`'s `partDetail`
 * view) already has its full saved record -- `initialPart` skips
 * `candidate`'s LLM re-extraction entirely rather than re-running
 * SPEC-202's pipeline on a part that's already confirmed and saved. */
type PartDetailProps = {
  /** CTX-304.3: the currently open project, if any -- threaded through
   * so a successful "Save to Library" (the `candidate` path only; a
   * part opened via `initialPart` is already saved) can also add a
   * real Project→Part reference. `null`/omitted means "no project
   * open" -- Save to Library behaves exactly as before, global save
   * only, no reference added, no error. */
  currentProject?: Project | null
} & ({ candidate: ComponentCandidate; initialPart?: never } | { candidate?: never; initialPart: SavedPart })

// CTX-315.4: derives the initialPart entry point's own starting
// extraction/symbol shape once, reused by both the lazy `useState`
// initializers below (so the very first render already has real data,
// not a null flash before the effect runs) and the effect itself.
function initialPartToExtraction(part: SavedPart): ExtractedSchema {
  return { part_number: part.part_id, package: part.package, pins: part.pins }
}
function initialPartToSymbol(part: SavedPart): SavedSymbol {
  return { symbol_id: part.symbol_id, reference_prefix: '', pins: part.pins }
}

export function PartDetail({ candidate, initialPart, currentProject }: PartDetailProps) {
  const [status, setStatus] = useState<Status>(initialPart ? 'ready' : 'extracting')
  const [error, setError] = useState<string | null>(null)
  const [extraction, setExtraction] = useState<ExtractedSchema | null>(() =>
    initialPart ? initialPartToExtraction(initialPart) : null,
  )
  const [savedSymbol, setSavedSymbol] = useState<SavedSymbol | null>(() =>
    initialPart ? initialPartToSymbol(initialPart) : null,
  )
  const [savedPart, setSavedPart] = useState<SavedPart | null>(initialPart ?? null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  // CTX-304.3: separate from `saveError` -- the Part is genuinely saved
  // either way; only the project-linkage step can fail independently,
  // and it must never look like the save itself failed.
  const [projectLinkWarning, setProjectLinkWarning] = useState<string | null>(null)
  const [exportedPath, setExportedPath] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  // CTX-315.2: SPEC-315 §5's own "Add to library..." action -- a real,
  // separate step from "Save to Library" above (which always tags into
  // Default, unchanged). Only ever offers real custom libraries (Default
  // is implicit, never shown as something to pick/uncheck).
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false)
  const [availableLibraries, setAvailableLibraries] = useState<LibrarySummary[] | null>(null)
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<string[]>([])
  const [taggingLibraries, setTaggingLibraries] = useState(false)
  const [libraryTagError, setLibraryTagError] = useState<string | null>(null)
  const [libraryTagMessage, setLibraryTagMessage] = useState<string | null>(null)

  // CTX-308.2: the found-or-create footprint flow, once a Part exists but
  // has no footprint_id yet. Only searches this machine's own directly
  // configured KiCad libraries (CTX-308.1's own real scope limit).
  const [footprintQuery, setFootprintQuery] = useState('')
  const [footprintStatus, setFootprintStatus] = useState<FootprintSearchStatus>('idle')
  const [footprintError, setFootprintError] = useState<string | null>(null)
  const [footprintCandidates, setFootprintCandidates] = useState<FootprintCandidate[] | null>(null)
  const [attachingFootprint, setAttachingFootprint] = useState<string | null>(null)

  // CTX-314.2: SPEC-314's third footprint source -- a real, curated
  // allowlist of GitHub-hosted community libraries, alongside the
  // installed-library search above. Reuses footprintQuery as the search
  // term but keeps its own separate results/status, since the two
  // sources are searched by separate real network calls. A `.kicad_sym`
  // candidate's own real, multi-symbol structure (SPEC-314 §2) means
  // "Import" is a real two-step flow: communitySymbolBrowse holds the
  // real symbol names found inside a chosen library file, once fetched,
  // before any one of them is actually imported.
  const [communityStatus, setCommunityStatus] = useState<FootprintSearchStatus>('idle')
  const [communityError, setCommunityError] = useState<string | null>(null)
  const [communityCandidates, setCommunityCandidates] = useState<CommunityLibraryCandidate[] | null>(null)
  const [communityImportingPath, setCommunityImportingPath] = useState<string | null>(null)
  const [communitySymbolBrowse, setCommunitySymbolBrowse] = useState<{
    candidate: CommunityLibraryCandidate
    symbols: CommunitySymbolOption[]
  } | null>(null)
  const [communityImportedSymbolId, setCommunityImportedSymbolId] = useState<string | null>(null)

  // CTX-308.5: source three (PRODUCT-PLAN.md §8 item 3) -- generate a
  // footprint from this part's own datasheet dimensions when nothing
  // installed matches. footprintGenerated is deliberately local-only UI
  // state (like exportedPath above), not derived from savedPart itself --
  // there's no cheap way to tell "generated" from "found" apart just by
  // looking at footprint_id without a second load_footprint round trip.
  const [generatingFootprint, setGeneratingFootprint] = useState(false)
  const [footprintGenerated, setFootprintGenerated] = useState(false)

  // CTX-308.6: export the linked footprint to a real .pretty library
  // (SPEC-308 §1's own stated goal). Only ever succeeds for a footprint
  // with real pad geometry -- the daemon route itself returns a clear
  // error otherwise, surfaced here the same way footprintError already is.
  const [exportedFootprintPath, setExportedFootprintPath] = useState<string | null>(null)
  const [exportingFootprint, setExportingFootprint] = useState(false)
  const [exportFootprintError, setExportFootprintError] = useState<string | null>(null)

  // CTX-308.7: SPEC-308's third named concern (decoupling, protection,
  // power) -- available once a part and its footprint are both real
  // (SPEC-308 §5's own stated product stage), not gated on
  // footprintGenerated -- guidance is just as useful for a found
  // footprint as a generated one.
  const [guidance, setGuidance] = useState<ConnectionGuidance | null>(null)
  const [loadingGuidance, setLoadingGuidance] = useState(false)
  const [guidanceError, setGuidanceError] = useState<string | null>(null)

  // CTX-205.4: SPEC-205's real Design Requirements panel -- the result
  // itself lives on savedPart.design_guidance (the route persists onto
  // and returns the whole Part, matching attachFootprintToPart's own
  // "re-save returns the fresh whole record" shape), so no separate
  // result state var is needed here, only the real in-flight/error state.
  const [generatingDesignGuidance, setGeneratingDesignGuidance] = useState(false)
  const [designGuidanceError, setDesignGuidanceError] = useState<string | null>(null)
  const [openingCitationPage, setOpeningCitationPage] = useState<number | null>(null)
  const [citationOpenError, setCitationOpenError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    setExtraction(null)
    setSavedSymbol(null)
    setSavedPart(null)
    setExportedPath(null)
    setSaveError(null)
    setProjectLinkWarning(null)
    setExportError(null)
    setFootprintQuery('')
    setFootprintStatus('idle')
    setFootprintError(null)
    setFootprintCandidates(null)
    setCommunityStatus('idle')
    setCommunityError(null)
    setCommunityCandidates(null)
    setCommunityImportingPath(null)
    setCommunitySymbolBrowse(null)
    setCommunityImportedSymbolId(null)
    setGeneratingFootprint(false)
    setFootprintGenerated(false)
    setExportedFootprintPath(null)
    setExportingFootprint(false)
    setExportFootprintError(null)
    setGuidance(null)
    setLoadingGuidance(false)
    setGuidanceError(null)
    setGeneratingDesignGuidance(false)
    setDesignGuidanceError(null)
    setOpeningCitationPage(null)
    setCitationOpenError(null)
    setLibraryPickerOpen(false)
    setAvailableLibraries(null)
    setSelectedLibraryIds([])
    setTaggingLibraries(false)
    setLibraryTagError(null)
    setLibraryTagMessage(null)

    if (initialPart) {
      // Already-saved -- hydrate directly from the Library's own real
      // record rather than replaying SPEC-202's LLM extraction for a
      // part that's already confirmed. Matches the lazy `useState`
      // initializers above, which already seeded the very first render
      // with this same data -- this just re-applies it if `initialPart`
      // itself changes later (a different Part opened while mounted).
      setExtraction(initialPartToExtraction(initialPart))
      setSavedPart(initialPart)
      setSavedSymbol(initialPartToSymbol(initialPart))
      setStatus('ready')
      return () => {
        cancelled = true
      }
    }

    setStatus('extracting')
    const confirmedCandidate = candidate

    // CTX-306.3: a candidate confirmed from search may already be a real,
    // saved Part (SPEC-306's own confidence-based matching doesn't know
    // about the library) -- try the cheap, real hydration path first
    // rather than always re-running SPEC-202's LLM extraction on
    // something already confirmed and saved once before. A miss here
    // (genuinely new part) is the expected, common case and falls
    // straight through to extraction, unchanged.
    async function loadOrExtract() {
      try {
        const saved = await loadPart(confirmedCandidate.part_number)
        if (cancelled) return
        setExtraction(initialPartToExtraction(saved))
        setSavedPart(saved)
        setSavedSymbol(initialPartToSymbol(saved))
        setStatus('ready')
        return
      } catch {
        // Not saved yet -- fall through to real extraction below.
      }

      try {
        const schema = await extractPartDetail(confirmedCandidate.part_number)
        if (cancelled) return
        setExtraction(schema)
        setStatus('ready')
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setStatus('error')
      }
    }

    void loadOrExtract()

    return () => {
      cancelled = true
    }
  }, [candidate?.part_number, initialPart?.part_id])

  async function handleSave() {
    if (!extraction || !candidate) return
    setSaving(true)
    setSaveError(null)
    setProjectLinkWarning(null)
    try {
      const saved = await saveConfirmedPart(candidate, extraction)
      setSavedSymbol(saved.symbol)
      setSavedPart(saved.part)

      // CTX-304.3: a real, separate step from the save above -- a
      // failure here never rolls back or hides the already-succeeded
      // save, it's only ever surfaced as its own, non-blocking warning.
      if (currentProject) {
        try {
          await addProjectPartReference(currentProject.name, saved.part.part_id)
        } catch (err) {
          setProjectLinkWarning(
            `Saved, but couldn't link it to project "${currentProject.name}": ${
              err instanceof Error ? err.message : String(err)
            }`,
          )
        }
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  /** CTX-315.2/SPEC-315 §5: a real, separate action from "Save to
   * Library" above -- opens a picker over the real current set of
   * custom libraries (Default excluded; it's implicit and never a
   * choice to make here). */
  async function handleOpenLibraryPicker() {
    if (!savedPart) return
    setLibraryTagError(null)
    setLibraryTagMessage(null)
    setLibraryPickerOpen(true)
    try {
      const libraries = await listLibraries()
      setAvailableLibraries(libraries.filter((l) => l.id !== 'default'))
    } catch (err) {
      setLibraryTagError(err instanceof Error ? err.message : String(err))
    }
  }

  function handleToggleLibrarySelection(libraryId: string) {
    setSelectedLibraryIds((prev) =>
      prev.includes(libraryId) ? prev.filter((id) => id !== libraryId) : [...prev, libraryId],
    )
  }

  async function handleConfirmAddToLibrary() {
    if (!savedPart) return
    setTaggingLibraries(true)
    setLibraryTagError(null)
    try {
      await tagObject('part', savedPart.part_id, selectedLibraryIds)
      setLibraryTagMessage('Added to library.')
      setLibraryPickerOpen(false)
    } catch (err) {
      setLibraryTagError(err instanceof Error ? err.message : String(err))
    } finally {
      setTaggingLibraries(false)
    }
  }

  async function handleFootprintSearch() {
    const trimmed = footprintQuery.trim()
    if (!trimmed) return

    setFootprintStatus('searching')
    setFootprintError(null)
    try {
      const results = await searchFootprints(trimmed)
      setFootprintCandidates(results)
      setFootprintStatus('idle')
    } catch (err) {
      setFootprintCandidates(null)
      setFootprintError(err instanceof Error ? err.message : String(err))
      setFootprintStatus('error')
    }
  }

  async function handleAttachFootprint(candidateFootprint: FootprintCandidate) {
    if (!savedPart) return
    setAttachingFootprint(candidateFootprint.footprint_name)
    try {
      const updated = await attachFootprintToPart(savedPart, candidateFootprint.library, candidateFootprint.footprint_name)
      setSavedPart(updated)
    } catch (err) {
      setFootprintError(err instanceof Error ? err.message : String(err))
    } finally {
      setAttachingFootprint(null)
    }
  }

  async function handleCommunitySearch() {
    const trimmed = footprintQuery.trim()
    if (!trimmed) return

    setCommunityStatus('searching')
    setCommunityError(null)
    setCommunitySymbolBrowse(null)
    try {
      const results = await searchCommunityFootprints(trimmed)
      setCommunityCandidates(results)
      setCommunityStatus('idle')
    } catch (err) {
      setCommunityCandidates(null)
      setCommunityError(err instanceof Error ? err.message : String(err))
      setCommunityStatus('error')
    }
  }

  /** A `.kicad_mod` candidate imports and attaches to the Part directly.
   * A `.kicad_sym` candidate's own file may hold many real symbols
   * (SPEC-314 §2) -- this first call (no symbolName) always returns the
   * real browse list, never guessing which one the user wants. */
  async function handleImportCommunityCandidate(candidateFootprint: CommunityLibraryCandidate) {
    if (!savedPart) return
    setCommunityImportingPath(candidateFootprint.path)
    setCommunityError(null)
    try {
      const result = await importCommunityFootprint(candidateFootprint)
      if ('symbols' in result) {
        setCommunitySymbolBrowse({ candidate: candidateFootprint, symbols: result.symbols })
      } else {
        const updated = await attachCommunityFootprintToPart(savedPart, result)
        setSavedPart(updated)
      }
    } catch (err) {
      setCommunityError(err instanceof Error ? err.message : String(err))
    } finally {
      setCommunityImportingPath(null)
    }
  }

  /** The real, chosen second step for a `.kicad_sym` candidate -- SPEC-314
   * §1's own non-goal boundary (no schematic symbol placement) means this
   * only ever persists the symbol to the local library, never attaches it
   * to the Part the way a footprint import does. */
  async function handleImportCommunitySymbol(symbolName: string) {
    if (!communitySymbolBrowse) return
    const { candidate } = communitySymbolBrowse
    setCommunityImportingPath(candidate.path)
    setCommunityError(null)
    try {
      const result = await importCommunityFootprint(candidate, symbolName)
      setCommunityImportedSymbolId('symbol_id' in result ? result.symbol_id ?? null : null)
      setCommunitySymbolBrowse(null)
    } catch (err) {
      setCommunityError(err instanceof Error ? err.message : String(err))
    } finally {
      setCommunityImportingPath(null)
    }
  }

  async function handleGenerateFootprint() {
    if (!savedPart) return
    setGeneratingFootprint(true)
    setFootprintError(null)
    try {
      const updated = await generateFootprintFromPart(savedPart)
      setSavedPart(updated)
      setFootprintGenerated(true)
      setFootprintStatus('idle')
    } catch (err) {
      setFootprintError(err instanceof Error ? err.message : String(err))
      setFootprintStatus('error')
    } finally {
      setGeneratingFootprint(false)
    }
  }

  async function handleExportFootprint() {
    if (!savedPart?.footprint_id) return
    setExportingFootprint(true)
    setExportFootprintError(null)
    try {
      const path = await exportFootprint(savedPart.footprint_id)
      setExportedFootprintPath(path)
    } catch (err) {
      setExportFootprintError(err instanceof Error ? err.message : String(err))
    } finally {
      setExportingFootprint(false)
    }
  }

  /** Real bug found by live user testing: the previous "Open symbol"/
   * "Open footprint" buttons called `open()` fire-and-forget -- no
   * await, no error handling -- so a failure (e.g. no OS file
   * association for .kicad_sym/.kicad_mod, very likely on a machine
   * without KiCad's file associations set up) silently did nothing,
   * with no visible sign the click was even registered. Mirrors
   * `handleOpenCitation`'s own real await/try/catch shape. */
  async function handleOpenSymbol() {
    if (!exportedPath) return
    setExportError(null)
    try {
      await open(exportedPath)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleOpenFootprint() {
    if (!exportedFootprintPath) return
    setExportFootprintError(null)
    try {
      await open(exportedFootprintPath)
    } catch (err) {
      setExportFootprintError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleGetGuidance() {
    if (!savedPart) return
    setLoadingGuidance(true)
    setGuidanceError(null)
    try {
      const result = await getConnectionGuidance(savedPart.part_id)
      setGuidance(result)
    } catch (err) {
      setGuidanceError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingGuidance(false)
    }
  }

  /** SPEC-205: available as soon as a Part is real, not gated on a
   * footprint the way Connection Guidance is -- design requirements
   * (decoupling, reset, layout…) are useful before any footprint
   * exists. */
  async function handleGenerateDesignGuidance() {
    if (!savedPart) return
    setGeneratingDesignGuidance(true)
    setDesignGuidanceError(null)
    try {
      const updated = await generateDesignGuidance(savedPart.part_id)
      setSavedPart(updated)
    } catch (err) {
      setDesignGuidanceError(err instanceof Error ? err.message : String(err))
    } finally {
      setGeneratingDesignGuidance(false)
    }
  }

  /** SPEC-205 §5: "opens the datasheet at that page" -- resolves the
   * real local cached PDF path (reusing cacheDatasheet, the same real
   * function ComponentDiscovery's own "Open" button already calls;
   * datasheet.generate_guidance's own response never returns a path,
   * only a content_hash) and opens it with a `#page=N` fragment. No
   * existing precedent in this repo for whether the OS's default PDF
   * viewer actually honors that fragment via plugin-shell's open() --
   * a real, named, not-yet-verified assumption, not a proven feature. */
  async function handleOpenCitation(item: DesignGuidanceItem) {
    if (!savedPart) return
    setOpeningCitationPage(item.page)
    setCitationOpenError(null)
    try {
      const path = await cacheDatasheet(savedPart.part_id, savedPart.datasheet_url)
      await open(`${path}#page=${item.page}`)
    } catch (err) {
      setCitationOpenError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningCitationPage(null)
    }
  }

  async function handleExport() {
    if (!savedSymbol) return
    setExporting(true)
    setExportError(null)
    try {
      const path = await exportSymbol(savedSymbol.symbol_id)
      setExportedPath(path)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err))
    } finally {
      setExporting(false)
    }
  }

  if (status === 'extracting') {
    return <p className="text-sm text-fg-muted">Extracting pin data for {candidate?.part_number}…</p>
  }

  if (status === 'error') {
    return <p className="text-sm text-danger">{error}</p>
  }

  const schema = extraction as ExtractedSchema
  // CTX-315.4: a freshly-confirmed candidate carries manufacturer on its
  // own record (SPEC-202's extraction call never returns it); an
  // already-saved Part carries it on the Part record itself instead.
  const manufacturer = initialPart?.manufacturer ?? candidate?.manufacturer

  return (
    <div className="flex w-full max-w-4xl flex-col gap-3">
      <p className="text-sm font-medium text-fg">
        {schema.part_number} <span className="text-fg-muted">{manufacturer}</span>{' '}
        <span className="text-fg-muted">{schema.package}</span>
      </p>

      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-fg-muted">
            <th className="pr-2 font-medium">#</th>
            <th className="pr-2 font-medium">Name</th>
            <th className="pr-2 font-medium">Type</th>
            <th className="font-medium">Source</th>
          </tr>
        </thead>
        <tbody>
          {schema.pins.map((pin) => (
            <tr key={pin.number} className="text-fg-secondary">
              <td className="pr-2">{pin.number}</td>
              <td className="pr-2">{pin.name}</td>
              <td className="pr-2">{pin.electrical_type}</td>
              <td className="text-fg-muted">llm_extraction</td>
            </tr>
          ))}
        </tbody>
      </table>

      {!savedSymbol ? (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            className="self-start rounded bg-accent px-4 py-2 text-sm font-medium text-accent-fg disabled:opacity-50"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving…' : 'Save to Library'}
          </button>
          {saveError && <p className="text-sm text-danger">{saveError}</p>}
        </div>
      ) : (
        <div className="flex flex-col gap-2 rounded border border-line p-3">
          <p className="text-sm text-success">Saved to library.</p>
          {projectLinkWarning && <p className="text-xs text-warning">{projectLinkWarning}</p>}
          {!exportedPath ? (
            <button
              type="button"
              className="self-start rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
              onClick={handleExport}
              disabled={exporting}
            >
              {exporting ? 'Exporting…' : 'Export Symbol (.kicad_sym)'}
            </button>
          ) : (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-fg-muted">Exported: {exportedPath}</p>
              <button
                type="button"
                className="self-start rounded border border-line px-2 py-0.5 text-xs"
                onClick={() => void handleOpenSymbol()}
              >
                Open symbol
              </button>
            </div>
          )}
          {exportError && <p className="text-sm text-danger">{exportError}</p>}
        </div>
      )}

      {savedPart && (
        <div className="flex flex-col gap-2 rounded border border-line p-3">
          {/* CTX-315.2/SPEC-315 §5: real, separate from "Save to Library"
              -- always saves to Default already; this tags into 0+
              additional custom libraries. */}
          <div className="flex flex-col gap-2 border-b border-line-subtle pb-2">
            {!libraryPickerOpen ? (
              <button
                type="button"
                className="self-start rounded border border-line px-3 py-1 text-xs font-medium"
                onClick={() => void handleOpenLibraryPicker()}
              >
                Add to library…
              </button>
            ) : (
              <div className="flex flex-col gap-2">
                {availableLibraries === null && !libraryTagError && (
                  <p className="text-xs text-fg-muted">Loading libraries…</p>
                )}
                {availableLibraries !== null && availableLibraries.length === 0 && (
                  <p className="text-xs text-fg-muted">
                    No custom libraries yet. Create one from the Library area.
                  </p>
                )}
                {availableLibraries?.map((library) => (
                  <label key={library.id} className="flex items-center gap-2 text-xs text-fg-secondary">
                    <input
                      type="checkbox"
                      checked={selectedLibraryIds.includes(library.id)}
                      onChange={() => handleToggleLibrarySelection(library.id)}
                    />
                    {library.name}
                  </label>
                ))}
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="self-start rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
                    onClick={() => void handleConfirmAddToLibrary()}
                    disabled={taggingLibraries || selectedLibraryIds.length === 0}
                  >
                    {taggingLibraries ? 'Adding…' : 'Confirm'}
                  </button>
                  <button
                    type="button"
                    className="self-start rounded border border-line px-3 py-1 text-xs"
                    onClick={() => setLibraryPickerOpen(false)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {libraryTagError && <p className="text-sm text-danger">{libraryTagError}</p>}
            {libraryTagMessage && <p className="text-sm text-success">{libraryTagMessage}</p>}
          </div>

          {/* CTX-205.3/.4/.7, SPEC-205: real, cited (Class B) design
              requirements grouped by category -- available as soon as a
              Part is real, not gated on a footprint the way Connection
              Guidance below is (decoupling/reset/layout guidance is
              useful before any footprint exists). Only Class B (cited
              datasheet prose) exists today; Class A (typed facts) and
              Class C (general practice) are real, deferred backend
              work, not shown as an empty placeholder section. Per
              SPEC-205 §5 (amended in CTX-205.7): each category leads
              with its real plain-language summary -- the primary
              reading surface -- with its underlying cited items
              collapsed below it, available on demand as proof, not the
              first thing a reader has to parse. A category with no
              summary yet (a pre-CTX-205.7 record, or a category whose
              synthesis genuinely produced nothing) falls back to
              showing its citations directly, open by default, since
              there's nothing else to lead with. */}
          <div className="flex flex-col gap-2 border-b border-line-subtle pb-2">
            <div className="flex items-center gap-2">
              <p className="flex-1 text-xs font-medium uppercase text-fg-muted">Design Requirements</p>
              {savedPart.design_guidance && (
                <button
                  type="button"
                  className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                  onClick={() => void handleGenerateDesignGuidance()}
                  disabled={generatingDesignGuidance}
                >
                  {generatingDesignGuidance ? 'Regenerating…' : 'Regenerate'}
                </button>
              )}
            </div>

            {!savedPart.design_guidance ? (
              <button
                type="button"
                className="self-start rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                onClick={() => void handleGenerateDesignGuidance()}
                disabled={generatingDesignGuidance}
              >
                {generatingDesignGuidance ? 'Generating…' : 'Generate Design Requirements'}
              </button>
            ) : (
              <div className="flex flex-col gap-3">
                {Object.entries(DESIGN_GUIDANCE_CATEGORY_LABELS).map(([key, label]) => {
                  const items = savedPart.design_guidance?.categories[key] ?? []
                  const summary = savedPart.design_guidance?.category_summaries[key] ?? null
                  return (
                    <div key={key} className="flex flex-col gap-1">
                      <p className="text-xs font-medium text-fg-secondary">{label}</p>
                      {items.length === 0 ? (
                        <p className="text-xs text-fg-muted">No guidance found for this category.</p>
                      ) : (
                        <>
                          {summary && <p className="text-xs text-fg-secondary">{summary}</p>}
                          <details open={!summary}>
                            <summary className="cursor-pointer text-xs font-medium text-fg-muted">
                              {summary
                                ? `${items.length} citation${items.length === 1 ? '' : 's'}`
                                : 'Citations'}
                            </summary>
                            <ul className="mt-1 flex flex-col gap-1">
                              {items.map((item, i) => (
                                <li key={i} className="flex items-start gap-2 text-xs text-fg-secondary">
                                  <button
                                    type="button"
                                    className="shrink-0 rounded border border-line px-2 py-0.5 text-xs font-medium text-fg-secondary disabled:opacity-50"
                                    onClick={() => void handleOpenCitation(item)}
                                    disabled={openingCitationPage !== null}
                                    title="Open the datasheet at this page"
                                  >
                                    {openingCitationPage === item.page ? '…' : `Page ${item.page}`}
                                  </button>
                                  <span>{item.quote}</span>
                                </li>
                              ))}
                            </ul>
                          </details>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            {designGuidanceError && <p className="text-sm text-danger">{designGuidanceError}</p>}
            {citationOpenError && <p className="text-sm text-danger">{citationOpenError}</p>}
          </div>

          {savedPart.footprint_id ? (
            <>
              <p className="text-sm text-success">
                Footprint linked: {savedPart.footprint_id}
                {footprintGenerated && (
                  <span className="ml-2 text-xs font-medium text-warning">
                    (generated from datasheet dimensions — unverified)
                  </span>
                )}
              </p>
              {!exportedFootprintPath ? (
                <button
                  type="button"
                  className="self-start rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                  onClick={handleExportFootprint}
                  disabled={exportingFootprint}
                >
                  {exportingFootprint ? 'Exporting…' : 'Export Footprint (.kicad_mod)'}
                </button>
              ) : (
                <div className="flex flex-col gap-1">
                  <p className="text-xs text-fg-muted">Exported: {exportedFootprintPath}</p>
                  <button
                    type="button"
                    className="self-start rounded border border-line px-2 py-0.5 text-xs"
                    onClick={() => void handleOpenFootprint()}
                  >
                    Open footprint
                  </button>
                </div>
              )}
              {exportFootprintError && <p className="text-sm text-danger">{exportFootprintError}</p>}

              {/* CTX-308.7: SPEC-308's third named concern -- available
                  now that a part and its footprint are both real. */}
              <div className="flex flex-col gap-2 border-t border-line-subtle pt-2">
                {!guidance ? (
                  <button
                    type="button"
                    className="self-start rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                    onClick={handleGetGuidance}
                    disabled={loadingGuidance}
                  >
                    {loadingGuidance ? 'Getting guidance…' : 'Get Connection Guidance'}
                  </button>
                ) : (
                  <div className="flex flex-col gap-2">
                    <p className="text-xs font-medium uppercase text-fg-muted">Connection Guidance</p>
                    {guidance.pin_guidance.length === 0 ? (
                      <p className="text-xs text-fg-muted">No pin-specific guidance for this part.</p>
                    ) : (
                      <ul className="flex flex-col gap-1">
                        {guidance.pin_guidance.map((entry) => (
                          <li key={entry.pin_number} className="text-xs text-fg-secondary">
                            <span className="font-medium text-fg">Pin {entry.pin_number}:</span>{' '}
                            {entry.guidance}
                          </li>
                        ))}
                      </ul>
                    )}
                    {guidance.general_notes && (
                      <p className="text-xs text-fg-tertiary">{guidance.general_notes}</p>
                    )}
                  </div>
                )}
                {guidanceError && <p className="text-sm text-danger">{guidanceError}</p>}
              </div>
            </>
          ) : (
            <>
              <p className="text-xs font-medium uppercase text-fg-muted">Find Footprint</p>
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded border border-line bg-surface px-3 py-2 text-sm"
                  placeholder="search this machine's own KiCad libraries"
                  value={footprintQuery}
                  onChange={(e) => setFootprintQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleFootprintSearch()
                  }}
                />
                <button
                  type="button"
                  className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                  onClick={handleFootprintSearch}
                  disabled={footprintQuery.trim().length === 0 || footprintStatus === 'searching'}
                >
                  {footprintStatus === 'searching' ? 'Searching…' : 'Search'}
                </button>
              </div>

              {footprintStatus === 'error' && footprintError && (
                <p className="text-sm text-danger">{footprintError}</p>
              )}

              {footprintCandidates !== null && footprintCandidates.length === 0 && (
                <p className="text-xs text-fg-muted">
                  No match in this machine's own configured KiCad libraries.
                </p>
              )}

              {/* CTX-308.5: source three -- generate from this part's own
                  datasheet dimensions (PRODUCT-PLAN.md §8 item 3), no new
                  search needed. Always available, not gated on a zero-result
                  search -- a user who already knows nothing installed will
                  match shouldn't have to search first. */}
              <div className="flex items-center gap-2 border-t border-line-subtle pt-2">
                <button
                  type="button"
                  className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                  onClick={handleGenerateFootprint}
                  disabled={generatingFootprint}
                >
                  {generatingFootprint ? 'Generating…' : 'Generate from datasheet dimensions'}
                </button>
              </div>

              {footprintCandidates !== null && footprintCandidates.length > 0 && (
                <div className="flex flex-col gap-2">
                  {footprintCandidates.map((fp) => (
                    <div
                      key={`${fp.library}:${fp.footprint_name}`}
                      className="flex items-center justify-between gap-3 rounded border border-line-subtle p-2"
                    >
                      <p className="text-xs text-fg-secondary">
                        {fp.footprint_name} <span className="text-fg-muted">{fp.library}</span>{' '}
                        <span className="text-fg-faint">
                          {fp.source === 'your_library' ? '· previously saved' : '· KiCad library'}
                        </span>
                      </p>
                      <button
                        type="button"
                        className="rounded border border-line px-2 py-0.5 text-xs font-medium disabled:opacity-50"
                        onClick={() => handleAttachFootprint(fp)}
                        disabled={attachingFootprint !== null}
                      >
                        {attachingFootprint === fp.footprint_name ? 'Linking…' : 'Use this'}
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* CTX-314.2/SPEC-314: source four -- a real, curated
                  allowlist of GitHub-hosted community libraries, alongside
                  the installed-library results above. Reuses the same
                  query, its own separate search action/results. */}
              <div className="flex flex-col gap-2 border-t border-line-subtle pt-2">
                <div className="flex items-center gap-2">
                  <p className="flex-1 text-xs font-medium uppercase text-fg-muted">Community Libraries</p>
                  <button
                    type="button"
                    className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                    onClick={handleCommunitySearch}
                    disabled={footprintQuery.trim().length === 0 || communityStatus === 'searching'}
                  >
                    {communityStatus === 'searching' ? 'Searching…' : 'Search community libraries'}
                  </button>
                </div>

                {communityStatus === 'error' && communityError && (
                  <p className="text-sm text-danger">{communityError}</p>
                )}

                {communityCandidates !== null && communityCandidates.length === 0 && (
                  <p className="text-xs text-fg-muted">No match in the known community libraries.</p>
                )}

                {communityImportedSymbolId && (
                  <p className="text-xs text-success">
                    Imported symbol <code>{communityImportedSymbolId}</code> to your library.
                  </p>
                )}

                {communitySymbolBrowse && (
                  <div className="flex flex-col gap-2 rounded border border-line-subtle p-2">
                    <p className="text-xs text-fg-tertiary">
                      {communitySymbolBrowse.candidate.path} contains {communitySymbolBrowse.symbols.length} real
                      symbols -- choose one to import:
                    </p>
                    {communitySymbolBrowse.symbols.map((s) => (
                      <div key={s.name} className="flex items-center justify-between gap-3">
                        <p className="text-xs text-fg-secondary">
                          {s.name} <span className="text-fg-faint">· {s.pin_count} pins</span>
                        </p>
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-0.5 text-xs font-medium disabled:opacity-50"
                          onClick={() => handleImportCommunitySymbol(s.name)}
                          disabled={communityImportingPath !== null}
                        >
                          {communityImportingPath === communitySymbolBrowse.candidate.path ? 'Importing…' : 'Import'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {communityCandidates !== null && communityCandidates.length > 0 && (
                  <div className="flex flex-col gap-2">
                    {communityCandidates.map((c) => (
                      <div
                        key={`${c.owner}/${c.repo}/${c.path}`}
                        className="flex items-center justify-between gap-3 rounded border border-line-subtle p-2"
                      >
                        <p className="text-xs text-fg-secondary">
                          {c.path.split('/').pop()}{' '}
                          <span className="text-fg-muted">
                            {c.owner}/{c.repo}
                          </span>{' '}
                          <span className="text-fg-faint">
                            · {c.license} · {c.kind}
                          </span>
                        </p>
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-0.5 text-xs font-medium disabled:opacity-50"
                          onClick={() => handleImportCommunityCandidate(c)}
                          disabled={communityImportingPath !== null}
                        >
                          {communityImportingPath === c.path ? 'Importing…' : 'Import'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
