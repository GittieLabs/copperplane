import { useState } from 'react'

import type { CheckResult, Violation, ViolationItem } from '../lib/boardAdvisor'
import { FabricationSummaryBanner } from './FabricationSummaryBanner'
import { explainTerms, IGNORED_CHECK_NOTES } from '../lib/kicadGlossary'

/** Matches the review panel's own left-border treatment so the two lists on
 *  one screen read as the same kind of thing. */
const _SEVERITY_BORDER: Record<string, string> = {
  error: 'border-l-2 border-l-danger',
  warning: 'border-l-2 border-l-warning',
}

const _SEVERITY_COLOR: Record<string, string> = {
  error: 'text-danger',
  warning: 'text-warning',
  exclusion: 'text-fg-muted',
}

/** Shared between BoardAdvisor (DRC) and SchematicAdvisor (ERC) --
 * both real KiCad checks explained via the same component_pipeline
 * shape (SPEC-309). `hideSourcePath` lets a caller that already shows
 * the checked file's own path elsewhere (a highlighted list item) skip
 * repeating it here. */
export function ViolationsList({
  result,
  kind,
  hideSourcePath = false,
}: {
  result: CheckResult
  /** Which check produced this. Required rather than defaulted: the ignored-
   *  checks block names the tool and the menu path to fix it, and defaulting
   *  to one of them would put DRC's wording on the Schematic tab -- which is
   *  exactly what it did until this prop existed. */
  kind: 'drc' | 'erc'
  hideSourcePath?: boolean
}) {
  return (
    <div className="flex flex-col gap-2">
      {!hideSourcePath && <p className="text-xs text-fg-muted">{result.source_path}</p>}
      {/* KiCad reports three kinds of problem under three separate JSON
          keys, and only `violations` was ever explained. On a real board
          that key can be EMPTY while 18 unconnected-item errors sit in
          another -- so "no violations found" was said about a board KiCad
          had 19 complaints about. These counts come straight from KiCad and
          do not depend on the explanation call succeeding. */}
      {(result.unconnected_count || result.parity_count) ? (
        <p className="text-sm text-warning">
          KiCad reports {result.violation_count ?? 0} design-rule violation
          {(result.violation_count ?? 0) === 1 ? '' : 's'}
          {result.unconnected_count
            ? `, ${result.unconnected_count} unconnected item${result.unconnected_count === 1 ? '' : 's'}`
            : ''}
          {result.parity_count
            ? `, and ${result.parity_count} schematic mismatch${result.parity_count === 1 ? '' : 'es'}`
            : ''}
          .
        </p>
      ) : null}

      <SeverityFilter severities={result.included_severities} />

      {/* SPEC-340: the before-and-after rides above the one findings list
          rather than duplicating it. `fabrication` is absent unless a
          capability profile was used. */}
      {result.fabrication && <FabricationSummaryBanner fabrication={result.fabrication} />}

      <IgnoredChecks checks={result.ignored_checks} kind={kind} />

      {/* SPEC-340: the other half of the connection. Reported by a real
          click-through -- this card and the review below each showed part of
          the picture and neither mentioned the other.
          Reported again on contrast: this is an introductory statement, not a
          section header, and rendering it in the same muted grey as the
          collapsible header above made the two read as the same kind of thing. */}
      <p className="border-l-2 border-l-line-strong pl-2 text-xs text-fg-secondary">
        This is what {kind.toUpperCase()} reports. Copperplane also checks things{' '}
        {kind.toUpperCase()} cannot see, such as a symbol and footprint disagreeing about pin
        count — those are in “Review the {kind === 'erc' ? 'schematic' : 'board'}” below.
      </p>

      {result.violations.length === 0 ? (
        <p className={result.unconnected_count || result.parity_count
          ? 'text-sm text-fg-tertiary'
          : 'text-sm text-success'}>
          {result.unconnected_count || result.parity_count
            ? 'No explanations were produced for them.'
            : 'No violations found.'}
        </p>
      ) : (
        <>
          <p className="text-sm text-fg-secondary">{result.summary}</p>
          <FindingsList violations={result.violations} truncatedCount={result.truncated_count} />
        </>
      )}
    </div>
  )
}

/** How many findings are shown before the list asks. A real board produced 28,
 *  which is a long scroll before the review panel underneath even begins --
 *  reported from the running app as "extremely long and potentially
 *  distracting if you want to focus on one section". */
const PAGE_SIZE = 10

