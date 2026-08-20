import { useEffect, useState } from 'react'
import {
  createLibrary,
  listFootprints,
  listLibraries,
  listParts,
  listSymbols,
  loadFootprint,
  loadPart,
  loadSymbol,
  type LibraryFootprintSummary,
  type LibraryPartSummary,
  type LibrarySummary,
  type LibrarySymbolSummary,
} from '../lib/library'

type ViewState = { kind: 'list' } | { kind: 'detail'; library: LibrarySummary }

/** CTX-315.2/SPEC-315: the real Library area -- resolves SPEC-305's own
 * placeholder note ("a real browsing UI ... is out of scope, deferred
 * to a future spec"). A list of real libraries (Default plus any
 * user-created custom ones), each with real counts; selecting one shows
 * its own two real sections (Datasheets/Pins, Footprints) -- never
 * merged into one list (SPEC-315 §3's own named hazard, since a
 * Footprint is a real, independently-shared object, not bundled with
 * whichever Part happens to reference it). */
export function LibraryArea({ initialLibraryId }: { initialLibraryId?: string } = {}) {
  const [view, setView] = useState<ViewState>({ kind: 'list' })
  const [libraries, setLibraries] = useState<LibrarySummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [newLibraryName, setNewLibraryName] = useState('')
  const [creating, setCreating] = useState(false)

  const [parts, setParts] = useState<LibraryPartSummary[] | null>(null)
  const [symbols, setSymbols] = useState<LibrarySymbolSummary[] | null>(null)
  const [footprints, setFootprints] = useState<LibraryFootprintSummary[] | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  async function refreshLibraries() {
    try {
      setLibraries(await listLibraries())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    void refreshLibraries()
  }, [])

  // SPEC-316: Library menu > "Default Library" deep-links straight into
  // Default's own detail view, reusing this component's already-existing
  // list->detail transition -- not a new code path. Falls back to the
  // list view (the existing initial state) if no match is found, a real
  // edge case (e.g. Default somehow didn't load) rather than an error.
  useEffect(() => {
    if (!initialLibraryId || !libraries) return
    const match = libraries.find((library) => library.id === initialLibraryId)
    if (match) setView({ kind: 'detail', library: match })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialLibraryId, libraries])

  useEffect(() => {
    if (view.kind !== 'detail') return
    let cancelled = false
    setParts(null)
    setSymbols(null)
    setFootprints(null)
    setDetailError(null)

    async function loadDetail() {
      try {
        const libraryId = (view as { kind: 'detail'; library: LibrarySummary }).library.id
        const [partIds, symbolIds, footprintIds] = await Promise.all([
          listParts(libraryId),
          listSymbols(libraryId),
          listFootprints(libraryId),
        ])
        const [loadedParts, loadedSymbols, loadedFootprints] = await Promise.all([
          Promise.all(partIds.map(loadPart)),
          Promise.all(symbolIds.map(loadSymbol)),
          Promise.all(footprintIds.map(loadFootprint)),
        ])
        if (cancelled) return
        setParts(loadedParts)
        setSymbols(loadedSymbols)
        setFootprints(loadedFootprints)
      } catch (err) {
        if (cancelled) return
        setDetailError(err instanceof Error ? err.message : String(err))
      }
    }

    void loadDetail()
    return () => {
      cancelled = true
    }
  }, [view])

  async function handleCreateLibrary() {
    const name = newLibraryName.trim()
    if (!name) return
    setCreating(true)
    setError(null)
    try {
      await createLibrary(name)
      setNewLibraryName('')
      await refreshLibraries()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setCreating(false)
    }
  }

  if (view.kind === 'detail') {
    return (
      <div className="flex w-full max-w-4xl flex-col gap-4 text-neutral-100">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="text-xs text-neutral-500 hover:text-neutral-300"
            onClick={() => setView({ kind: 'list' })}
          >
            ← Libraries
          </button>
        </div>
        <h2 className="text-lg font-medium">{view.library.name}</h2>
        {detailError && <p className="text-sm text-red-400">{detailError}</p>}

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-neutral-400">
            Datasheets / Pins ({(parts?.length ?? 0) + (symbols?.length ?? 0)})
          </h3>
          {parts === null && symbols === null && !detailError && (
            <p className="text-xs text-neutral-500">Loading…</p>
          )}
          {parts !== null && symbols !== null && parts.length === 0 && symbols.length === 0 && (
            <p className="text-xs text-neutral-500">No parts or symbols in this library yet.</p>
          )}
          {parts?.map((p) => (
            <div key={p.part_id} className="rounded border border-neutral-800 p-2 text-xs text-neutral-300">
              {[p.part_id, p.manufacturer, p.package].filter(Boolean).join(' · ')}
            </div>
          ))}
          {symbols?.map((s) => (
            <div key={s.symbol_id} className="rounded border border-neutral-800 p-2 text-xs text-neutral-300">
              {s.symbol_name ?? s.symbol_id}
            </div>
          ))}
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-neutral-400">Footprints ({footprints?.length ?? 0})</h3>
          {footprints === null && !detailError && <p className="text-xs text-neutral-500">Loading…</p>}
          {footprints !== null && footprints.length === 0 && (
            <p className="text-xs text-neutral-500">No footprints in this library yet.</p>
          )}
          {footprints?.map((f) => (
            <div key={f.footprint_id} className="rounded border border-neutral-800 p-2 text-xs text-neutral-300">
              {[f.footprint_name ?? f.footprint_id, f.provenance?.license].filter(Boolean).join(' · ')}
            </div>
          ))}
        </section>
      </div>
    )
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-4 text-neutral-100">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Libraries</h2>
        <div className="flex items-center gap-2">
          <input
            className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs"
            placeholder="new library name"
            value={newLibraryName}
            onChange={(e) => setNewLibraryName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleCreateLibrary()
            }}
          />
          <button
            type="button"
            className="rounded border border-neutral-700 px-3 py-1 text-xs font-medium disabled:opacity-50"
            onClick={() => void handleCreateLibrary()}
            disabled={!newLibraryName.trim() || creating}
          >
            {creating ? 'Creating…' : '+ New library'}
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {libraries === null && !error && <p className="text-sm text-neutral-500">Loading…</p>}

      <div className="flex flex-col gap-2">
        {libraries?.map((library) => (
          <button
            key={library.id}
            type="button"
            className="flex items-center justify-between rounded border border-neutral-800 p-3 text-left hover:bg-neutral-900"
            onClick={() => setView({ kind: 'detail', library })}
          >
            <span className="text-sm font-medium">{library.name}</span>
            <span className="text-xs text-neutral-500">
              {library.part_count} parts, {library.symbol_count} symbols, {library.footprint_count} footprints
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
