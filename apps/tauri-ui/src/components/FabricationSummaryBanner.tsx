import type { FabricationSummary } from '../lib/boardAdvisor'

/**
 * SPEC-340 §2 and §2.1: the before-and-after, and the third state.
 *
 * This is a *banner over one findings list*, not a second result. The first
 * version of this feature rendered its own copy of the findings beside the
 * board check's, and a real click-through found the obvious problem: two
 * surfaces running the same engine over the same board, one explained and one
 * not, with nothing saying which to use. `ViolationsList` owns the findings;
 * this owns the framing around them.
 *
 * Two rules, both from `SPEC-114` rather than taste:
 *
 * 1. **Both counts, always together.** "27 findings" alone reads as a broken
 *    board. "4 with KiCad's defaults, 27 against the house you picked" reads as
 *    the discovery it is, and that difference is the whole argument (§2.8).
 * 2. **Nothing here says the board is good to order** (§3). This is the screen
 *    where that sentence wants to get written, so a test asserts over the
 *    rendered output.
 */
const OUTCOME_LABELS: Record<string, string> = {
  built_silently_wrong: 'would be built, and quietly wrong',
  would_be_rejected: 'your fab would question or reject',
  cosmetic: 'comes back looking wrong, works fine',
}

/** Display order: the class a maker had no way to know about comes first. */
const OUTCOME_ORDER = ['built_silently_wrong', 'would_be_rejected', 'cosmetic']

export function FabricationSummaryBanner({ fabrication }: { fabrication: FabricationSummary }) {
  const added = fabrication.after_count - fabrication.before_count

  return (
    <div className="flex flex-col gap-2">
      <div className="rounded border border-line-strong p-3">
        <p className="text-sm text-fg-bright">
          KiCad&rsquo;s own default rules find <strong>{fabrication.before_count}</strong>{' '}
          {fabrication.before_count === 1 ? 'issue' : 'issues'} on this board. Against{' '}
          {fabrication.house_name}, it finds <strong>{fabrication.after_count}</strong>.
        </p>
        {added > 0 && (
          <>
            <p className="mt-1 text-xs text-fg-tertiary">
              {added} of {fabrication.after_count} {added === 1 ? 'is' : 'are'} something
              KiCad&rsquo;s defaults never asked about. They are listed below with everything else.
            </p>
            <ul className="mt-1 text-xs text-fg-muted">
              {OUTCOME_ORDER.filter(
                (outcome) => (fabrication.counts_by_outcome[outcome as never] ?? 0) > 0,
              ).map((outcome) => (
                <li key={outcome}>
                  {fabrication.counts_by_outcome[outcome as never]} {OUTCOME_LABELS[outcome]}
                </li>
              ))}
            </ul>
          </>
        )}
        {added <= 0 && (
          <p className="mt-1 text-xs text-fg-tertiary">
            Nothing in your board falls outside what this house publishes. That is one check,
            against the numbers you entered — not a verdict on the whole board.
          </p>
        )}
      </div>

      {fabrication.verification_state === 'indeterminate' && <CouldNotConfirm />}
      <NotChecked fabrication={fabrication} />
    </div>
  )
}

/**
 * The third state, and the one genuinely new design decision in `SPEC-340`.
 *
 * The board has no copper track for the verification canary to catch, so
 * whether the generated rules took effect **cannot be observed**. The findings
 * are real; the confidence in them is not. Rendering this as either a pass or a
 * failure would throw away exactly the honesty `CTX-114.1`'s Phase 1 harness
 * exists to provide, so it is styled as neither.
 */
function CouldNotConfirm() {
  return (
    <p className="rounded border border-line-strong p-2 text-xs text-warning">
      Copperplane could not confirm these rules took effect on this board, because there is no
      copper track here for its verification check to catch. The findings may be incomplete. This
      is not a problem with your board.
    </p>
  )
}

/** Three separate lists, because they go unchecked for three separate reasons.
 *  Collapsing them would re-introduce the completeness claim the daemon
 *  deliberately refused to make. */
function NotChecked({ fabrication }: { fabrication: FabricationSummary }) {
  const gated = fabrication.not_checked.profile_rules_gated_off
  const unenforceable = fabrication.not_checked.recorded_but_unenforceable
  const total = gated.length + unenforceable.length
  if (total === 0) return null

  return (
    <details className="rounded border border-line-subtle p-2 text-xs">
      <summary className="cursor-pointer text-fg-muted">
        Limits from your board house that were not checked ({total})
      </summary>

      {gated.length > 0 && (
        <div className="mt-2">
          <p className="text-fg-tertiary">
            Your project switches these checks off, so the limits you set for them did not run.
            Copperplane does not change your project settings.
          </p>
          <ul className="mt-1 list-disc pl-4 text-fg-muted">
            {gated.map((rule) => (
              <li key={rule.field}>
                {rule.field.replace(/_/g, ' ')}
                {rule.fully_gated ? '' : ' (partly — some of its checks still ran)'}
              </li>
            ))}
          </ul>
        </div>
      )}

      {unenforceable.length > 0 && (
        <div className="mt-2">
          <p className="text-fg-tertiary">
            You recorded these, but KiCad&rsquo;s design rules have no check for them, so they were
            not applied to your board.
          </p>
          <ul className="mt-1 list-disc pl-4 text-fg-muted">
            {unenforceable.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </details>
  )
}
