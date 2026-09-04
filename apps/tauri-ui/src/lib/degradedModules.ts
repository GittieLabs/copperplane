/** SPEC-407 §5: what a user loses when the daemon starts with a module missing.
 *
 *  `daemon.py` guards every optional import and records the failures. That
 *  degradation is correct — a missing module must not take the whole daemon
 *  down — and until now nothing in the app read it. So a build with, say, no
 *  `chat_agents` started cleanly, answered `daemon.ready`, and presented a
 *  perfectly healthy app whose AI features silently did nothing. §1 calls that
 *  worse than a crash: *"a crash sends you to the packaging; a healthy-looking
 *  daemon ... sends you hunting for a UI bug that does not exist."*
 *
 *  Each entry names the capability in the user's own terms, not the module's.
 *  A module with no entry is **named as itself** rather than glossed — KiCad
 *  and this app both gain modules, and inventing a description for one we do
 *  not recognise would be a confident guess in exactly the place a user is
 *  already confused. */
const _WHAT_IS_LOST: Record<string, string> = {
  chat_agents: 'The project chat and the AI reviews',
  llm_providers: 'Everything that uses AI — reviews, part lookups and the project chat',
  tool_registry: "The agents' ability to read your data while answering",
  component_pipeline: 'Creating a component from a part number',
  datasheet_guidance: 'Design guidance generated from a datasheet',
  datasheet_structure: 'Reading specific pages of a datasheet',
  context_index: 'Searching what the app has already learned about your parts and projects',

  kicad_cli: 'Board and schematic checks (DRC and ERC)',
  kicad_project: 'Linking a KiCad project, and everything read from it',
  kicad_board: 'Reading the components on your board',
  kicad_bridge: 'Talking to a running KiCad — reading your files still works',
  kicad_write: 'Writing a footprint into your KiCad library',
  kicad_pcb_import: 'Sizing an enclosure from your board file',
  fp_lib_table: "Searching KiCad's installed footprints",
  footprint_detail: "Explaining what a footprint's name means",
  community_libraries: 'Searching community footprint libraries',

  freecad_bridge: 'Generating and exporting enclosures',
  library_store: 'Saving and loading projects, and your parts library',
}

export interface LostCapability {
  module: string
  /** What the user cannot do. `null` when this app has no entry for the
   *  module — the module name is then shown as itself. */
  plain: string | null
}

export function describeDegraded(modules: string[] | undefined): LostCapability[] {
  return (modules ?? []).map((module) => ({ module, plain: _WHAT_IS_LOST[module] ?? null }))
}
