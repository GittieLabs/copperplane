import type { ConversationTurn, ExportHistoryEntry, Project } from '../lib/projects'
import { STATUS_AREA_LABELS, buildAreaStatuses, mergeActivityFeed } from '../lib/overview'

/** SPEC-313/CTX-313.1: the Overview tab's own per-project dashboard --
 * real status cards (honest about which areas have no persisted result
 * yet) plus a merged, time-ordered activity feed. Purely presentational;
 * `project`/`chatHistory` are already loaded by `Overview`'s own
 * effects, so this component fetches nothing itself. */
export function OverviewDashboard({
  project,
  chatHistory,
}: {
  project: Project | null
  chatHistory: ConversationTurn[]
}) {
  const statuses = buildAreaStatuses(project?.last_results)
  const exportHistory: ExportHistoryEntry[] = project?.export_history ?? []
  const feed = mergeActivityFeed(chatHistory, exportHistory)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-2">
        {statuses.map((status) => (
          <div
            key={status.area}
            data-testid={`status-card-${status.area}`}
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          >
            <p className="text-xs font-medium text-neutral-300">{STATUS_AREA_LABELS[status.area]}</p>
            {status.checked ? (
              <p className="text-xs text-emerald-400">{status.summary ?? 'Checked'}</p>
            ) : (
              <p className="text-xs text-neutral-500">Not yet checked this session</p>
            )}
          </div>
        ))}
      </div>

      {feed.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-neutral-300">Activity</p>
          <ul className="flex flex-col gap-1" data-testid="activity-feed">
            {feed.map((item, index) => (
              <li key={index} className="text-xs text-neutral-400">
                {item.summary}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
