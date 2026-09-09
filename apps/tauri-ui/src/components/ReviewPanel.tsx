import { useEffect, useRef, useState } from 'react'
import { Markdown } from './Markdown'
import type { Area, MenuCommand } from '../lib/areas'
import {
  loadStoredReview,
  runReview,
  type ChatScope,
  type ReviewFinding,
  type SourceRef,
  type StoredReview,
} from '../lib/chat'
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


/** When a kept review ran, in a reader's words rather than an ISO string. */
function whenItRan(iso: string): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'earlier'
  const minutes = Math.round((Date.now() - then.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const sameDay = then.toDateString() === new Date().toDateString()
  const time = then.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  return sameDay ? `at ${time}` : `on ${then.toLocaleDateString()} at ${time}`
}

/** What to say about a kept review, and never "re-run this now".
 *
 *  SPEC-339: a stale review is shown, labelled, and left alone. Re-running
 *  costs the user real money and a real minute, and that decision is theirs --
 *  which is also why each of these names what actually changed rather than
 *  saying "stale". */
function stalenessNote(review: StoredReview): string | null {
  const file = review.source?.path?.split('/').pop()
  const ran = whenItRan(review.ran_at)
  switch (review.stale_reason) {
    case 'source_changed':
      return `${file ?? 'The file'} has been saved since this review ran ${ran}. What it says may no longer match your design.`
    case 'source_missing':
      return `This review ran ${ran}, and ${file ?? 'the file'} it read is no longer where it was.`
    case 'checks_changed':
      return `This review ran ${ran}, before some of the checks this app makes existed. Nothing in your design changed -- there is simply more to look for now.`
    default:
      return null
  }
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
  /** SPEC-340: the ERC/DRC card sitting directly above this one.
   *
   *  Reported by a real click-through: this panel said "2 findings" on a board
   *  whose DRC also had four errors and a missing connection, and neither card
   *  referred to the other. The review is not ignoring them -- it deliberately
   *  lists only what ERC and DRC do NOT report (SPEC-113) -- but without
   *  naming that count, "2 findings" reads as the whole story.
   *
   *  `count` is null when that check has not been run this session, which must
   *  never look the same as a check that ran and found nothing. */
  siblingCheck?: { label: string; count: number | null; where: string }
}

export function ReviewPanel({
  area,
  scope,
  scopeId,
  title,
  projectName,
  menuCommand,
  siblingCheck,
}: ReviewPanelProps) {
  const [findings, setFindings] = useState<ReviewFinding[] | null>(null)
  const [stored, setStored] = useState<StoredReview | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openingSourceKey, setOpeningSourceKey] = useState<string | null>(null)
  const [openSourceError, setOpenSourceError] = useState<string | null>(null)

  /* SPEC-339: a review that already ran is loaded back, not thrown away.
     This component used to reset its state to null on every scope change,
     so opening Settings and returning destroyed a review and the next look
     cost another ERC or DRC run plus another real LLM call for a file
     nobody had touched.

     There is no reset here at all now. The panel is keyed on its scope at
     every mount site, so a scope change is a remount with fresh state --
     `CTX-318.7`'s lesson, where an effect that reset state after the commit
     silently undid a click that landed in the same window. This effect only
     ever fetches. */
  useEffect(() => {
    let cancelled = false
    loadStoredReview(area, projectName, scopeId)
      .then((review) => {
        // A run started while this was in flight owns the panel. The stored
        // copy is by definition older than the run the user just asked for.
        if (cancelled || !review) return
        setStored(review)
        setFindings(review.findings)
      })
      .catch(() => {
        // A kept review that cannot be read is not an error worth showing:
        // the button still works and says so. Failing loudly here would put
        // a red line under an area that is simply not reviewed yet.
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* SPEC-316: a Design > <Area> > "Run Review" menu click.
     The last nonce is held in a ref initialised to whatever arrived with the
     mount, so mounting never counts as a click. Without that, keying this
     component would make a project switch re-fire a stale menu command and
     spend a real LLM call nobody asked for -- which `SPEC-339` says must
     never happen. */
  const handledNonce = useRef(menuCommand?.nonce)
  useEffect(() => {
    if (menuCommand?.nonce === handledNonce.current) return
    handledNonce.current = menuCommand?.nonce
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
      // Just run, so current by definition. Re-read rather than assumed:
      // the daemon is what decides freshness and it has just stored this one.
      setStored(await loadStoredReview(area, projectName, scopeId).catch(() => null))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  const ourFindingCount = (findings ?? []).filter((f) => f.origin === 'copperplane').length

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
    setStored(null)
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

          {/* SPEC-339: when it ran, and what has moved since -- never a
              prompt to re-run. The button is right there; the app volunteering
              "re-run this" would be volunteering the user's money. */}
          {stored && !running && (
            <p className={`text-xs ${stored.stale_reason ? 'text-warning' : 'text-fg-muted'}`}>
              {stalenessNote(stored) ?? `Reviewed ${whenItRan(stored.ran_at)}.`}
            </p>
          )}

          {/* SPEC-113 §5: a finding this app computed must never be mistaken
              for one KiCad reported. The maintainer's own first look at a real
              review put it plainly -- the distinction was "just a simple line
              in the explanation", buried in prose the reader has to reach the
              middle of before learning that no checker in their toolchain
              reports this at all. It is the whole added value, so it is said
              once, above the list, and marked on every card it applies to. */}
          {ourFindingCount > 0 && (
            <p className="text-xs text-accent">
              {ourFindingCount === 1
                ? '1 of these was found by Copperplane. ERC and DRC do not report it.'
                : `${ourFindingCount} of these were found by Copperplane. ERC and DRC do not report them.`}
            </p>
          )}
          {siblingCheck && (
            <p className="text-xs text-fg-tertiary">
              {siblingCheck.count === null
                ? `${siblingCheck.label} has not been run yet — run it under ${siblingCheck.where} for the problems it reports. This review only lists the ones it does not.`
                : `${siblingCheck.label} separately reports ${siblingCheck.count} ${siblingCheck.count === 1 ? 'problem' : 'problems'} on this ${area === 'schematic' ? 'schematic' : 'board'}, listed under ${siblingCheck.where}. This review does not repeat them.`}
            </p>
          )}

          {findings.map((finding, i) => (
            <div
              key={i}
              className={`flex flex-col gap-1 rounded border bg-surface p-2 ${
                finding.origin === 'copperplane'
                  ? 'border-l-2 border-l-accent border-y-line-subtle border-r-line-subtle'
                  : 'border-line-subtle'
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className={`text-xs font-medium uppercase ${SEVERITY_CLASS[finding.severity]}`}>
                  {SEVERITY_LABEL[finding.severity]}
                </p>
                {finding.origin === 'copperplane' && (
                  <span className="rounded-full border border-accent px-2 py-0.5 text-xs font-medium text-accent">
                    Not reported by ERC or DRC
                  </span>
                )}
              </div>
              <p className="text-sm font-medium text-fg">{finding.title}</p>
              <Markdown text={finding.detail} className="text-sm text-fg-secondary" />
              {/* `general_practice` means "SOME of this relies on general
                  engineering knowledge", not "none of this is grounded". The
                  old wording claimed the latter, and appeared under a finding
                  that opened "DRC detected 2 missing connections" -- measured
                  from the user's own board seconds earlier. Telling someone to
                  discount a real measurement is worse than saying nothing. */}
              {finding.general_practice && (
                <p className="text-xs font-medium text-warning">
                  Includes general engineering practice, not only this area's own data.
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
