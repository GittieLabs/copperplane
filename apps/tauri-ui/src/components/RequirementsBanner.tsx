import { useState } from 'react'

import { missingRequirements, type Requirement } from '../lib/requirements'
import type { DaemonCapabilities } from '../lib/settings'

/** SPEC-336: the persistent notice that replaced the first draft's hard gate.
 *
 *  The maintainer's reasoning for removing the gate: *"Blocking the user may
 *  not be the answer. We could replace this with banner messages to let the
 *  user know about missing requirements and still let the user get to the main
 *  app and fix later."* That puts real weight here — this is the only thing
 *  standing between an unconfigured app and the "watching features fail one at
 *  a time" experience the spec exists to end.
 *
 *  So it collapses and never dismisses. SPEC-336 §3: *"A dismissible banner is
 *  the trap in a different costume ... whatever dismissal exists must keep a
 *  way back to the guided setup permanently visible."* Collapsed leaves a
 *  one-line strip that still carries the action. */
export function RequirementsBanner({
  capabilities,
  onOpenSetup,
  onRecheck,
}: {
  capabilities: DaemonCapabilities | null
  onOpenSetup: (requirementId: Requirement['id']) => void
  onRecheck?: () => void
}) {
  const [collapsed, setCollapsed] = useState(false)
  const missing = missingRequirements(capabilities)

  if (missing.length === 0) return null

  const summary = missing.map((m) => m.title.replace(' was not found', '').replace('No AI provider is configured', 'AI provider')).join(', ')

  if (collapsed) {
    return (
      <div
        className="flex items-center justify-between gap-3 border-b border-warning/40 bg-warning/10 px-4 py-1 text-xs"
        role="status"
      >
        <span className="text-fg-secondary">
          Setup incomplete: {summary}
        </span>
        <span className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            className="underline decoration-dotted underline-offset-2 text-fg-secondary hover:text-fg-bright"
            onClick={() => onOpenSetup(missing[0].id)}
          >
            Finish setting up
          </button>
          <button
            type="button"
            className="text-fg-muted hover:text-fg-secondary"
            onClick={() => setCollapsed(false)}
          >
            Show details
          </button>
        </span>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col gap-2 border-b border-warning/40 bg-warning/10 px-4 py-3 text-xs"
      role="status"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium text-fg-bright">
          {missing.length === 1
            ? 'One thing is missing before Copperplane can do everything'
            : `${missing.length} things are missing before Copperplane can do everything`}
        </p>
        {/* Collapse, not dismiss. There is no control here that makes this
            go away for good while the problem remains. */}
        <button
          type="button"
          className="shrink-0 text-fg-muted hover:text-fg-secondary"
          onClick={() => setCollapsed(true)}
        >
          Collapse
        </button>
      </div>

      <ul className="flex flex-col gap-2">
        {missing.map((requirement) => (
          <li key={requirement.id} className="flex flex-col gap-0.5">
            <p className="text-fg-secondary">
              <span className="font-medium text-fg-bright">{requirement.title}.</span>{' '}
              {requirement.consequence}
            </p>
            <p className="text-fg-muted">{requirement.action}</p>
            {requirement.detail && (
              <p className="break-all text-fg-faint">{requirement.detail}</p>
            )}
            <button
              type="button"
              className="self-start underline decoration-dotted underline-offset-2 text-fg-secondary hover:text-fg-bright"
              onClick={() => onOpenSetup(requirement.id)}
            >
              Fix this
            </button>
          </li>
        ))}
      </ul>

      {onRecheck && (
        /* SPEC-336: fixing the problem outside the app -- installing KiCad
           while Copperplane is open -- should not need a restart to notice. */
        <button
          type="button"
          className="self-start text-fg-muted hover:text-fg-secondary"
          onClick={onRecheck}
        >
          Check again
        </button>
      )}
    </div>
  )
}
