import { useCallback, useEffect, useState } from 'react'
import { open } from '@tauri-apps/plugin-shell'
import { type JobHandle } from '../lib/ipc'
import { generateEnclosure, pickPcbFile, type EnclosureParams, type EnclosureResult } from '../lib/enclosure'
import { listOpenBoards, openKicad, type BoardCandidate, type ListOpenBoardsResult } from '../lib/boardAdvisor'
import { EnclosureViewer } from './EnclosureViewer'

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
export function EnclosurePanel({ projectName }: { projectName: string }) {
  const [mode, setMode] = useState<'board' | 'manual'>('board')

  const [loadingList, setLoadingList] = useState(false)
  const [listResult, setListResult] = useState<ListOpenBoardsResult | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [openingKicad, setOpeningKicad] = useState(false)
  const [openKicadError, setOpenKicadError] = useState<string | null>(null)

  const [selectedBoard, setSelectedBoard] = useState<BoardCandidate | null>(null)
  const [manualPcbPath, setManualPcbPath] = useState<string | null>(null)

  const [dims, setDims] = useState({ width: 50, depth: 30, height: 20 })
  const [boardParams, setBoardParams] = useState(_DEFAULT_BOARD_PARAMS)

  const [job, setJob] = useState<JobHandle<EnclosureResult> | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<EnclosureResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const running = status === 'running'
  // A manually-picked file always wins once chosen -- it's the user's
  // explicit override of whatever the list auto-selected or offered.
  const pcbPath = manualPcbPath ?? selectedBoard?.path ?? null

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
      const listed = await listOpenBoards()
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
  }, [])

  useEffect(() => {
    void refreshList()
  }, [refreshList])

  async function handleOpenKicad() {
    setOpeningKicad(true)
    setOpenKicadError(null)
    try {
      await openKicad()
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

  async function handleGenerate() {
    setError(null)
    setResult(null)
    setStatus('running')

    const params: EnclosureParams =
      mode === 'manual'
        ? { height: dims.height, width: dims.width, depth: dims.depth, project_name: projectName }
        : { ...boardParams, pcb_path: pcbPath ?? undefined, project_name: projectName }

    try {
      const handle = await generateEnclosure(params)
      setJob(handle)
      handle.onUpdate((update) => setStatus(update.status))

      setResult(await handle.result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setJob(null)
    }
  }

  async function handleCancel() {
    await job?.cancel()
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-2">
      <div className="flex gap-2">
        <button
          type="button"
          className={`rounded px-3 py-1 text-sm ${
            mode === 'board' ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:bg-neutral-900'
          }`}
          onClick={() => setMode('board')}
          disabled={running}
        >
          Board
        </button>
        <button
          type="button"
          className={`rounded px-3 py-1 text-sm ${
            mode === 'manual' ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:bg-neutral-900'
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
          <p className="text-xs text-neutral-500">
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
              <span className="text-neutral-300">
                {label} {required ? <span className="text-neutral-500">(required)</span> : <span className="text-neutral-500">(optional)</span>}
              </span>
              <input
                type="number"
                className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
                value={boardParams[field]}
                onChange={(e) => setBoardParams((prev) => ({ ...prev, [field]: Number(e.target.value) }))}
                disabled={running}
              />
              <span className="text-neutral-500">{hint}</span>
            </label>
          ))}
        </div>
      )}

      {mode === 'manual' && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-neutral-500">
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
              <span className="text-neutral-300">{label} <span className="text-neutral-500">(required)</span></span>
              <input
                type="number"
                className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
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
          className="flex-1 rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
          onClick={() => void handleGenerate()}
          disabled={running || (mode === 'board' && !pcbPath)}
        >
          {running ? 'Generating…' : 'Generate Enclosure'}
        </button>
        {running && (
          <button
            type="button"
            className="rounded border border-neutral-700 px-4 py-2 text-sm font-medium disabled:opacity-50"
            onClick={() => void handleCancel()}
          >
            Cancel
          </button>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {result && result.unrecognized_holes.length > 0 && (
        <p className="text-sm text-amber-400">
          {result.unrecognized_holes.length} hole(s) on this board weren't recognized as mounting
          holes and were skipped -- no standoff was drilled for them.
        </p>
      )}
      {result && (
        <>
          <p className="text-sm text-neutral-400">Generated: {result.glb_path}</p>
          <EnclosureViewer glbPath={result.glb_path} />
          <button
            type="button"
            className="self-start rounded border border-neutral-700 px-2 py-0.5 text-xs"
            onClick={() => open(result.step_path)}
          >
            Open .step
          </button>
        </>
      )}
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
    <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
      <p className="text-xs text-neutral-500">
        Already checked your board on the PCB tab? Use the same file here.
      </p>

      {loadingList && <p className="text-neutral-400">Scanning for boards open in KiCad…</p>}

      {showGuidance && (
        <div className="flex flex-col gap-2">
          <p className="text-neutral-200">
            {listError ? "KiCad doesn't appear to be running yet." : 'No board is currently open in KiCad.'}
          </p>
          {openKicadError && <p className="text-xs text-red-400">{openKicadError}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-950 disabled:opacity-50"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Opening…' : 'Open KiCad'}
            </button>
            <button type="button" className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200" onClick={onRefreshList}>
              Refresh
            </button>
            <button
              type="button"
              className="rounded bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-950 disabled:opacity-50"
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
          <p className="text-neutral-200">
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
                        ? 'border-neutral-100 bg-neutral-800 text-neutral-100'
                        : 'border-neutral-700 text-neutral-200 hover:bg-neutral-800'
                    }`}
                    onClick={() => onSelectBoard(candidate)}
                    disabled={running}
                  >
                    <span className="block font-medium">{candidate.label}</span>
                    <span className="block break-all text-neutral-500">{candidate.path}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          {openKicadError && <p className="text-xs text-red-400">{openKicadError}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200 disabled:opacity-50"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Switching…' : 'Switch to KiCad'}
            </button>
            <button type="button" className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200" onClick={onRefreshList}>
              Refresh
            </button>
            <button
              type="button"
              className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200 disabled:opacity-50"
              onClick={onPickManually}
              disabled={running}
            >
              Choose a different file…
            </button>
          </div>
        </div>
      )}

      {manualPcbPath && (
        <p className="truncate text-xs text-neutral-400">Manually picked: {manualPcbPath}</p>
      )}
    </div>
  )
}
