import { open as openDialog } from '@tauri-apps/plugin-dialog'
import { submitJob, type JobHandle } from './ipc'

/** Mirrors `daemon.py`'s real `freecad_generate_enclosure` params
 * (CTX-109.1, `pcb_path` added by CTX-310.1/SPEC-310). Mode selection is
 * explicit, in the daemon's own fixed priority order: `width`+`depth`
 * (manual) > `pcb_path` (file) > live board (board-driven, requires a
 * live KiCad connection) -- supplying more than one is never
 * ambiguous, since the daemon route only ever picks the highest-priority
 * one present. The four `*_mm` geometry params and `project_name` are
 * all optional, matching the same defaults/gating the daemon route
 * itself applies. */
export interface EnclosureParams {
  height: number
  width?: number
  depth?: number
  pcb_path?: string
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

/** SPEC-310: the file-based board-driven mode needs no live KiCad
 * connection at all, so it asks for a `.kicad_pcb` path via a real
 * native file picker -- mirrors `boardAdvisor.ts`'s own
 * `pickSchematicFile` pattern exactly, filtered to `.kicad_pcb` instead
 * of `.kicad_sch`. Returns `null` on cancel, not an error -- the user
 * closing the dialog is a normal, expected outcome. */
export async function pickPcbFile(): Promise<string | null> {
  const selected = await openDialog({
    filters: [{ name: 'KiCad PCB', extensions: ['kicad_pcb'] }],
  })
  return typeof selected === 'string' ? selected : null
}
