import { useEffect, useRef, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
import {
  submitJob,
  dispatchTool,
  MENU_SAVE_PROJECT_EVENT,
  MENU_OPEN_PROJECT_EVENT,
  MENU_OPEN_SETTINGS_EVENT,
  MENU_OPEN_DEFAULT_LIBRARY_EVENT,
  MENU_MANAGE_LIBRARIES_EVENT,
  MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT,
  MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT,
  MENU_DESIGN_PCB_OPEN_KICAD_EVENT,
  MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT,
  MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT,
  MENU_DESIGN_ENCLOSURE_GENERATE_EVENT,
  MENU_OPEN_LIBRARY_EVENT,
} from './lib/ipc'
import { parseCommand } from './lib/commands'
import {
  appendConversationTurn,
  listLibraryParts,
  listProjects,
  loadConversation,
  loadProject,
  openProjectFromDirectory,
  pickProjectDirectory,
  saveProject,
  type ConversationTurn,
  type Project,
} from './lib/projects'
import { listLibraries } from './lib/library'
import { syncLibraryMenu, setDesignMenuEnabled } from './lib/menu'
import type { Area, MenuCommand } from './lib/areas'
import { BoardAdvisor } from './components/BoardAdvisor'
import { ComponentDiscovery } from './components/ComponentDiscovery'
import { EnclosurePanel, type EnclosureExportSuccessEvent } from './components/EnclosurePanel'
import { LibraryArea } from './components/LibraryArea'
import { OverviewDashboard } from './components/OverviewDashboard'
import { PartDetail } from './components/PartDetail'
import { Rail } from './components/Rail'
import { SchematicAdvisor } from './components/SchematicAdvisor'
import { Settings } from './components/Settings'
import { loadPart, type SavedPart } from './lib/partDetail'

// SPEC-108's own Cross-Module Impacts section names a fixed placement
// position as enough for a first UI trigger ("even a hardcoded
// board-origin default for M1's demo"). A real position-picker UI is
// future work, not this command's job.
const _INJECT_DEFAULT_POSITION_MM = { x: 50, y: 50 }

type Status = 'pending' | 'done' | 'error'
type InjectStatus = Status | 'awaiting_confirmation'

type ChatMessage =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'generate'; status: Status; partNumber: string; schema?: Record<string, unknown>; error?: string }
  | { id: string; kind: 'inject'; status: InjectStatus; error?: string; pendingInput?: Record<string, unknown> }
  | { id: string; kind: 'chat'; status: Status; text?: string; error?: string }

let nextMessageId = 1
function newMessageId(): string {
  return `msg_${nextMessageId++}`
}

/** SPEC-305 §2: the five per-project area tabs, in the shell's own
 * order. Overview and Enclosure carry real, already-shipped content
 * forward; Components/Schematic/PCB are visible-but-empty until
 * SPEC-306/308/309 build them. `Area` itself lives in `lib/areas.ts`,
 * not here, so the area components (SPEC-316's `menuCommand` prop) can
 * import it without a circular import back into this file. */
const AREAS: { key: Area; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'components', label: 'Components' },
  { key: 'schematic', label: 'Schematic' },
  { key: 'pcb', label: 'PCB' },
  { key: 'enclosure', label: 'Enclosure' },
]

type View =
  | { kind: 'settings' }
  | { kind: 'library'; initialLibraryId?: string }
  | { kind: 'project'; name: string; area: Area }
  // CTX-315.4: a Part is a global SPEC-304 object, not project-scoped, so
  // reopening one from the Library doesn't require a project to be open --
  // a real, separate top-level view rather than folding it into `project`.
  | { kind: 'partDetail'; partId: string }
  | null

