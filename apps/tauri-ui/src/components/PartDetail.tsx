import { open } from '@tauri-apps/plugin-shell'
import { useEffect, useState } from 'react'
import type { ComponentCandidate } from '../lib/components'
import { exportSymbol, extractPartDetail, saveConfirmedPart, type ExtractedSchema, type SavedSymbol } from '../lib/partDetail'

type Status = 'extracting' | 'ready' | 'error'

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
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [exportedPath, setExportedPath] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setStatus('extracting')
    setError(null)
    setExtraction(null)
    setSavedSymbol(null)
    setExportedPath(null)
    setSaveError(null)
    setExportError(null)

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
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
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
    </div>
  )
}
