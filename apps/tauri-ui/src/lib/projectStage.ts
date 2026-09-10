import { dispatch } from './ipc'
import type { Area } from './areas'

/** Where a project stands, computed from its record -- `SPEC-343` §2.4.
 *
 *  Nothing here is stored and nothing is declared by the user. `CTX-343.1`
 *  Phase 1 measured that the READING is the feature and the action is a
 *  convenience: four of six actions are "press the button on the tab this
 *  points at", but *"your schematic changed after the PCB check"* is something
 *  no tab can say, because no tab knows about two stages at once. */
export interface StageReading {
  state:
    | 'no_goal'
    | 'no_files'
    | 'regressed'
    | 'nothing_checked'
    | 'schematic_only'
    | 'board_only'
    | 'both_checked'
    | 'complete'
  /** `null` in the `complete` state. `SPEC-343` §2.6 leaves open what to say
   *  when nothing is wrong, and §3 warns generic praise is worse than silence,
   *  so until that is settled it says nothing rather than filling the space. */
  action: string | null
  /** Which tab the action lives on. This NAMES a destination; it never
   *  navigates. `SPEC-300`'s AI boundary applies to this surface even though it
   *  is not an AI surface, because a user cannot tell the difference. */
  area: Area | null
  /** Why the reading came out this way. `SPEC-343` §3: a guided surface that is
   *  wrong once is worse than none, so a wrong reading has to be debuggable by
   *  whoever is looking at it. */
  evidence: string
  stale_areas: string[]
}

export async function projectStage(projectName: string): Promise<StageReading> {
  const response = await dispatch('project.stage', { name: projectName })
  if (response.error) throw new Error(response.error.message)
  return response.result as StageReading
}
