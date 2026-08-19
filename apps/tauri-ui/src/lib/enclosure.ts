import { open as openDialog, save as saveDialog } from '@tauri-apps/plugin-dialog'
import { dispatch, submitJob, type JobHandle } from './ipc'

/** Mirrors `daemon.py`'s real `freecad_generate_enclosure` params
 * (CTX-109.1, `pcb_path` added by CTX-310.1/SPEC-310). Mode selection is
 * explicit, in the daemon's own fixed priority order: `width`+`depth`
 * (manual) > `pcb_path` (file) > live board (board-driven, requires a
 * live KiCad connection) -- supplying more than one is never
 * ambiguous, since the daemon route only ever picks the highest-priority
 * one present. The four `*_mm` geometry params are all optional,
 * matching the same defaults the daemon route itself applies. */
export interface EnclosureParams {
  height: number
  width?: number
  depth?: number
  pcb_path?: string
  wall_thickness_mm?: number
  clearance_mm?: number
  fillet_radius_mm?: number
  standoff_height_mm?: number
  /** CTX-311.2: board-driven mode only -- the daemon route raises a
   * clean error if combined with `width`/`depth` (manual mode has no
   * open top for a lid to close). */
  lid?: boolean
  /** Defaults to `wall_thickness_mm` on the daemon side when omitted. */
  lid_thickness_mm?: number
}

/** Mirrors `freecad_generate_enclosure`'s real return shape.
 * `unrecognized_holes` is always present (possibly empty).
 * `lid_glb_path`/`lid_step_path` (CTX-311.2) only appear when
 * `lid: true` was requested. `no_mounting_holes_found` (CTX-311.1) only
 * appears in file/live mode -- manual mode has no board data to have
 * found holes on.
 *
 * CTX-311.13: Generate itself no longer persists anything -- the real,
 * confirmed, live bug this used to have (the frontend always supplied
 * `project_name`, so every single Generate silently wrote a stale-prone
 * Artifact record) is fixed by removing the concept entirely. There is
 * no more `artifact_id` here; `exportEnclosure` below is the one real,
 * explicit "keep this" action, and it needs no artifact bookkeeping of
 * its own -- the exported file living at a location the user chose is
 * the persistence. */
