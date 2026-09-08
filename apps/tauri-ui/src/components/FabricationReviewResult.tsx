import type { FabricationReview } from '../lib/fabricationReview'
import { groupByOutcome } from '../lib/fabricationReview'

/**
 * SPEC-340 §2 and §2.1: the before and after, and the third state.
 *
 * Two rules govern everything in this file, both from `SPEC-114` rather than
 * taste:
 *
 * 1. **Both counts, always together.** "27 findings" alone reads as a broken
 *    board. "4 with KiCad's defaults, 27 against the house you picked" reads as
 *    the discovery it actually is, and that difference is the entire argument
 *    for the feature (`SPEC-114` §2.8).
 * 2. **Nothing here says the board is good to order.** `SPEC-114` §3 puts that
 *    out of scope, and `SPEC-340` §3 names this screen as the one place the
 *    sentence wants to get written. `FabricationReviewResult.test.tsx` asserts
 *    over the rendered output because a review habit will not survive the
 *    component growing.
 */
export function FabricationReviewResult({ review }: { review: FabricationReview }) {
  const groups = groupByOutcome(review)
  const added = review.after_count - review.before_count

  return (
    <div className="flex flex-col gap-3">
      <BeforeAndAfter review={review} added={added} />
      {review.verification_state === 'indeterminate' && <CouldNotConfirm />}
      <NotChecked review={review} />

      {groups.length === 0 ? (
        <p className="text-sm text-fg-tertiary">
          Nothing in your board falls outside what {review.house_name} publishes. That is one
          check, against the numbers you entered — not a verdict on the whole board.
        </p>
      ) : (
        groups.map((group) => (
          <section key={group.outcome} className="flex flex-col gap-1">
            <h4 className="text-sm font-medium text-fg-bright">
              {group.label}{' '}
              <span className="text-fg-muted">({group.findings.length})</span>
            </h4>
            <ul className="flex flex-col gap-1">
              {group.findings.map((finding, index) => (
                <li
                  key={`${finding.type}-${index}`}
                  className="rounded border border-line-subtle p-2 text-xs"
                >
                  <p className="text-fg-secondary">{finding.description}</p>
                  {finding.items?.[0]?.description && (
                    <p className="text-fg-muted">{finding.items[0].description}</p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}

/** Never renders `after_count` on its own. See rule 1 above. */
function BeforeAndAfter({ review, added }: { review: FabricationReview; added: number }) {
  return (
    <div className="rounded border border-line-strong p-3">
      <p className="text-sm text-fg-bright">
        KiCad&rsquo;s own default rules find <strong>{review.before_count}</strong>{' '}
        {review.before_count === 1 ? 'issue' : 'issues'} on this board. Against{' '}
        {review.house_name}, it shows <strong>{review.after_count}</strong>.
      </p>
      {added > 0 && (
        <p className="mt-1 text-xs text-fg-tertiary">
          {added} of {review.after_count} {added === 1 ? 'is' : 'are'} something KiCad&rsquo;s
          defaults never asked about.
        </p>
      )}
    </div>
  )
}

/**
 * The third state, and the one genuinely new design decision in `SPEC-340`.
 *
 * The board has no copper track for the verification canary to catch, so
 * whether the generated rules took effect **cannot be observed**. The findings
 * below are real; the confidence in them is not. Rendering this as either a
 * pass or a failure would throw away exactly the honesty that `CTX-114.1`'s
 * whole Phase 1 harness exists to provide, so it is neither styled as danger
 * nor as success.
 */
function CouldNotConfirm() {
  return (
    <p className="rounded border border-line-strong p-2 text-xs text-warning">
      Copperplane could not confirm these rules took effect on this board, because there is no
      copper track here for its verification check to catch. The findings below may be incomplete.
      This is not a problem with your board.
    </p>
  )
}

/**
 * Everything the review could not check.
 *
 * Three separate things, because they fail for three separate reasons, and the
 * daemon deliberately kept them apart. Collapsing them here would re-introduce
 * the completeness claim it refused to make.
 */
function NotChecked({ review }: { review: FabricationReview }) {
  const { ignored_by_project: ignored, profile_rules_gated_off: gated } = review.not_checked
  const unenforceable = review.not_checked.recorded_but_unenforceable
  const total = ignored.length + gated.length + unenforceable.length
  if (total === 0) return null

  return (
    <details className="rounded border border-line-subtle p-2 text-xs">
      <summary className="cursor-pointer text-fg-muted">
        What this check could not tell you ({total})
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

      {ignored.length > 0 && (
        <div className="mt-2">
          <p className="text-fg-tertiary">
            KiCad did not run these tests at all, so your board can look clean because a check is
            off rather than because it passed.
          </p>
          <ul className="mt-1 list-disc pl-4 text-fg-muted">
            {ignored.map((check) => (
              <li key={check.key}>{check.description || check.key}</li>
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
