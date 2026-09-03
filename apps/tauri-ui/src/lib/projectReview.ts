import { checkBoard, checkSchematic, type CheckResult } from './boardAdvisor'
import {
  checkSchematicParity, componentEnvelopes, resolveKicadProject,
  type EnvelopeResult, type ParityResult,
} from './kicadProject'

/** SPEC-335 step 4: the four checks a new project gets, run against explicit
 *  file paths rather than a saved project.
 *
 *  That matters for more than tidiness. Every route here takes paths, so the
 *  review can run before the project record exists — which is what keeps
 *  "nothing is written until the last step" true through the whole wizard.
 *
 *  They are four independent async jobs, so each result lands on its own.
 *  **This needs no streaming support in AgentFlow**: only token-by-token
 *  rendering of the final summary would, and the summary is a single ordinary
 *  call. */

export type ReviewCheckKey = 'parity' | 'components' | 'erc' | 'drc'

export interface ReviewCheckState {
  key: ReviewCheckKey
  label: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  /** One line, in the user's terms. */
  summary?: string
  /** Why it could not run. Never rendered as a pass. */
  error?: string
}

export const REVIEW_CHECKS: { key: ReviewCheckKey; label: string }[] = [
  { key: 'parity', label: 'Schematic and board agree' },
  { key: 'components', label: 'Board components' },
  { key: 'erc', label: 'Schematic check (ERC)' },
  { key: 'drc', label: 'Board check (DRC)' },
]

function parityLine(r: ParityResult): string {
  return r.in_sync
    ? 'Your schematic and board match.'
    : `${r.issue_count} difference${r.issue_count === 1 ? '' : 's'} between your schematic and board — ` +
      'run Tools → Update PCB from Schematic in KiCad if the schematic is the version you want.'
}

function componentsLine(r: EnvelopeResult): string {
  const parts = [`${r.components.length} component${r.components.length === 1 ? '' : 's'}`]
  const noModel = r.components.filter((c) => c.footprint && !c.has_model).length
  if (noModel > 0) parts.push(`${noModel} with no 3D model`)
  if (r.min_interior_height_mm != null) {
    parts.push(`enclosure needs at least ${r.min_interior_height_mm}mm inside`)
  }
  if (r.unknown > 0) parts.push(`${r.unknown} with no known height`)
  return parts.join(', ') + '.'
}

function checkLine(r: CheckResult, kind: 'ERC' | 'DRC'): string {
  const counts: string[] = []
  const violations = r.violation_count ?? r.violations.length
  counts.push(`${violations} violation${violations === 1 ? '' : 's'}`)
  if (r.unconnected_count) counts.push(`${r.unconnected_count} unconnected item${r.unconnected_count === 1 ? '' : 's'}`)
  if (r.parity_count) counts.push(`${r.parity_count} schematic mismatch${r.parity_count === 1 ? '' : 'es'}`)
  const total = violations + (r.unconnected_count ?? 0) + (r.parity_count ?? 0)
  return total === 0 ? `${kind} found nothing.` : `${kind}: ${counts.join(', ')}.`
}

/** Runs the four checks, reporting each as it lands.
 *
 *  Each is caught on its own: one failing check reports itself and does not
 *  cost the user the other three — the same degrade-rather-than-fail rule
 *  `_explain_or_report_plainly` follows on the daemon side. */
export async function runProjectReview(
  kicadProjectPath: string | null,
  onUpdate: (state: ReviewCheckState) => void,
): Promise<void> {
  if (!kicadProjectPath) {
    for (const c of REVIEW_CHECKS) {
      onUpdate({ ...c, status: 'skipped', summary: 'No KiCad project linked, so this cannot run.' })
    }
    return
  }

  let files
  try {
    files = await resolveKicadProject(kicadProjectPath)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    for (const c of REVIEW_CHECKS) onUpdate({ ...c, status: 'failed', error: message })
    return
  }

  const run = async (
    key: ReviewCheckKey,
    label: string,
    needs: string | null,
    missing: string,
    work: () => Promise<string>,
  ) => {
    if (!needs) {
      onUpdate({ key, label, status: 'skipped', summary: missing })
      return
    }
    onUpdate({ key, label, status: 'running' })
    try {
      onUpdate({ key, label, status: 'done', summary: await work() })
    } catch (err) {
      onUpdate({ key, label, status: 'failed', error: err instanceof Error ? err.message : String(err) })
    }
  }

  // Started together so the slowest does not gate the others; each renders as
  // it resolves.
  await Promise.all([
    run('parity', 'Schematic and board agree', files.pcb_path, 'This project has no board yet.',
      async () => parityLine(await checkSchematicParity(files.pcb_path!))),
    run('components', 'Board components', files.pcb_path ?? files.schematic_path,
      'This project has no schematic or board yet.',
      async () => componentsLine(await componentEnvelopes(files.schematic_path, files.pcb_path, {}))),
    run('erc', 'Schematic check (ERC)', files.schematic_path, 'This project has no schematic yet.',
      async () => checkLine(await checkSchematic(files.schematic_path!), 'ERC')),
    run('drc', 'Board check (DRC)', files.pcb_path, 'This project has no board yet.',
      async () => checkLine(await checkBoard(files.pcb_path!), 'DRC')),
  ])
}
