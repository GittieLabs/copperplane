import { useState } from 'react'

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
  projects,
  removedProjects = [],
  storageRoot,
  loading = false,
  onCreateProject,
  onOpenProject,
  onRestoreProject,
}: {
  projects: string[]
  /** SPEC-333: projects hidden from the list. Shown only when there are any,
   *  because a removal with no visible route back is a trap. */
  removedProjects?: string[]
  onRestoreProject?: (name: string) => void
  /** Where the app is looking for projects. An empty list and a list pointed
   *  at the wrong folder look identical without it. */
  storageRoot?: string | null
  loading?: boolean
  onCreateProject: () => void
  /** Opens a named project. The first version of this took no argument and
   *  set a message telling the user to use the rail -- a message rendered
   *  only inside the project view, so the button did nothing at all. */
  onOpenProject: (name: string) => void
}) {
  const [choosing, setChoosing] = useState(false)
  const [showingRemoved, setShowingRemoved] = useState(false)
  const projectCount = projects.length

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
            aria-expanded={choosing}
            onClick={() => setChoosing((prev) => !prev)}
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

      {/* The list itself, not a pointer at the rail. A button whose whole
          effect is "look over there" is barely a button, and the first
          version's message did not even render on this view. */}
      {choosing && projectCount > 0 && (
        <ul className="flex w-full max-w-md flex-col gap-1">
          {projects.map((name) => (
            <li key={name}>
              <button
                type="button"
                className="w-full rounded border border-line-subtle px-3 py-2 text-left text-sm text-fg-secondary hover:bg-surface-alt hover:text-fg-bright"
                onClick={() => onOpenProject(name)}
              >
                {name}
              </button>
            </li>
          ))}
        </ul>
      )}

      {!loading && projectCount === 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs text-fg-muted">
            No projects yet. Creating one links it to a KiCad project you already have — Copperplane
            does not make the schematic for you.
          </p>
          {/* CTX-110.2: an empty list and a list looking in the wrong place
              are indistinguishable, and the maintainer hit the second one.
              Saying where it looked is the difference. */}
          {storageRoot && (
            <p className="break-all text-xs text-fg-faint">
              Looking in {storageRoot}. Projects live in this folder — if yours are elsewhere,
              change the storage location in Settings.
            </p>
          )}
        </div>
      )}

      {removedProjects.length > 0 && onRestoreProject && (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            className="self-start text-xs text-fg-muted underline decoration-dotted underline-offset-2 hover:text-fg-secondary"
            aria-expanded={showingRemoved}
            onClick={() => setShowingRemoved((prev) => !prev)}
          >
            {removedProjects.length} removed from this list
          </button>
          {showingRemoved && (
            <ul className="flex w-full max-w-md flex-col gap-1">
              {removedProjects.map((name) => (
                <li key={name} className="flex items-center justify-between gap-3">
                  <span className="truncate text-xs text-fg-secondary">{name}</span>
                  <button
                    type="button"
                    className="shrink-0 rounded border border-line px-2 py-1 text-xs text-fg-secondary hover:bg-surface-alt"
                    onClick={() => onRestoreProject(name)}
                  >
                    Put back
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
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
