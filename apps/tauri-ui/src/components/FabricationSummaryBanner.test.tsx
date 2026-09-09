import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { FabricationSummaryBanner } from './FabricationSummaryBanner'

/** The real payload the frozen sidecar returned during CTX-114.1: 4 findings
 *  becoming 27, with the five checks this board ignores by default. Copied from
 *  a real run rather than invented, so the component is exercised against the
 *  shape it will actually receive. */
const REVIEW = {
  house_name: 'Generic 2-layer standard process (not a real vendor quote)',
  verification_state: 'applied' as const,
  before_count: 4,
  after_count: 27,
  findings: [
    {
      type: 'annular_width',
      description: "Annular width (rule 'min-annular-ring' min annular width 0.1300 mm)",
      severity: 'error',
      items: [{ description: 'PTH pad 1 [GND] of D1' }],
      explanation: '',
      suggested_fix: '',
    },
    {
      type: 'silk_overlap',
      description: "Silkscreen clipped by solder mask (rule 'min-silk-clearance')",
      severity: 'warning',
      items: [{ description: 'Arc of D1 on F.Silkscreen' }],
      explanation: '',
      suggested_fix: '',
    },
  ],
  profile_findings_count: 23,
  counts_by_outcome: { built_silently_wrong: 1, cosmetic: 1 },
  rule_hits: { 'min-annular-ring': 4 },
  not_checked: {
    ignored_by_project: [
      { key: 'missing_courtyard', description: 'Footprint has no courtyard defined' },
    ],
    profile_rules_gated_off: [],
    recorded_but_unenforceable: [],
  },
  profile_is_stale: false,
  unconfirmed_fields: ['min_drill'],
}

describe('FabricationSummaryBanner', () => {
  // TEST-012
  it('renders both counts together, never the after-count alone', () => {
    render(<FabricationSummaryBanner fabrication={REVIEW as never} />)

    // "27 findings" on its own reads as a broken board. The before-count is
    // what turns it into a discovery -- SPEC-340 section 2.
    expect(screen.getByText(/4/)).toBeTruthy()
    const body = document.body.textContent ?? ''
    expect(body).toContain('4')
    expect(body).toContain('27')
    expect(body).toMatch(/default rules/i)
  })

  // TEST-013
  it('puts the silently-wrong group above the cosmetic one', () => {
    render(<FabricationSummaryBanner fabrication={REVIEW as never} />)
    const body = document.body.textContent ?? ''
    expect(body.indexOf('quietly wrong')).toBeGreaterThan(-1)
    expect(body.indexOf('quietly wrong')).toBeLessThan(body.indexOf('looking wrong'))
  })

  // TEST-016
  it('renders the limits the profile set that were not checked', () => {
    const review = {
      ...REVIEW,
      not_checked: {
        ...REVIEW.not_checked,
        profile_rules_gated_off: [
          {
            field: 'min_drill',
            constraint: 'hole_size',
            rule: 'min-drill',
            ignored_keys: ['drill_out_of_range'],
            fully_gated: true,
          },
        ],
        recorded_but_unenforceable: ['min mask dam is recorded as 0.1mm but cannot be checked'],
      },
    }
    render(<FabricationSummaryBanner fabrication={review as never} />)
    const body = document.body.textContent ?? ''
    expect(body).toContain('min drill')
    expect(body).toContain('cannot be checked')

    // Deliberately NOT here: KiCad's own switched-off tests are rendered by
    // ViolationsList's existing SPEC-332 block, directly below this banner.
    // Showing them twice is the duplication this whole fold-in removes.
    expect(body).not.toContain('Footprint has no courtyard defined')
  })

  it('says when a gated rule is only partly switched off', () => {
    const review = {
      ...REVIEW,
      not_checked: {
        ...REVIEW.not_checked,
        profile_rules_gated_off: [
          {
            field: 'min_silk_clearance',
            constraint: 'silk_clearance',
            rule: 'min-silk-clearance',
            ignored_keys: ['silk_overlap'],
            fully_gated: false,
          },
        ],
      },
    }
    render(<FabricationSummaryBanner fabrication={review as never} />)
    expect(document.body.textContent).toContain('partly')
  })

  // TEST-014
  it('reads an indeterminate result as neither a pass nor a failure', () => {
    render(
      <FabricationSummaryBanner
        fabrication={{ ...REVIEW, verification_state: 'indeterminate' } as never}
      />,
    )
    const body = document.body.textContent ?? ''

    // The findings are real; the confidence in them is not. It must not read as
    // a failure of the user's board, nor as a clean pass.
    expect(body).toMatch(/could not confirm/i)
    expect(body).toMatch(/not a problem with your board/i)
    expect(body).toContain('27')
  })

  it('does not show the could-not-confirm notice on a verified result', () => {
    render(<FabricationSummaryBanner fabrication={REVIEW as never} />)
    expect(document.body.textContent).not.toMatch(/could not confirm/i)
  })

  // TEST-017
  it('never tells the user the board is good to order', () => {
    // SPEC-114 section 3 puts this out of scope, and SPEC-340 section 3 names
    // this screen as where the sentence wants to be written. An assertion over
    // rendered output is the only thing that keeps it out as this file grows.
    const cases = [
      REVIEW,
      { ...REVIEW, after_count: 4, counts_by_outcome: {}, findings: [] },
      { ...REVIEW, verification_state: 'indeterminate' as const },
    ]
    for (const review of cases) {
      const { unmount } = render(<FabricationSummaryBanner fabrication={review as never} />)
      const body = (document.body.textContent ?? '').toLowerCase()
      // Verdict phrases only. A bare "passed" is too blunt: the ignored-checks
      // note correctly says a board "can look clean because a check is off
      // rather than because it passed", which is the opposite of a verdict.
      for (const forbidden of [
        'good to order',
        'ready to order',
        'safe to order',
        'ready to manufacture',
        'your board passed',
        'this board passed',
        'no problems found',
        'you are good',
        "you're good",
      ]) {
        expect(body).not.toContain(forbidden)
      }
      unmount()
    }
  })

  it('says a clean result is one check, not a verdict', () => {
    render(
      <FabricationSummaryBanner
        fabrication={{ ...REVIEW, counts_by_outcome: {}, after_count: 4 } as never}
      />,
    )
    expect(document.body.textContent).toMatch(/not a verdict on the whole board/i)
  })
})
