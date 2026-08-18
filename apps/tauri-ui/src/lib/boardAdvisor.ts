import { open as openDialog } from '@tauri-apps/plugin-dialog'
import { submitJob } from './ipc'

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
}

/** kicad.check_board's real, structured three-way envelope (CTX-309.3)
 * when no explicit pcbPath is given -- replaces the old always-a-
 * CheckResult-or-throws contract, since "nothing open" and "more than
 * one open" are both real, normal, expected states worth their own
 * guided UI, not an exception to catch and stringify. */
export interface CheckBoardOk extends CheckResult {
  status: 'ok'
}
export interface NoBoardOpen {
  status: 'no_board_open'
}
export interface BoardCandidate {
  path: string
  label: string
}
export interface NeedsBoardSelection {
  status: 'needs_selection'
  candidates: BoardCandidate[]
}
export type CheckBoardResult = CheckBoardOk | NoBoardOpen | NeedsBoardSelection

/** kicad.check_board (CTX-309.1) auto-resolves the currently open board
 * when pcbPath is omitted -- a real live IPC call, only reachable this
 * way since there's no direct "give me the open board's path" UI
 * action; the daemon route does that resolution itself. A real
 * subprocess plus a real LLM call, both genuinely multi-second, so
 * submitJob -- matching every other real async kicad and component
 * route's own precedent. */
export async function checkBoard(pcbPath?: string): Promise<CheckBoardResult> {
  const handle = await submitJob<CheckBoardResult>(
    'kicad.check_board',
    pcbPath ? { pcb_path: pcbPath } : {},
  )
  return handle.result
}

/** SPEC-309 §2's own confirmed, real finding: live IPC has no
 * schematic-document resolution capability at all -- unlike
 * checkBoard, this always needs an explicit path, so the UI must ask
 * for one via a real native file picker (mirrors settings.ts's own
 * folder-picker pattern for storage_root_override) rather than ever
 * attempting auto-resolution. Returns null on cancel, not an error --
 * the user closing the dialog is a normal, expected outcome. */
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