export interface EnclosureResult {
  glb_path: string
  step_path: string
  unrecognized_holes: { x_mm: number; y_mm: number; diameter_mm: number; recognized: false }[]
  no_mounting_holes_found?: boolean
  lid_glb_path?: string
  lid_step_path?: string
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

/** CTX-311.13: which already-generated real source file(s) to export --
 * `'lid'`/`'combined'` only make sense once `EnclosureResult.lid_step_
 * path`/`lid_glb_path` actually exist. */
export type ExportParts = 'combined' | 'body' | 'lid'

/** STEP/STL/GLB are all already produced by a real Generate; native
 * FreeCAD (`.FCStd`) is new, real, `doc.saveAs`-based export (CTX-311.13)
 * -- always the whole design when a lid exists, regardless of `parts`
 * (see `freecad_bridge._export_fcstd`'s own docstring). */
export type ExportFormat = 'step' | 'stl' | 'glb' | 'fcstd'

const _EXPORT_FORMAT_EXTENSIONS: Record<ExportFormat, string[]> = {
  step: ['step', 'stp'],
  stl: ['stl'],
  glb: ['glb'],
  fcstd: ['FCStd'],
}

/** Mirrors `daemon.py`'s real `freecad_export_enclosure` params. Every
 * source path is optional here the same way it is on the daemon side --
 * the caller only ever needs to supply the ones `parts`/`fmt` actually
 * require, straight from an already-completed `EnclosureResult`. */
export interface ExportEnclosureParams {
  parts: ExportParts
  fmt: ExportFormat
  dest_path: string
  glb_path?: string
  step_path?: string
  lid_glb_path?: string
  lid_step_path?: string
}

export interface ExportEnclosureResult {
  dest_path: string
}

/** The real, explicit Save/Export action (CTX-311.13, `SPEC-311` §2) --
 * `freecad.export_enclosure` is a real async route (some formats/parts
 * combinations are a real `freecadcmd` subprocess), so this returns a
 * `JobHandle` exactly like `generateEnclosure` above. Never regenerates
 * geometry -- every source path here should come straight from an
 * already-completed `EnclosureResult`. */
export async function exportEnclosure(
  params: ExportEnclosureParams,
): Promise<JobHandle<ExportEnclosureResult>> {
  return submitJob<ExportEnclosureResult>('freecad.export_enclosure', { ...params })
}

/** A real native "Save As" dialog (CTX-311.13) -- every other dialog use
 * in this codebase before this was `open()`; `save()` is a genuinely new
 * call for this app, gated behind the new `dialog:allow-save` capability.
 * `defaultPath` (when given, e.g. the current project's own real
 * directory from `getProjectDirectory` below, plus a sensible filename)
 * pre-fills both the folder and name while still letting the user browse
 * elsewhere in the same dialog. Returns `null` on cancel, not an error --
 * matching `pickPcbFile`'s own convention above. */
export async function pickExportDestination(
  fmt: ExportFormat,
  defaultPath?: string,
): Promise<string | null> {
  const selected = await saveDialog({
    filters: [{ name: fmt.toUpperCase(), extensions: _EXPORT_FORMAT_EXTENSIONS[fmt] }],
    defaultPath,
  })
  return typeof selected === 'string' ? selected : null
}

/** CTX-311.13: the current project's own real directory on disk --
 * defaults the Export dialog to the project's own folder instead of
 * wherever the OS last remembered. A fast IPC lookup, no subprocess, so
 * plain `dispatch`, not `submitJob` (matching `boardAdvisor.ts`'s own
 * `listOpenBoards` precedent for a sync route). */
export async function getProjectDirectory(projectName: string): Promise<string> {
  const response = await dispatch('project.get_directory', { name: projectName })
  if (response.error) {
    throw new Error(response.error.message)
  }
  return (response.result as { path: string }).path
}

export interface ExportBoardGlbResult {
  glb_path: string
}

/** CTX-311.15: the real, assembled board's own `.glb` -- substrate plus
 * every real component's real 3D model, positioned by KiCad itself --
 * the visual source for the board-inside-enclosure fit check
 * `EnclosureViewer.tsx` composites. Real `kicad-cli` subprocess
 * (`kicad.export_board_glb` is in `ASYNC_ROUTES`), so this returns a
 * `JobHandle` like `generateEnclosure`/`exportEnclosure` above.
 * Real-origins the export server-side to the board's own bounding-box
 * corner -- the caller needs no board outline data of its own to place
 * it correctly inside the enclosure, only the enclosure's own already-
 * known wall/clearance/standoff parameters. */
export async function exportBoardGlb(pcbPath: string): Promise<JobHandle<ExportBoardGlbResult>> {
  return submitJob<ExportBoardGlbResult>('kicad.export_board_glb', { pcb_path: pcbPath })
}

export interface ComponentHeightsResult {
  known: { reference: string; height_mm: number }[]
  unknown: string[]
}

/** CTX-311.15: which real reference designators have no resolvable 3D
 * model -- `kicad-cli`'s own board `.glb` export (above) silently omits
 * exactly these components, so this is what lets the board overlay
 * name them honestly (SPEC-311 §5) instead of leaving their absence
 * unexplained. Live-only (no `pcb_path` parameter -- reads whatever
 * board is currently open in KiCad); the caller is responsible for only
 * calling this when that's known to be the same board being shown. */
export async function getComponentHeights(): Promise<JobHandle<ComponentHeightsResult>> {
  return submitJob<ComponentHeightsResult>('kicad.get_component_heights', {})
}
