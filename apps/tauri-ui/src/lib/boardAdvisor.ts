import { invoke } from '@tauri-apps/api/core'
import { open as openDialog } from '@tauri-apps/plugin-dialog'
import { dispatch, submitJob } from './ipc'

/** Mirrors component_pipeline.py's explain_violations output shape
 * (CTX-309.1) -- each real KiCad violation enriched with a real
 * explanation/suggested_fix, plus items/sheet_path passed straight
 * through from kicad-cli's own real JSON. */
export interface Violation {
  description: string
  severity: string
  type: string
  items: unknown[]
  sheet_path?: string
  explanation: string
  suggested_fix: string
}

export interface CheckResult {
  violations: Violation[]
  summary: string
  truncated_count: number
  source_path: string
  /** KiCad's own counts, per kind, independent of the LLM explanation
   *  path. Reported so the UI can never say "no violations" about a board
   *  KiCad found problems on: `violations` is empty on the maintainer's
   *  own board while `unconnected_count` is 18, every one severity error.
   *  Optional because a result cached before SPEC-326 §2.7 lacks them. */
  violation_count?: number
  unconnected_count?: number
  parity_count?: number
}

export interface BoardCandidate {
  path: string
  label: string
}
export interface NoBoardOpen {
  status: 'no_board_open'
}
export interface BoardsFound {
  status: 'boards_found'
  candidates: BoardCandidate[]
}
export type ListOpenBoardsResult = NoBoardOpen | BoardsFound

/** kicad.list_open_boards (CTX-309.4): a real, cheap, read-only lookup of
 * every board currently open in KiCad -- feeds a real "here's what's
 * open, pick one" picker, always shown before any check runs (even for a
 * single open board), rather than the old CTX-309.3 behavior of silently
 * auto-resolving whichever one board happened to be open. Real user
 * feedback exercising the actual running app found that opaque -- a
 * novice never saw *which* board was about to be checked. A fast IPC
 * lookup with no subprocess/LLM call, so plain `dispatch`, not
 * `submitJob` (matching settings.ts's own `kicad.get_version` precedent
 * for a sync route). */
export async function listOpenBoards(): Promise<ListOpenBoardsResult> {
  const response = await dispatch('kicad.list_open_boards', {})
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as ListOpenBoardsResult
}

/** CTX-309.4: launches the real KiCad desktop app (core/tauri-rust's
 * `open_kicad` command) -- real user feedback found the old "no board
 * open" guidance still left a novice stuck not knowing where to find
 * KiCad at all. Verified working on macOS directly on this dev machine;
 * not verified on Windows/Linux (see the Rust command's own doc
 * comment) -- if it fails there, the caller's existing walkthrough text
 * is still the real fallback. */
export async function openKicad(): Promise<void> {
  await invoke('open_kicad')
}

/** kicad.check_board (SPEC-309/CTX-309.4) always takes an explicit,
 * user-picked path now -- kicad.list_open_boards above owns showing the
 * real picker; this route no longer auto-resolves or returns a
 * "pick one" state itself. A real subprocess plus a real LLM call, both
 * genuinely multi-second, so submitJob -- matching every other real
 * async kicad and component route's own precedent. */
export async function checkBoard(pcbPath: string): Promise<CheckResult> {
  const handle = await submitJob<CheckResult>('kicad.check_board', { pcb_path: pcbPath })
  return handle.result
}

export interface SchematicCandidate {
  path: string
  label: string
}
export interface NoSchematicFound {
  status: 'no_schematic_found'
}
export interface SchematicsFound {
  status: 'schematics_found'
  candidates: SchematicCandidate[]
}
export type ListProjectSchematicsResult = NoSchematicFound | SchematicsFound

/** kicad.list_project_schematics: real user feedback asked why
 * Schematic checking couldn't work like Board checking, with a live
 * list instead of a blind file dialog. KiCad's IPC server has no
 * handler for listing open schematics at all -- confirmed live,
 * unconditionally, unlike the PCB case -- so this derives each
 * currently open board's own project's root schematic path instead,
 * filtered to ones that actually exist on disk (never a guessed path
 * presented as real). Sync, like listOpenBoards, for the same reason. */
export async function listProjectSchematics(): Promise<ListProjectSchematicsResult> {
  const response = await dispatch('kicad.list_project_schematics', {})
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as ListProjectSchematicsResult
}

/** A manual fallback for when no schematic could be derived from an
 * open board (nothing open, or a genuinely standalone schematic not
 * tied to any board currently open in KiCad) -- mirrors settings.ts's
 * own folder-picker pattern for storage_root_override. Returns null on
 * cancel, not an error -- the user closing the dialog is a normal,
 * expected outcome. */
export async function pickSchematicFile(): Promise<string | null> {
  const selected = await openDialog({
    filters: [{ name: 'KiCad Schematic', extensions: ['kicad_sch'] }],
  })
  return typeof selected === 'string' ? selected : null
}

export async function checkSchematic(schPath: string): Promise<CheckResult> {
  const handle = await submitJob<CheckResult>('kicad.check_schematic', { sch_path: schPath })
  return handle.result
}
