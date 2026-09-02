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

/** SPEC-326: a clearance envelope per component, plus the minimum interior
 *  height they imply.
 *
 *  A recommendation, never an override -- SPEC-311's enclosure height stays
 *  user-entered. Silently resizing a box from a partly-stated set of volumes
 *  would be the confident-wrong-answer this spec exists to avoid. */
export interface ComponentEnvelope {
  reference: string
  footprint: string | null
  x_mm: number | null
  y_mm: number | null
  z_mm: number | null
  /** Which of SPEC-326 §2.3's ordered sources supplied the height. */
  source: 'model' | 'package_dimensions' | 'user' | 'unknown'
  /** X/Y came from the footprint's courtyard, which approximates the body
   *  and can be smaller than it -- never a guaranteed enclosure. */
  x_within_courtyard: boolean
}

export interface EnvelopeResult {
  envelopes: ComponentEnvelope[]
  measured: number
  stated: number
  unknown: number
  source_path: string
  /** SPEC-326 §2.7: which file these numbers describe. The BOARD is the
   *  source of truth — it is the thing going in the box. `'schematic'` means
   *  the board had no footprints on it at all (a project drawn but not laid
   *  out yet), and the caller must say so rather than let it pass as a board
   *  measurement. */
  measured_from: 'board' | 'schematic'
  read_at: string
  min_interior_height_mm: number | null
  tallest: { reference: string; z_mm: number; source: string } | null
}

export async function componentEnvelopes(
  schPath: string | null,
  pcbPath: string | null,
  heightOverrides: Record<string, number> = {},
): Promise<EnvelopeResult> {
  const handle = await submitJob<EnvelopeResult>('kicad.component_envelopes', {
    sch_path: schPath,
    pcb_path: pcbPath,
    height_overrides: heightOverrides,
  })
  return handle.result
}

/** SPEC-326 §2.7: where the board and its schematic disagree.
 *
 *  KiCad does not push a schematic edit to the board -- a user runs
 *  "Update PCB from Schematic" by hand, and until they do the two files
 *  disagree silently. Each opens and renders correctly on its own, so
 *  neither KiCad view shows a problem.
 *
 *  This matters to SPEC-326 specifically and not just as hygiene: every
 *  volume number above is read from the SCHEMATIC's footprints, while the
 *  enclosure is built around the BOARD. When they disagree, the interior
 *  height describes a part that is not on the board being built. */
export interface ParityIssue {
  type: string
  severity: string
  description: string
}

export interface ParityResult {
  pcb_path: string
  in_sync: boolean
  issue_count: number
  issues: ParityIssue[]
  checked_at: string
}

/** Async route: runs `kicad-cli pcb drc`, a real subprocess. */
export async function checkSchematicParity(pcbPath: string): Promise<ParityResult> {
  const handle = await submitJob<ParityResult>('kicad.check_schematic_parity', {
    pcb_path: pcbPath,
  })
  return handle.result
}
