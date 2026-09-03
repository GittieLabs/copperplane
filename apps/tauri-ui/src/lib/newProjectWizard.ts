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
