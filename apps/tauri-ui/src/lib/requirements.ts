import type { DaemonCapabilities } from './settings'

/** SPEC-336 §3: what is missing, what it stops working, and how to fix it.
 *
 *  The spec is explicit that this must be specific — *"KiCad not found, so
 *  board checks and the enclosure cannot run"*, never a generic "setup
 *  incomplete". That is not a style preference: a generic banner sends the
 *  user to a settings screen to guess, which is the experience this spec
 *  exists to end.
 *
 *  Derived from `daemon.get_capabilities`, so it is always current rather
 *  than a record of what was true when onboarding ran. The wizard records
 *  that setup was *offered*; this records what is *true*. */
export interface Requirement {
  /** Stable id, for keys and for deciding which setup step to reopen. */
  id: 'kicad' | 'freecad' | 'provider'
  title: string
  /** What stops working. Named features, not a severity word. */
  consequence: string
  /** What the user does about it. */
  action: string
  /** Where the daemon looked, when it can say. Shown so a user with the tool
   *  installed elsewhere can see that the app looked somewhere else. */
  detail: string | null
}

export function missingRequirements(caps: DaemonCapabilities | null): Requirement[] {
  if (!caps) return []
  const missing: Requirement[] = []

  if (!caps.kicad_cli_available) {
    missing.push({
      id: 'kicad',
      title: 'KiCad was not found',
      consequence:
        'Board and schematic checks cannot run, component lists cannot be read, and an enclosure cannot be measured from your board.',
      action: 'Install KiCad 9 or later, or point Copperplane at it if it is installed somewhere unusual.',
      // A configured path that does not exist is the likeliest cause once a
      // picker exists, and a bare "not found" would send the user looking for
      // a KiCad they have actually installed.
      detail: caps.kicad_cli_path_source === 'override'
        ? `The configured path did not work: ${caps.kicad_cli_error ?? 'unknown error'}`
        : caps.kicad_cli_error,
    })
  }

  if (!caps.freecad_available) {
    missing.push({
      id: 'freecad',
      title: 'FreeCAD was not found',
      consequence: 'Enclosures cannot be generated or exported.',
      action: 'Install FreeCAD, or point Copperplane at it if it is installed somewhere unusual.',
      detail: caps.freecad_error,
    })
  }

  if (caps.llm_providers.length === 0) {
    missing.push({
      id: 'provider',
      title: 'No AI provider is configured',
      consequence:
        'Reviews, part lookups and the project chat cannot run. Everything that reads your files still works.',
      action: 'Add an API key for one provider.',
      detail: null,
    })
  }

  return missing
}

/** True when the app can do everything it claims. Deliberately not the
 *  inverse of "onboarding was completed": a user who finished the wizard and
 *  later uninstalled KiCad is not ready, and one who skipped every step and
 *  already had both tools is. */
export function isFullyConfigured(caps: DaemonCapabilities | null): boolean {
  return caps !== null && missingRequirements(caps).length === 0
}
