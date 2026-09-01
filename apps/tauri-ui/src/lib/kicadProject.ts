/** SPEC-325: read a KiCad project's files directly, with KiCad closed.
 *
 * The app's existing path (`kicad.list_project_schematics`) derives a
 * schematic from whichever board KiCad currently has open, because KiCad's
 * IPC server has never implemented a schematic-listing handler at all --
 * `kicad_bridge`'s own docstring records that, confirmed live. That needs
 * KiCad running, its API enabled, and the right document focused: three
 * preconditions for a fact sitting in a file.
 *
 * These routes read the files. Nothing here needs KiCad running, and
 * nothing here writes. */
import { open as openDialog } from '@tauri-apps/plugin-dialog'

import { dispatch, submitJob } from './ipc'

export interface KicadProjectFiles {
  project_name: string
  project_dir: string
  pro_path: string
  /** `null` when the project genuinely has no schematic or board yet --
   *  an ordinary state for a new project, not an error. */
  schematic_path: string | null
  pcb_path: string | null
  /** From the project's own `sheets` list. `null` means the file did not
   *  say, which is a different claim from "this project has no sheets".
   *
   *  SPEC-325 §3: whether `kicad-cli sch export bom` walks a hierarchy
   *  from the root sheet is UNVERIFIED -- no multi-sheet project was
   *  available to test against. A count above 1 is a reason to treat the
   *  component list as possibly incomplete. */
  sheet_count: number | null
}

export interface SchematicComponent {
  reference: string
  value: string | null
  footprint: string | null
  dnp: boolean
  /** Whether the footprint resolves in this install's libraries. */
  footprint_found: boolean
  /** What the footprint claims its 3D model is, if anything. */
  model_ref: string | null
  /** Where that model actually is. `null` when the footprint names one
   *  that is not installed -- which is common: KiCad's own Battery
   *  library ships 53 footprints against 29 STEP models. */
  model_path: string | null
  has_model: boolean
}

export interface SchematicRead {
  source_path: string
  /** When this was read. The file can lag an editor holding unsaved
   *  changes, so the UI says what it read and when rather than implying
   *  live sync. */
  read_at: string
  components: SchematicComponent[]
}

export async function pickKicadProject(): Promise<string | null> {
  const selected = await openDialog({
    multiple: false,
    filters: [{ name: 'KiCad project', extensions: ['kicad_pro'] }],
  })
  return typeof selected === 'string' ? selected : null
}

/** Sync route: one small JSON read and two stats, so no job round trip. */
export async function resolveKicadProject(proPath: string): Promise<KicadProjectFiles> {
  const response = await dispatch('kicad.resolve_project', { pro_path: proPath })
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as KicadProjectFiles
}

/** Async route: runs `kicad-cli`, a real subprocess. */
export async function listSchematicComponents(schPath: string): Promise<SchematicRead> {
  const handle = await submitJob<SchematicRead>('kicad.list_schematic_components', {
    sch_path: schPath,
  })
  return handle.result
}
