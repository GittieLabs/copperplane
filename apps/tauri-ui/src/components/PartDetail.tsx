import { open } from '@tauri-apps/plugin-shell'
import { useEffect, useState } from 'react'
import type { ComponentCandidate } from '../lib/components'
import { attachFootprintToPart, generateFootprintFromPart, searchFootprints, type FootprintCandidate } from '../lib/footprints'
import { exportSymbol, extractPartDetail, saveConfirmedPart, type ExtractedSchema, type SavedPart, type SavedSymbol } from '../lib/partDetail'

type Status = 'extracting' | 'ready' | 'error'
type FootprintSearchStatus = 'idle' | 'searching' | 'error'

/** SPEC-307: replaces SPEC-306's confirmed-candidate dead end with a
 * real pin diagram/table -- a second, real re-run of SPEC-202's
 * extraction for actual pin data (Discovery's own ranking call never
 * returns pins). "Save to Library" assembles provenance from the
 * confirmed candidate plus this extraction and persists a real Part +
 * Symbol; "Export Symbol" then writes a real, KiCad-openable
 * .kicad_sym file. */
export function PartDetail({ candidate }: { candidate: ComponentCandidate }) {
  const [status, setStatus] = useState<Status>('extracting')
  const [error, setError] = useState<string | null>(null)
  const [extraction, setExtraction] = useState<ExtractedSchema | null>(null)
  const [savedSymbol, setSavedSymbol] = useState<SavedSymbol | null>(null)
  const [savedPart, setSavedPart] = useState<SavedPart | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [exportedPath, setExportedPath] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  // CTX-308.2: the found-or-create footprint flow, once a Part exists but
  // has no footprint_id yet. Only searches this machine's own directly
  // configured KiCad libraries (CTX-308.1's own real scope limit).
  const [footprintQuery, setFootprintQuery] = useState('')
  const [footprintStatus, setFootprintStatus] = useState<FootprintSearchStatus>('idle')
  const [footprintError, setFootprintError] = useState<string | null>(null)
  const [footprintCandidates, setFootprintCandidates] = useState<FootprintCandidate[] | null>(null)
  const [attachingFootprint, setAttachingFootprint] = useState<string | null>(null)

  // CTX-308.5: source three (PRODUCT-PLAN.md §8 item 3) -- generate a
  // footprint from this part's own datasheet dimensions when nothing
  // installed matches. footprintGenerated is deliberately local-only UI
  // state (like exportedPath above), not derived from savedPart itself --
  // there's no cheap way to tell "generated" from "found" apart just by
  // looking at footprint_id without a second load_footprint round trip.
  const [generatingFootprint, setGeneratingFootprint] = useState(false)
  const [footprintGenerated, setFootprintGenerated] = useState(false)

  useEffect(() => {
    let cancelled = false
    setStatus('extracting')
    setError(null)
    setExtraction(null)
    setSavedSymbol(null)
    setSavedPart(null)
    setExportedPath(null)
    setSaveError(null)
    setExportError(null)
    setFootprintQuery('')
    setFootprintStatus('idle')
    setFootprintError(null)
    setFootprintCandidates(null)
    setGeneratingFootprint(false)
    setFootprintGenerated(false)

    extractPartDetail(candidate.part_number)
      .then((schema) => {
        if (cancelled) return
        setExtraction(schema)
        setStatus('ready')
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setStatus('error')
      })

    return () => {
      cancelled = true
    }
  }, [candidate.part_number])

  async function handleSave() {
    if (!extraction) return
    setSaving(true)
    setSaveError(null)
    try {
      const saved = await saveConfirmedPart(candidate, extraction)
      setSavedSymbol(saved.symbol)
      setSavedPart(saved.part)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
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
    return <p className="text-sm text-neutral-500">Extracting pin data for {candidate.part_number}…</p>
  }

  if (status === 'error') {
    return <p className="text-sm text-red-400">{error}</p>
  }

  const schema = extraction as ExtractedSchema

  return (
    <div className="flex w-full max-w-md flex-col gap-3">
      <p className="text-sm font-medium text-neutral-100">
        {schema.part_number} <span className="text-neutral-500">{candidate.manufacturer}</span>{' '}
        <span className="text-neutral-500">{schema.package}</span>
      </p>

      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-neutral-500">
            <th className="pr-2 font-medium">#</th>
            <th className="pr-2 font-medium">Name</th>
            <th className="pr-2 font-medium">Type</th>
            <th className="font-medium">Source</th>
          </tr>
        </thead>
        <tbody>
          {schema.pins.map((pin) => (
            <tr key={pin.number} className="text-neutral-300">
              <td className="pr-2">{pin.number}</td>
              <td className="pr-2">{pin.name}</td>
              <td className="pr-2">{pin.electrical_type}</td>
              <td className="text-neutral-500">llm_extraction</td>
            </tr>
          ))}
        </tbody>
      </table>

      {!savedSymbol ? (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            className="self-start rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving…' : 'Save to Library'}
          </button>
          {saveError && <p className="text-sm text-red-400">{saveError}</p>}
        </div>
      ) : (
        <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
          <p className="text-sm text-emerald-400">Saved to library.</p>
          {!exportedPath ? (
            <button
              type="button"
              className="self-start rounded border border-neutral-700 px-3 py-1 text-xs font-medium disabled:opacity-50"
              onClick={handleExport}
              disabled={exporting}
            >
              {exporting ? 'Exporting…' : 'Export Symbol (.kicad_sym)'}
            </button>
          ) : (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-neutral-500">Exported: {exportedPath}</p>
              <button
                type="button"
                className="self-start rounded border border-neutral-700 px-2 py-0.5 text-xs"
                onClick={() => open(exportedPath)}
              >
                Open symbol
              </button>
            </div>
          )}
          {exportError && <p className="text-sm text-red-400">{exportError}</p>}
        </div>
      )}

      {savedPart && (
        <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
          {savedPart.footprint_id ? (
            <p className="text-sm text-emerald-400">
              Footprint linked: {savedPart.footprint_id}
              {footprintGenerated && (
                <span className="ml-2 text-xs font-medium text-amber-400">
                  (generated from datasheet dimensions — unverified)
                </span>
              )}
            </p>
          ) : (
            <>
              <p className="text-xs font-medium uppercase text-neutral-500">Find Footprint</p>
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
                  placeholder="search this machine's own KiCad libraries"
                  value={footprintQuery}
                  onChange={(e) => setFootprintQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleFootprintSearch()
                  }}
                />
                <button
                  type="button"
                  className="rounded border border-neutral-700 px-3 py-1 text-xs font-medium disabled:opacity-50"
                  onClick={handleFootprintSearch}
                  disabled={footprintQuery.trim().length === 0 || footprintStatus === 'searching'}
                >
                  {footprintStatus === 'searching' ? 'Searching…' : 'Search'}
                </button>
              </div>

              {footprintStatus === 'error' && footprintError && (
                <p className="text-sm text-red-400">{footprintError}</p>
              )}

              {footprintCandidates !== null && footprintCandidates.length === 0 && (
                <p className="text-xs text-neutral-500">
                  No match in this machine's own configured KiCad libraries.
                </p>
              )}

              {/* CTX-308.5: source three -- generate from this part's own
                  datasheet dimensions (PRODUCT-PLAN.md §8 item 3), no new
                  search needed. Always available, not gated on a zero-result
                  search -- a user who already knows nothing installed will
                  match shouldn't have to search first. */}
              <div className="flex items-center gap-2 border-t border-neutral-800 pt-2">
                <button
                  type="button"
                  className="rounded border border-neutral-700 px-3 py-1 text-xs font-medium disabled:opacity-50"
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
                      className="flex items-center justify-between gap-3 rounded border border-neutral-800 p-2"
                    >
                      <p className="text-xs text-neutral-300">
                        {fp.footprint_name} <span className="text-neutral-500">{fp.library}</span>{' '}
                        <span className="text-neutral-600">
                          {fp.source === 'your_library' ? '· previously saved' : '· KiCad library'}
                        </span>
                      </p>
                      <button
                        type="button"
                        className="rounded border border-neutral-700 px-2 py-0.5 text-xs font-medium disabled:opacity-50"
                        onClick={() => handleAttachFootprint(fp)}
                        disabled={attachingFootprint !== null}
                      >
                        {attachingFootprint === fp.footprint_name ? 'Linking…' : 'Use this'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
