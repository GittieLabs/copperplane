import { submitJob } from './ipc'

/** SPEC-335's step sequence, kept out of the component file so the component
 *  module exports only a component (the same split `lib/markdown.tsx` uses).
 *
 *  The order is the maintainer's: name, then the KiCad project — because
 *  nothing in the app works without one — then intent by conversation, then a
 *  real review of what was found. */
export const WIZARD_STEPS = [
  { key: 'name', title: 'Name your project' },
  { key: 'kicad', title: 'Link your KiCad project' },
  { key: 'intent', title: 'What are you building?' },
  { key: 'review', title: 'Reviewing your project' },
] as const

export type WizardStepKey = (typeof WIZARD_STEPS)[number]['key']

/** Why a name cannot be used, or `null` when it can.
 *
 *  A duplicate must be refused rather than allowed through: `save_project`
 *  keys on the name, so creating a second "test 1" would write into the first
 *  one's record rather than making a new project. */
export function nameProblem(name: string, existing: string[]): string | null {
  const trimmed = name.trim()
  if (!trimmed) return null
  if (existing.includes(trimmed)) {
    return `You already have a project called "${trimmed}".`
  }
  return null
}

/** Summarises what the user said they are building, so they can confirm the
 *  app understood before it is stored as the project's intent.
 *
 *  A plain `llm.chat` rather than the project agent: the project does not
 *  exist yet, and creating one just to ask it a question would undo the
 *  "nothing is written until the last step" guarantee that makes Cancel safe.
 */
export async function summariseIntent(description: string): Promise<string> {
  const handle = await submitJob<{ text: string }>('llm.chat', {
    prompt:
      'A maker is starting a PCB project and described what they are building. ' +
      'Restate it in one or two plain sentences, as the project goal. Keep their ' +
      'own words and specifics where you can. Do not add requirements they did not ' +
      'state, do not ask questions, and reply with the restatement only.\n\n' +
      description,
    history: [],
  })
  return (await handle.result).text.trim()
}
