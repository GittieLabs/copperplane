
/** SPEC-305 §2: the left rail SPEC-300 §2 designed -- Projects, then
 * Library, then Settings anchored at the bottom. Real projects and a
 * real library count (SPEC-304), never mocked data. */
export function Rail({
  projects,
  selectedProject,
  onSelectProject,
  onStartNewProject,
  projectsLoading = false,
  libraryCount,
  librarySelected,
  onSelectLibrary,
  settingsSelected,
  onSelectSettings,
}: {
  projects: string[]
  selectedProject: string | null
  onSelectProject: (name: string) => void
  /** SPEC-318 §2.4: `intent` is only passed when the user actually typed
   * something -- omitted entirely (not an empty string) when skipped, so
   * `saveProject({ name })`'s existing unchanged-behavior path for a
   * skipped intent stays exactly that: no second argument at all. */
  /** SPEC-335: opens the wizard in the main area. The inline form this
   *  replaces had no cancel, and asked for intent in a 192px column. */
  onStartNewProject: () => void
  /** Listing projects reads every record off disk. Creating one while that is
   *  in flight raced the in-flight list, which came back holding the state
   *  from before the new project existed and overwrote it. App.tsx now merges
   *  rather than replaces; this also stops the user starting the race. */
  projectsLoading?: boolean
  libraryCount: number
  librarySelected: boolean
  onSelectLibrary: () => void
  settingsSelected: boolean
  onSelectSettings: () => void
}) {


  return (
    <nav className="flex h-full w-48 flex-col gap-6 border-r border-line-subtle p-4 text-sm">
      <div className="flex flex-col gap-1">
        <h2 className="px-2 text-xs font-medium uppercase text-fg-muted">Projects</h2>
        {projectsLoading && (
          <p className="px-2 py-1 text-xs text-fg-muted" role="status">Loading…</p>
        )}
        {projects.map((name) => (
          <button
            key={name}
            type="button"
            className={`rounded px-2 py-1 text-left ${
              !settingsSelected && selectedProject === name
                ? 'bg-surface-alt text-fg'
                : 'text-fg-secondary hover:bg-surface'
            }`}
            onClick={() => onSelectProject(name)}
          >
            {selectedProject === name && !settingsSelected ? '> ' : ''}
            {name}
          </button>
        ))}
        <button
          type="button"
          className="rounded px-2 py-1 text-left text-fg-muted hover:bg-surface disabled:opacity-50"
          onClick={onStartNewProject}
          disabled={projectsLoading}
          title={projectsLoading ? 'Still loading your projects…' : undefined}
        >
          + New…
        </button>
      </div>

      <div className="flex flex-col gap-1">
        <h2 className="px-2 text-xs font-medium uppercase text-fg-muted">Library</h2>
        <button
          type="button"
          className={`rounded px-2 py-1 text-left ${
            librarySelected ? 'bg-surface-alt text-fg' : 'text-fg-tertiary hover:bg-surface'
          }`}
          onClick={onSelectLibrary}
        >
          {libraryCount} parts
        </button>
      </div>

      <button
        type="button"
        className={`mt-auto rounded px-2 py-1 text-left ${
          settingsSelected ? 'bg-surface-alt text-fg' : 'text-fg-secondary hover:bg-surface'
        }`}
        onClick={onSelectSettings}
      >
        ⚙ Settings
      </button>
    </nav>
  )
}
