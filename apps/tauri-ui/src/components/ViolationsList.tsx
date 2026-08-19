import type { CheckResult, Violation } from '../lib/boardAdvisor'

const _SEVERITY_COLOR: Record<string, string> = {
  error: 'text-red-400',
  warning: 'text-amber-400',
  exclusion: 'text-neutral-500',
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
      {!hideSourcePath && <p className="text-xs text-neutral-500">{result.source_path}</p>}
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