function App() {
  const [projects, setProjects] = useState<string[]>([])
  const [libraryCount, setLibraryCount] = useState(0)
  const [view, setView] = useState<View>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [menuCommand, setMenuCommand] = useState<MenuCommand | null>(null)
  // Read by the menu-listener effect below, which only re-subscribes on
  // `currentProject` changes -- a ref keeps it seeing the real current
  // `view` (e.g. after switching area tabs) without resubscribing on
  // every tab switch.
  const viewRef = useRef<View>(null)
  useEffect(() => {
    viewRef.current = view
  }, [view])

  // CTX-316.2: populates the native Library menu's real custom-library
  // items even before a user ever opens the Library area -- the native
  // menu is built before the daemon is ready to answer
  // `library.list_libraries()`, so this is the real, later sync
  // `SPEC-316`'s own Known Constraints named. Best-effort: `syncLibraryMenu`
  // swallows its own failures, and `.catch` here covers `listLibraries()`
  // itself rejecting before that ever runs.
  useEffect(() => {
    void listLibraries().then(syncLibraryMenu).catch(() => {})
  }, [])

  // CTX-316.2: keeps the native Design menu's enabled state in sync with
  // whether a project is actually open -- the one real, coarse-grained
  // sync point SPEC-316's own Known Constraints named (not per-action
  // preconditions).
  useEffect(() => {
    void setDesignMenuEnabled(view?.kind === 'project')
  }, [view?.kind])

  // CTX-312.1: the current project's own real record -- SPEC-304 §2.1's
  // long-described "link to a KiCad project directory on disk," plus
  // the real Save Project manifest fields (`last_results`,
  // `export_history`). Reloaded whenever the selected project changes;
  // `null` while loading or when no project is selected at all.
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [savingProject, setSavingProject] = useState(false)
  const [projectActionError, setProjectActionError] = useState<string | null>(null)
  // CTX-312.2: real user feedback -- clicking "Save Project" (or "Link to
  // folder…") gave no visible confirmation at all, so a real successful
  // save looked identical to nothing happening. A real, named message per
  // action, matching CTX-311.13's own "Exported to <path>" precedent --
  // persists until the next real action, not on an auto-dismiss timer.
  const [projectActionMessage, setProjectActionMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [names, parts] = await Promise.all([listProjects(), listLibraryParts()])
        if (cancelled) return
        setProjects(names)
        setLibraryCount(parts.length)
        setView((prev) => {
          if (prev !== null) return prev
          return names.length > 0 ? { kind: 'project', name: names[0], area: 'overview' } : prev
        })
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err))
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  // CTX-312.1: loads the selected project's own real record (directory
  // link, last results, export history) -- reset to null immediately on
  // every project switch so a stale previous project's state can never
  // flash or leak into the next one while the real load is in flight.
  useEffect(() => {
    if (view?.kind !== 'project') {
      setCurrentProject(null)
      return
    }
    let cancelled = false
    setCurrentProject(null)
    setProjectActionError(null)
    setProjectActionMessage(null)
    loadProject(view.name)
      .then((project) => {
        if (!cancelled) setCurrentProject(project)
      })
      .catch((err) => {
        if (!cancelled) setProjectActionError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [view?.kind === 'project' ? view.name : null])

  async function handleCreateProject(name: string) {
    try {
      await saveProject({ name })
      setProjects((prev) => (prev.includes(name) ? prev : [...prev, name]))
      setView({ kind: 'project', name, area: 'overview' })
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    }
  }

  function handleSelectProject(name: string) {
    setView({ kind: 'project', name, area: 'overview' })
  }

  function handleSelectArea(area: Area) {
    setView((prev) => (prev?.kind === 'project' ? { ...prev, area } : prev))
  }

  async function handleLinkDirectory() {
    if (!currentProject) return
    setProjectActionError(null)
    setProjectActionMessage(null)
    try {
      const directory = await pickProjectDirectory()
      if (!directory) return
      const saved = await saveProject({ ...currentProject, directory })
      setCurrentProject(saved)
      setProjectActionMessage(`Linked to ${directory}`)
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleSaveProject() {
    if (!currentProject) return
    setSavingProject(true)
    setProjectActionError(null)
    setProjectActionMessage(null)
    try {
      const saved = await saveProject(currentProject)
      setCurrentProject(saved)
      setProjectActionMessage('Project saved.')
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingProject(false)
    }
  }

  // CTX-312.3: the real backend for the native menu's "Open Project…" --
  // restores a project from a real, already-linked folder (e.g. copied
  // from another machine), the actual payoff of CTX-312.1's own
  // portability work. Deliberately not gated on `currentProject` --
  // unlike Link/Save (real actions on whichever project is already
  // selected), opening one doesn't depend on one being selected yet,
  // matching `handleCreateProject`'s own shape and its own `loadError`.
  async function handleOpenProject() {
    try {
      const directory = await pickProjectDirectory()
      if (!directory) return
      const opened = await openProjectFromDirectory(directory)
      setProjects((prev) => (prev.includes(opened.name) ? prev : [...prev, opened.name]))
      setView({ kind: 'project', name: opened.name, area: 'overview' })
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    }
  }

  // CTX-312.3: the real native menu's own File > Save Project / Open
  // Project… items (`core/tauri-rust/src/menu.rs`) only ever emit a
  // real event -- these listeners are what actually runs the same real
  // handlers the on-screen buttons already call. Re-subscribed whenever
  // `currentProject` changes so `handleSaveProject`'s own closure never
  // sees a stale value (`handleOpenProject` captures no project state at
  // all, so it's always fresh regardless).
  //
  // CTX-316.1 adds the rest of the menu's real command surface to this
  // same effect/cleanup pattern. A Design command with no project open
  // is a real, silent no-op for this phase -- CTX-316.2's own enable/
  // disable sync is what prevents the click from being possible at all,
  // not this handler.
  useEffect(() => {
    let cancelled = false
    const unlisten: (() => void)[] = []

    function on(event: string, handler: () => void) {
      listen(event, handler).then((fn) => {
        if (cancelled) {
          fn()
          return
        }
        unlisten.push(fn)
      })
    }

    function onDesignCommand(area: Area, command: string) {
      if (viewRef.current?.kind !== 'project') return
      setView({ ...viewRef.current, area })
      setMenuCommand((prev) => ({ area, command, nonce: prev ? prev.nonce + 1 : 0 }))
    }

    on(MENU_SAVE_PROJECT_EVENT, () => void handleSaveProject())
    on(MENU_OPEN_PROJECT_EVENT, () => void handleOpenProject())
    on(MENU_OPEN_SETTINGS_EVENT, () => setView({ kind: 'settings' }))
    on(MENU_OPEN_DEFAULT_LIBRARY_EVENT, () => setView({ kind: 'library', initialLibraryId: 'default' }))
    on(MENU_MANAGE_LIBRARIES_EVENT, () => setView({ kind: 'library' }))
    on(MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT, () => onDesignCommand('schematic', 'open_kicad'))
    on(MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT, () => onDesignCommand('schematic', 'pick_manually'))
    on(MENU_DESIGN_PCB_OPEN_KICAD_EVENT, () => onDesignCommand('pcb', 'open_kicad'))
    on(MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT, () => onDesignCommand('enclosure', 'open_kicad'))
    on(MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT, () => onDesignCommand('enclosure', 'pick_pcb'))
    on(MENU_DESIGN_ENCLOSURE_GENERATE_EVENT, () => onDesignCommand('enclosure', 'generate'))

    // CTX-316.2: the one menu event with a real payload -- a custom
    // library's own id, which can't have a compile-time const the way
    // every other event above does. Wired directly rather than through
    // `on()`, which only supports payload-less handlers.
    listen<string>(MENU_OPEN_LIBRARY_EVENT, (event) =>
      setView({ kind: 'library', initialLibraryId: event.payload }),
    ).then((fn) => {
      if (cancelled) {
        fn()
        return
      }
      unlisten.push(fn)
    })

    return () => {
      cancelled = true
      unlisten.forEach((fn) => fn())
    }
  }, [currentProject])

  // CTX-312.1: a real export (CTX-311.13's own "keep this" action) is
  // persisted to the current project's real, permanent export_history
  // immediately, not deferred to a separate "Save Project" click a user
  // could forget -- the real file was already kept on disk; the record
  // of that shouldn't depend on a second, easy-to-skip step.
  async function handleExportSuccess(event: EnclosureExportSuccessEvent) {
    if (!currentProject) return
    const updated: Project = {
      ...currentProject,
      last_results: {
        ...currentProject.last_results,
        enclosure: {
          glb_path: event.glbPath,
          step_path: event.stepPath,
          wall_thickness_mm: event.wallThicknessMm,
          clearance_mm: event.clearanceMm,
          standoff_height_mm: event.standoffHeightMm,
        },
      },
      export_history: [
        ...(currentProject.export_history ?? []),
        { area: 'enclosure', dest_path: event.destPath, exported_at: new Date().toISOString() },
      ],
    }
    try {
      const saved = await saveProject(updated)
      setCurrentProject(saved)
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="flex min-h-screen bg-base text-fg">
      <Rail
        projects={projects}
        selectedProject={view?.kind === 'project' ? view.name : null}
        onSelectProject={handleSelectProject}
        onCreateProject={handleCreateProject}
        libraryCount={libraryCount}
        librarySelected={view?.kind === 'library' || view?.kind === 'partDetail'}
        onSelectLibrary={() => setView({ kind: 'library' })}
        settingsSelected={view?.kind === 'settings'}
        onSelectSettings={() => setView({ kind: 'settings' })}
      />
      <main className="flex flex-1 flex-col items-center gap-6 overflow-auto p-8">
        {loadError && <p className="w-full max-w-4xl text-sm text-danger">{loadError}</p>}

        {view === null && (
          <p className="text-sm text-fg-muted">Create a project on the left to get started.</p>
        )}

        {view?.kind === 'settings' && <Settings />}

        {view?.kind === 'library' && (
          <LibraryArea
            initialLibraryId={view.initialLibraryId}
            onSelectPart={(partId) => setView({ kind: 'partDetail', partId })}
          />
        )}

        {view?.kind === 'partDetail' && (
          <PartDetailView partId={view.partId} onBack={() => setView({ kind: 'library' })} />
        )}

        {view?.kind === 'project' && (
          <>
            {/* CTX-312.1: project-scoped chrome, shown above every area
             * tab rather than folded into Overview -- SPEC-312's own
             * Non-Goals deliberately leave Overview's eventual purpose
             * (dashboard vs. cross-project landing page) undecided, so
             * these real, already-scoped actions don't get entangled
             * with a surface whose future shape isn't settled yet. */}
            <div className="flex w-full max-w-4xl items-center justify-between gap-2 text-xs">
              <button
                type="button"
                className="truncate text-left text-fg-tertiary hover:text-fg-bright"
                onClick={() => void handleLinkDirectory()}
                disabled={!currentProject}
                title={currentProject?.directory ?? undefined}
              >
                {currentProject?.directory ? `Linked: ${currentProject.directory}` : 'Link to folder…'}
              </button>
              <button
                type="button"
                className="shrink-0 rounded border border-line px-2 py-1 font-medium text-fg-bright hover:bg-surface-alt disabled:opacity-50"
                onClick={() => void handleSaveProject()}
                disabled={!currentProject || savingProject}
              >
                {savingProject ? 'Saving…' : 'Save Project'}
              </button>
            </div>
            {projectActionError && (
              <p className="w-full max-w-4xl text-xs text-danger">{projectActionError}</p>
            )}
            {!projectActionError && projectActionMessage && (
              <p className="w-full max-w-4xl truncate text-xs text-success">{projectActionMessage}</p>
            )}

            <div className="flex w-full max-w-4xl gap-1 border-b border-line-subtle pb-2">
              {AREAS.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  className={`rounded px-3 py-1 text-sm ${
                    view.area === key
                      ? 'bg-surface-alt text-fg'
                      : 'text-fg-tertiary hover:bg-surface'
                  }`}
                  onClick={() => handleSelectArea(key)}
                >
                  {label}
                </button>
              ))}
            </div>

            {view.area === 'overview' && <Overview projectName={view.name} project={currentProject} />}
            {/* ComponentDiscovery/BoardAdvisor/SchematicAdvisor/EnclosurePanel
             * stay mounted across every area, not just while their own tab
             * is selected -- real user feedback found that switching tabs
             * away and back threw away a check (or, for Enclosure, a
             * just-generated real enclosure), or for Components, a whole
             * confirmed part's in-progress Save/Export/Generate Design
             * Requirements work, that had just finished, with no reason
             * to. Hidden via CSS instead of unmounted, so their own state
             * survives the round trip; each resets that state itself when
             * `projectName` changes, so switching *projects* still starts
             * fresh. Per SPEC-300's original stage-machine design, ERC
             * (Schematic) and DRC (PCB) are two separate stages -- real
             * user feedback flagged the earlier both-checks-under-PCB
             * layout as a mismatch, not SPEC-308's own still-unbuilt
             * footprint/connection-guidance work, which will eventually
             * join SchematicAdvisor here. */}
            <div data-testid="components-area" className={view.area === 'components' ? 'w-full' : 'hidden'}>
              <ComponentDiscovery projectName={view.name} />
            </div>
            <div data-testid="schematic-area" className={view.area === 'schematic' ? 'w-full' : 'hidden'}>
              <SchematicAdvisor projectName={view.name} menuCommand={menuCommand} />
            </div>
            <div data-testid="pcb-area" className={view.area === 'pcb' ? 'w-full' : 'hidden'}>
              <BoardAdvisor projectName={view.name} menuCommand={menuCommand} />
            </div>
            <div data-testid="enclosure-area" className={view.area === 'enclosure' ? 'w-full' : 'hidden'}>
              <EnclosurePanel projectName={view.name} onExportSuccess={handleExportSuccess} menuCommand={menuCommand} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}

/** CTX-315.4: loads an already-saved Part's whole record (`loadPart`,
 * reusing `library.load_part`) before rendering `PartDetail` with
 * `initialPart` -- the real fix for "Save to Library is the only way
 * in": until now, reopening a saved Part meant re-running the search/
 * confirm/extract flow from scratch, as if it were a brand-new,
 * unconfirmed candidate. Kept as its own small component (not folded
 * into `App`) so its load state doesn't entangle with `App`'s own
 * project-loading effects. */
function PartDetailView({ partId, onBack }: { partId: string; onBack: () => void }) {
  const [part, setPart] = useState<SavedPart | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setPart(null)
    setLoadError(null)
    loadPart(partId)
      .then((loaded) => {
        if (!cancelled) setPart(loaded)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [partId])

  return (
    <div className="flex w-full max-w-4xl flex-col gap-4">
      <button
        type="button"
        className="self-start text-xs text-fg-muted hover:text-fg-secondary"
        onClick={onBack}
      >
        ← Library
      </button>
      {loadError && <p className="text-sm text-danger">{loadError}</p>}
      {!loadError && !part && <p className="text-sm text-fg-muted">Loading…</p>}
      {part && <PartDetail initialPart={part} />}
    </div>
  )
}

/** SPEC-305 §2: Overview re-houses the existing chat surface unchanged
 * in substance, scoped to the selected project instead of one global
 * `chatHistory`. Only plain chat turns persist to `SPEC-304`'s
 * conversation log (SPEC-302 §2's own named limitation) -- a
 * `generate`/`inject` command's own message isn't folded back into the
 * LLM's context or persisted in this pass. Switching projects resets
 * all of this state so no conversation leaks across the boundary
 * (SPEC-305 §3's own named hazard). */
function Overview({ projectName, project }: { projectName: string; project: Project | null }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [latestSchema, setLatestSchema] = useState<Record<string, unknown> | null>(null)
  const [chatHistory, setChatHistory] = useState<ConversationTurn[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setInput('')
    setMessages([])
    setLatestSchema(null)
    setChatHistory([])
    setLoaded(false)
    setLoadError(null)

    loadConversation(projectName)
      .then((turns) => {
        if (cancelled) return
        setChatHistory(turns)
        setMessages(
          turns.map((turn) =>
            turn.role === 'user'
              ? { id: newMessageId(), kind: 'user', text: turn.content }
              : { id: newMessageId(), kind: 'chat', status: 'done', text: turn.content },
          ),
        )
        setLoaded(true)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err instanceof Error ? err.message : String(err))
        setLoaded(true)
      })

    return () => {
      cancelled = true
    }
  }, [projectName])

  async function handleSend() {
    const text = input.trim()
    if (!text) return
    setInput('')
    setMessages((prev) => [...prev, { id: newMessageId(), kind: 'user', text }])

    const command = parseCommand(text)

    if (command.type === 'generate') {
      const id = newMessageId()
      setMessages((prev) => [
        ...prev,
        { id, kind: 'generate', status: 'pending', partNumber: command.partNumber },
      ])
      try {
        // SPEC-202: kicad.generate_component is a real, validated
        // pipeline -- an async job (a real LLM extraction call is
        // multi-second) that raises a clean error naming the failed
        // safety check, rather than ever returning a best-effort result.
        const handle = await submitJob<Record<string, unknown>>('kicad.generate_component', {
          part_number: command.partNumber,
        })
        const schema = await handle.result
        setLatestSchema(schema)
        setMessages((prev) =>
          prev.map((m) => (m.id === id && m.kind === 'generate' ? { ...m, status: 'done', schema } : m)),
        )
      } catch (err) {
        const error = err instanceof Error ? err.message : String(err)
        setMessages((prev) =>
          prev.map((m) => (m.id === id && m.kind === 'generate' ? { ...m, status: 'error', error } : m)),
        )
      }
      return
    }

    if (command.type === 'inject') {
      const id = newMessageId()
      if (latestSchema === null) {
        setMessages((prev) => [
          ...prev,
          {
            id,
            kind: 'inject',
            status: 'error',
            error: 'Nothing to inject yet — generate a component first.',
          },
        ])
        return
      }
      setMessages((prev) => [...prev, { id, kind: 'inject', status: 'pending' }])
      const toolInput = {
        schema: latestSchema,
        x_mm: _INJECT_DEFAULT_POSITION_MM.x,
        y_mm: _INJECT_DEFAULT_POSITION_MM.y,
      }
      try {
        // SPEC-108/CTX-204.1: kicad.inject_component writes into
        // whatever board KiCad already has open -- the only tool
        // SPEC-204 gates behind explicit confirmation, since it's the
        // only one that mutates a document the user didn't ask this
        // app to open. The first (unconfirmed) call never touches the
        // real board; awaitInjectConfirmation below sends the second.
        const outcome = await dispatchTool<Record<string, unknown>>('kicad.inject_component', toolInput)
        if (outcome.kind === 'pending_confirmation') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id && m.kind === 'inject' ? { ...m, status: 'awaiting_confirmation', pendingInput: outcome.input } : m,
            ),
          )
          return
        }
        await outcome.handle.result
        setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'done' } : m)))
      } catch (err) {
        const error = err instanceof Error ? err.message : String(err)
        setMessages((prev) =>
          prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'error', error } : m)),
        )
      }
      return
    }

    // Plain chat turn -- SPEC-201's llm.chat, with this project's prior
    // plain-chat turns as real multi-turn context (SPEC-302's own
    // backend addition to llm_providers.chat/daemon.llm_chat), now
    // persisted to SPEC-304's conversation log instead of living only
    // in React state.
    const id = newMessageId()
    setMessages((prev) => [...prev, { id, kind: 'chat', status: 'pending' }])
    try {
      const handle = await submitJob<string>('llm.chat', {
        prompt: command.message,
        history: chatHistory,
      })
      const reply = await handle.result
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'chat' ? { ...m, status: 'done', text: reply } : m)))
      // CTX-313.1: stamped once per turn and reused for both the local
      // state and the persisted call, so the Overview activity feed's
      // merge/sort sees the same value the UI already rendered.
      const userTurn: ConversationTurn = { role: 'user', content: command.message, timestamp: new Date().toISOString() }
      const assistantTurn: ConversationTurn = { role: 'assistant', content: reply, timestamp: new Date().toISOString() }
      setChatHistory((prev) => [...prev, userTurn, assistantTurn])
      await appendConversationTurn(projectName, userTurn)
      await appendConversationTurn(projectName, assistantTurn)
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'chat' ? { ...m, status: 'error', error } : m)))
    }
  }

  /** SPEC-204's confirmation gate, actually reachable: re-dispatches the
   * exact proposed input with `confirmed: true`, which now runs through
   * the real async job protocol identically to any other route. */
  async function handleConfirmInject(id: string) {
    const message = messages.find((m) => m.id === id)
    if (!message || message.kind !== 'inject' || !message.pendingInput) return

    setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'pending' } : m)))
    try {
      const outcome = await dispatchTool<Record<string, unknown>>('kicad.inject_component', message.pendingInput, true)
      if (outcome.kind === 'pending_confirmation') {
        throw new Error('Expected a confirmed dispatch to run, got pending_confirmation again')
      }
      await outcome.handle.result
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'done' } : m)))
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'error', error } : m)))
    }
  }

  /** Never calls the daemon at all -- declining a proposed board write
   * is a purely local decision, not something the daemon needs to know
   * about (there is nothing running to cancel; the first, unconfirmed
   * call never started any work). */
  function handleCancelInject(id: string) {
    setMessages((prev) =>
      prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'error', error: 'Cancelled — board not modified.' } : m)),
    )
  }

  if (!loaded) {
    return <p className="text-sm text-fg-muted">Loading conversation…</p>
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-3">
      {loadError && <p className="text-sm text-danger">{loadError}</p>}
      <OverviewDashboard project={project} chatHistory={chatHistory} />
      <div className="flex flex-col gap-2">
        {messages.map((message) => (
          <ChatMessageView
            key={message.id}
            message={message}
            onConfirmInject={handleConfirmInject}
            onCancelInject={handleCancelInject}
          />
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-line bg-surface px-3 py-2 text-sm"
          placeholder="generate ATtiny85, inject, or just ask a question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend()
          }}
        />
        <button
          type="button"
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-accent-fg disabled:opacity-50"
          onClick={handleSend}
          disabled={input.trim().length === 0}
        >
          Send
        </button>
      </div>
    </div>
  )
}

