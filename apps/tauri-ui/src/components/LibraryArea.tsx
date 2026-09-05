import { useRef, useEffect, useState } from 'react'
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
import { syncLibraryMenu } from '../lib/menu'

type ViewState = { kind: 'list' } | { kind: 'detail'; library: LibrarySummary }

/** CTX-315.2/SPEC-315: the real Library area -- resolves SPEC-305's own
 * placeholder note ("a real browsing UI ... is out of scope, deferred
 * to a future spec"). A list of real libraries (Default plus any
 * user-created custom ones), each with real counts; selecting one shows
 * its own two real sections (Datasheets/Pins, Footprints) -- never
 * merged into one list (SPEC-315 §3's own named hazard, since a
 * Footprint is a real, independently-shared object, not bundled with
 * whichever Part happens to reference it). */
export function LibraryArea({
  initialLibraryId,
  onSelectPart,
}: { initialLibraryId?: string; onSelectPart?: (partId: string) => void } = {}) {
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
      const result = await listLibraries()
      setLibraries(result)
      // CTX-316.2: keeps the native Library menu in sync with the real
      // registry -- covers both this component's own initial mount and
      // the post-create refresh below ("+ New library" already calls
      // this same function today).
      void syncLibraryMenu(result)
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

  const nameInputRef = useRef<HTMLInputElement>(null)

  async function handleCreateLibrary() {
    const name = newLibraryName.trim()
    // Reported as "new library button does not work". It was disabled, because
    // the name field was empty -- and a disabled button at 50% opacity, on a
    // dark surface, beside a field showing only placeholder text, is not a
    // sentence. Clicking now says what is needed and puts the cursor there.
    if (!name) {
      setError('Give the library a name first.')
      nameInputRef.current?.focus()
      return
    }
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
      <div className="flex w-full max-w-4xl flex-col gap-4 text-fg">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="text-xs text-fg-muted hover:text-fg-secondary"
            onClick={() => setView({ kind: 'list' })}
          >
            ← Libraries
          </button>
        </div>
        <h2 className="text-lg font-medium">{view.library.name}</h2>
        {detailError && <p className="text-sm text-danger">{detailError}</p>}

        {/* Real bug found by live user testing: Parts and Symbols were
            rendered as siblings under one combined "Datasheets / Pins"
            label, so a Symbol (e.g. "DIP-8_8pin", the raw symbol_id
            `library.save_confirmed_part` derives from a Part's own
            package/pin-count) looked like a second, unrelated entry
            rather than that same Part's own generated symbol. This
            module's own doc comment above already named the underlying
            principle for Footprints ("a real, independently-shared
            object... never bundled with whichever Part happens to
            reference it") -- Symbols share that same real property and
            should never have been merged into Parts' own section
            either. Split into two real, separately-labeled sections,
            matching Footprints' own already-correct precedent below. */}
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-fg-tertiary">Parts ({parts?.length ?? 0})</h3>
          {parts === null && !detailError && <p className="text-xs text-fg-muted">Loading…</p>}
          {parts !== null && parts.length === 0 && (
            <p className="text-xs text-fg-muted">No parts in this library yet.</p>
          )}
          {parts?.map((p) =>
            onSelectPart ? (
              <button
                key={p.part_id}
                type="button"
                className="rounded border border-line-subtle p-2 text-left text-xs text-fg-secondary hover:bg-surface"
                onClick={() => onSelectPart(p.part_id)}
              >
                {[p.part_id, p.manufacturer, p.package].filter(Boolean).join(' · ')}
              </button>
            ) : (
              <div key={p.part_id} className="rounded border border-line-subtle p-2 text-xs text-fg-secondary">
                {[p.part_id, p.manufacturer, p.package].filter(Boolean).join(' · ')}
              </div>
            ),
          )}
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-fg-tertiary">Symbols ({symbols?.length ?? 0})</h3>
          {symbols === null && !detailError && <p className="text-xs text-fg-muted">Loading…</p>}
          {symbols !== null && symbols.length === 0 && (
            <p className="text-xs text-fg-muted">No symbols in this library yet.</p>
          )}
          {symbols?.map((s) => (
            <div key={s.symbol_id} className="rounded border border-line-subtle p-2 text-xs text-fg-secondary">
              {s.symbol_name ?? s.symbol_id}
            </div>
          ))}
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-fg-tertiary">Footprints ({footprints?.length ?? 0})</h3>
          {footprints === null && !detailError && <p className="text-xs text-fg-muted">Loading…</p>}
          {footprints !== null && footprints.length === 0 && (
            <p className="text-xs text-fg-muted">No footprints in this library yet.</p>
          )}
          {footprints?.map((f) => (
            <div key={f.footprint_id} className="rounded border border-line-subtle p-2 text-xs text-fg-secondary">
              {[f.footprint_name ?? f.footprint_id, f.provenance?.license].filter(Boolean).join(' · ')}
            </div>
          ))}
        </section>
      </div>
    )
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-4 text-fg">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Libraries</h2>
        <div className="flex items-center gap-2">
          <input
            ref={nameInputRef}
            className="rounded border border-line bg-surface px-2 py-1 text-xs"
            placeholder="new library name"
            value={newLibraryName}
            onChange={(e) => {
              setNewLibraryName(e.target.value)
              if (error) setError(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleCreateLibrary()
            }}
          />
          <button
            type="button"
            className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
            onClick={() => void handleCreateLibrary()}
            disabled={creating}
          >
            {creating ? 'Creating…' : '+ New library'}
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {libraries === null && !error && <p className="text-sm text-fg-muted">Loading…</p>}

      <div className="flex flex-col gap-2">
        {libraries?.map((library) => (
          <button
            key={library.id}
            type="button"
            className="flex items-center justify-between rounded border border-line-subtle p-3 text-left hover:bg-surface"
            onClick={() => setView({ kind: 'detail', library })}
          >
            <span className="text-sm font-medium">{library.name}</span>
            <span className="text-xs text-fg-muted">
              {library.part_count} parts, {library.symbol_count} symbols, {library.footprint_count} footprints
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
