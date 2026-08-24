import { useState } from 'react'

/** SPEC-305 §2: the left rail SPEC-300 §2 designed -- Projects, then
 * Library, then Settings anchored at the bottom. Real projects and a
 * real library count (SPEC-304), never mocked data. */
export function Rail({
  projects,
  selectedProject,
  onSelectProject,
  onCreateProject,
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
  onCreateProject: (name: string, intent?: string) => void
  libraryCount: number
  librarySelected: boolean
  onSelectLibrary: () => void
  settingsSelected: boolean
  onSelectSettings: () => void
}) {
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectIntent, setNewProjectIntent] = useState('')
  const [creating, setCreating] = useState(false)

  function handleCreate() {
    const name = newProjectName.trim()
    if (!name) return
    const intent = newProjectIntent.trim()
    if (intent) {
      onCreateProject(name, intent)
    } else {
      onCreateProject(name)
    }
    setNewProjectName('')
    setNewProjectIntent('')
    setCreating(false)
  }

  return (
    <nav className="flex h-full w-48 flex-col gap-6 border-r border-line-subtle p-4 text-sm">
      <div className="flex flex-col gap-1">
        <h2 className="px-2 text-xs font-medium uppercase text-fg-muted">Projects</h2>
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
        {creating ? (
          <div className="flex flex-col gap-1 px-2 py-1">
            <input
              autoFocus
              className="w-full rounded border border-line bg-surface px-1 py-0.5 text-xs"
              placeholder="project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate()
                if (e.key === 'Escape') setCreating(false)
              }}
            />
            {/* SPEC-318 §2.4: optional, skip-first-class -- the textarea's
             * own placeholder is the only prompt; leaving it blank is a
             * normal outcome, not a validation error. */}
            <textarea
              className="w-full rounded border border-line bg-surface px-1 py-0.5 text-xs"
              rows={2}
              placeholder="what are you building? (optional)"
              value={newProjectIntent}
              onChange={(e) => setNewProjectIntent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setCreating(false)
              }}
            />
            <button
              type="button"
              className="self-start rounded bg-accent px-2 py-0.5 text-xs font-medium text-accent-fg disabled:opacity-50"
              onClick={handleCreate}
              disabled={!newProjectName.trim()}
            >
              Add
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="rounded px-2 py-1 text-left text-fg-muted hover:bg-surface"
            onClick={() => setCreating(true)}
          >
            + New…
          </button>
        )}
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
