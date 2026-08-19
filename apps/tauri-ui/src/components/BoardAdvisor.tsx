import { useCallback, useEffect, useState } from 'react'
import {
  checkBoard,
  listOpenBoards,
  openKicad,
  type BoardCandidate,
  type CheckResult,
  type ListOpenBoardsResult,
} from '../lib/boardAdvisor'
import { ViolationsList } from './ViolationsList'

/** SPEC-309: real DRC via kicad-cli (CTX-309.1), explained in plain
 * language. Lives in the PCB area (App.tsx) -- the Schematic (ERC)
 * side of SPEC-309 moved to its own SchematicAdvisor component, in the
 * Schematic area, per SPEC-300's own original stage-machine design
 * (real user feedback flagged the PCB/Schematic split as wrong when
 * both checks briefly lived here together).
 *
 * CTX-309.4: scans for open boards as soon as this screen mounts and
 * always shows them as a real, clickable list -- even a single one --
 * rather than a blind "Check Board" button that silently auto-resolved
 * whichever board happened to be open (CTX-309.3). Real user feedback
 * exercising the actual running app found that still too opaque for
 * someone new to KiCad: it never showed *which* board was about to be
 * checked, and offered no way to actually open KiCad from here. Zero
 * boards open now offers a real "Open KiCad" action plus a concrete
 * walkthrough, not just prose. A second real click-through found three
 * more gaps this fixes too: "couldn't reach KiCad" rendered as an
 * alarming red error on someone's very first visit to this tab, before
 * they'd had any reason to open KiCad yet; picking a board from a
 * multi-board list gave no way to open a *different* one without
 * leaving the app; and a long file path overflowed its own box instead
 * of wrapping.
 *
 * This component stays mounted across every area tab, not just while
 * "PCB" is selected (App.tsx hides it with CSS instead of unmounting
 * it) -- real feedback found switching tabs away and back threw out a
 * check that had just finished, with no reason to. `projectName` is
 * only used to know when to actually reset that state: a genuine
 * project switch, not a tab switch. */
export function BoardAdvisor({ projectName }: { projectName: string }) {
  const [loadingBoardList, setLoadingBoardList] = useState(false)
  const [boardListResult, setBoardListResult] = useState<ListOpenBoardsResult | null>(null)
  const [boardListError, setBoardListError] = useState<string | null>(null)
  const [openingKicad, setOpeningKicad] = useState(false)
  const [openKicadError, setOpenKicadError] = useState<string | null>(null)

  const [checkingBoard, setCheckingBoard] = useState(false)
  const [selectedBoard, setSelectedBoard] = useState<BoardCandidate | null>(null)
  const [boardCheckResult, setBoardCheckResult] = useState<CheckResult | null>(null)
  const [boardCheckError, setBoardCheckError] = useState<string | null>(null)

  // A genuine project switch starts fresh -- unlike a tab switch (this
  // component stays mounted for those), the previously-checked board
  // belongs to whichever project it was checked under, not this new
  // one. The board list itself is left alone: which boards KiCad has
  // open is real desktop state, not scoped to this app's own project.
  useEffect(() => {
    setSelectedBoard(null)
    setBoardCheckResult(null)
    setBoardCheckError(null)
  }, [projectName])

  const refreshBoardList = useCallback(async () => {
    setLoadingBoardList(true)
    setBoardListError(null)
    try {
      setBoardListResult(await listOpenBoards())
    } catch (err) {
      setBoardListError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingBoardList(false)
    }
  }, [])

  // Scan for open boards as soon as this screen is shown, instead of
  // waiting for a blind first click -- the user sees real state
  // immediately.
  useEffect(() => {
    void refreshBoardList()
  }, [refreshBoardList])

  async function handleOpenKicad() {
    setOpeningKicad(true)
    setOpenKicadError(null)
    try {
      await openKicad()
    } catch (err) {
      // Deliberately its own state, not folded into boardListError: a
      // failed *launch* (e.g. KiCad isn't installed where expected) is a
      // real, different, actionable problem from "KiCad just isn't
      // running yet" -- it must stay visible, not get swallowed into the
      // calm not-running-yet copy below.
      setOpenKicadError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningKicad(false)
    }
  }

  async function handleCheckBoard(candidate: BoardCandidate) {
    setSelectedBoard(candidate)
    setCheckingBoard(true)
    setBoardCheckError(null)
    setBoardCheckResult(null)
    try {
      setBoardCheckResult(await checkBoard(candidate.path))
    } catch (err) {
      setBoardCheckError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingBoard(false)
    }
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-6">
      <BoardCheckSection
        loadingList={loadingBoardList}
        listResult={boardListResult}
        listError={boardListError}
        onRefreshList={() => void refreshBoardList()}
        onOpenKicad={() => void handleOpenKicad()}
        openingKicad={openingKicad}
        openKicadError={openKicadError}
        selectedBoard={selectedBoard}
        checkingBoard={checkingBoard}
        checkResult={boardCheckResult}
        checkError={boardCheckError}
        onCheckBoard={(candidate) => void handleCheckBoard(candidate)}
      />
    </div>
  )
}

