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
import type { BoardCandidate } from './boardAdvisor'

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
  /** The components these envelopes were computed from. Rendered as the
   *  table, so the rows and the summary above them are the same set by
   *  construction rather than by two calls staying in step. */
  components: SchematicComponent[]
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


/** SPEC-325 §2.1 applied to the PCB and Enclosure tabs.
 *
 *  Board discovery used to run only through `kicad.list_open_boards`, which
 *  talks to KiCad's IPC and therefore needs KiCad running with a board
 *  focused — three preconditions for a fact that is sitting in a file. The
 *  Schematic tab stopped needing KiCad open at SPEC-325; the other two tabs
 *  kept asking for it, for no reason that survives inspection: every route
 *  they actually call (`kicad.check_board`, `freecad.generate_enclosure`)
 *  takes an explicit path and reads the file.
 *
 *  So: if a project has a linked `.kicad_pro`, its board is knowable with
 *  KiCad closed. Returns `null` when nothing is linked, which is the one
 *  case that genuinely has nothing to fall back on. */
export async function linkedProjectBoard(projectName: string): Promise<BoardCandidate | null> {
  const { loadProject } = await import('./projects')
  try {
    const project = await loadProject(projectName)
    if (!project.kicad_project_path) return null
    const files = await resolveKicadProject(project.kicad_project_path)
    if (!files.pcb_path) return null
    return { path: files.pcb_path, label: files.pcb_path.split('/').pop() ?? files.pcb_path }
  } catch {
    // A project with no link, or a .kicad_pro that has moved. Neither is an
    // error worth surfacing here -- the caller's existing "open KiCad"
    // guidance is still the honest fallback.
    return null
  }
}

/** SPEC-325 §2.1 for the Schematic tab, the last one still asking for KiCad.
 *
 *  `kicad.list_project_schematics` derives a schematic from whichever board
 *  KiCad currently has open, because KiCad's IPC has never implemented
 *  schematic listing at all -- which is why the guidance told users to open
 *  the PCB Editor to find their *schematic*. A linked `.kicad_pro` names it
 *  outright. */
export async function linkedProjectSchematic(
  projectName: string,
): Promise<{ path: string; label: string } | null> {
  const { loadProject } = await import('./projects')
  try {
    const project = await loadProject(projectName)
    if (!project.kicad_project_path) return null
    const files = await resolveKicadProject(project.kicad_project_path)
    if (!files.schematic_path) return null
    const path = files.schematic_path
    return { path, label: path.split('/').pop() ?? path }
  } catch {
    return null
  }
}

/** SPEC-334: what a footprint actually is, read from its own `.kicad_mod`.
 *
 *  A user cannot tell `P2.54mm_Vertical` from `P2.00mm_Horizontal` by name, and
 *  KiCad's own file already says: "Through hole straight pin header, 1x04,
 *  2.54mm pitch, single row". Measured before being relied on — 400 of 400
 *  sampled KiCad footprints carry a non-empty description. */
export interface FootprintDetail {
  footprint_id: string
  library: string | null
  name: string
  /** The library author's own words. `null` for a library that carries none. */
  description: string | null
  tags: string[]
  /** Whatever URL the description contained. Surfaced, never followed. */
  datasheet_url: string | null
  pad_count: number | null
  mounting: string | null
  /** Plain-language readings of the naming conventions, silent about anything
   *  unrecognised rather than inventing one. */
  name_notes: string[]
  footprint_found: boolean
  courtyard: { x_mm: number; y_mm: number } | null
  model_ref: string | null
  model_path: string | null
  has_model: boolean
}

export async function describeFootprint(footprintId: string): Promise<FootprintDetail> {
  const handle = await submitJob<FootprintDetail>('kicad.describe_footprint', {
    footprint_id: footprintId,
  })
  return handle.result
}

/** SPEC-337: the `.kicad_pro` files directly inside a folder.
 *
 *  Setting a project folder used to say nothing about the KiCad project it
 *  obviously contained — leaving a project that read as linked, generated an
 *  enclosure with no mounting posts, and explained none of it. */
export interface ProjectsInDirectory {
  directory: string
  projects: string[]
  count: number
}

export async function findProjectsInDirectory(directory: string): Promise<ProjectsInDirectory> {
  const handle = await submitJob<ProjectsInDirectory>('kicad.find_projects_in_directory', {
    directory,
  })
  return handle.result
}
