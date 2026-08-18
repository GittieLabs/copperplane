import { useCallback, useEffect, useState } from 'react'
import {
  checkBoard,
  checkSchematic,
  listOpenBoards,
  openKicad,
  pickSchematicFile,
  type CheckResult,
  type ListOpenBoardsResult,
  type Violation,
} from '../lib/boardAdvisor'

/** SPEC-309: real ERC/DRC via kicad-cli (CTX-309.1), explained in plain
 * language. Lives in the PCB area -- already reserved for SPEC-309 by
 * App.tsx's own prior NotBuiltPlaceholder -- and offers both checks
 * from here rather than splitting DRC into PCB and ERC into Schematic,
 * since the Schematic area is SPEC-308's own reserved home instead.
 *
 * CTX-309.4: the Board (DRC) side scans for open boards as soon as this
 * screen mounts and always shows them as a real, clickable list -- even
 * a single one -- rather than a blind "Check Board" button that
 * silently auto-resolved whichever board happened to be open (CTX-309.3).
 * Real user feedback exercising the actual running app found that still
 * too opaque for someone new to KiCad: it never showed *which* board was
 * about to be checked, and offered no way to actually open KiCad from
 * here. Zero boards open now offers a real "Open KiCad" action plus a
 * concrete walkthrough, not just prose. */
export function BoardAdvisor() {
  const [loadingBoardList, setLoadingBoardList] = useState(false)
  const [boardListResult, setBoardListResult] = useState<ListOpenBoardsResult | null>(null)
  const [boardListError, setBoardListError] = useState<string | null>(null)
  const [openingKicad, setOpeningKicad] = useState(false)

  const [checkingBoard, setCheckingBoard] = useState(false)
  const [boardCheckResult, setBoardCheckResult] = useState<CheckResult | null>(null)
  const [boardCheckError, setBoardCheckError] = useState<string | null>(null)

  const [checkingSchematic, setCheckingSchematic] = useState(false)
  const [schematicResult, setSchematicResult] = useState<CheckResult | null>(null)
  const [schematicError, setSchematicError] = useState<string | null>(null)

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
    setBoardListError(null)
    try {
      await openKicad()
    } catch (err) {
      setBoardListError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningKicad(false)
    }
  }

  async function handleCheckBoard(pcbPath: string) {
    setCheckingBoard(true)
    setBoardCheckError(null)
    setBoardCheckResult(null)
    try {
      setBoardCheckResult(await checkBoard(pcbPath))
    } catch (err) {
      setBoardCheckError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingBoard(false)
    }
  }

  async function handleCheckSchematic() {
    // pickSchematicFile returning null (the user closed the dialog) is
    // a normal, silent no-op -- not an error state.
    const path = await pickSchematicFile()
    if (!path) return

    setCheckingSchematic(true)
    setSchematicError(null)
    try {
      setSchematicResult(await checkSchematic(path))
    } catch (err) {
      setSchematicError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingSchematic(false)
    }
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-6">
      <BoardCheckSection
        loadingList={loadingBoardList}
        listResult={boardListResult}
        listError={boardListError}
        onRefreshList={() => void refreshBoardList()}
        onOpenKicad={() => void handleOpenKicad()}
        openingKicad={openingKicad}
        checkingBoard={checkingBoard}
        checkResult={boardCheckResult}
        checkError={boardCheckError}
        onCheckBoard={(path) => void handleCheckBoard(path)}
      />
      <CheckSection
        title="Schematic (ERC)"
        checkLabel="Check Schematic…"
        checking={checkingSchematic}
        onCheck={handleCheckSchematic}
        result={schematicResult}
        error={schematicError}
      />
    </div>
  )
}

const _SEVERITY_COLOR: Record<string, string> = {
  error: 'text-red-400',
  warning: 'text-amber-400',
  exclusion: 'text-neutral-500',
}

/** CTX-309.4: the Board (DRC) section, kept separate from the generic
 * CheckSection below since schematic checks always need an explicit,
 * user-picked file path (no live board-listing capability exists for
 * schematics, per SPEC-309 §2's own confirmed IPC limitation). */
