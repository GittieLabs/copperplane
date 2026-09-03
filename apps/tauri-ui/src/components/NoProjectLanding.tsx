import { GITHUB_REPO_URL, openExternal } from '../lib/externalLinks'

/** SPEC-336: the launch view.
 *
 *  Replaces `App.tsx`'s old behaviour of opening `names[0]` from a sorted
 *  list — the *alphabetically first* project, which the spec calls "stable,
 *  and meaningless". The maintainer's concern, quoted in §1: *"It's possible
 *  that the project could have moved, is corrupted, or isn't the project the
 *  user expected to open."*
 *
 *  The rail stays beside this (see the context's §0.5): it is the fastest
 *  route to the thing this view exists to offer, so hiding it would be
 *  perverse. That also makes "closed a project" and "launched with none" the
 *  same state rather than two that merely look alike. */
export function NoProjectLanding({
  projectCount,
  loading = false,
  onCreateProject,
  onOpenProject,
}: {
  projectCount: number
  loading?: boolean
  onCreateProject: () => void
  onOpenProject: () => void
}) {
  return (
    <div className="flex h-full flex-col items-start justify-center gap-6 p-10">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-medium text-fg-bright">Copperplane</h1>
        <p className="max-w-xl text-sm text-fg-secondary">
          A co-pilot for the parts of a hardware project that are easy to get wrong: reading your
          KiCad schematic and board, checking them, explaining what the checks mean, and sizing an
          enclosure that actually fits.
        </p>
        <p className="max-w-xl text-xs text-fg-muted">
          Your files stay yours. Copperplane reads the KiCad project you point it at and writes
          only where you ask it to.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="rounded bg-accent px-3 py-2 text-sm font-medium text-accent-fg hover:opacity-90"
          onClick={onCreateProject}
        >
          New project
        </button>
        {/* Only offered when there is something to open. A button that opens
            an empty list is how a first run starts with a dead end. */}
        {projectCount > 0 && (
          <button
            type="button"
            className="rounded border border-line px-3 py-2 text-sm text-fg-secondary hover:bg-surface-alt"
            onClick={onOpenProject}
          >
            Open a project
            <span className="ml-1 text-fg-muted">
              ({projectCount})
            </span>
          </button>
        )}
        {loading && (
          <span className="text-xs text-fg-muted" role="status">
            Loading your projects…
          </span>
        )}
      </div>

      {!loading && projectCount === 0 && (
        <p className="text-xs text-fg-muted">
          No projects yet. Creating one links it to a KiCad project you already have — Copperplane
          does not make the schematic for you.
        </p>
      )}

      <button
        type="button"
        className="text-xs text-fg-muted underline decoration-dotted underline-offset-2 hover:text-fg-secondary"
        onClick={() => void openExternal(GITHUB_REPO_URL)}
      >
        Source and documentation on GitHub
      </button>
    </div>
  )
}
