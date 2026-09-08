import type { Violation } from './boardAdvisor'
import { dispatch, submitJob } from './ipc'

/**
 * SPEC-340: the client for SPEC-114's fabrication capability profiles.
 *
 * Everything dangerous here already happened on the daemon side and was
 * measured there -- `CTX-114.1` built the verified `.kicad_dru` generator, both
 * trap regressions, and the frozen-sidecar probe. This file is the wire.
 *
 * The one thing it must not do is flatten the daemon's honesty. Three separate
 * fields exist because three different things can go unchecked, and a client
 * that collapsed them into a boolean would quietly re-introduce the claim the
 * daemon deliberately refused to make.
 */

/** What a board house says it can build. Every value is optional: an absent
 *  field produces no rule rather than a guess (SPEC-114 §2.6), which is the
 *  single most important rule in the whole feature. */
export interface CapabilityProfile {
  house_name: string
  schema_version?: number
  layer_count?: number
  copper_weight_oz?: number
  board_thickness_mm?: number
  min_track_width?: number | null
  min_clearance?: number | null
  min_annular_ring?: number | null
  min_drill?: number | null
  min_hole_to_hole?: number | null
  min_silk_clearance?: number | null
  min_text_height?: number | null
  min_text_thickness?: number | null
  min_edge_clearance?: number | null
  min_courtyard_clearance?: number | null
  /** Recorded and shown, never checked -- no DRC constraint class exists. */
  min_mask_dam?: number | null
  min_mask_expansion?: number | null
  provenance: Record<string, FieldProvenance>
}

export interface FieldProvenance {
  source_url: string
  recorded_on: string
  confirmed_by_user: boolean
  note?: string
}

/** Whether the generated rules were observed taking effect.
 *
 *  `indeterminate` is not a failure and not a pass. The board has no copper
 *  track for the verification canary to catch, so whether the sidecar applied
 *  cannot be observed. SPEC-340 §2.1 names presenting this honestly as the one
 *  genuinely new design decision in the surface. */
export type VerificationState = 'applied' | 'indeterminate' | 'discarded'

export interface GatedRule {
  field: string
  constraint: string
  rule: string
  ignored_keys: string[]
  /** A rule reporting under two keys with only one ignored still finds some of
   *  its violations. "Partly" is more use than a flat "off". */
  fully_gated: boolean
}

/** Everything the review could NOT check. Rendering only `findings` and
 *  dropping this would claim a completeness the daemon refused to claim. */
export interface NotChecked {
  ignored_by_project: { key: string; description: string }[]
  profile_rules_gated_off: GatedRule[]
  recorded_but_unenforceable: string[]
}

export interface FabricationReview {
  house_name: string
  verification_state: VerificationState
  /** KiCad's own defaults. Never render `after_count` without this one:
   *  "27 findings" alone reads as a broken board (SPEC-340 §2). */
  before_count: number
  after_count: number
  findings: Violation[]
  profile_findings_count: number
  counts_by_outcome: Partial<Record<FindingOutcome, number>>
  rule_hits: Record<string, number>
  not_checked: NotChecked
  profile_is_stale: boolean
  unconfirmed_fields: string[]
}

export type FindingOutcome = 'built_silently_wrong' | 'would_be_rejected' | 'cosmetic'

/** Display order, and the argument for the whole feature: the class a maker had
 *  no way to know about comes first. The daemon already ranks `findings` this
 *  way -- preserve that order rather than re-sorting. */
export const OUTCOME_ORDER: FindingOutcome[] = [
  'built_silently_wrong',
  'would_be_rejected',
  'cosmetic',
]

export const OUTCOME_LABELS: Record<FindingOutcome, string> = {
  built_silently_wrong: 'Would be built, and quietly wrong',
  would_be_rejected: 'Your fab would question or reject this',
  cosmetic: 'Comes back looking wrong, works fine',
}

/** The rules provably did not run.
 *
 *  Distinct from a transport failure on purpose: the user needs to know their
 *  design rules were silently discarded, not that "something went wrong". This
 *  is SPEC-114 §2.2 Limit 2 reaching the surface. */
export class SidecarDiscardedError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SidecarDiscardedError'
  }
}