/** The findings, in a form that can be skimmed.
 *
 *  Three problems reported from the running app, all in one place:
 *  every card was fully expanded so 28 findings meant an enormous scroll; the
 *  ones past the explanation cap said "+13 more not shown" with no way to see
 *  them; and severity was styled differently here than in the review panel
 *  directly below, so the same idea looked like two different things.
 *
 *  Collapsed by default past the first few: the heading of each card carries
 *  the severity and the description, which is what a user scans. The detail is
 *  one click away rather than always on screen. */
function FindingsList({
  violations,
  truncatedCount,
}: {
  violations: Violation[]
  truncatedCount: number
}) {
  const [shown, setShown] = useState(PAGE_SIZE)
  const visible = violations.slice(0, shown)
  const remaining = violations.length - visible.length

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {visible.map((violation, index) => (
          <ViolationCard
            key={index}
            violation={violation}
            /* The first few open, so the section is useful without a click;
               the rest collapsed, so the page stays skimmable. */
            defaultOpen={index < 3}
          />
        ))}
      </ul>

      {remaining > 0 && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
            onClick={() => setShown((n) => n + PAGE_SIZE)}
          >
            Show {Math.min(PAGE_SIZE, remaining)} more
          </button>
          <button
            type="button"
            className="text-xs text-fg-muted underline"
            onClick={() => setShown(violations.length)}
          >
            Show all {violations.length}
          </button>
        </div>
      )}

      {shown >= violations.length && violations.length > PAGE_SIZE && (
        <button
          type="button"
          className="self-start text-xs text-fg-muted underline"
          onClick={() => setShown(PAGE_SIZE)}
        >
          Show fewer
        </button>
      )}

      {truncatedCount > 0 && (
        <p className="text-xs text-fg-muted">
          {truncatedCount} of these {truncatedCount === 1 ? 'is' : 'are'} listed without a
          plain-language explanation. KiCad reported them and they are all shown above; only the
          explanations are limited.
        </p>
      )}
    </div>
  )
}

/** One finding.
 *
 *  Severity is carried by a coloured left border AND the word, matching the
 *  review panel directly below. Those two lists used different visual
 *  languages for the same idea, which was reported as making the sections hard
 *  to tell apart and hard to compare. Border alone would be colour-only
 *  information; the word stays. */
function ViolationCard({
  violation,
  defaultOpen,
}: {
  violation: Violation
  defaultOpen: boolean
}) {
  const hasDetail = Boolean(
    violation.explanation || violation.suggested_fix || (violation.items ?? []).length,
  )

  return (
    <li
      className={`rounded border border-y-line-subtle border-r-line-subtle p-2 text-xs ${
        _SEVERITY_BORDER[violation.severity] ?? 'border-l-2 border-l-line-strong'
      }`}
    >
      <details open={defaultOpen}>
        <summary className={hasDetail ? 'cursor-pointer' : 'cursor-default list-none'}>
          <span className="font-medium text-fg">
            <span className={_SEVERITY_COLOR[violation.severity] ?? 'text-fg-tertiary'}>
              {violation.severity.toUpperCase()}
            </span>{' '}
            {violation.description}
            {violation.sheet_path && (
              <span className="text-fg-muted"> ({violation.sheet_path})</span>
            )}
          </span>
        </summary>

        {violation.explanation && (
          <p className="mt-1 text-fg-secondary">{violation.explanation}</p>
        )}
        {violation.suggested_fix && (
          <p className="mt-1 text-fg-tertiary">Suggested fix: {violation.suggested_fix}</p>
        )}
        {!violation.explanation && (
          <p className="mt-1 text-fg-muted">
            KiCad reported this one; Copperplane did not write an explanation for it.
          </p>
        )}
        <WhereItIs items={violation.items} />
      </details>
    </li>
  )
}

/** WHERE the problem is, which used to be discarded with the rest of `items`
 *  as "internal uuids" -- only `uuid` is. KiCad's own dialog shows exactly
 *  this text, so a user can match what they read here against what they see
 *  there, and the mm position lets them find it on the board.
 *
 *  Reported: "we didn't even tell the user where to find the problems on the
 *  board." */
