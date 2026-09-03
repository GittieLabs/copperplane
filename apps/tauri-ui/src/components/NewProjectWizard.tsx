import { useState } from 'react'

import type { Area } from '../lib/areas'
import { pickKicadProject } from '../lib/kicadProject'
import { openKicad } from '../lib/boardAdvisor'
import { WIZARD_STEPS, nameProblem, summariseIntent } from '../lib/newProjectWizard'
import {
  REVIEW_CHECKS, runProjectReview, type ReviewCheckState,
} from '../lib/projectReview'

/** SPEC-335: creating a project, in the main content area.
 *
 *  Replaces a name field and an optional intent box in a 192px sidebar column
 *  with no cancel. Nothing is written until the last step, so cancelling at any
 *  point leaves no project behind — which is also what lets every step be
 *  skipped (SPEC-336's rule that the app never traps a user mid-setup). */
export function NewProjectWizard({
  onCancel,
  onCreate,
  existingProjects,
}: {
  onCancel: () => void
  onCreate: (project: {
    name: string
    intent?: string
    kicadProjectPath?: string | null
    openArea: Area
  }) => void
  existingProjects: string[]
}) {
  const [stepIndex, setStepIndex] = useState(0)
  const step = WIZARD_STEPS[stepIndex]

  const [name, setName] = useState('')
  const [kicadPath, setKicadPath] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const [summary, setSummary] = useState<string | null>(null)
  const [summarising, setSummarising] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checks, setChecks] = useState<ReviewCheckState[]>([])
  const [reviewStarted, setReviewStarted] = useState(false)

  const problem = nameProblem(name, existingProjects)
  const canLeaveName = name.trim().length > 0 && problem === null

  async function handlePickKicad() {
    setError(null)
    try {
      const picked = await pickKicadProject()
      if (picked) setKicadPath(picked)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleSummarise() {
    if (!description.trim()) return
    setSummarising(true)
    setError(null)
    try {
      setSummary(await summariseIntent(description))
    } catch {
      // The description is still theirs to keep -- a failed summary must not
      // cost them what they typed.
      setSummary(description.trim())
      setError('Could not summarise that, so your own words are kept as written.')
    } finally {
      setSummarising(false)
    }
  }

  function startReview() {
    setReviewStarted(true)
    setChecks(REVIEW_CHECKS.map((c) => ({ ...c, status: 'pending' })))
    void runProjectReview(kicadPath, (update) => {
      setChecks((prev) => prev.map((c) => (c.key === update.key ? update : c)))
    })
  }

  function goNext() {
    const next = stepIndex + 1
    setStepIndex(next)
    if (WIZARD_STEPS[next]?.key === 'review' && !reviewStarted) startReview()
  }

  function finish(openArea: Area) {
    onCreate({
      name: name.trim(),
      intent: summary?.trim() || undefined,
      kicadProjectPath: kicadPath,
      openArea,
    })
  }

  return (
    <div className="flex w-full max-w-2xl flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase text-fg-muted">
            New project · step {stepIndex + 1} of {WIZARD_STEPS.length}
          </p>
          <h1 className="text-xl font-semibold text-fg-bright">{step.title}</h1>
        </div>
        {/* The action that did not exist before. Safe at every step precisely
            because nothing has been written yet. */}
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
                : i < stepIndex ? 'border-line text-fg-tertiary' : 'border-line-subtle text-fg-faint'
            }`}
          >
            {i < stepIndex ? '✓ ' : ''}{s.title}
          </li>
        ))}
      </ol>

      {error && <p className="text-xs text-danger">{error}</p>}

      <div className="flex flex-col gap-3 rounded border border-line-subtle p-4 text-sm">
        {step.key === 'name' && (
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-fg-secondary">Project name</span>
            <input
              autoFocus
              className="rounded border border-line bg-surface px-3 py-2 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="project name"
            />
            {/* Refused rather than allowed through: save_project keys on the
                name, so a second "test 1" would write into the first one's
                record instead of making a new project. */}
            {problem && <span className="text-danger">{problem}</span>}
          </label>
        )}

        {step.key === 'kicad' && (
          <>
            <p className="text-fg-secondary">
              Copperplane reads your KiCad project to check the schematic and board, list components
              and size an enclosure. KiCad does not need to be running.
            </p>
            {kicadPath ? (
              <p className="break-all text-xs text-fg-muted">
                Linked: <span className="text-fg-secondary">{kicadPath}</span>
              </p>
            ) : (
              <p className="text-xs text-fg-muted">
                No KiCad project linked yet. You can link one later — the app will tell you what is
                unavailable until you do.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded border border-line px-3 py-1 text-xs text-fg-bright hover:bg-surface-alt"
                onClick={() => void handlePickKicad()}
              >
                {kicadPath ? 'Choose a different project…' : 'Choose .kicad_pro…'}
              </button>
              <button
                type="button"
                className="rounded border border-line px-3 py-1 text-xs text-fg-secondary hover:bg-surface-alt"
                onClick={() => void openKicad()}
              >
                Open KiCad to create one
              </button>
            </div>
          </>
        )}

        {step.key === 'intent' && (
          <>
            <p className="text-fg-secondary">
              Tell the assistant what you are building. Without this it answers generically, because
              it has nothing about your project to go on.
            </p>
            <textarea
              className="min-h-24 rounded border border-line bg-surface px-3 py-2 text-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="a blinking LED badge that runs off a coin cell…"
            />
            <div>
              <button
                type="button"
                className="rounded border border-line px-3 py-1 text-xs text-fg-bright hover:bg-surface-alt disabled:opacity-50"
                onClick={() => void handleSummarise()}
                disabled={summarising || description.trim().length === 0}
              >
                {summarising ? 'Reading that…' : summary ? 'Summarise again' : 'Summarise'}
              </button>
            </div>
            {summary !== null && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-fg-secondary">
                  Here is what I understood — correct it if I have it wrong:
                </span>
                {/* Editable on purpose: it is the user's project, and the
                    summary is the agent's words until they agree with it. */}
                <textarea
                  className="min-h-20 rounded border border-line bg-surface px-3 py-2 text-sm"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                />
              </label>
            )}
          </>
        )}

        {step.key === 'review' && (
          <>
            <p className="text-fg-secondary">
              {kicadPath
                ? 'Checking your project against KiCad. Each result appears as it finishes.'
                : 'Nothing to check yet — no KiCad project is linked.'}
            </p>
            <ul className="flex flex-col gap-2">
              {checks.map((c) => (
                <li key={c.key} className="flex gap-2 text-xs">
                  <span aria-hidden className="w-4 shrink-0">
                    {c.status === 'done' ? '✓'
                      : c.status === 'failed' ? '⚠'
                        : c.status === 'skipped' ? '—' : '○'}
                  </span>
                  <span className="flex flex-col gap-0.5">
                    <span className="text-fg-bright">{c.label}</span>
                    {c.status === 'running' && <span className="text-fg-muted">Running…</span>}
                    {c.status === 'pending' && <span className="text-fg-faint">Waiting</span>}
                    {c.summary && <span className="text-fg-secondary">{c.summary}</span>}
                    {/* A failed check says so as itself. It never reads as a
                        pass, and never costs the user the other three. */}
                    {c.error && <span className="text-danger">Could not run: {c.error}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border border-line px-3 py-1 text-xs text-fg-secondary hover:bg-surface-alt disabled:opacity-50"
          onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
          disabled={stepIndex === 0}
        >
          Back
        </button>
        {step.key !== 'review' && (
          <button
            type="button"
            className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
            onClick={goNext}
            disabled={step.key === 'name' && !canLeaveName}
          >
            {step.key === 'name' ? 'Next' : 'Skip for now'}
          </button>
        )}
        {step.key === 'kicad' && kicadPath && (
          <button
            type="button"
            className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg"
            onClick={goNext}
          >
            Next
          </button>
        )}
      </div>

      {step.key === 'review' && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-fg-muted">Create the project and start where you want:</p>
          <div className="flex flex-wrap gap-2">
            {(['overview', 'components', 'schematic', 'pcb', 'enclosure'] as Area[]).map((area) => (
              <button
                key={area}
                type="button"
                className="rounded border border-line px-3 py-1 text-xs capitalize text-fg-bright hover:bg-surface-alt"
                onClick={() => finish(area)}
              >
                {area}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