/** Renders what a message actually did -- a generate message shows the
 * real schema, an inject message shows success/failure exactly as
 * CTX-108.3's plain button did, a chat message shows the model's real
 * text response. Per-message state, not one global pending boolean
 * (SPEC-302 §3's own named risk). An `awaiting_confirmation` inject
 * message (CTX-204.1/CTX-108.4) is the one place this view has its own
 * buttons, rather than only reflecting state `handleSend` already
 * decided -- SPEC-204's whole point is that this decision needs a real
 * person in the loop before the daemon runs it. */
function ChatMessageView({
  message,
  onConfirmInject,
  onCancelInject,
}: {
  message: ChatMessage
  onConfirmInject: (id: string) => void
  onCancelInject: (id: string) => void
}) {
  if (message.kind === 'user') {
    return <p className="text-sm text-fg">{'> '}{message.text}</p>
  }

  if (message.kind === 'generate') {
    if (message.status === 'pending') {
      return <p className="text-sm text-fg-tertiary">Generating {message.partNumber}…</p>
    }
    if (message.status === 'error') {
      return <p className="text-sm text-danger">{message.error}</p>
    }
    return (
      <div className="flex flex-col gap-1 rounded bg-surface p-3">
        <p className="text-sm text-fg-secondary">
          Generated {String(message.schema?.part_number ?? message.partNumber)}
          {message.schema?.package ? ` (${String(message.schema.package)})` : ''}
        </p>
        <pre className="overflow-auto text-xs">{JSON.stringify(message.schema, null, 2)}</pre>
      </div>
    )
  }

  if (message.kind === 'inject') {
    if (message.status === 'pending') return <p className="text-sm text-fg-tertiary">Injecting…</p>
    if (message.status === 'awaiting_confirmation') {
      return (
        <div className="flex flex-col gap-2 rounded border border-warning-line bg-surface p-3">
          <p className="text-sm text-warning">
            This will write into the board KiCad currently has open. Confirm?
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-warning-accent px-3 py-1 text-xs font-medium text-accent-fg"
              onClick={() => onConfirmInject(message.id)}
            >
              Confirm
            </button>
            <button
              type="button"
              className="rounded bg-surface-alt px-3 py-1 text-xs font-medium text-fg-bright"
              onClick={() => onCancelInject(message.id)}
            >
              Cancel
            </button>
          </div>
        </div>
      )
    }
    if (message.status === 'error') return <p className="text-sm text-danger">{message.error}</p>
    return <p className="text-sm text-success">Injected into the open board.</p>
  }

  // message.kind === 'chat'
  if (message.status === 'pending') return <p className="text-sm text-fg-tertiary">Thinking…</p>
  if (message.status === 'error') return <p className="text-sm text-danger">{message.error}</p>
  return <p className="text-sm text-fg-bright">{message.text}</p>
}

export default App
