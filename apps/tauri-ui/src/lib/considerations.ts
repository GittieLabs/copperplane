import { submitJob } from './ipc'

/** A consideration -- `SPEC-210` §2.1. */
export interface Consideration {
  id: string
  type: string
  domain: string
  claim_class: 'computed' | 'cited' | 'judgement'
  trigger: { kind: string; ref: string; parts?: string }
  explanation: string
  state: 'raised' | 'answered' | 'satisfied' | 'dismissed'
  /** `SPEC-210` §2.1: where a `cited` claim's fact came from — a standard, a
   *  datasheet page. `considerations.make` refuses to build a cited claim
   *  without one, and refuses a computed claim that carries one, so this is
   *  null exactly when the class says it should be. */
  source: { ref: string; title?: string; note?: string } | null
  /** `SPEC-210` §2.0.1: the calculation behind a claim that rests on one. The
   *  explanation already reads the sum out in prose, so this is here for a
   *  surface that wants to show its working separately -- `SPEC-211` §2.6
   *  leaves inline-or-on-demand open. */
  arithmetic?: Record<string, unknown> | null
}

export interface ConsiderationsResult {
  needs_attention: Consideration[]
  /** `SPEC-343` §2.7: what a pack checked and found correct. The finding that
   *  was NOT raised, which is the only baseline honest reinforcement has. */
  cleared: Consideration[]
  /** The packs that actually ran. What makes the "not checked" line honest, and
   *  keeps it honest as packs are added -- derived from the registry rather
   *  than written once and left to rot. */
  checked: string[]
  source_path: string | null
  reason: string | null
}

/** `SPEC-343` §2.7. Async-registered on the daemon (a kicad-cli netlist
 *  export), so this goes through submitJob rather than a plain dispatch. */
export async function projectConsiderations(projectName: string): Promise<ConsiderationsResult> {
  const handle = await submitJob<ConsiderationsResult>('project.considerations', { name: projectName })
  return handle.result
}
