import type { CheckResult, Violation } from '../lib/boardAdvisor'

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
      <p className="mt-1 text-fg-secondary">{violation.explanation}</p>
      <p className="mt-1 text-fg-tertiary">Suggested fix: {violation.suggested_fix}</p>
    </li>
  )
}
