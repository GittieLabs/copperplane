import { submitJob, type JobHandle } from './ipc'

/** Mirrors `daemon.py`'s real `freecad_generate_enclosure` params
 * (CTX-109.1). `width`/`depth` are the real mode-selection signal --
 * supplying both means manual mode, always; omitting them means
 * board-driven mode, which requires a live KiCad connection. The four
 * `*_mm` geometry params and `project_name` are all optional, matching
 * the same defaults/gating the daemon route itself applies. */
export interface EnclosureParams {
  height: number
  width?: number
  depth?: number
  wall_thickness_mm?: number
  clearance_mm?: number
  fillet_radius_mm?: number
  standoff_height_mm?: number
  project_name?: string
}

/** Mirrors `freecad_generate_enclosure`'s real return shape.
 * `unrecognized_holes` is always present (possibly empty); `artifact_id`
 * only appears when `project_name` was supplied and a real Artifact was
 * saved. */
export interface EnclosureResult {
  glb_path: string
  step_path: string
  unrecognized_holes: { x_mm: number; y_mm: number; diameter_mm: number; recognized: false }[]
  artifact_id?: string
}

/** Thin delegation to the real async route -- no logic of its own,
 * matching `lib/projects.ts`'s own thin-wrapper convention over daemon
 * routes. `freecad.generate_enclosure` is registered as an async route
 * (SPEC-105), so this returns a `JobHandle` the caller drives (progress,
 * cancellation, final result) exactly like `EnclosurePanel` already does
 * today. */
export async function generateEnclosure(params: EnclosureParams): Promise<JobHandle<EnclosureResult>> {
  return submitJob<EnclosureResult>('freecad.generate_enclosure', { ...params })
}
