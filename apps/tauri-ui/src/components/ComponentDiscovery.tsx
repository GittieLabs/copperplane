import { writeText } from '@tauri-apps/plugin-clipboard-manager'
import { open } from '@tauri-apps/plugin-shell'
import { useEffect, useState } from 'react'
import { cacheDatasheet, searchComponents, type ComponentCandidate } from '../lib/components'
import { listParts } from '../lib/library'
import { loadPart, type SavedPart } from '../lib/partDetail'
import type { Project } from '../lib/projects'
import { PartDetail } from './PartDetail'

type Status = 'idle' | 'searching' | 'error'

/** SPEC-306: the Components area's real search/disambiguation surface,
 * replacing SPEC-305's NotBuiltPlaceholder there. Always renders a
 * "did you mean" card list and always requires an explicit confirm --
 * never auto-selects a single candidate, even a high-confidence one
 * (SPEC-306 §2's own rule against reintroducing the silent-substitution
 * bug with a confidence threshold instead of a regex). Stops at a
 * confirmed candidate; Part Detail and the actual library save are
 * SPEC-307's job, not built yet.
 *
 * Real bug found by live user testing: this component used to be
 * unmounted the instant the user switched to any other area tab (a
 * plain conditional render in App.tsx), throwing away in-progress
 * search results, a just-confirmed candidate, and everything
 * PartDetail itself had done underneath it (Save to Library, Export,
 * Generate Design Requirements) with no warning. Stays mounted across
 * every area tab now (App.tsx hides it with CSS instead of
 * unmounting it), same as SchematicAdvisor/BoardAdvisor/EnclosurePanel
 * and for the same reason. `projectName` only resets state on a
 * genuine project switch, mirroring their own established pattern. */
