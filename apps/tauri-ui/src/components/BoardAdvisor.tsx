import { useCallback, useEffect, useState } from 'react'
import type { MenuCommand } from '../lib/areas'
import {
  checkBoard,
  checkResultForProject,
  listOpenBoards,
  openKicad,
  type BoardCandidate,
  type CheckResult,
  type ListOpenBoardsResult,
} from '../lib/boardAdvisor'
import { AgentChat } from './AgentChat'
import { ReviewPanel } from './ReviewPanel'
import { ViolationsList } from './ViolationsList'
import { linkedProjectBoard } from '../lib/kicadProject'
import { setProjectCheckResult } from '../lib/projects'

/** The one board's path, when there is exactly one. More than one is never
 *  guessed -- opening the wrong board is worse than opening none. */
function soleCandidatePath(result: ListOpenBoardsResult | null): string | null {
  return result?.status === 'boards_found' && result.candidates.length === 1
    ? result.candidates[0].path
    : null
}

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
export function BoardAdvisor({
  projectName,
  menuCommand,
}: {
  projectName: string
  /** SPEC-316: a Design > PCB menu click -- only 'open_kicad' is a real
   * command here today; `handleCheckBoard` needs a specific candidate a
   * menu click can't supply, and this component has no manual-pick
   * equivalent yet. */
  menuCommand?: MenuCommand | null
}) {
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
      // The linked project first: its board is a fact in a file, knowable
      // with KiCad closed. Asking KiCad's IPC needs KiCad running with the
      // right document focused -- three preconditions the Schematic tab
      // stopped requiring at SPEC-325, and that this tab kept demanding even
      // though `kicad.check_board` only ever wanted a path.
      const linked = await linkedProjectBoard(projectName)
      if (linked) {
        setBoardListResult({ status: 'boards_found', candidates: [linked] })
        return
      }
      setBoardListResult(await listOpenBoards())
    } catch (err) {
      setBoardListError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingBoardList(false)
    }
  }, [projectName])

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
      // Open the board itself when we know which one -- the selected board,
      // or the project's single linked one. A bare KiCad window makes the
      // user go find a file the app is already holding the path to.
      await openKicad(selectedBoard?.path ?? soleCandidatePath(boardListResult))
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
      const result = await checkBoard(candidate.path)
      setBoardCheckResult(result)
      // SPEC-319 §2.1's prerequisite: persist it so the review and chat
      // agents can actually see it. Held only in React state before, which
      // is why the PCB review was told "No DRC check result is available
      // this session" on a board with real errors -- it has no tool to run
      // DRC itself, so it had nothing to review.
      try {
        await setProjectCheckResult(projectName, 'pcb', checkResultForProject(result, 'pcb'))
      } catch (persistErr) {
        // The check itself succeeded and is on screen. Failing to record it
        // degrades the review, not this result -- never swallow it silently
        // though, since a review that then finds nothing looks like a clean
        // board rather than a missing record.
        setBoardCheckError(
          `Checked, but could not save the result for review: ${
            persistErr instanceof Error ? persistErr.message : String(persistErr)
          }`,
        )
      }
    } catch (err) {
      setBoardCheckError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingBoard(false)
    }
  }

  // SPEC-316: Design > PCB menu clicks dispatch to this same handler --
  // no new business logic, just a second entry point.
  useEffect(() => {
    if (menuCommand?.area !== 'pcb') return
    if (menuCommand.command === 'open_kicad') void handleOpenKicad()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuCommand?.nonce])

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
      {/* SPEC-319 §2.4: a sibling action, not inside AgentChat -- a review
          is a flow step with a typed result, not a conversational turn. */}
      <ReviewPanel
        area="pcb"
        scope="project"
        scopeId={`${projectName}:pcb`}
        title="Review the board"
        projectName={projectName}
        menuCommand={menuCommand}
      />
      {/* SPEC-318 §5: "a collapsible chat panel at the foot of each area."
          A project-scoped chat has no single Part to offer as a promotion
          target -- "this project" is the only real target here. */}
      <AgentChat
        area="pcb"
        scope="project"
        scopeId={`${projectName}:pcb`}
        title="Ask about the board"
        projectName={projectName}
        promotionTargets={[{ label: 'this project', scope: 'project', id: projectName }]}
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
    <div className="flex flex-col gap-2 rounded border border-line p-3">
      <p className="text-xs font-medium uppercase text-fg-muted">Board (DRC)</p>

      {loadingList && <p className="text-sm text-fg-tertiary">Scanning for boards open in KiCad…</p>}

      {showGuidance && (
        <div className="flex flex-col gap-2 rounded border border-line-subtle bg-surface p-3 text-sm">
          <p className="text-fg-bright">
            {listError ? "KiCad doesn't appear to be running yet." : 'No board is currently open in KiCad.'}
          </p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-fg-tertiary">
            <li>Click <strong className="text-fg-secondary">Open KiCad</strong> below (or open it yourself).</li>
            <li>
              Open your project, then open its <strong className="text-fg-secondary">PCB Editor</strong> window
              (not just the project manager).
            </li>
            <li>
              Confirm the IPC API is enabled: <strong className="text-fg-secondary">Preferences → Plugins</strong>.
            </li>
            <li>Click <strong className="text-fg-secondary">Refresh</strong> below -- this app doesn't know when
              KiCad opens or closes a board on its own.</li>
          </ol>
          {openKicadError && <p className="text-xs text-danger">{openKicadError}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Opening…' : 'Open KiCad'}
            </button>
            <button
              type="button"
              className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
              onClick={onRefreshList}
            >
              Refresh
            </button>
          </div>
        </div>
      )}

      {!loadingList && !showGuidance && listResult?.status === 'boards_found' && (
        <div className="flex flex-col gap-2 rounded border border-line-subtle bg-surface p-3 text-sm">
          <p className="text-fg-bright">
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
                        ? 'border-fg bg-surface-alt text-fg'
                        : 'border-line text-fg-bright hover:bg-surface-alt'
                    }`}
                    onClick={() => onCheckBoard(candidate)}
                    disabled={checkingBoard}
                  >
                    <span className="block font-medium">{candidate.label}</span>
                    <span className="block break-all text-fg-muted">{candidate.path}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          <p className="text-xs text-fg-muted">
            Don't see the board you want? Switch to KiCad and open it there, then click Refresh.
          </p>
          {openKicadError && <p className="text-xs text-danger">{openKicadError}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
              onClick={onOpenKicad}
              disabled={openingKicad}
            >
              {openingKicad ? 'Switching…' : 'Switch to KiCad'}
            </button>
            <button
              type="button"
              className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
              onClick={onRefreshList}
            >
              Refresh
            </button>
          </div>
        </div>
      )}

      {checkingBoard && (
        <p className="text-sm text-fg-tertiary">
          Running DRC checks on {selectedBoard?.label ?? 'the selected board'}… this can take a few seconds.
        </p>
      )}
      {checkError && <p className="text-sm text-danger">{checkError}</p>}
      {checkResult && <ViolationsList result={checkResult} hideSourcePath />}
    </div>
  )
}
