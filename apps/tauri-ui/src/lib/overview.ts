import type { ConversationTurn, ExportHistoryEntry, Project } from './projects'

/** CTX-313.1: the Overview dashboard's own status-card area keys --
 * deliberately reuses `App.tsx`'s existing `Area` union values
 * (`'components' | 'schematic' | 'pcb' | 'enclosure'`, minus `'overview'`
 * itself) rather than inventing new names, since these are exactly the
 * area tabs a status card summarizes. */
export type StatusAreaKey = 'pcb' | 'schematic' | 'enclosure' | 'components'

export const STATUS_AREA_ORDER: StatusAreaKey[] = ['pcb', 'schematic', 'enclosure', 'components']

export const STATUS_AREA_LABELS: Record<StatusAreaKey, string> = {
  pcb: 'PCB',
  schematic: 'Schematic',
  enclosure: 'Enclosure',
  components: 'Components',
}

export interface AreaStatus {
  area: StatusAreaKey
  /** Whether `Project.last_results` has a real entry for this area yet --
   * only `enclosure` does today (`App.tsx`'s `handleExportSuccess`,
   * `CTX-312.1`). `false` renders an honest "not yet checked" state,
   * never a fake pass/fail. */
  checked: boolean
  summary?: string
}

/** Real shape `handleExportSuccess` already writes into
 * `last_results.enclosure` (`App.tsx`) -- the one area with real data
 * today. Narrowed here rather than trusting `last_results`'s own loose
 * `Record<string, unknown>` type blindly. */
interface EnclosureLastResult {
  glb_path?: string
  step_path?: string
  wall_thickness_mm?: number
  clearance_mm?: number
  standoff_height_mm?: number
}

function isEnclosureLastResult(value: unknown): value is EnclosureLastResult {
  return typeof value === 'object' && value !== null
}

/** CTX-313.1 Phase 2: builds one status entry per area tab from
 * `Project.last_results`. Honest by construction -- an absent key means
 * `checked: false`, never inferred as "ok" or silently skipped. */
export function buildAreaStatuses(lastResults: Project['last_results']): AreaStatus[] {
  return STATUS_AREA_ORDER.map((area) => {
    const result = lastResults?.[area]
    if (result === undefined || result === null) {
      return { area, checked: false }
    }
    if (area === 'enclosure' && isEnclosureLastResult(result)) {
      const parts: string[] = []
      if (typeof result.wall_thickness_mm === 'number') parts.push(`${result.wall_thickness_mm}mm walls`)
      if (typeof result.standoff_height_mm === 'number') parts.push(`${result.standoff_height_mm}mm standoffs`)
      return { area, checked: true, summary: parts.length > 0 ? parts.join(', ') : 'Generated' }
    }
    return { area, checked: true }
  })
}

export interface ActivityFeedItem {
  kind: 'chat' | 'export'
  /** `null` for a conversation turn written before `CTX-313.1` (no
   * `timestamp` field existed yet) -- sorted to the end, not treated as
   * "now" or dropped. Real, named migration gap; see the context's own
   * Plan Drift. */
  timestamp: string | null
  summary: string
}

/** CTX-313.1 Phase 3: merges the two real, already-persisted timelines
 * (`conversation.jsonl` turns and `Project.export_history`) into one
 * descending time-ordered feed. Pure function, no new daemon route --
 * both inputs are already loaded by the time Overview renders. */
export function mergeActivityFeed(turns: ConversationTurn[], exportHistory: ExportHistoryEntry[]): ActivityFeedItem[] {
  const chatItems: ActivityFeedItem[] = turns.map((turn) => ({
    kind: 'chat',
    timestamp: turn.timestamp ?? null,
    summary: turn.role === 'user' ? `You: ${turn.content}` : `Assistant: ${turn.content}`,
  }))
  const exportItems: ActivityFeedItem[] = exportHistory.map((entry) => ({
    kind: 'export',
    timestamp: entry.exported_at,
    summary: `Exported ${entry.area} to ${entry.dest_path}`,
  }))
  return [...chatItems, ...exportItems].sort((a, b) => {
    if (a.timestamp === null && b.timestamp === null) return 0
    if (a.timestamp === null) return 1
    if (b.timestamp === null) return -1
    return b.timestamp.localeCompare(a.timestamp)
  })
}
