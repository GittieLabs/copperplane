import { useState } from 'react'

import { describeDegraded } from '../lib/degradedModules'
import type { DaemonCapabilities } from '../lib/settings'

/** SPEC-407 §5: the app says its own build is at fault.
 *
 *  Deliberately **not** shaped like `RequirementsBanner`, which is about
 *  configuration a user can fix and therefore never dismisses. This is about a
 *  broken build: *"there is no retry button, because nothing the user can do at
 *  runtime will fix a bad build."* Keeping an unfixable notice on screen
 *  forever is nagging without a remedy, so it can be dismissed — the spec asks
 *  for exactly that.
 *
 *  It does not block. KiCad, FreeCAD, the library and the viewer may all still
 *  be real; §5 is explicit that this is not a crash dialog. */
export function DegradedBuildNotice({ capabilities }: { capabilities: DaemonCapabilities | null }) {
  const [dismissed, setDismissed] = useState(false)
  const lost = describeDegraded(capabilities?.degraded_modules)

  if (lost.length === 0 || dismissed) return null

  return (
    <div
      className="flex flex-col gap-2 border-b border-danger/40 bg-danger/10 px-4 py-3 text-xs"
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium text-fg-bright">
          This build of Copperplane started with reduced capability. The app is working correctly;
          the build it came from is incomplete.
        </p>
        <button
          type="button"
          className="shrink-0 text-fg-muted hover:text-fg-secondary"
          onClick={() => setDismissed(true)}
        >
          Dismiss
        </button>
      </div>

      <ul className="flex list-disc flex-col gap-1 pl-4">
        {lost.map(({ module, plain }) => (
          <li key={module} className="text-fg-secondary">
            {plain ?? (
              <>
                The <code>{module}</code> component did not load. This version of the app has no
                description for it.
              </>
            )}
            {plain && <span className="text-fg-muted"> ({module})</span>}
          </li>
        ))}
      </ul>

      <p className="text-fg-muted">
        Nothing you can change here will fix this — it needs a rebuilt sidecar.
        {capabilities?.log_path && (
          <>
            {' '}The reason is in the daemon log:{' '}
            <span className="break-all text-fg-tertiary">{capabilities.log_path}</span>
          </>
        )}
      </p>
    </div>
  )
}
