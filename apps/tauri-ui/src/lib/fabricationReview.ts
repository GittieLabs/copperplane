import { dispatch } from './ipc'

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
