import type { CheckResult, Violation, ViolationItem } from '../lib/boardAdvisor'
import { explainTerms, IGNORED_CHECK_NOTES } from '../lib/kicadGlossary'

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
  hideSourcePath = false,
}: {
  result: CheckResult
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

      <IgnoredChecks checks={result.ignored_checks} />

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
          <ul className="flex flex-col gap-2">
            {result.violations.map((violation, index) => (
              <ViolationCard key={index} violation={violation} />
            ))}
          </ul>
          {result.truncated_count > 0 && (
            <p className="text-xs text-fg-muted">
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
    <li className="rounded border border-line-subtle p-2 text-xs">
      <p className="font-medium text-fg">
        <span className={_SEVERITY_COLOR[violation.severity] ?? 'text-fg-tertiary'}>
          {violation.severity.toUpperCase()}
        </span>{' '}
        {violation.description}
        {violation.sheet_path && <span className="text-fg-muted"> ({violation.sheet_path})</span>}
      </p>
      {violation.explanation && (
        <p className="mt-1 text-fg-secondary">{violation.explanation}</p>
      )}
      {violation.suggested_fix && (
        <p className="mt-1 text-fg-tertiary">Suggested fix: {violation.suggested_fix}</p>
      )}
      <WhereItIs items={violation.items} />
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
function IgnoredChecks({ checks }: { checks?: { key: string; description: string }[] }) {
  if (!checks || checks.length === 0) return null

  const notable = checks.filter((c) => IGNORED_CHECK_NOTES[c.key]?.matters)

  return (
    <details className="rounded border border-line-subtle p-2 text-xs">
      <summary className="cursor-pointer text-fg-muted">
        {checks.length} DRC test{checks.length === 1 ? '' : 's'} switched off
        {notable.length > 0 && (
          <span className="text-warning">
            {' '}— {notable.length} worth turning back on
          </span>
        )}
      </summary>
      <p className="mt-2 text-fg-tertiary">
        KiCad did not run these, so your board can look clean because a check is off rather than
        because it passed. Turn them on in KiCad under{' '}
        <strong>Inspect → Design Rules Checker → Edit ignored tests</strong>.
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
