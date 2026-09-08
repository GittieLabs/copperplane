import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()
const dispatchMock = vi.fn()

vi.mock('./ipc', () => ({ submitJob: submitJobMock, dispatch: dispatchMock }))

const {
  genericProfile,
  validateProfile,
  setProjectProfile,
  reviewBoard,
  groupByOutcome,
  outcomeOf,
  foundNothingNew,
  SidecarDiscardedError,
  OUTCOME_ORDER,
} = await import('./fabricationReview')

beforeEach(() => {
  submitJobMock.mockReset()
  dispatchMock.mockReset()
})

/** A real review payload, shaped exactly as the daemon returned it when driven
 *  into the frozen sidecar during CTX-114.1 -- 4 findings becoming 27, with the
 *  five checks this board ignores by default. Not invented. */
const REVIEW = {
  house_name: 'Generic 2-layer standard process (not a real vendor quote)',
  verification_state: 'applied' as const,
  before_count: 4,
  after_count: 27,
  findings: [
    { type: 'annular_width', description: 'Annular width', severity: 'error', items: [], explanation: '', suggested_fix: '' },
    { type: 'silk_overlap', description: 'Silkscreen clipped', severity: 'warning', items: [], explanation: '', suggested_fix: '' },
    { type: 'drill_out_of_range', description: 'Drill too small', severity: 'warning', items: [], explanation: '', suggested_fix: '' },
  ],
  profile_findings_count: 23,
  counts_by_outcome: { built_silently_wrong: 7, cosmetic: 20 },
  rule_hits: { 'min-annular-ring': 4, 'min-track-width': 0 },
  not_checked: {
    ignored_by_project: [{ key: 'missing_courtyard', description: 'Footprint has no courtyard defined' }],
    profile_rules_gated_off: [],
    recorded_but_unenforceable: [],
  },
  profile_is_stale: false,
  unconfirmed_fields: ['min_drill'],
}

const PROFILE = { house_name: 'H', min_drill: 0.3, provenance: {} }

describe('sync routes', () => {
  it('dispatches the three sync routes plainly, never through submitJob', async () => {
    dispatchMock.mockResolvedValue({ result: { house_name: 'H', provenance: {} } })

    await genericProfile()
    await validateProfile(PROFILE as never)
    await setProjectProfile('alpha', PROFILE as never)

    expect(dispatchMock.mock.calls.map((c) => c[0])).toEqual([
      'fabrication.generic_profile',
      'fabrication.validate_profile',
      'project.set_fabrication_profile',
    ])
    expect(submitJobMock).not.toHaveBeenCalled()
  })

  it('sends the project name and profile the daemon expects', async () => {
    dispatchMock.mockResolvedValue({ result: {} })
    await setProjectProfile('alpha', PROFILE as never)
    expect(dispatchMock).toHaveBeenCalledWith('project.set_fabrication_profile', {
      project_name: 'alpha',
      profile: PROFILE,
    })
  })

  it('surfaces a daemon error rather than returning an undefined result', async () => {
    dispatchMock.mockResolvedValue({ error: { message: 'min_drill must be positive' } })
    await expect(validateProfile(PROFILE as never)).rejects.toThrow('min_drill must be positive')
  })
})

describe('reviewBoard', () => {
  // TEST-005
  it('dispatches through the async job path, since it runs real subprocesses', async () => {
    submitJobMock.mockResolvedValueOnce({
      jobId: 'job_1',
      result: Promise.resolve(REVIEW),
      onUpdate: vi.fn(),
      cancel: vi.fn(),
    })

    await expect(reviewBoard('/tmp/b.kicad_pcb', PROFILE as never)).resolves.toEqual(REVIEW)
    expect(submitJobMock).toHaveBeenCalledWith('fabrication.review_board', {
      pcb_path: '/tmp/b.kicad_pcb',
      profile: PROFILE,
    })
  })

  // TEST-006
  it('raises a discarded sidecar as its own error, not a generic failure', async () => {
    submitJobMock.mockResolvedValueOnce({
      jobId: 'job_2',
      result: Promise.reject(new Error('KiCad silently discarded /tmp/b.kicad_dru: the canary…')),
      onUpdate: vi.fn(),
      cancel: vi.fn(),
    })

    // The user needs to know their design rules did not run at all, which is a
    // different sentence from "something went wrong".
    await expect(reviewBoard('/tmp/b.kicad_pcb', PROFILE as never)).rejects.toBeInstanceOf(
      SidecarDiscardedError,
    )
  })

  it('leaves an ordinary transport failure as an ordinary error', async () => {
    submitJobMock.mockResolvedValueOnce({
      jobId: 'job_3',
      result: Promise.reject(new Error('daemon is not running')),
      onUpdate: vi.fn(),
      cancel: vi.fn(),
    })

    const failure = reviewBoard('/tmp/b.kicad_pcb', PROFILE as never)
    await expect(failure).rejects.toThrow('daemon is not running')
    await expect(failure).rejects.not.toBeInstanceOf(SidecarDiscardedError)
  })
})

describe('grouping and ranking', () => {
  // TEST-013
  it('keeps the daemon ranking, with the silently-wrong class first', () => {
    const groups = groupByOutcome(REVIEW as never)
    expect(groups.map((g) => g.outcome)).toEqual(['built_silently_wrong', 'cosmetic'])
    expect(OUTCOME_ORDER[0]).toBe('built_silently_wrong')
  })

  it('omits an outcome with no findings rather than rendering it empty', () => {
    // An empty "would be built quietly wrong" heading reads as a finding.
    const groups = groupByOutcome(REVIEW as never)
    expect(groups.map((g) => g.outcome)).not.toContain('would_be_rejected')
  })

  // TEST-007
  it('classifies an unrecognised finding as shown, not buried', () => {
    expect(outcomeOf({ type: 'something_new_in_kicad_11' } as never)).toBe('would_be_rejected')
  })

  it('mirrors the daemon classification for the measured headline types', () => {
    expect(outcomeOf({ type: 'annular_width' } as never)).toBe('built_silently_wrong')
    expect(outcomeOf({ type: 'silk_overlap' } as never)).toBe('cosmetic')
    expect(outcomeOf({ type: 'drill_out_of_range' } as never)).toBe('would_be_rejected')
  })

  it('reports "found nothing new" without ever calling it a pass', () => {
    expect(foundNothingNew(REVIEW as never)).toBe(false)
    expect(foundNothingNew({ ...REVIEW, after_count: 4 } as never)).toBe(true)
  })
})
