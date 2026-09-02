import { useEffect, useState } from 'react'
import type { Area, MenuCommand } from '../lib/areas'
import { runReview, type ChatScope, type ReviewFinding, type SourceRef } from '../lib/chat'
import { isOpenableSource, openSource, sourceChipLabel } from '../lib/sourceRefs'

/** SPEC-319 §2.4: a **Run Review** action beside each area's existing
 * chat panel, not inside it -- a review is a flow step with a typed
 * result (`PRODUCT-PLAN.md` §3.3), not a conversational turn. Reuses
 * `AgentChat`'s own source-chip rendering (`lib/sourceRefs.ts`, CTX-319.2)
 * rather than a second implementation. Every mount point supplies its
 * own `area`/`scope`/`scopeId`/`title`/`projectName` -- the same shape
 * `AgentChat` already established. */

const SEVERITY_LABEL: Record<ReviewFinding['severity'], string> = {
  warning: 'Warning',
  suggestion: 'Suggestion',
  info: 'Info',
}

const SEVERITY_CLASS: Record<ReviewFinding['severity'], string> = {
  warning: 'text-warning',
  suggestion: 'text-fg-secondary',
  info: 'text-fg-muted',
}

export interface ReviewPanelProps {
  area: Area
  scope: ChatScope
  scopeId: string
  title: string
  projectName?: string
  /** SPEC-319 §2.4/CTX-319.6: a Design > <Area> > "Run Review" menu
   * click -- only Schematic/PCB/Enclosure have a real Design submenu at
   * all (SPEC-316's own menu), so this is `undefined` for Overview and
   * Components; the in-area button is their only real entry point. */
  menuCommand?: MenuCommand | null
}

export function ReviewPanel({ area, scope, scopeId, title, projectName, menuCommand }: ReviewPanelProps) {
  const [findings, setFindings] = useState<ReviewFinding[] | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openingSourceKey, setOpeningSourceKey] = useState<string | null>(null)
  const [openSourceError, setOpenSourceError] = useState<string | null>(null)

  // A stale review from a different part/project must never linger once
  // the real scope moves on -- matches AgentChat's own identity-reset
  // convention for the same reason (SPEC-318 §2.2's mount-always pattern
  // means the same mounted instance's scope can genuinely change).
  useEffect(() => {
    setFindings(null)
    setRunning(false)
    setError(null)
    setOpenSourceError(null)
  }, [scope, scopeId])

  // SPEC-316: a Design > <Area> > "Run Review" menu click -- the same
  // real handler the in-area button already calls, matching every other
  // area component's own established menuCommand convention exactly.
  useEffect(() => {
    if (menuCommand?.area !== area) return
    if (menuCommand.command === 'run_review') void handleRunReview()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuCommand?.nonce])

  async function handleRunReview() {
    setRunning(true)
    setError(null)
    try {
      const result = await runReview(scope, scopeId, area, projectName)
      setFindings(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  async function handleOpenSource(ref: SourceRef, key: string) {
    setOpeningSourceKey(key)
    setOpenSourceError(null)
    try {
      await openSource(ref)
    } catch (err) {
      setOpenSourceError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningSourceKey(null)
    }
  }

  function handleDismiss() {
    setFindings(null)
    setError(null)
  }

  return (
    <div className="flex flex-col gap-2 rounded border border-line-subtle p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-fg-muted">{title}</p>
        <button
          type="button"
          className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
          onClick={() => void handleRunReview()}
          disabled={running}
        >
          {running ? 'Reviewing…' : 'Run Review'}
        </button>
      </div>

      {/* SPEC-318 §3: no streaming -- the button's own "Reviewing…" label
          is the real, honest static in-progress state, never a typing
          indicator implying token-by-token progress. */}
      {error && <p className="text-sm text-danger">{error}</p>}

      {findings && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-fg-muted">
              {findings.length === 0
                ? // "Nothing stood out" used to be said whether or not any check
                  // had run -- and for the PCB and schematic areas, none ever
                  // had, so it read as "your design is fine" when it meant
                  // "the agent was shown nothing". The check now runs as part
                  // of the review, so this only ever follows a real one; the
                  // wording still says what was actually done rather than
                  // pronouncing the design clean.
                  'Reviewed — nothing worth flagging.'
                : `${findings.length} finding${findings.length === 1 ? '' : 's'}`}
            </p>
            <button type="button" className="text-xs text-fg-muted underline" onClick={handleDismiss}>
              Dismiss
            </button>
          </div>

          {findings.map((finding, i) => (
            <div key={i} className="flex flex-col gap-1 rounded border border-line-subtle bg-surface p-2">
              <p className={`text-xs font-medium uppercase ${SEVERITY_CLASS[finding.severity]}`}>
                {SEVERITY_LABEL[finding.severity]}
              </p>
              <p className="text-sm font-medium text-fg">{finding.title}</p>
              <p className="text-sm text-fg-secondary">{finding.detail}</p>
              {finding.general_practice && (
                <p className="text-xs font-medium text-warning">
                  General engineering practice -- not from this area's own data.
                </p>
              )}
              {finding.sources.length > 0 && (
                <ul className="mt-1 flex flex-wrap gap-1">
                  {finding.sources.map((ref, j) => {
                    const key = `${i}-${ref.kind}-${j}`
                    const openable = isOpenableSource(ref)
                    return (
                      <li key={key}>
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-0.5 text-xs disabled:opacity-50"
                          onClick={openable ? () => void handleOpenSource(ref, key) : undefined}
                          disabled={!openable || openingSourceKey === key}
                          title={openable ? 'Open the real source' : undefined}
                        >
                          {openable && openingSourceKey === key ? '…' : sourceChipLabel(ref)}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          ))}
          {openSourceError && <p className="text-xs text-danger">{openSourceError}</p>}
        </div>
      )}
    </div>
  )
}