function BoardCheckSection({
  loadingList,
  listResult,
  listError,
  onRefreshList,
  onOpenKicad,
  openingKicad,
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
  checkingBoard: boolean
  checkResult: CheckResult | null
  checkError: string | null
  onCheckBoard: (pcbPath: string) => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
      <p className="text-xs font-medium uppercase text-neutral-500">Board (DRC)</p>

      {loadingList && <p className="text-sm text-neutral-400">Scanning for boards open in KiCad…</p>}

      {!loadingList && listError && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-red-400">{listError}</p>
          {/* CTX-309.4 revision: "could not connect" almost always means
           * KiCad simply isn't running yet -- the real, most common novice
           * case -- so this offers the same Open KiCad action as the
           * empty-list state, not just a bare Retry. */}
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
              Retry
            </button>
          </div>
        </div>
      )}

      {!loadingList && !listError && listResult?.status === 'no_board_open' && (
        <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
          <p className="text-neutral-200">No board is currently open in KiCad.</p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-neutral-400">
            <li>Click <strong className="text-neutral-300">Open KiCad</strong> below (or open it yourself).</li>
            <li>
              Open your project, then open its <strong className="text-neutral-300">PCB Editor</strong> window
              (not just the project manager).
            </li>
            <li>
              Confirm the IPC API is enabled: <strong className="text-neutral-300">Preferences → Plugins</strong>.
            </li>
            <li>Click <strong className="text-neutral-300">Refresh</strong> below.</li>
          </ol>
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

      {!loadingList && !listError && listResult?.status === 'boards_found' && (
        <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
          <p className="text-neutral-200">
            {listResult.candidates.length === 1
              ? 'Board open in KiCad:'
              : 'Boards open in KiCad — pick one to check:'}
          </p>
          <ul className="flex flex-col gap-1">
            {listResult.candidates.map((candidate) => (
              <li key={candidate.path}>
                <button
                  type="button"
                  className="w-full rounded border border-neutral-700 px-3 py-2 text-left text-xs text-neutral-200 hover:bg-neutral-800 disabled:opacity-50"
                  onClick={() => onCheckBoard(candidate.path)}
                  disabled={checkingBoard}
                >
                  <span className="block font-medium">{candidate.label}</span>
                  <span className="block text-neutral-500">{candidate.path}</span>
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="self-start rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
            onClick={onRefreshList}
          >
            Refresh
          </button>
        </div>
      )}

      {checkingBoard && <p className="text-sm text-neutral-400">Checking…</p>}
      {checkError && <p className="text-sm text-red-400">{checkError}</p>}
      {checkResult && <ViolationsList result={checkResult} />}
    </div>
  )
}

function CheckSection({
  title,
  checkLabel,
  checking,
  onCheck,
  result,
  error,
}: {
  title: string
  checkLabel: string
  checking: boolean
  onCheck: () => void
  result: CheckResult | null
  error: string | null
}) {
  return (
    <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
      <p className="text-xs font-medium uppercase text-neutral-500">{title}</p>
      <button
        type="button"
        className="self-start rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
        onClick={onCheck}
        disabled={checking}
      >
        {checking ? 'Checking…' : checkLabel}
      </button>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && <ViolationsList result={result} />}
    </div>
  )
}

function ViolationsList({ result }: { result: CheckResult }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-neutral-500">{result.source_path}</p>
      {result.violations.length === 0 ? (
        <p className="text-sm text-emerald-400">No violations found.</p>
      ) : (
        <>
          <p className="text-sm text-neutral-300">{result.summary}</p>
          <ul className="flex flex-col gap-2">
            {result.violations.map((violation, index) => (
              <ViolationCard key={index} violation={violation} />
            ))}
          </ul>
          {result.truncated_count > 0 && (
            <p className="text-xs text-neutral-500">
              +{result.truncated_count} more violation(s) not shown.
            </p>
          )}
        </>
      )}
    </div>
  )
}

function ViolationCard({ violation }: { violation: Violation }) {
  return (
    <li className="rounded border border-neutral-800 p-2 text-xs">
      <p className="font-medium text-neutral-100">
        <span className={_SEVERITY_COLOR[violation.severity] ?? 'text-neutral-400'}>
          {violation.severity.toUpperCase()}
        </span>{' '}
        {violation.description}
        {violation.sheet_path && <span className="text-neutral-500"> ({violation.sheet_path})</span>}
      </p>
      <p className="mt-1 text-neutral-300">{violation.explanation}</p>
      <p className="mt-1 text-neutral-400">Suggested fix: {violation.suggested_fix}</p>
    </li>
  )
}