export function ComponentDiscovery({
  projectName,
  currentProject,
}: {
  projectName: string
  /** CTX-304.3: threaded straight through to `PartDetail`, matching
   * `Overview`'s own existing `project={currentProject}` pattern in
   * `App.tsx` -- so a successful "Save to Library" can also add a real
   * Project→Part reference. Optional/omitted (rather than required)
   * so every pre-existing test rendering this component doesn't need
   * updating just to pass a prop it doesn't exercise. */
  currentProject?: Project | null
}) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<ComponentCandidate[]>([])
  const [confirmed, setConfirmed] = useState<{
    candidate: ComponentCandidate
    datasheetPath: string | null
    cacheError: string | null
  } | null>(null)
  const [confirmingPartNumber, setConfirmingPartNumber] = useState<string | null>(null)
  const [pathCopied, setPathCopied] = useState(false)
  // CTX-306.3: best-effort -- a listing failure shouldn't block search
  // results from rendering, it just means no candidate gets a badge.
  const [savedPartIds, setSavedPartIds] = useState<Set<string> | null>(null)

  // CTX-306.4: real user feedback -- after saving a part and navigating
  // away, Components showed only the last-viewed candidate or nothing
  // at all, with no persistent record of what this project actually
  // references. `projectParts` hydrates `currentProject.parts`' bare
  // id list (CTX-304.3) into real, displayable records; `openedPartId`
  // is a separate, real "detail view with back navigation" state from
  // `confirmed` above -- opening an already-saved part from this list
  // needs no datasheet-caching UI or re-confirmation, just a straight
  // reopen (mirroring `App.tsx`'s own `PartDetailView`/`initialPart`
  // shape, but kept local here rather than routed through `App`'s view
  // state, so it stays inside the Components tab the user is already in).
  const [projectParts, setProjectParts] = useState<SavedPart[] | null>(null)
  const [openedPartId, setOpenedPartId] = useState<string | null>(null)
  const [openedPart, setOpenedPart] = useState<SavedPart | null>(null)
  const [openedPartError, setOpenedPartError] = useState<string | null>(null)

  useEffect(() => {
    setQuery('')
    setStatus('idle')
    setError(null)
    setCandidates([])
    setConfirmed(null)
    setConfirmingPartNumber(null)
    setPathCopied(false)
    setSavedPartIds(null)
    setOpenedPartId(null)
  }, [projectName])

  const projectPartIds = currentProject?.parts?.join(',') ?? ''

  useEffect(() => {
    let cancelled = false
    const ids = currentProject?.parts ?? []
    if (ids.length === 0) {
      setProjectParts([])
      return
    }
    setProjectParts(null)
    Promise.allSettled(ids.map((id) => loadPart(id))).then((results) => {
      if (cancelled) return
      // Best-effort, same as savedPartIds above -- a part_id referenced
      // by the project but no longer loadable (e.g. deleted from the
      // Library outside this app) is silently omitted, not an error
      // that blocks the rest of the list from rendering.
      setProjectParts(
        results
          .filter((r): r is PromiseFulfilledResult<SavedPart> => r.status === 'fulfilled')
          .map((r) => r.value),
      )
    })
    return () => {
      cancelled = true
    }
  }, [projectName, projectPartIds])

  useEffect(() => {
    if (!openedPartId) {
      setOpenedPart(null)
      setOpenedPartError(null)
      return
    }
    let cancelled = false
    setOpenedPart(null)
    setOpenedPartError(null)
    loadPart(openedPartId)
      .then((part) => {
        if (!cancelled) setOpenedPart(part)
      })
      .catch((err) => {
        if (!cancelled) setOpenedPartError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [openedPartId])

  async function handleCopyPath(path: string) {
    await writeText(path)
    setPathCopied(true)
  }

  // Real end-to-end verification found this: a plain <a target="_blank">
  // does not reliably escape the Tauri webview (no browser chrome to open
  // a new tab into), and asking the user to copy a local file path into a
  // terminal to run `open <path>` themselves is real, reported friction.
  // tauri-plugin-shell's open() hands both cases to the OS directly.
  async function handleOpen(target: string) {
    await open(target)
  }

  async function handleSearch() {
    const trimmed = query.trim()
    if (!trimmed) return

    setStatus('searching')
    setError(null)
    setConfirmed(null)

    try {
      const results = await searchComponents(trimmed)
      setCandidates(results)
      setStatus('idle')
    } catch (err) {
      setCandidates([])
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
      return
    }

    // CTX-306.3: real user feedback found parts already in the library
    // showing up in search results indistinguishable from brand-new ones,
    // with no signal that confirming would just re-run extraction on
    // something already saved. Best-effort, not a gate on search itself.
    try {
      const ids = await listParts()
      setSavedPartIds(new Set(ids))
    } catch {
      setSavedPartIds(null)
    }
  }

  function handleOpenProjectPart(partId: string) {
    setConfirmed(null)
    setOpenedPartId(partId)
  }

  /** Real bug found by live user testing: `candidates` only ever reset on
   * a genuine project switch, so once a search had run, its results
   * stayed on screen forever -- the Project Parts list (gated on
   * `candidates.length === 0`) could never come back without navigating
   * away and back. This is the explicit escape hatch back to that
   * default view. */
  function handleClearSearch() {
    setQuery('')
    setStatus('idle')
    setError(null)
    setCandidates([])
    setSavedPartIds(null)
  }

  async function handleConfirm(candidate: ComponentCandidate) {
    setOpenedPartId(null)
    setConfirmingPartNumber(candidate.part_number)
    setPathCopied(false)

    // Datasheet caching is best-effort, not a gate on confirmation --
    // real verification found a vendor site (microchip.com) sitting
    // behind Akamai bot protection that rejects any plain HTTP client
    // outright, even with browser-spoofed headers. Blocking confirmation
    // on that would make a correctly-identified, real part permanently
    // unconfirmable through no fault of the identification itself.
    try {
      const datasheetPath = await cacheDatasheet(candidate.part_number, candidate.datasheet_url)
      setConfirmed({ candidate, datasheetPath, cacheError: null })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setConfirmed({ candidate, datasheetPath: null, cacheError: message })
    } finally {
      setConfirmingPartNumber(null)
    }
  }

  if (openedPartId) {
    return (
      <div className="flex w-full max-w-4xl flex-col gap-2 rounded border border-line p-4">
        <button
          type="button"
          className="self-start rounded border border-line px-3 py-1 text-xs"
          onClick={() => setOpenedPartId(null)}
        >
          ← Back to project parts
        </button>
        {openedPartError && <p className="text-sm text-danger">{openedPartError}</p>}
        {!openedPartError && !openedPart && <p className="text-sm text-fg-muted">Loading…</p>}
        {openedPart && (
          <div className="mt-2 border-t border-line-subtle pt-3">
            <PartDetail initialPart={openedPart} currentProject={currentProject} />
          </div>
        )}
      </div>
    )
  }

  if (confirmed) {
    return (
      <div className="flex w-full max-w-4xl flex-col gap-2 rounded border border-line p-4">
        <p className="text-sm font-medium text-fg">
          Confirmed: {confirmed.candidate.part_number} ({confirmed.candidate.manufacturer}, {confirmed.candidate.package})
        </p>
        {confirmed.datasheetPath ? (
          <div className="flex flex-col gap-1">
            <p className="text-xs text-fg-muted">Datasheet cached: {confirmed.datasheetPath}</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="self-start rounded border border-line px-2 py-0.5 text-xs"
                onClick={() => handleOpen(confirmed.datasheetPath as string)}
              >
                Open datasheet
              </button>
              <button
                type="button"
                className="self-start rounded border border-line px-2 py-0.5 text-xs"
                onClick={() => handleCopyPath(confirmed.datasheetPath as string)}
              >
                Copy local path
              </button>
              {pathCopied && <span className="text-xs text-success">Copied.</span>}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <p className="text-xs text-warning">
              Datasheet couldn't be cached automatically ({confirmed.cacheError}).
            </p>
            <button
              type="button"
              className="self-start rounded border border-line px-2 py-0.5 text-xs"
              onClick={() => handleOpen(confirmed.candidate.datasheet_url)}
            >
              Open datasheet externally
            </button>
          </div>
        )}
        <button
          type="button"
          className="mt-2 self-start rounded border border-line px-3 py-1 text-xs"
          onClick={() => setConfirmed(null)}
        >
          Back to results
        </button>

        <div className="mt-2 border-t border-line-subtle pt-3">
          <PartDetail candidate={confirmed.candidate} currentProject={currentProject} />
        </div>
      </div>
    )
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-3">
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-line bg-surface px-3 py-2 text-sm"
          placeholder="search for a part, e.g. atiny85"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearch()
          }}
        />
        <button
          type="button"
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-accent-fg disabled:opacity-50"
          onClick={handleSearch}
          disabled={query.trim().length === 0 || status === 'searching'}
        >
          {status === 'searching' ? 'Searching…' : 'Search'}
        </button>
      </div>

      {status === 'error' && error && <p className="text-sm text-danger">{error}</p>}

      {candidates.length === 0 && (currentProject?.parts?.length ?? 0) > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium uppercase text-fg-muted">Project Parts</p>
          {projectParts === null && <p className="text-xs text-fg-muted">Loading…</p>}
          {projectParts?.map((part) => (
            <div
              key={part.part_id}
              className="flex items-center justify-between gap-3 rounded border border-line p-3"
            >
              <div className="flex flex-col gap-1">
                <p className="text-sm text-fg">
                  {part.part_id} <span className="text-fg-muted">{part.manufacturer}</span>
                </p>
                <p className="text-xs text-fg-muted">{part.package}</p>
              </div>
              <button
                type="button"
                className="rounded border border-line px-3 py-1 text-xs font-medium"
                onClick={() => handleOpenProjectPart(part.part_id)}
              >
                Open
              </button>
            </div>
          ))}
        </div>
      )}

      {candidates.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <p className="flex-1 text-xs font-medium uppercase text-fg-muted">Did you mean:</p>
            <button
              type="button"
              className="text-xs text-fg-tertiary underline"
              onClick={handleClearSearch}
            >
              ← Back to project parts
            </button>
          </div>
          {candidates.map((candidate) => (
            <div
              key={candidate.part_number}
              className="flex items-center justify-between gap-3 rounded border border-line p-3"
            >
              <div className="flex flex-col gap-1">
                <p className="text-sm text-fg">
                  {candidate.part_number} <span className="text-fg-muted">{candidate.manufacturer}</span>
                  {savedPartIds?.has(candidate.part_number) && (
                    <span className="ml-2 rounded border border-line-strong px-1.5 py-0.5 text-xs font-medium text-success">
                      Already in your library
                    </span>
                  )}
                </p>
                <p className="text-xs text-fg-muted">
                  {candidate.package} · confidence: {candidate.confidence}
                </p>
                <button
                  type="button"
                  className="self-start text-xs text-fg-tertiary underline"
                  onClick={() => handleOpen(candidate.datasheet_url)}
                >
                  view datasheet
                </button>
              </div>
              <button
                type="button"
                className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
                onClick={() => handleConfirm(candidate)}
                disabled={confirmingPartNumber !== null}
              >
                {confirmingPartNumber === candidate.part_number ? 'Confirming…' : 'This one'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
