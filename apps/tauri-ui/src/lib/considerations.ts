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