function isDiscarded(message: string): boolean {
  return /silently discarded|SidecarDiscarded/i.test(message)
}

/** Plain sync dispatch, matching `listOpenBoards`'s own precedent. These three
 *  routes do no subprocess or LLM work, so they are not in `ASYNC_ROUTES` and
 *  must not go through `submitJob` -- which would throw for a missing job_id. */
async function call<T>(method: string, params: Record<string, unknown>): Promise<T> {
  const response = await dispatch(method, params)
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as T
}


/** `fabrication.generic_profile` -- a starting point attributed to nobody.
 *
 *  SPEC-114 §2.9 lists real numbers for real houses as an open research task,
 *  so no profile here claims a vendor published it. Every field arrives
 *  `confirmed_by_user: false` precisely so the UI has something true to say. */
export async function genericProfile(): Promise<CapabilityProfile> {
  return call<CapabilityProfile>('fabrication.generic_profile', {})
}

export interface ProfileSummary {
  house_name: string
  enforceable_fields: string[]
  recorded_but_unenforceable: string[]
  unenforceable_notes: string[]
  unconfirmed_fields: string[]
  is_stale: boolean
}

export async function validateProfile(profile: CapabilityProfile): Promise<ProfileSummary> {
  return call<ProfileSummary>('fabrication.validate_profile', { profile })
}

export async function setProjectProfile(
  projectName: string,
  profile: CapabilityProfile | null,
): Promise<void> {
  await call('project.set_fabrication_profile', { project_name: projectName, profile })
}

/**
 * `fabrication.review_board` -- the before and after.
 *
 * Registered in `ASYNC_ROUTES` because it runs two or three real `kicad-cli`
 * subprocesses, so it goes through `submitJob` exactly like `checkBoard` does.
 * Measured at roughly five seconds on the example board.
 */
export async function reviewBoard(
  pcbPath: string,
  profile: CapabilityProfile,
): Promise<FabricationReview> {
  const handle = await submitJob<FabricationReview>('fabrication.review_board', {
    pcb_path: pcbPath,
    profile,
  })
  try {
    return await handle.result
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (isDiscarded(message)) {
      throw new SidecarDiscardedError(message)
    }
    throw error
  }
}

/** Findings grouped for display, in the daemon's own ranking order.
 *
 *  Groups with no findings are omitted rather than rendered empty -- an empty
 *  "would be built quietly wrong" heading reads as a finding of its own. */
export function groupByOutcome(
  review: FabricationReview,
): { outcome: FindingOutcome; label: string; findings: Violation[] }[] {
  const counts = review.counts_by_outcome
  return OUTCOME_ORDER.filter((outcome) => (counts[outcome] ?? 0) > 0).map((outcome) => ({
    outcome,
    label: OUTCOME_LABELS[outcome],
    findings: review.findings.filter((f) => outcomeOf(f) === outcome),
  }))
}

/** Mirrors `fabrication_review._OUTCOME_BY_TYPE`. An unrecognised type is shown
 *  rather than buried, matching the daemon's own choice. */
const OUTCOME_BY_TYPE: Record<string, FindingOutcome> = {
  annular_width: 'built_silently_wrong',
  hole_to_hole: 'built_silently_wrong',
  connection_width: 'built_silently_wrong',
  copper_edge_clearance: 'built_silently_wrong',
  clearance: 'built_silently_wrong',
  track_width: 'built_silently_wrong',
  drill_out_of_range: 'would_be_rejected',
  invalid_outline: 'would_be_rejected',
  courtyards_overlap: 'would_be_rejected',
  silk_overlap: 'cosmetic',
  silk_over_copper: 'cosmetic',
  text_height: 'cosmetic',
  text_thickness: 'cosmetic',
}

export function outcomeOf(violation: Violation): FindingOutcome {
  return OUTCOME_BY_TYPE[violation.type] ?? 'would_be_rejected'
}

/** True when the review found nothing the profile added.
 *
 *  Deliberately not called "passed". SPEC-114 §3 puts anything reading as "you
 *  are good to order" out of scope, and this is the screen where that sentence
 *  wants to be written. */
export function foundNothingNew(review: FabricationReview): boolean {
  return review.after_count <= review.before_count
}
