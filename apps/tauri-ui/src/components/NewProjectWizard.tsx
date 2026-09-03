import { useState } from 'react'

import { WIZARD_STEPS } from '../lib/newProjectWizard'

/** SPEC-335: creating a project, in the main content area.
 *
 *  Replaces a name field and an optional intent box in a 192px sidebar column
 *  with no cancel: "We should make creating a project do everything in the
 *  main content area and not show our tabbed view until the project is
 *  submitted."
 *
 *  Nothing is written until the last step. Cancelling at any point therefore
 *  leaves no project behind, which is what makes every step safely skippable
 *  (SPEC-335 §2, following SPEC-336's rule that the app never traps a user
 *  mid-setup). */

export function NewProjectWizard({
  onCancel,
  onCreate,
  existingProjects,
}: {
  onCancel: () => void
  /** Called once, on the last step. Until then nothing is written, which is
   *  what makes Cancel safe at every step. */
  onCreate: (name: string, intent?: string) => void
  /** Used from Phase 2 to refuse a duplicate name rather than silently
   *  merging into an existing project. */
  existingProjects: string[]
}) {
  const [stepIndex, setStepIndex] = useState(0)
  /* Phase 2 moves this into a real step-1 form with duplicate-name checking.
     It lives here in Phase 1 so the wizard has a completion path at all --
     without one, "the tabbed view is not shown until the wizard completes"
     cannot be demonstrated. */
  const [draftName, setDraftName] = useState('')
  const step = WIZARD_STEPS[stepIndex]

  return (
    <div className="flex w-full max-w-2xl flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase text-fg-muted">
            New project · step {stepIndex + 1} of {WIZARD_STEPS.length}
          </p>
          <h1 className="text-xl font-semibold text-fg-bright">{step.title}</h1>
        </div>
        {/* The action that did not exist before: "There is not a way to cancel
            creating a new project." Safe at every step precisely because
            nothing has been written yet. */}
        <button
          type="button"
          className="shrink-0 rounded border border-line px-3 py-1 text-xs text-fg-secondary hover:bg-surface-alt"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>

      <ol className="flex flex-wrap gap-2 text-xs">
        {WIZARD_STEPS.map((s, i) => (
          <li
            key={s.key}
            aria-current={i === stepIndex ? 'step' : undefined}
            className={`rounded border px-2 py-1 ${
              i === stepIndex
                ? 'border-accent/50 bg-accent/10 text-fg-bright'
                : i < stepIndex
                  ? 'border-line text-fg-tertiary'
                  : 'border-line-subtle text-fg-faint'
            }`}
          >
            {i < stepIndex ? '✓ ' : ''}
            {s.title}
          </li>
        ))}
      </ol>

      <div className="rounded border border-line-subtle p-4 text-sm text-fg-secondary">
        {/* Phases 2-4 replace this with the real steps. Named rather than left
            blank so a half-built wizard reads as unfinished, not broken. */}
        <p>This step is not built yet — CTX-335.1 Phase {stepIndex + 2}.</p>
        {stepIndex === 0 && (
          <label className="mt-2 flex flex-col gap-1 text-xs">
            <span className="text-fg-secondary">Project name</span>
            <input
              className="rounded border border-line bg-surface px-3 py-2 text-sm"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder="project name"
            />
          </label>
        )}
        <p className="mt-1 text-xs text-fg-muted">
          Nothing is saved until the last step, so cancelling now leaves nothing behind.
          {existingProjects.length > 0 &&
            ` You have ${existingProjects.length} existing project${existingProjects.length === 1 ? '' : 's'}.`}
        </p>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          className="rounded border border-line px-3 py-1 text-xs text-fg-secondary hover:bg-surface-alt disabled:opacity-50"
          onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
          disabled={stepIndex === 0}
        >
          Back
        </button>
        {stepIndex < WIZARD_STEPS.length - 1 ? (
          <button
            type="button"
            className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg"
            onClick={() => setStepIndex((i) => i + 1)}
          >
            Next
          </button>
        ) : (
          /* The only write in the whole flow. Phase 2 replaces the placeholder
             name with the one the user actually typed. */
          <button
            type="button"
            className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg"
            onClick={() => onCreate(draftName.trim())}
            disabled={draftName.trim().length === 0}
          >
            Create project
          </button>
        )}
      </div>
    </div>
  )
}
