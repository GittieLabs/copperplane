import { useEffect, useRef, useState } from 'react'
import { writeText } from '@tauri-apps/plugin-clipboard-manager'
import { pickKicadProject } from './lib/kicadProject'
import { listen } from '@tauri-apps/api/event'
import {
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
  MENU_DESIGN_SCHEMATIC_RUN_REVIEW_EVENT,
  MENU_DESIGN_PCB_RUN_REVIEW_EVENT,
  MENU_DESIGN_ENCLOSURE_RUN_REVIEW_EVENT,
  MENU_OPEN_LIBRARY_EVENT,
} from './lib/ipc'
import {
  listLibraryParts,
  listProjects,
  loadProject,
  openProjectFromDirectory,
  pickProjectDirectory,
  saveProject,
  type Project,
} from './lib/projects'
import { listLibraries } from './lib/library'
import { syncLibraryMenu, setDesignMenuEnabled } from './lib/menu'
import type { Area, MenuCommand } from './lib/areas'
import { BoardAdvisor } from './components/BoardAdvisor'
import { ComponentDiscovery } from './components/ComponentDiscovery'
import { EnclosurePanel, type EnclosureExportSuccessEvent } from './components/EnclosurePanel'
import { LibraryArea } from './components/LibraryArea'
import { Overview } from './components/Overview'
import { PartDetail } from './components/PartDetail'
import { Rail } from './components/Rail'
import { NewProjectWizard } from './components/NewProjectWizard'
import { findProjectsInDirectory } from './lib/kicadProject'
import { listRemovedProjects, renameProject, setProjectRemoved } from './lib/projects'
import { SchematicAdvisor } from './components/SchematicAdvisor'
import { Settings } from './components/Settings'
import { Welcome } from './components/Welcome'
import { GuidedSetup } from './components/GuidedSetup'
import { NoProjectLanding } from './components/NoProjectLanding'
import { RequirementsBanner } from './components/RequirementsBanner'
import type { Requirement } from './lib/requirements'
import {
  confirmRemoveProject,
  getCapabilities,
  getConfig,
  updateConfig,
  type DaemonCapabilities,
  type DaemonConfig,
} from './lib/settings'
import { loadPart, type SavedPart } from './lib/partDetail'

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
  /* SPEC-336: the first-run surfaces. `welcome` is only ever reached when
     onboarding has not been dismissed; `guidedSetup` is reachable at any time
     from the requirements banner, which is the route back the spec insists
     must stay permanently available. */
  | { kind: 'welcome' }
  | { kind: 'guidedSetup'; startAt: 'provider' | 'tools' }
  /* SPEC-336: the launch view, and where closing a project returns to. Not
     `null`: that meant "nothing decided yet" and rendered a bare sentence. */
  | { kind: 'noProject' }
  /* SPEC-335: creating a project owns the whole main area, and the tabbed
     project view is not shown until it completes. */
  | { kind: 'newProject' }
  | { kind: 'library'; initialLibraryId?: string }
  | { kind: 'project'; name: string; area: Area }
  // CTX-315.4: a Part is a global SPEC-304 object, not project-scoped, so
  // reopening one from the Library doesn't require a project to be open --
  // a real, separate top-level view rather than folding it into `project`.
  | { kind: 'partDetail'; partId: string }
  | null

/** A project folder shown by its own name, for the same reason the
 *  `.kicad_pro` beside it is: "we should change this to not show the path of
 *  the project and use a copy project path button". The full path stays in the
 *  tooltip and on the copy button. */
function folderName(directory?: string | null): string | null {
  if (!directory) return null
  const parts = directory.split('/').filter(Boolean)
  return parts[parts.length - 1] ?? directory
}

/** A .kicad_pro shown by name. The full path is a tooltip: it is long, it is
 *  rarely what a user is checking, and it pushed everything else off the row. */
function kicadProjectName(path?: string | null): string | null {
  if (!path) return null
  return (path.split('/').pop() ?? path).replace(/\.kicad_pro$/, '')
}

