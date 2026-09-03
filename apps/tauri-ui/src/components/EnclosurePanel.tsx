import { useCallback, useEffect, useState } from 'react'
import type { MenuCommand } from '../lib/areas'
import { type JobHandle } from '../lib/ipc'
import {
  exportBoardGlb,
  exportEnclosure,
  generateEnclosure,
  getComponentHeights,
  getProjectDirectory,
  pickExportDestination,
  pickPcbFile,
  type EnclosureParams,
  type EnclosureResult,
  type ExportFormat,
  type ExportParts,
} from '../lib/enclosure'
import { listOpenBoards, openKicad, type BoardCandidate, type ListOpenBoardsResult } from '../lib/boardAdvisor'
import { componentEnvelopes, linkedProjectBoard, type EnvelopeResult } from '../lib/kicadProject'
import { setProjectCheckResult } from '../lib/projects'
import { AgentChat } from './AgentChat'
import { ReviewPanel } from './ReviewPanel'
import { EnclosureViewer } from './EnclosureViewer'

/** Real, defensive path join -- avoids pulling in `@tauri-apps/api/path`
 * (a separate real permission surface) purely to pre-fill a save
 * dialog's own default location, a nice-to-have, not required for
 * correctness: `pickExportDestination` still works with no default at
 * all if this guesses wrong. Detects the separator already present in a
 * real OS-native directory path rather than assuming one. */
function _joinPath(dir: string, filename: string): string {
  const sep = dir.includes('\\') ? '\\' : '/'
  return dir.endsWith(sep) ? `${dir}${filename}` : `${dir}${sep}${filename}`
}

const _DEFAULT_BOARD_PARAMS = {
  height: 20,
  wall_thickness_mm: 2.0,
  clearance_mm: 0.5,
  fillet_radius_mm: 1.0,
  standoff_height_mm: 5.0,
}

/** SPEC-109/SPEC-310: real board-driven enclosure generation via
 * FreeCAD, explained in plain language.
 *
 * Real user feedback exercising the actual running app: the old
 * "From board" mode's five geometry fields showed as an unlabeled
 * stack of numbers -- each field's label was passed as an HTML
 * `placeholder`, which never renders once a real default value is
 * already filled in (every field had one). The old three-mode split
 * ("Manual dimensions" default-selected, "From board" gated behind a
 * live-KiCad capability check, "Import board file…" a blind file
 * dialog) also never reused a board the user already had open in
 * KiCad, even though `lib/boardAdvisor.ts`'s `listOpenBoards()`
 * (built for the PCB/Schematic tabs) already does exactly that real
 * lookup.
 *
 * Redesigned into two modes: "Board" (merges the old live/file modes
 * into one list-first picker, mirroring `BoardAdvisor`'s own pattern --
 * auto-selects a real, currently-open board when there's exactly one,
 * still lets the user pick a different one or a file manually) and
 * "Manual (no PCB)" (kept, but demoted to last/least-prominent, since a
 * hand-typed rectangle is the least useful starting point for someone
 * with a real board). Every mode produces the same shape -- a
 * rectangular box sized from either typed dimensions or the board's
 * real *bounding box* (`kicad_bridge.get_board_outline()`'s own
 * docstring: "the real, sufficient board-outline data for SPEC-109's
 * fixed-rectangular-enclosure scope") -- said honestly in the UI
 * instead of implying "From board" traces a non-rectangular outline. */
/** CTX-312.1: one real export event, reported straight from the point a
 * real `freecad.export_enclosure` call actually succeeds -- App.tsx's
 * own `handleExportSuccess` immediately persists it into the current
 * Project's real, permanent `export_history`, rather than depending on
 * a separate, easy-to-forget "Save Project" click to not lose it. */
export interface EnclosureExportSuccessEvent {
  destPath: string
  glbPath: string
  stepPath: string
  wallThicknessMm?: number
  clearanceMm?: number
  standoffHeightMm?: number
}