/** CTX-309.4: the Board (DRC) section. */
function BoardCheckSection({
  loadingList,
  listResult,
  listError,
  onRefreshList,
  onOpenKicad,
  openingKicad,
  openKicadError,
  selectedBoard,
  checkingBoard,
  checkResult,
  checkError,
  onCheckBoard,
}: {
  loadingList: boolean
  listResult: ListOpenBoardsResult | null
  listError: string | null
  onRefreshList: () => void
  onOpenKicad: () => void
  openingKicad: boolean
  openKicadError: string | null
  selectedBoard: BoardCandidate | null
  checkingBoard: boolean
  checkResult: CheckResult | null
  checkError: string | null
  onCheckBoard: (candidate: BoardCandidate) => void
}) {
  // CTX-309.4 second revision: real clicking-through found the first cut
  // still showing "could not connect" in alarming red on the very first
  // visit to this tab -- before the user had any reason to have opened
  // KiCad yet. From here, "couldn't reach KiCad" and "reached KiCad but
  // nothing's open" are the same actionable state for the user (go open
  // a board), so both render through this one calm, neutral guidance
  // card rather than one of them looking like a failure.
  const showGuidance = !loadingList && (listError !== null || listResult?.status === 'no_board_open')

  return (
    <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
      <p className="text-xs font-medium uppercase text-neutral-500">Board (DRC)</p>

      {loadingList && <p className="text-sm text-neutral-400">Scanning for boards open in KiCad…</p>}

      {showGuidance && (
        <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
          <p className="text-neutral-200">
            {listError ? "KiCad doesn't appear to be running yet." : 'No board is currently open in KiCad.'}
          </p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-neutral-400">
            <li>Click <strong className="text-neutral-300">Open KiCad</strong> below (or open it yourself).</li>
            <li>
              Open your project, then open its <strong className="text-neutral-300">PCB Editor</strong> window
              (not just the project manager).
            </li>
            <li>
              Confirm the IPC API is enabled: <strong className="text-neutral-300">Preferences → Plugins</strong>.
            </li>
            <li>Click <strong className="text-neutral-300">Refresh</strong> below -- this app doesn't know when
              KiCad opens or closes a board on its own.</li>
          </ol>
          {openKicadError && <p className="text-xs text-red-400">{openKicadError}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-950 disabled:opacity-50"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Opening…' : 'Open KiCad'}
            </button>
            <button
              type="button"
              className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
              onClick={onRefreshList}
            >
              Refresh
            </button>
          </div>
        </div>
      )}

      {!loadingList && !showGuidance && listResult?.status === 'boards_found' && (
        <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
          <p className="text-neutral-200">
            {listResult.candidates.length === 1
              ? 'Board open in KiCad:'
              : 'Boards open in KiCad — pick one to check:'}
          </p>
          <ul className="flex flex-col gap-1">
            {listResult.candidates.map((candidate) => {
              const isSelected = selectedBoard?.path === candidate.path
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
                    onClick={() => onCheckBoard(candidate)}
                    disabled={checkingBoard}
                  >
                    <span className="block font-medium">{candidate.label}</span>
                    <span className="block break-all text-neutral-500">{candidate.path}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          <p className="text-xs text-neutral-500">
            Don't see the board you want? Switch to KiCad and open it there, then click Refresh.
          </p>
          {openKicadError && <p className="text-xs text-red-400">{openKicadError}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Switching…' : 'Switch to KiCad'}
            </button>
            <button
              type="button"
              className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
              onClick={onRefreshList}
            >
              Refresh
            </button>
          </div>
        </div>
      )}

      {checkingBoard && (
        <p className="text-sm text-neutral-400">
          Running DRC checks on {selectedBoard?.label ?? 'the selected board'}… this can take a few seconds.
        </p>
      )}
      {checkError && <p className="text-sm text-red-400">{checkError}</p>}
      {checkResult && <ViolationsList result={checkResult} hideSourcePath />}
    </div>
  )
}
