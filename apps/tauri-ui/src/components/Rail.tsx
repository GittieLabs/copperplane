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
  onCreateProject: (name: string) => void
  libraryCount: number
  librarySelected: boolean
  onSelectLibrary: () => void
  settingsSelected: boolean
  onSelectSettings: () => void
}) {
  const [newProjectName, setNewProjectName] = useState('')
  const [creating, setCreating] = useState(false)

  function handleCreate() {
    const name = newProjectName.trim()
    if (!name) return
    onCreateProject(name)
    setNewProjectName('')
    setCreating(false)
  }

  return (
    <nav className="flex h-full w-48 flex-col gap-6 border-r border-neutral-800 p-4 text-sm">
      <div className="flex flex-col gap-1">
        <h2 className="px-2 text-xs font-medium uppercase text-neutral-500">Projects</h2>
        {projects.map((name) => (
          <button
            key={name}
            type="button"
            className={`rounded px-2 py-1 text-left ${
              !settingsSelected && selectedProject === name
                ? 'bg-neutral-800 text-neutral-100'
                : 'text-neutral-300 hover:bg-neutral-900'
            }`}
            onClick={() => onSelectProject(name)}
          >
            {selectedProject === name && !settingsSelected ? '> ' : ''}
            {name}
          </button>
        ))}
        {creating ? (
          <div className="flex gap-1 px-2 py-1">
            <input
              autoFocus
              className="w-full rounded border border-neutral-700 bg-neutral-900 px-1 py-0.5 text-xs"
              placeholder="project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate()
                if (e.key === 'Escape') setCreating(false)
              }}
            />
            <button
              type="button"
              className="rounded bg-neutral-100 px-2 text-xs font-medium text-neutral-950 disabled:opacity-50"
              onClick={handleCreate}
              disabled={!newProjectName.trim()}
            >
              Add
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="rounded px-2 py-1 text-left text-neutral-500 hover:bg-neutral-900"
            onClick={() => setCreating(true)}
          >
            + New…
          </button>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <h2 className="px-2 text-xs font-medium uppercase text-neutral-500">Library</h2>
        <button
          type="button"
          className={`rounded px-2 py-1 text-left ${
            librarySelected ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:bg-neutral-900'
          }`}
          onClick={onSelectLibrary}
        >
          {libraryCount} parts
        </button>
      </div>

      <button
        type="button"
        className={`mt-auto rounded px-2 py-1 text-left ${
          settingsSelected ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-300 hover:bg-neutral-900'
        }`}
        onClick={onSelectSettings}
      >
        ⚙ Settings
      </button>
    </nav>
  )
}