function WhereItIs({ items }: { items?: ViolationItem[] }) {
  const located = (items ?? []).filter((i) => i.description)
  if (located.length === 0) return null

  const terms = new Map<string, string>()
  for (const item of located) {
    for (const entry of explainTerms(item.description ?? '')) {
      if (!terms.has(entry.term)) terms.set(entry.term, entry.plain)
    }
  }

  return (
    <div className="mt-2 flex flex-col gap-1 rounded bg-surface-alt/60 p-2">
      <p className="font-medium text-fg-secondary">Where to find it</p>
      <ul className="flex flex-col gap-0.5">
        {located.map((item, i) => (
          <li key={i} className="text-fg-secondary">
            {item.description}
            {item.pos && (
              <span className="text-fg-tertiary">
                {' '}— at x {item.pos.x}mm, y {item.pos.y}mm
              </span>
            )}
          </li>
        ))}
      </ul>
      {terms.size > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-fg-muted">What these terms mean</summary>
          <dl className="mt-1 flex flex-col gap-1">
            {[...terms].map(([term, plain]) => (
              <div key={term}>
                <dt className="inline font-mono text-fg-secondary">{term}</dt>
                <dd className="inline text-fg-tertiary"> — {plain}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  )
}

/** The DRC tests KiCad did NOT run.
 *
 *  Invisible everywhere else: a board with a check switched off looks exactly
 *  like a board that passed it. These settings are usually inherited -- copied
 *  from an older project's template for a reason that no longer applies --
 *  rather than chosen for this design. The maintainer raised it directly:
 *  "Maybe there was a reason to ignore these tests in a previous project that
 *  carried forward to this one... we should alert the user."
 *
 *  Collapsed by default so it never competes with real findings, but the
 *  count and any that matter are visible without opening it. */
/** SPEC-332: what the check was NOT asked to look for.
 *
 *  KiCad can run a check filtered to one severity. A result that found no
 *  errors, presented as "no problems", is then the same lie as a clean result
 *  from a test that was switched off -- which is the failure `IgnoredChecks`
 *  below already exists to prevent, one level up.
 *
 *  Silent in the ordinary case. Saying "errors and warnings were included" on
 *  every clean run is noise, and noise is how a real warning gets ignored. */
function SeverityFilter({ severities }: { severities?: string[] }) {
  if (!severities || severities.length === 0) return null
  const missing = ['error', 'warning'].filter((s) => !severities.includes(s))
  if (missing.length === 0) return null

  return (
    <p className="text-xs text-warning">
      This check only looked for {severities.join(' and ')} —{' '}
      {missing.join(' and ')} {missing.length === 1 ? 'was' : 'were'} not included, so a clean
      result here does not mean there is nothing to see.
    </p>
  )
}

function IgnoredChecks({
  checks,
  kind,
}: {
  checks?: { key: string; description: string }[]
  kind: 'drc' | 'erc'
}) {
  if (!checks || checks.length === 0) return null

  const notable = checks.filter((c) => IGNORED_CHECK_NOTES[c.key]?.matters)
  // Both paths read from KiCad's own binaries rather than from memory:
  // eeschema and pcbnew each carry "Edit ignored tests", under their own
  // checker. Getting this wrong sends a user hunting through the wrong editor.
  const where =
    kind === 'erc'
      ? 'Inspect → Electrical Rules Checker → Edit ignored tests'
      : 'Inspect → Design Rules Checker → Edit ignored tests'
  const subject = kind === 'erc' ? 'schematic' : 'board'

  return (
    <details className="rounded border border-line-subtle p-2 text-xs">
      {/* Reported on contrast: this is a section holder and was rendered in
          the same muted grey as ordinary body copy below it, so it did not
          read as one. */}
      <summary className="cursor-pointer font-medium text-fg-secondary">
        {checks.length} {kind.toUpperCase()} test{checks.length === 1 ? '' : 's'} switched off
        {notable.length > 0 && (
          <span className="text-warning">
            {' '}— {notable.length} worth turning back on
          </span>
        )}
      </summary>
      <p className="mt-2 text-fg-tertiary">
        KiCad did not run these, so your {subject} can look clean because a check is off rather
        than because it passed. Turn them on in KiCad under <strong>{where}</strong>.
      </p>
      <ul className="mt-2 flex flex-col gap-2">
        {checks.map((check) => {
          const note = IGNORED_CHECK_NOTES[check.key]
          return (
            <li key={check.key}>
              <p className={note?.matters ? 'font-medium text-warning' : 'font-medium text-fg-secondary'}>
                {check.description}
              </p>
              {/* An unknown key is reported as itself rather than guessed at:
                  KiCad can add checks we have not written a note for, and
                  inventing an explanation is worse than admitting we lack one. */}
              <p className="text-fg-tertiary">
                {note ? note.plain : 'No plain-language note for this check yet.'}
              </p>
            </li>
          )
        })}
      </ul>
    </details>
  )
}
