import { useState } from 'react'
import { checkBoard, checkSchematic, pickSchematicFile, type CheckResult, type Violation } from '../lib/boardAdvisor'

/** SPEC-309: real ERC/DRC via kicad-cli (CTX-309.1), explained in plain
 * language. Lives in the PCB area -- already reserved for SPEC-309 by
 * App.tsx's own prior NotBuiltPlaceholder -- and offers both checks
 * from here rather than splitting DRC into PCB and ERC into Schematic,
 * since the Schematic area is SPEC-308's own reserved home instead. */
export function BoardAdvisor() {
  const [checkingBoard, setCheckingBoard] = useState(false)
  const [boardResult, setBoardResult] = useState<CheckResult | null>(null)
  const [boardError, setBoardError] = useState<string | null>(null)

  const [checkingSchematic, setCheckingSchematic] = useState(false)
  const [schematicResult, setSchematicResult] = useState<CheckResult | null>(null)
  const [schematicError, setSchematicError] = useState<string | null>(null)

  async function handleCheckBoard() {
    setCheckingBoard(true)
    setBoardError(null)
    try {
      setBoardResult(await checkBoard())
    } catch (err) {
      setBoardError(err instanceof Error ? err.message : String(err))
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
      <CheckSection
        title="Board (DRC)"
        checkLabel="Check Board"
        checking={checkingBoard}
        onCheck={handleCheckBoard}
        result={boardResult}
        error={boardError}
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

      {result && (
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