function App() {
  const [projects, setProjects] = useState<string[]>([])
  /* Listing projects reads every project record off disk and can take a
     visible moment. Until it finishes the main area was simply blank, with
     nothing to say why -- and a project created in that window was dropped
     when the in-flight list came back and overwrote it. */
  const [projectsLoading, setProjectsLoading] = useState(true)
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
  const [projectActionError, setProjectActionError] = useState<string | null>(null)
  // CTX-312.2: real user feedback -- clicking "Save Project" (or "Link to
  // folder…") gave no visible confirmation at all, so a real successful
  // save looked identical to nothing happening. A real, named message per
  // action, matching CTX-311.13's own "Exported to <path>" precedent --
  // persists until the next real action, not on an auto-dismiss timer.
  const [projectActionMessage, setProjectActionMessage] = useState<string | null>(null)

  /* SPEC-336: what is actually true about this install, re-read on demand.
     The banner and the guided steps both read this rather than any record of
     what onboarding did -- a user who finished the wizard and later
     uninstalled KiCad is not configured. */
  const [capabilities, setCapabilities] = useState<DaemonCapabilities | null>(null)
  /* Kept only so the initial read is observable to tests and future readers.
     Deliberately not passed to any writer: a held snapshot is what caused the
     clobber this context records as Deviation 10. */
  const [, setConfig] = useState<DaemonConfig>({})

  async function refreshCapabilities() {
    try {
      setCapabilities(await getCapabilities())
    } catch {
      // A capability probe that fails leaves `null`, which renders no banner
      // at all -- better than a banner asserting things are missing because
      // we could not ask.
    }
  }

  /* Decides the very first view: welcome only when onboarding has never been
     dismissed. Runs once, before the project list lands, so a first-time user
     never sees the landing view flash past first. */
  useEffect(() => {
    let cancelled = false
    void (async () => {
      let onboarded = true
      try {
        const cfg = await getConfig()
        if (cancelled) return
        setConfig(cfg)
        onboarded = cfg.onboarding_completed === true
      } catch {
        // Unreadable config is not a reason to trap someone in a wizard.
        onboarded = true
      }
      if (cancelled) return
      // Decided here and nowhere else, and before capabilities are probed --
      // a slow probe must not delay the first screen. `prev ?? ...` still
      // yields to a view the user has already navigated to.
      setView((prev) => prev ?? (onboarded ? { kind: 'noProject' } : { kind: 'welcome' }))
      await refreshCapabilities()
    })()
    return () => { cancelled = true }
  }, [])

  /* SPEC-336: records that setup was OFFERED, not that it succeeded. */
  async function dismissOnboarding() {
    try {
      // Read-modify-write, not a save of this component's snapshot: that
      // snapshot is from launch, and guided setup has written to the same
      // file since. Saving it back reverted the provider the user just chose.
      setConfig(await updateConfig({ onboarding_completed: true }))
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleFinishSetup() {
    await dismissOnboarding()
    await refreshCapabilities()
    setView({ kind: 'noProject' })
  }

  function handleOpenSetup(requirement: Requirement['id']) {
    setView({ kind: 'guidedSetup', startAt: requirement === 'provider' ? 'provider' : 'tools' })
  }

  /* SPEC-336: closing a project, which did not exist -- only switching to a
     different one did. Nothing is persisted on the way out: every project
     edit already writes through, as of SPEC-333's resolution. */
  /* SPEC-333: moves the record rather than writing a second one. The rail,
     the open view and the project record all key on the name, so all three
     follow the rename rather than being reloaded from disk. */
  async function handleRenameProject() {
    const next = draftName.trim()
    const current = currentProject?.name
    if (!current || !next || next === current) {
      setRenaming(false)
      return
    }
    try {
      const saved = await renameProject(current, next)
      setProjects((prev) => prev.map((entry) => (entry === current ? saved : entry)).sort())
      setCurrentProject((prev) => (prev ? { ...prev, name: saved } : prev))
      setView((prev) => (prev?.kind === 'project' ? { ...prev, name: saved } : prev))
      setRenaming(false)
      setProjectActionMessage(`Renamed to ${saved}`)
    } catch (err) {
      // Stays in edit mode: a refused name is something to correct, not to
      // lose. The collision message names the project already using it.
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  async function refreshRemoved() {
    try {
      setRemovedProjects(await listRemovedProjects())
    } catch {
      // Not worth surfacing: it only feeds an optional "show removed" line.
    }
  }

  /* SPEC-333: "All this should do is remove from the project list in the app."
     Deletes nothing, and says so -- the word a user brings to this is
     "delete", and being wrong in either direction is bad. */
  async function handleRemoveProject(name: string) {
    const confirmed = await confirmRemoveProject(name)
    if (!confirmed) return
    try {
      await setProjectRemoved(name, true)
      setProjects((prev) => prev.filter((entry) => entry !== name))
      await refreshRemoved()
      setView({ kind: 'noProject' })
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleRestoreProject(name: string) {
    try {
      await setProjectRemoved(name, false)
      setProjects((prev) => (prev.includes(name) ? prev : [...prev, name].sort()))
      await refreshRemoved()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    }
  }

  function handleCloseProject() {
    setView({ kind: 'noProject' })
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [names, parts] = await Promise.all([listProjects(), listLibraryParts()])
        if (cancelled) return
        // Merged, not replaced: a project created while this was in flight is
        // already in state, and this list was read before it existed.
        setProjects((prev) => [...names, ...prev.filter((n) => !names.includes(n))])
        setLibraryCount(parts.length)
        void refreshRemoved()
        // SPEC-336: emphatically NOT `names[0]`. `list_projects` is sorted,
        // so that opened the alphabetically first project -- "stable, and
        // meaningless", and possibly one that has since moved or broken.
        //
        // This effect no longer picks a view at all. Two effects both setting
        // the initial view raced: whichever of `list_projects` and
        // `get_config` resolved first won, so on a genuine first run the
        // welcome screen appeared or did not depending on disk timing. The
        // onboarding effect below is now the single decider.
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setProjectsLoading(false)
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

  // SPEC-318 §2.4: `intent` is only passed by Rail when the user actually
  // typed one -- `saveProject({ name })`'s existing behavior for a
  // skipped intent stays exactly as it was before this spec.
  /** SPEC-335: the wizard's single write, at the end of the flow. Everything
   *  it gathered arrives together, and the user chooses which tab to land on
   *  rather than always being dropped on Overview. */
  async function handleCreateProject(draft: {
    name: string
    intent?: string
    kicadProjectPath?: string | null
    openArea: Area
  }) {
    const { name, intent, kicadProjectPath, openArea } = draft
    try {
      // `intent` is omitted entirely rather than passed as undefined, keeping
      // saveProject({ name })'s existing skipped-intent path untouched.
      await saveProject({
        name,
        ...(intent ? { intent } : {}),
        ...(kicadProjectPath ? { kicad_project_path: kicadProjectPath } : {}),
      })
      setProjects((prev) => (prev.includes(name) ? prev : [...prev, name]))
      setView({ kind: 'project', name, area: openArea })
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

  /* SPEC-337: this sets the project FOLDER. It does not link a KiCad project,
     and it no longer says "Linked to <path>" -- which was true, and was read
     as the other link, by the person who wrote both specs. */
  async function handleSetProjectFolder() {
    if (!currentProject) return
    setProjectActionError(null)
    setProjectActionMessage(null)
    setFolderOffer(null)
    try {
      const directory = await pickProjectDirectory()
      if (!directory) return
      const saved = await saveProject({ ...currentProject, directory })
      setCurrentProject(saved)
      setProjectActionMessage(`Project folder set to ${directory}`)

      // Offered, never assumed (SPEC-337 §2). A second consequential write
      // from one choice is exactly what this app has been trimming out.
      if (!saved.kicad_project_path) {
        try {
          const found = await findProjectsInDirectory(directory)
          if (found.count > 0) setFolderOffer(found.projects)
        } catch {
          // A failed scan is not worth a visible error: the folder was set,
          // which is what the user asked for, and the banner still says a
          // KiCad project is missing.
        }
      }
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  /* Links a `.kicad_pro` the folder scan found, without a second file dialog. */
  async function handleLinkFoundProject(path: string) {
    if (!currentProject) return
    setFolderOffer(null)
    try {
      const saved = await saveProject({ ...currentProject, kicad_project_path: path })
      setCurrentProject(saved)
      setProjectActionMessage(`KiCad project linked: ${kicadProjectName(path) ?? path}`)
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  // A project's folder is a real path a user needs outside this app -- to open
  // it in Finder, or to hand to a tool. Copying beats a clickable path that
  // silently opens a dialog, which is what this used to be.
  const [copiedPath, setCopiedPath] = useState(false)
  /* SPEC-337: `.kicad_pro` files found in a just-set project folder, offered
     for linking. `null` when there is nothing to offer. */
  const [folderOffer, setFolderOffer] = useState<string[] | null>(null)
  /* SPEC-333: projects hidden from the list. Tracked so a removal always has a
     visible route back -- a removal with no way back is a different feature,
     and a worse one. */
  const [removedProjects, setRemovedProjects] = useState<string[]>([])
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState('')

  // Linking the .kicad_pro is also offered on the Schematic tab; doing it from
  // the header saves the same field through the same route. The project view
  // is keyed on the path (below) so panels holding schematic/board data
  // re-read rather than showing the previous project's components.
  async function handleChangeKicadProject() {
    if (!currentProject) return
    try {
      const picked = await pickKicadProject()
      if (!picked) return
      const saved = await saveProject({ ...currentProject, kicad_project_path: picked })
      setCurrentProject(saved)
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleCopyProjectPath() {
    if (!currentProject?.directory) return
    try {
      await writeText(currentProject.directory)
      setCopiedPath(true)
      window.setTimeout(() => setCopiedPath(false), 1500)
    } catch (err) {
      setProjectActionError(err instanceof Error ? err.message : String(err))
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
    on(MENU_DESIGN_SCHEMATIC_RUN_REVIEW_EVENT, () => onDesignCommand('schematic', 'run_review'))
    on(MENU_DESIGN_PCB_RUN_REVIEW_EVENT, () => onDesignCommand('pcb', 'run_review'))
    on(MENU_DESIGN_ENCLOSURE_RUN_REVIEW_EVENT, () => onDesignCommand('enclosure', 'run_review'))

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
        onStartNewProject={() => setView({ kind: 'newProject' })}
        projectsLoading={projectsLoading}
        libraryCount={libraryCount}
        librarySelected={view?.kind === 'library' || view?.kind === 'partDetail'}
        onSelectLibrary={() => setView({ kind: 'library' })}
        settingsSelected={view?.kind === 'settings'}
        onSelectSettings={() => setView({ kind: 'settings' })}
      />
      <main className="flex flex-1 flex-col overflow-auto">
        {/* SPEC-336: the only thing standing between an unconfigured app and
            "watching features fail one at a time". Not shown on the onboarding
            surfaces themselves, which are already about exactly this. */}
        {view?.kind !== 'welcome' && view?.kind !== 'guidedSetup' && (
          <RequirementsBanner
            capabilities={capabilities}
            onOpenSetup={handleOpenSetup}
            onRecheck={() => void refreshCapabilities()}
          />
        )}

        <div className="flex flex-1 flex-col items-center gap-6 p-8">
        {loadError && <p className="w-full max-w-4xl text-sm text-danger">{loadError}</p>}

        {view?.kind === 'welcome' && (
          <Welcome
            onChooseGuided={() => setView({ kind: 'guidedSetup', startAt: 'provider' })}
            onChooseManual={() => { void dismissOnboarding(); setView({ kind: 'settings' }) }}
            onSkip={() => void handleFinishSetup()}
          />
        )}

        {view?.kind === 'guidedSetup' && (
          <GuidedSetup
            capabilities={capabilities}
            startAt={view.startAt}
            onCapabilitiesChanged={setCapabilities}
            onFinish={() => void handleFinishSetup()}
            onOpenManualSettings={() => { void dismissOnboarding(); setView({ kind: 'settings' }) }}
          />
        )}

        {(view === null || view?.kind === 'noProject') && (
          <NoProjectLanding
            projects={projects}
            removedProjects={removedProjects}
            onRestoreProject={(name) => void handleRestoreProject(name)}
            storageRoot={capabilities?.storage_root ?? null}
            loading={projectsLoading}
            onCreateProject={() => setView({ kind: 'newProject' })}
            onOpenProject={handleSelectProject}
          />
        )}

        {view?.kind === 'newProject' && (
          <NewProjectWizard
            existingProjects={projects}
            onCreate={handleCreateProject}
            /* Cancel returns to whatever "no project" looks like today. Nothing
               was written, so there is nothing to undo. */
            onCancel={() => setView(null)}
          />
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
            {/* SPEC-335 Phase 5 / SPEC-336: skipping the KiCad link is allowed,
                so the app has to say what that costs rather than leaving the
                user to find out by watching features fail one at a time. Not
                dismissible: a banner that can be dismissed forever returns the
                user to an unexplained broken app with no route back. */}
            {currentProject && !currentProject.kicad_project_path && (
              <div className="flex w-full max-w-4xl items-center justify-between gap-3 rounded border border-warning/40 bg-warning/5 px-3 py-2 text-xs">
                <span className="text-warning">
                  No KiCad project (<code>.kicad_pro</code>) is linked, so board and schematic
                  checks, the component list and the enclosure cannot run. A project folder is a
                  different setting and does not replace this.
                </span>
                <button
                  type="button"
                  className="shrink-0 rounded border border-warning/50 px-2 py-1 font-medium text-warning hover:bg-warning/10"
                  onClick={() => void handleChangeKicadProject()}
                >
                  Link one
                </button>
              </div>
            )}

            <div className="flex w-full max-w-4xl items-center justify-between gap-2 text-xs">
              {/* Paths are long, and neither one earns permanent screen space:
                  "showing the complete paths ... only clutters the screen.
                  Neither offers enough value to be statically shown." So the
                  KiCad project shows by FILE NAME, its full path is one hover
                  away, and the project folder is a copy button rather than a
                  wall of text. */}
              <div data-testid="project-header" className="flex min-w-0 flex-col gap-0.5">
                {/* SPEC-333: renaming happens on the name itself. A native
                    dialog cannot take text, and a second modal to type into
                    would be heavier than the thing it renames. */}
                {renaming ? (
                  <span className="flex items-center gap-2">
                    <input
                      aria-label="Project name"
                      autoFocus
                      className="min-w-0 flex-1 rounded border border-line bg-surface px-2 py-0.5 text-xl font-semibold text-fg-bright"
                      value={draftName}
                      onChange={(e) => setDraftName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void handleRenameProject()
                        if (e.key === 'Escape') setRenaming(false)
                      }}
                    />
                    <button
                      type="button"
                      className="shrink-0 rounded bg-accent px-2 py-1 text-xs font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
                      disabled={!draftName.trim() || draftName.trim() === currentProject?.name}
                      onClick={() => void handleRenameProject()}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="shrink-0 text-xs text-fg-muted hover:text-fg-secondary"
                      onClick={() => setRenaming(false)}
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <p className="truncate text-xl font-semibold text-fg-bright">
                      {currentProject?.name ?? 'Untitled project'}
                    </p>
                    <button
                      type="button"
                      className="shrink-0 rounded border border-line px-1 text-xs text-fg-tertiary hover:bg-surface-alt hover:text-fg-bright disabled:opacity-50"
                      onClick={() => {
                        setDraftName(currentProject?.name ?? '')
                        setProjectActionError(null)
                        setRenaming(true)
                      }}
                      disabled={!currentProject}
                    >
                      Rename
                    </button>
                  </span>
                )}
                {/* SPEC-337: two links, two names, both stated. "Linked" is
                    now used only for the KiCad project; a folder is "set". */}
                <p className="flex items-center gap-2 text-xs text-fg-muted">
                  <span className="truncate" title={currentProject?.kicad_project_path ?? undefined}>
                    Linked KiCad project:{' '}
                    <span className="text-fg-secondary">
                      {kicadProjectName(currentProject?.kicad_project_path) ?? 'none yet'}
                    </span>
                  </span>
                  {/* Names what it changes. "Change folder…" sat next to two
                      different paths and could be read as either. */}
                  <button
                    type="button"
                    className="shrink-0 rounded border border-line px-1 text-fg-tertiary hover:bg-surface-alt hover:text-fg-bright disabled:opacity-50"
                    onClick={() => void handleChangeKicadProject()}
                    disabled={!currentProject}
                  >
                    {currentProject?.kicad_project_path ? 'Change' : 'Link'}
                  </button>
                  {/* A new project has no folder until one is chosen, and the
                      folder is where its artifacts and portable manifest live
                      -- so linking stays reachable, just only while it is
                      actually missing. Once linked, the path is a copy button
                      rather than a permanent line of text. */}
                  {/* SPEC-336: closing a project, which had no equivalent --
                      only switching to a different one did. */}
                  <button
                    type="button"
                    className="shrink-0 rounded border border-line px-1 text-fg-tertiary hover:bg-surface-alt hover:text-fg-bright"
                    onClick={handleCloseProject}
                  >
                    Close project
                  </button>
                  <button
                    type="button"
                    className="shrink-0 rounded border border-line px-1 text-fg-tertiary hover:bg-surface-alt hover:text-fg-bright disabled:opacity-50"
                    onClick={() => currentProject && void handleRemoveProject(currentProject.name)}
                    disabled={!currentProject}
                  >
                    Remove from list
                  </button>
                </p>
                <p className="flex items-center gap-2 text-xs text-fg-muted">
                  <span
                    data-testid="project-folder"
                    className="truncate"
                    title={currentProject?.directory ?? undefined}
                  >
                    Project folder:{' '}
                    <span className="text-fg-secondary">
                      {folderName(currentProject?.directory) ?? 'none yet'}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="shrink-0 rounded border border-line px-1 text-fg-tertiary hover:bg-surface-alt hover:text-fg-bright disabled:opacity-50"
                    onClick={() => void handleSetProjectFolder()}
                    disabled={!currentProject}
                  >
                    {currentProject?.directory ? 'Change folder…' : 'Set folder…'}
                  </button>
                  {currentProject?.directory && (
                    <button
                      type="button"
                      className="shrink-0 rounded border border-line px-1 text-fg-tertiary hover:bg-surface-alt hover:text-fg-bright"
                      onClick={() => void handleCopyProjectPath()}
                      title={currentProject.directory}
                    >
                      {copiedPath ? 'Copied' : 'Copy folder path'}
                    </button>
                  )}
                </p>
              </div>
              {/* "I still don't believe we need a Save project button. We
                  should save the project at project creation time and have all
                  other edits update as things change which is mostly what is
                  happening anyway." -- correct, and it was worse than
                  redundant: it wrote a whole in-memory snapshot, erasing
                  anything a dedicated route had written since (SPEC-333).
                  Every field now persists at the moment it changes. */}
            </div>
            {/* SPEC-337: the folder that was just set contains a KiCad
                project. Offered in one click; never linked automatically. */}
            {folderOffer && folderOffer.length > 0 && (
              <div className="flex w-full max-w-4xl flex-col gap-2 rounded border border-line bg-surface-alt/50 px-3 py-2 text-xs">
                <span className="text-fg-secondary">
                  {folderOffer.length === 1
                    ? 'That folder contains a KiCad project. Link it too?'
                    : `That folder contains ${folderOffer.length} KiCad projects. Link one?`}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  {folderOffer.map((path) => (
                    <button
                      key={path}
                      type="button"
                      className="rounded border border-line px-2 py-1 text-fg-secondary hover:bg-surface-alt hover:text-fg-bright"
                      onClick={() => void handleLinkFoundProject(path)}
                      title={path}
                    >
                      Link {kicadProjectName(path) ?? path}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="text-fg-muted hover:text-fg-secondary"
                    onClick={() => setFolderOffer(null)}
                  >
                    Not now
                  </button>
                </span>
              </div>
            )}

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

            {/* Overview/ComponentDiscovery/BoardAdvisor/SchematicAdvisor/
             * EnclosurePanel stay mounted across every area, not just
             * while their own tab is selected -- real user feedback found
             * that switching tabs away and back threw away a check (or,
             * for Enclosure, a just-generated real enclosure), or for
             * Components, a whole confirmed part's in-progress Save/
             * Export/Generate Design Requirements work, that had just
             * finished, with no reason to. Hidden via CSS instead of
             * unmounted, so their own state survives the round trip; each
             * resets that state itself when `projectName` changes, so
             * switching *projects* still starts fresh. CTX-306.2 recorded
             * Overview as the one area "simply never included when that
             * fix was made" -- SPEC-318 §2.2 finishes migrating it here,
             * so an in-flight chat answer or a half-typed question now
             * survives a tab switch too. Per SPEC-300's original
             * stage-machine design, ERC (Schematic) and DRC (PCB) are two
             * separate stages -- real user feedback flagged the earlier
             * both-checks-under-PCB layout as a mismatch, not SPEC-308's
             * own still-unbuilt footprint/connection-guidance work, which
             * will eventually join SchematicAdvisor here. */}
            <div data-testid="overview-area" className={view.area === 'overview' ? 'w-full' : 'hidden'}>
              <Overview projectName={view.name} project={currentProject} onProjectUpdated={setCurrentProject} />
            </div>
            <div data-testid="components-area" className={view.area === 'components' ? 'w-full' : 'hidden'}>
              <ComponentDiscovery projectName={view.name} currentProject={currentProject} />
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
        </div>
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

export default App