export function EnclosurePanel({
  projectName,
  onExportSuccess,
  menuCommand,
}: {
  projectName: string
  onExportSuccess?: (event: EnclosureExportSuccessEvent) => void
  /** SPEC-316: a Design > Enclosure menu click -- 'open_kicad',
   * 'pick_pcb', and 'generate' are real commands here;
   * `handleSelectBoard` needs a specific candidate a menu click can't
   * supply. */
  menuCommand?: MenuCommand | null
}) {
  const [mode, setMode] = useState<'board' | 'manual'>('board')

  const [loadingList, setLoadingList] = useState(false)
  const [listResult, setListResult] = useState<ListOpenBoardsResult | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [openingKicad, setOpeningKicad] = useState(false)
  const [openKicadError, setOpenKicadError] = useState<string | null>(null)

  const [selectedBoard, setSelectedBoard] = useState<BoardCandidate | null>(null)
  const [manualPcbPath, setManualPcbPath] = useState<string | null>(null)

  const [dims, setDims] = useState({ width: 50, depth: 30, height: 20 })
  /* SPEC-326 §2.7: what the parts on the BOARD actually need. The 20mm
     default above is arbitrary — it was chosen before anything could be
     measured, and it looked derived while being pure coincidence. A default
     replaced by a measurement is not the "recommendation as override" that
     SPEC-326 §2 rules out: a value the user has typed is never overwritten. */
  const [measured, setMeasured] = useState<EnvelopeResult | null>(null)
  const [heightTouched, setHeightTouched] = useState(false)
  const [boardParams, setBoardParams] = useState(_DEFAULT_BOARD_PARAMS)

  // SPEC-311/CTX-311.2: lid is board-driven-mode-only on the daemon
  // side -- kept as its own toggle rather than a boardParams field so
  // switching to Manual mode doesn't need to silently drop it.
  const [lid, setLid] = useState(false)
  const [lidThicknessMm, setLidThicknessMm] = useState<number | ''>('')
  const [lidVisible, setLidVisible] = useState(true)

  const [job, setJob] = useState<JobHandle<EnclosureResult> | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<EnclosureResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // CTX-311.13/CTX-311.14: the real explicit Save/Export action --
  // Generate itself no longer persists anything (see lib/enclosure.ts's
  // own EnclosureResult docstring for the real, confirmed auto-save bug
  // this replaces). Real user feedback on the first click-through:
  // format and parts weren't grouped or ordered logically (parts shown
  // even for FreeCAD, which always ignores it), so `exportOpen` gates a
  // real two-step reveal -- Export opens a real, ordered card (format,
  // then parts *only if the format actually uses it*, then a real
  // choose-location action) instead of showing every control inline in
  // the button row at once. 'body' is the only parts value guaranteed
  // valid on every result -- a lid may not exist yet, and defaulting to
  // 'combined'/'lid' would need an extra effect just to reset itself the
  // moment a no-lid result arrives after a lidded one.
  const [exportOpen, setExportOpen] = useState(false)
  const [exportParts, setExportParts] = useState<ExportParts>('body')
  const [exportFormat, setExportFormat] = useState<ExportFormat>('step')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportedPath, setExportedPath] = useState<string | null>(null)

  // CTX-311.15: the real board-inside-enclosure visual fit check
  // (SPEC-311 §2). `resultBoardParams` freezes the exact pcb_path and
  // geometry values *this* result was actually generated from -- the
  // live `boardParams`/`pcbPath` state above can keep changing (the
  // user editing fields for their *next* attempt) without invalidating
  // an already-shown board overlay. `fromLiveList` gates the component-
  // visibility disclosure below: `kicad.get_component_heights` reads
  // whatever board is live in KiCad right now, not `pcbPath` -- only
  // safe to trust when this result came from `listOpenBoards`'s own
  // live-open list, not a manually-picked file that may not even be
  // open in KiCad at all.
  const [resultBoardParams, setResultBoardParams] = useState<{
    pcbPath: string
    wallThicknessMm: number
    clearanceMm: number
    standoffHeightMm: number
    fromLiveList: boolean
  } | null>(null)
  const [boardGlbPath, setBoardGlbPath] = useState<string | null>(null)
  const [boardVisible, setBoardVisible] = useState(false)
  const [loadingBoardGlb, setLoadingBoardGlb] = useState(false)
  const [boardGlbError, setBoardGlbError] = useState<string | null>(null)
  const [unknownComponentRefs, setUnknownComponentRefs] = useState<string[]>([])

  const running = status === 'running'
  // A manually-picked file always wins once chosen -- it's the user's
  // explicit override of whatever the list auto-selected or offered.
  const pcbPath = manualPcbPath ?? selectedBoard?.path ?? null

  // SPEC-326 §2.7: measure the board's own components and let the height
  // field start from what they need, rather than from an arbitrary 20.
  // Read-only and advisory -- a height the user has typed is never replaced.
  useEffect(() => {
    let cancelled = false
    if (!pcbPath) {
      setMeasured(null)
      return
    }
    void (async () => {
      try {
        const result = await componentEnvelopes(null, pcbPath, {})
        if (cancelled) return
        setMeasured(result)
        if (result.min_interior_height_mm != null) {
          // Only while untouched: replacing a default is help, replacing a
          // decision is an override.
          setBoardParams((prev) =>
            heightTouched ? prev : { ...prev, height: Math.ceil(result.min_interior_height_mm!) },
          )
        }
      } catch {
        // Measurement is advisory. Failing to measure must not block the
        // generator, which worked without any of this before.
        if (!cancelled) setMeasured(null)
      }
    })()
    return () => { cancelled = true }
  }, [pcbPath, heightTouched])

  useEffect(() => {
    setSelectedBoard(null)
    setManualPcbPath(null)
    setResult(null)
    setError(null)
  }, [projectName])

  const refreshList = useCallback(async () => {
    setLoadingList(true)
    setListError(null)
    try {
      // The linked project first -- its board is a fact in a file, readable
      // with KiCad closed. Everything this panel does with a board
      // (`freecad.generate_enclosure`, the envelope measurement) takes an
      // explicit path; only the discovery step ever needed KiCad running.
      const linked = await linkedProjectBoard(projectName)
      const listed: ListOpenBoardsResult = linked
        ? { status: 'boards_found', candidates: [linked] }
        : await listOpenBoards()
      setListResult(listed)
      // Real user feedback: "if we know that a pcb file has been
      // loaded, we should have that as selected." Only when exactly
      // one board is open -- more than one is never guessed.
      if (listed.status === 'boards_found' && listed.candidates.length === 1) {
        setSelectedBoard(listed.candidates[0])
      }
    } catch (err) {
      setListError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingList(false)
    }
  }, [projectName])

  useEffect(() => {
    void refreshList()
  }, [refreshList])

  async function handleOpenKicad() {
    setOpeningKicad(true)
    setOpenKicadError(null)
    try {
      // This panel already knows the board it is building an enclosure for.
      await openKicad(pcbPath)
    } catch (err) {
      setOpenKicadError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningKicad(false)
    }
  }

  async function handlePickPcbFile() {
    // pickPcbFile returning null (the user closed the dialog) is a
    // normal, silent no-op -- not an error state.
    const path = await pickPcbFile()
    if (path) {
      setManualPcbPath(path)
      setSelectedBoard(null)
    }
  }

  function handleSelectBoard(candidate: BoardCandidate) {
    setManualPcbPath(null)
    setSelectedBoard(candidate)
  }

  // SPEC-316: Design > Enclosure menu clicks dispatch to these same
  // three handlers -- no new business logic, just a second entry point.
  useEffect(() => {
    if (menuCommand?.area !== 'enclosure') return
    if (menuCommand.command === 'open_kicad') void handleOpenKicad()
    if (menuCommand.command === 'pick_pcb') void handlePickPcbFile()
    if (menuCommand.command === 'generate') void handleGenerate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuCommand?.nonce])

  async function handleGenerate() {
    setError(null)
    setResult(null)
    setStatus('running')
    // A new generation invalidates any already-shown board overlay --
    // its own real geometry params (wall thickness etc.) may no longer
    // match what's about to be built.
    setResultBoardParams(null)
    setBoardGlbPath(null)
    setBoardVisible(false)
    setBoardGlbError(null)
    setUnknownComponentRefs([])

    const params: EnclosureParams =
      mode === 'manual'
        ? { height: dims.height, width: dims.width, depth: dims.depth }
        : {
            ...boardParams,
            pcb_path: pcbPath ?? undefined,
            lid,
            lid_thickness_mm: lid && lidThicknessMm !== '' ? lidThicknessMm : undefined,
          }

    try {
      const handle = await generateEnclosure(params)
      setJob(handle)
      handle.onUpdate((update) => setStatus(update.status))

      setLidVisible(true)
      const generated = await handle.result
      setResult(generated)
      // SPEC-319 §2.1: `last_results.enclosure` is what the enclosure review
      // and chat agents are given as `enclosure_parameters` -- and it was
      // written ONLY on export, so an enclosure that had been generated but
      // not exported left the agent with nothing but the project intent.
      // Reported as "the enclosure view isn't connected to do anything",
      // which was accurate.
      try {
        await setProjectCheckResult(projectName, 'enclosure', {
          generated_at: new Date().toISOString(),
          mode,
          pcb_path: mode === 'board' ? pcbPath : null,
          height_mm: mode === 'board' ? boardParams.height : dims.height,
          wall_thickness_mm: boardParams.wall_thickness_mm,
          clearance_mm: boardParams.clearance_mm,
          standoff_height_mm: boardParams.standoff_height_mm,
          lid: mode === 'board' ? lid : false,
          // What the parts actually need, so the agent can reason about fit
          // rather than only repeating the numbers back.
          min_interior_height_mm: measured?.min_interior_height_mm ?? null,
          tallest_component: measured?.tallest?.reference ?? null,
          components_without_known_height: measured?.unknown ?? null,
          findings: [],
        })
      } catch {
        // Advisory only: a generated enclosure that could not be recorded is
        // still generated and on screen.
      }
      if (mode === 'board' && pcbPath) {
        setResultBoardParams({
          pcbPath,
          wallThicknessMm: boardParams.wall_thickness_mm,
          clearanceMm: boardParams.clearance_mm,
          standoffHeightMm: boardParams.standoff_height_mm,
          fromLiveList: !manualPcbPath,
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setJob(null)
    }
  }

  async function handleToggleShowBoard(checked: boolean) {
    setBoardVisible(checked)
    if (!checked || boardGlbPath || !resultBoardParams || loadingBoardGlb) return

    setLoadingBoardGlb(true)
    setBoardGlbError(null)
    try {
      const handle = await exportBoardGlb(resultBoardParams.pcbPath)
      const glbResult = await handle.result
      setBoardGlbPath(glbResult.glb_path)

      if (resultBoardParams.fromLiveList) {
        try {
          const heightsHandle = await getComponentHeights()
          const heights = await heightsHandle.result
          setUnknownComponentRefs(heights.unknown)
        } catch {
          // Best-effort disclosure only -- a failure here shouldn't block
          // showing the board itself, and this route reads whatever's
          // live in KiCad, which is a real, separate thing from the
          // board glb export that just succeeded above.
        }
      }
    } catch (err) {
      setBoardGlbError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingBoardGlb(false)
    }
  }

  async function handleCancel() {
    await job?.cancel()
  }

  function handleOpenExport() {
    setExportError(null)
    setExportedPath(null)
    setExportOpen(true)
  }

  function handleCancelExport() {
    setExportOpen(false)
    setExportError(null)
  }

  async function handleConfirmExport() {
    if (!result) return
    setExportError(null)

    // FreeCAD export always ignores `parts` (CTX-311.13's own decision --
    // the whole design, not a per-part document), so the defensive
    // lid-existence check below only applies to the formats where a
    // part choice is real.
    if (exportFormat !== 'fcstd' && exportParts !== 'body' && !result.lid_step_path) {
      // Defensive -- the parts <select>'s own disabled options already
      // prevent choosing this combination, but a result without a lid
      // can arrive *after* 'combined'/'lid' was already selected for a
      // previous, lidded result, and the <select>'s own value doesn't
      // reset itself.
      setExportError('No lid was generated for this enclosure.')
      return
    }

    let defaultPath: string | undefined
    try {
      const dir = await getProjectDirectory(projectName)
      const extension = exportFormat === 'fcstd' ? 'FCStd' : exportFormat
      const nameStem = exportFormat === 'fcstd' ? 'enclosure' : exportParts
      defaultPath = _joinPath(dir, `${nameStem}.${extension}`)
    } catch {
      // A real default is a convenience, not a requirement -- the save
      // dialog still works fine with no default path at all.
    }

    const destPath = await pickExportDestination(exportFormat, defaultPath)
    if (!destPath) return

    setExporting(true)
    try {
      const handle = await exportEnclosure({
        parts: exportParts,
        fmt: exportFormat,
        dest_path: destPath,
        glb_path: result.glb_path,
        step_path: result.step_path,
        lid_glb_path: result.lid_glb_path,
        lid_step_path: result.lid_step_path,
      })
      await handle.result
      setExportOpen(false)
      setExportedPath(destPath)
      onExportSuccess?.({
        destPath,
        glbPath: result.glb_path,
        stepPath: result.step_path,
        wallThicknessMm: resultBoardParams?.wallThicknessMm,
        clearanceMm: resultBoardParams?.clearanceMm,
        standoffHeightMm: resultBoardParams?.standoffHeightMm,
      })
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err))
    } finally {
      setExporting(false)
    }
  }

  return (
    // SPEC-311 §2: the Enclosure area specifically gets an even wider
    // layout than every other tab's own max-w-4xl (CTX-305.2) -- a large
    // 3D preview is a real, direct benefit of the extra room beyond what
    // a plain text/list column needs.
    <div className="flex w-full max-w-6xl flex-col gap-4">
    <div className="flex w-full flex-col gap-4 lg:flex-row lg:items-start">
      {/* CTX-305.3: the two-column split (a fixed-width sidebar next to a
       * flex-1 viewer column) only makes sense once there's a real result
       * to show on the right -- the viewer column below is now entirely
       * absent from the DOM until `result` exists, so this sidebar only
       * takes the narrow `lg:w-96` treatment when it actually has
       * something to share the row with. Before that, it's the row's only
       * child and naturally uses the full width, matching the below-`lg`
       * stacked layout instead of pre-reserving empty space for content
       * that doesn't exist yet. */}
      <div className={`flex w-full flex-col gap-2 ${result ? 'lg:w-96 lg:flex-none' : ''}`}>
        <div className="flex gap-2">
          <button
            type="button"
            className={`rounded px-3 py-1 text-sm ${
              mode === 'board' ? 'bg-surface-alt text-fg' : 'text-fg-tertiary hover:bg-surface'
            }`}
            onClick={() => setMode('board')}
            disabled={running}
          >
            Board
          </button>
          <button
            type="button"
            className={`rounded px-3 py-1 text-sm ${
              mode === 'manual' ? 'bg-surface-alt text-fg' : 'text-fg-tertiary hover:bg-surface'
            }`}
            onClick={() => setMode('manual')}
            disabled={running}
          >
            Manual (no PCB)
          </button>
        </div>

        {mode === 'board' && (
          <BoardPickerSection
            loadingList={loadingList}
            listResult={listResult}
            listError={listError}
            onRefreshList={() => void refreshList()}
            onOpenKicad={() => void handleOpenKicad()}
            openingKicad={openingKicad}
            openKicadError={openKicadError}
            selectedBoard={selectedBoard}
            manualPcbPath={manualPcbPath}
            onSelectBoard={handleSelectBoard}
            onPickManually={() => void handlePickPcbFile()}
            running={running}
          />
        )}

        {mode === 'board' && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-fg-muted">
              Enclosures are generated as a rectangular box sized to your board's bounding box --
              non-rectangular board outlines aren't traced precisely yet.
            </p>
            {(
              [
                ['height', 'Height (mm)', 'How tall the enclosure is inside, above the board.', true],
                ['wall_thickness_mm', 'Wall thickness (mm)', 'How thick the outer walls are.', false],
                ['clearance_mm', 'Clearance (mm)', "Extra gap between the board's edge and the inside wall.", false],
                ['fillet_radius_mm', 'Fillet radius (mm)', "Rounds the enclosure's outer corners -- 0 for sharp corners.", false],
                ['standoff_height_mm', 'Standoff height (mm)', 'How tall the mounting posts are that hold the board above the enclosure floor.', false],
              ] as const
            ).map(([field, label, hint, required]) => (
              <label key={field} className="flex flex-col gap-1 text-xs">
                <span className="text-fg-secondary">
                  {label} {required ? <span className="text-fg-muted">(required)</span> : <span className="text-fg-muted">(optional)</span>}
                </span>
                <input
                  type="number"
                  className="w-full rounded border border-line bg-surface px-3 py-2 text-sm"
                  value={boardParams[field]}
                  onChange={(e) => {
                    if (field === 'height') setHeightTouched(true)
                    setBoardParams((prev) => ({ ...prev, [field]: Number(e.target.value) }))
                  }}
                  disabled={running}
                />
                <span className="text-fg-muted">{hint}</span>
                {/* Deliberately NOT styled like the grey hint above it. This
                    is the only number on the panel derived from the user's own
                    board, and as a third muted line it read as boilerplate --
                    reported directly: "it blends into what labels look like". */}
                {field === 'height' && measured?.min_interior_height_mm != null && (
                  <div
                    className={`mt-1 flex items-start gap-2 rounded border px-2 py-1.5 ${
                      boardParams.height < measured.min_interior_height_mm
                        ? 'border-warning/50 bg-warning/10'
                        : 'border-accent/40 bg-accent/5'
                    }`}
                  >
                    <span
                      aria-hidden
                      className={
                        boardParams.height < measured.min_interior_height_mm
                          ? 'text-warning'
                          : 'text-accent'
                      }
                    >
                      {boardParams.height < measured.min_interior_height_mm ? '⚠' : '↳'}
                    </span>
                    <span className="flex flex-col gap-0.5">
                      <span
                        className={`font-medium ${
                          boardParams.height < measured.min_interior_height_mm
                            ? 'text-warning'
                            : 'text-fg-bright'
                        }`}
                      >
                        {boardParams.height < measured.min_interior_height_mm
                          ? `Too short — your board needs ${measured.min_interior_height_mm}mm`
                          : `Measured from your board: ${measured.min_interior_height_mm}mm needed`}
                        {measured.tallest ? `, set by ${measured.tallest.reference}` : ''}
                      </span>
                      {measured.unknown > 0 && (
                        <span className="text-fg-tertiary">
                          {measured.unknown} component{measured.unknown === 1 ? '' : 's'} still have
                          no known height, so the real minimum may be taller.
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </label>
            ))}

            <label className="flex items-center gap-2 text-xs text-fg-secondary">
              <input
                type="checkbox"
                checked={lid}
                onChange={(e) => setLid(e.target.checked)}
                disabled={running}
              />
              Add a lid
            </label>
            {lid && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-fg-secondary">
                  Lid thickness (mm) <span className="text-fg-muted">(optional -- defaults to wall thickness)</span>
                </span>
                <input
                  type="number"
                  className="w-full rounded border border-line bg-surface px-3 py-2 text-sm"
                  value={lidThicknessMm}
                  onChange={(e) => setLidThicknessMm(e.target.value === '' ? '' : Number(e.target.value))}
                  disabled={running}
                />
              </label>
            )}
          </div>
        )}

        {mode === 'manual' && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-fg-muted">
              A plain rectangular box, not based on any real board -- use Board above when you have a
              .kicad_pcb file available.
            </p>
            {(
              [
                ['width', 'Width (mm)'],
                ['depth', 'Depth (mm)'],
                ['height', 'Height (mm)'],
              ] as const
            ).map(([dim, label]) => (
              <label key={dim} className="flex flex-col gap-1 text-xs">
                <span className="text-fg-secondary">{label} <span className="text-fg-muted">(required)</span></span>
                <input
                  type="number"
                  className="w-full rounded border border-line bg-surface px-3 py-2 text-sm"
                  value={dims[dim]}
                  onChange={(e) => setDims((prev) => ({ ...prev, [dim]: Number(e.target.value) }))}
                  disabled={running}
                />
              </label>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            className="flex-1 rounded bg-accent px-4 py-2 text-sm font-medium text-accent-fg disabled:opacity-50"
            onClick={() => void handleGenerate()}
            disabled={running || (mode === 'board' && !pcbPath)}
          >
            {running ? 'Generating…' : 'Generate Enclosure'}
          </button>
          {running && (
            <button
              type="button"
              className="rounded border border-line px-4 py-2 text-sm font-medium disabled:opacity-50"
              onClick={() => void handleCancel()}
            >
              Cancel
            </button>
          )}
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>

      {result && (
        <div className="flex w-full flex-1 flex-col gap-2">
          {result.unrecognized_holes.length > 0 && (
            <p className="text-sm text-warning">
              {result.unrecognized_holes.length} hole(s) on this board weren't recognized as mounting
              holes and were skipped -- no standoff was drilled for them.
            </p>
          )}
          {result.no_mounting_holes_found && (
            <p className="text-sm text-warning">
              No mounting holes were found on this board -- the enclosure has no standoffs. If this
              board really does have mounting holes, confirm they're real NPTH pads in KiCad.
            </p>
          )}
          <>
            <EnclosureViewer
              glbPath={result.glb_path}
              lidGlbPath={result.lid_glb_path ?? null}
              lidVisible={lidVisible}
              onLidVisibleChange={setLidVisible}
              boardGlbPath={boardGlbPath}
              boardVisible={boardVisible}
              boardOffsetMm={
                resultBoardParams
                  ? {
                      margin: resultBoardParams.wallThicknessMm + resultBoardParams.clearanceMm,
                      floorAndStandoff:
                        resultBoardParams.wallThicknessMm + resultBoardParams.standoffHeightMm,
                    }
                  : null
              }
            />
            {resultBoardParams && (
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-xs text-fg-secondary">
                  <input
                    type="checkbox"
                    checked={boardVisible}
                    onChange={(e) => void handleToggleShowBoard(e.target.checked)}
                    disabled={loadingBoardGlb}
                  />
                  {loadingBoardGlb ? 'Loading board…' : 'Show board (visual fit check)'}
                </label>
                {boardGlbError && <p className="text-xs text-danger">{boardGlbError}</p>}
              </div>
            )}
            {boardVisible && unknownComponentRefs.length > 0 && (
              <p className="text-xs text-warning">
                {unknownComponentRefs.join(', ')} {unknownComponentRefs.length === 1 ? 'has' : 'have'} no
                3D model in KiCad and won't appear above. Often there is nothing to fix -- KiCad's own
                Battery library, for instance, ships 53 footprints against 29 models. Set a height for
                them in the Schematic tab and this enclosure can still be sized to clear them.
              </p>
            )}
            {!exportOpen && (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  className="self-start rounded border border-line px-3 py-1 text-xs font-medium text-fg-bright hover:bg-surface-alt"
                  onClick={handleOpenExport}
                >
                  Export…
                </button>
                {exportedPath && (
                  <p className="truncate text-xs text-fg-tertiary">Exported to {exportedPath}</p>
                )}
              </div>
            )}
            {exportOpen && (
              <div className="flex flex-col gap-2 rounded border border-line bg-surface p-3 text-sm">
                <label className="flex flex-col gap-1 text-xs">
                  <span className="text-fg-secondary">Format</span>
                  <select
                    aria-label="Export format"
                    className="rounded border border-line bg-surface px-2 py-1 text-xs text-fg-bright"
                    value={exportFormat}
                    onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                    disabled={exporting}
                  >
                    <option value="step">STEP</option>
                    <option value="stl">STL</option>
                    <option value="glb">GLB</option>
                    <option value="fcstd">FreeCAD (.FCStd)</option>
                  </select>
                </label>
                {exportFormat === 'fcstd' ? (
                  <p className="text-xs text-fg-muted">
                    FreeCAD export always includes the whole design -- body and lid together, when a
                    lid was generated.
                  </p>
                ) : (
                  <label className="flex flex-col gap-1 text-xs">
                    <span className="text-fg-secondary">Parts</span>
                    <select
                      aria-label="Export parts"
                      className="rounded border border-line bg-surface px-2 py-1 text-xs text-fg-bright"
                      value={exportParts}
                      onChange={(e) => setExportParts(e.target.value as ExportParts)}
                      disabled={exporting}
                    >
                      <option value="combined" disabled={!result.lid_step_path}>Combined (body + lid)</option>
                      <option value="body">Body only</option>
                      <option value="lid" disabled={!result.lid_step_path}>Lid only</option>
                    </select>
                  </label>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
                    onClick={() => void handleConfirmExport()}
                    disabled={exporting}
                  >
                    {exporting ? 'Exporting…' : 'Choose location…'}
                  </button>
                  <button
                    type="button"
                    className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright disabled:opacity-50"
                    onClick={handleCancelExport}
                    disabled={exporting}
                  >
                    Close
                  </button>
                </div>
                {exportError && <p className="text-xs text-danger">{exportError}</p>}
              </div>
            )}
          </>
        </div>
      )}
    </div>
    {/* SPEC-331: back on. It was switched off on 2026-09-02 because its one
        data tool needed KiCad running, so with KiCad closed it advised from
        nothing. It now receives a `fit` block measured from the board's own
        footprints per request -- better data than that tool ever had, and
        never stale. */}
    <ReviewPanel
      area="enclosure"
      scope="project"
      scopeId={`${projectName}:enclosure`}
      title="Review the enclosure"
      projectName={projectName}
      menuCommand={menuCommand}
    />
    {/* SPEC-318 §5: "a collapsible chat panel at the foot of each area."
        A project-scoped chat has no single Part to offer as a promotion
        target -- "this project" is the only real target here. */}
    <AgentChat
      area="enclosure"
      scope="project"
      scopeId={`${projectName}:enclosure`}
      title="Ask about the enclosure"
      projectName={projectName}
      promotionTargets={[{ label: 'this project', scope: 'project', id: projectName }]}
    />
    </div>
  )
}

function BoardPickerSection({
  loadingList,
  listResult,
  listError,
  onRefreshList,
  onOpenKicad,
  openingKicad,
  openKicadError,
  selectedBoard,
  manualPcbPath,
  onSelectBoard,
  onPickManually,
  running,
}: {
  loadingList: boolean
  listResult: ListOpenBoardsResult | null
  listError: string | null
  onRefreshList: () => void
  onOpenKicad: () => void
  openingKicad: boolean
  openKicadError: string | null
  selectedBoard: BoardCandidate | null
  manualPcbPath: string | null
  onSelectBoard: (candidate: BoardCandidate) => void
  onPickManually: () => void
  running: boolean
}) {
  const showGuidance = !loadingList && (listError !== null || listResult?.status === 'no_board_open')

  return (
    <div className="flex flex-col gap-2 rounded border border-line-subtle bg-surface p-3 text-sm">
      <p className="text-xs text-fg-muted">
        Already checked your board on the PCB tab? Use the same file here.
      </p>

      {loadingList && <p className="text-fg-tertiary">Scanning for boards open in KiCad…</p>}

      {showGuidance && (
        <div className="flex flex-col gap-2">
          <p className="text-fg-bright">
            {listError ? "KiCad doesn't appear to be running yet." : 'No board is currently open in KiCad.'}
          </p>
          {openKicadError && <p className="text-xs text-danger">{openKicadError}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Opening…' : 'Open KiCad'}
            </button>
            <button type="button" className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright" onClick={onRefreshList}>
              Refresh
            </button>
            <button
              type="button"
              className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
              onClick={onPickManually}
              disabled={running}
            >
              Choose a .kicad_pcb file…
            </button>
          </div>
        </div>
      )}

      {!loadingList && !showGuidance && listResult?.status === 'boards_found' && (
        <div className="flex flex-col gap-2">
          <p className="text-fg-bright">
            {listResult.candidates.length === 1 ? 'Board open in KiCad:' : 'Boards open in KiCad — pick one:'}
          </p>
          <ul className="flex flex-col gap-1">
            {listResult.candidates.map((candidate) => {
              const isSelected = !manualPcbPath && selectedBoard?.path === candidate.path
              return (
                <li key={candidate.path}>
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    className={`w-full rounded border px-3 py-2 text-left text-xs disabled:opacity-50 ${
                      isSelected
                        ? 'border-fg bg-surface-alt text-fg'
                        : 'border-line text-fg-bright hover:bg-surface-alt'
                    }`}
                    onClick={() => onSelectBoard(candidate)}
                    disabled={running}
                  >
                    <span className="block font-medium">{candidate.label}</span>
                    <span className="block break-all text-fg-muted">{candidate.path}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          {openKicadError && <p className="text-xs text-danger">{openKicadError}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright disabled:opacity-50"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Switching…' : 'Switch to KiCad'}
            </button>
            <button type="button" className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright" onClick={onRefreshList}>
              Refresh
            </button>
            <button
              type="button"
              className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright disabled:opacity-50"
              onClick={onPickManually}
              disabled={running}
            >
              Choose a different file…
            </button>
          </div>
        </div>
      )}

      {manualPcbPath && (
        <p className="truncate text-xs text-fg-tertiary">Manually picked: {manualPcbPath}</p>
      )}
    </div>
  )
}
