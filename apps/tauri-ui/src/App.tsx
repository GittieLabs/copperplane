import { useEffect, useState } from 'react'
import { open } from '@tauri-apps/plugin-shell'
import { submitJob, dispatchTool, type JobHandle } from './lib/ipc'
import { parseCommand } from './lib/commands'
import { generateEnclosure, pickPcbFile, type EnclosureParams, type EnclosureResult } from './lib/enclosure'
import {
  appendConversationTurn,
  listLibraryParts,
  listProjects,
  loadConversation,
  saveProject,
  type ConversationTurn,
} from './lib/projects'
import { getCapabilities } from './lib/settings'
import { BoardAdvisor } from './components/BoardAdvisor'
import { ComponentDiscovery } from './components/ComponentDiscovery'
import { EnclosureViewer } from './components/EnclosureViewer'
import { Rail } from './components/Rail'
import { SchematicAdvisor } from './components/SchematicAdvisor'
import { Settings } from './components/Settings'

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
 * SPEC-306/308/309 build them. */
type Area = 'overview' | 'components' | 'schematic' | 'pcb' | 'enclosure'

const AREAS: { key: Area; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'components', label: 'Components' },
  { key: 'schematic', label: 'Schematic' },
  { key: 'pcb', label: 'PCB' },
  { key: 'enclosure', label: 'Enclosure' },
]

type View = { kind: 'settings' } | { kind: 'project'; name: string; area: Area } | null

function App() {
  const [projects, setProjects] = useState<string[]>([])
  const [libraryCount, setLibraryCount] = useState(0)
  const [view, setView] = useState<View>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

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

  return (
    <div className="flex min-h-screen bg-neutral-950 text-neutral-100">
      <Rail
        projects={projects}
        selectedProject={view?.kind === 'project' ? view.name : null}
        onSelectProject={handleSelectProject}
        onCreateProject={handleCreateProject}
        libraryCount={libraryCount}
        settingsSelected={view?.kind === 'settings'}
        onSelectSettings={() => setView({ kind: 'settings' })}
      />
      <main className="flex flex-1 flex-col items-center gap-6 overflow-auto p-8">
        {loadError && <p className="w-full max-w-md text-sm text-red-400">{loadError}</p>}

        {view === null && (
          <p className="text-sm text-neutral-500">Create a project on the left to get started.</p>
        )}

        {view?.kind === 'settings' && <Settings />}

        {view?.kind === 'project' && (
          <>
            <div className="flex w-full max-w-md gap-1 border-b border-neutral-800 pb-2">
              {AREAS.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  className={`rounded px-3 py-1 text-sm ${
                    view.area === key
                      ? 'bg-neutral-800 text-neutral-100'
                      : 'text-neutral-400 hover:bg-neutral-900'
                  }`}
                  onClick={() => handleSelectArea(key)}
                >
                  {label}
                </button>
              ))}
            </div>

            {view.area === 'overview' && <Overview projectName={view.name} />}
            {view.area === 'enclosure' && <EnclosurePanel projectName={view.name} />}
            {view.area === 'components' && <ComponentDiscovery />}
            {/* BoardAdvisor/SchematicAdvisor stay mounted across every area,
             * not just while their own tab is selected -- real user feedback
             * found that switching tabs away and back threw away a check
             * that had just finished, with no reason to. Hidden via CSS
             * instead of unmounted, so their own state (which board/
             * schematic was picked, the result) survives the round trip;
             * each resets that state itself when `projectName` changes, so
             * switching *projects* still starts fresh. Per SPEC-300's
             * original stage-machine design, ERC (Schematic) and DRC (PCB)
             * are two separate stages -- real user feedback flagged the
             * earlier both-checks-under-PCB layout as a mismatch, not
             * SPEC-308's own still-unbuilt footprint/connection-guidance
             * work, which will eventually join SchematicAdvisor here. */}
            <div className={view.area === 'schematic' ? undefined : 'hidden'}>
              <SchematicAdvisor projectName={view.name} />
            </div>
            <div className={view.area === 'pcb' ? undefined : 'hidden'}>
              <BoardAdvisor projectName={view.name} />
            </div>
          </>
        )}
      </main>
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
function Overview({ projectName }: { projectName: string }) {
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
      setChatHistory((prev) => [
        ...prev,
        { role: 'user', content: command.message },
        { role: 'assistant', content: reply },
      ])
      await appendConversationTurn(projectName, { role: 'user', content: command.message })
      await appendConversationTurn(projectName, { role: 'assistant', content: reply })
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
    return <p className="text-sm text-neutral-500">Loading conversation…</p>
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-3">
      {loadError && <p className="text-sm text-red-400">{loadError}</p>}
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
          className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          placeholder="generate ATtiny85, inject, or just ask a question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend()
          }}
        />
        <button
          type="button"
          className="rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
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
    return <p className="text-sm text-neutral-100">{'> '}{message.text}</p>
  }

  if (message.kind === 'generate') {
    if (message.status === 'pending') {
      return <p className="text-sm text-neutral-400">Generating {message.partNumber}…</p>
    }
    if (message.status === 'error') {
      return <p className="text-sm text-red-400">{message.error}</p>
    }
    return (
      <div className="flex flex-col gap-1 rounded bg-neutral-900 p-3">
        <p className="text-sm text-neutral-300">
          Generated {String(message.schema?.part_number ?? message.partNumber)}
          {message.schema?.package ? ` (${String(message.schema.package)})` : ''}
        </p>
        <pre className="overflow-auto text-xs">{JSON.stringify(message.schema, null, 2)}</pre>
      </div>
    )
  }

  if (message.kind === 'inject') {
    if (message.status === 'pending') return <p className="text-sm text-neutral-400">Injecting…</p>
    if (message.status === 'awaiting_confirmation') {
      return (
        <div className="flex flex-col gap-2 rounded border border-amber-700 bg-neutral-900 p-3">
          <p className="text-sm text-amber-400">
            This will write into the board KiCad currently has open. Confirm?
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-amber-500 px-3 py-1 text-xs font-medium text-neutral-950"
              onClick={() => onConfirmInject(message.id)}
            >
              Confirm
            </button>
            <button
              type="button"
              className="rounded bg-neutral-800 px-3 py-1 text-xs font-medium text-neutral-200"
              onClick={() => onCancelInject(message.id)}
            >
              Cancel
            </button>
          </div>
        </div>
      )
    }
    if (message.status === 'error') return <p className="text-sm text-red-400">{message.error}</p>
    return <p className="text-sm text-emerald-400">Injected into the open board.</p>
  }

  // message.kind === 'chat'
  if (message.status === 'pending') return <p className="text-sm text-neutral-400">Thinking…</p>
  if (message.status === 'error') return <p className="text-sm text-red-400">{message.error}</p>
  return <p className="text-sm text-neutral-200">{message.text}</p>
}

/** Proves out CTX-105.2's job client against the one real async route
 * CTX-105.1 wired up (freecad.generate_enclosure). Re-housed into the
 * Enclosure area tab unchanged (SPEC-305 §2) -- enclosure generation
 * isn't part of Overview's "type to generate a footprint" promise.
 *
 * CTX-109.2 adds the real board-driven mode CTX-109.1 built on the
 * daemon side: "From board" only appears once `daemon.get_capabilities`
 * reports `kicad_available`, and manual dimensions stay the always-
 * available fallback, unchanged from the original three fields.
 * `projectName` (the real, already-selected project -- SPEC-305's
 * shell) is threaded through as `project_name`, so a generated
 * enclosure is actually saved as a real Artifact instead of the daemon
 * route silently skipping persistence the way it does with no
 * project_name at all.
 *
 * CTX-310.2 adds a third mode, "Import board file…", reusing the same
 * geometry fields "From board" already collects (the outline/hole
 * *source* differs -- a picked `.kicad_pcb` file vs. a live connection
 * -- but `freecad_generate_enclosure`'s geometry params are identical
 * either way). Unlike "From board", this is always offered, live KiCad
 * connection or not -- SPEC-310's whole point is not needing one. */
function EnclosurePanel({ projectName }: { projectName: string }) {
  const [kicadAvailable, setKicadAvailable] = useState(false)
  const [mode, setMode] = useState<'manual' | 'board' | 'file'>('manual')
  const [dims, setDims] = useState({ width: 50, depth: 30, height: 20 })
  const [boardParams, setBoardParams] = useState({
    height: 20,
    wall_thickness_mm: 2.0,
    clearance_mm: 0.5,
    fillet_radius_mm: 1.0,
    standoff_height_mm: 5.0,
  })
  const [pcbPath, setPcbPath] = useState<string | null>(null)
  const [job, setJob] = useState<JobHandle<EnclosureResult> | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<EnclosureResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const running = status === 'running'

  useEffect(() => {
    let cancelled = false
    getCapabilities()
      .then((caps) => {
        if (!cancelled) setKicadAvailable(caps.kicad_available)
      })
      .catch(() => {
        // A capabilities failure just leaves "From board" unoffered --
        // manual dimensions remain fully usable either way.
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handlePickPcbFile() {
    // pickPcbFile returning null (the user closed the dialog) is a
    // normal, silent no-op -- not an error state, matching
    // BoardAdvisor's own pickSchematicFile handling.
    const path = await pickPcbFile()
    if (path) setPcbPath(path)
  }

  async function handleGenerate() {
    setError(null)
    setResult(null)
    setStatus('running')

    const params: EnclosureParams =
      mode === 'manual'
        ? { height: dims.height, width: dims.width, depth: dims.depth, project_name: projectName }
        : mode === 'file'
          ? { ...boardParams, pcb_path: pcbPath ?? undefined, project_name: projectName }
          : { ...boardParams, project_name: projectName }

    try {
      const handle = await generateEnclosure(params)
      setJob(handle)
      handle.onUpdate((update) => setStatus(update.status))

      setResult(await handle.result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setJob(null)
    }
  }

  async function handleCancel() {
    await job?.cancel()
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-2">
      <div className="flex gap-2">
        <button
          type="button"
          className={`rounded px-3 py-1 text-sm ${
            mode === 'manual' ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:bg-neutral-900'
          }`}
          onClick={() => setMode('manual')}
          disabled={running}
        >
          Manual dimensions
        </button>
        {kicadAvailable && (
          <button
            type="button"
            className={`rounded px-3 py-1 text-sm ${
              mode === 'board' ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:bg-neutral-900'
            }`}
            onClick={() => setMode('board')}
            disabled={running}
          >
            From board
          </button>
        )}
        <button
          type="button"
          className={`rounded px-3 py-1 text-sm ${
            mode === 'file' ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:bg-neutral-900'
          }`}
          onClick={() => setMode('file')}
          disabled={running}
        >
          Import board file…
        </button>
      </div>

      {mode === 'manual' ? (
        <div className="flex gap-2">
          {(['width', 'depth', 'height'] as const).map((dim) => (
            <input
              key={dim}
              type="number"
              className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
              placeholder={dim}
              value={dims[dim]}
              onChange={(e) => setDims((prev) => ({ ...prev, [dim]: Number(e.target.value) }))}
              disabled={running}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {mode === 'file' && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-neutral-700 px-3 py-2 text-sm disabled:opacity-50"
                onClick={handlePickPcbFile}
                disabled={running}
              >
                Choose .kicad_pcb file…
              </button>
              <p className="truncate text-xs text-neutral-500">{pcbPath ?? 'No file selected.'}</p>
            </div>
          )}
          {(
            [
              ['height', 'height (mm)'],
              ['wall_thickness_mm', 'wall thickness (mm)'],
              ['clearance_mm', 'clearance (mm)'],
              ['fillet_radius_mm', 'fillet radius (mm)'],
              ['standoff_height_mm', 'standoff height (mm)'],
            ] as const
          ).map(([field, placeholder]) => (
            <input
              key={field}
              type="number"
              className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
              placeholder={placeholder}
              value={boardParams[field]}
              onChange={(e) => setBoardParams((prev) => ({ ...prev, [field]: Number(e.target.value) }))}
              disabled={running}
            />
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          className="flex-1 rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
          onClick={handleGenerate}
          disabled={running || (mode === 'file' && !pcbPath)}
        >
          {running ? 'Generating…' : 'Generate Enclosure'}
        </button>
        {running && (
          <button
            type="button"
            className="rounded border border-neutral-700 px-4 py-2 text-sm font-medium disabled:opacity-50"
            onClick={handleCancel}
          >
            Cancel
          </button>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {result && result.unrecognized_holes.length > 0 && (
        <p className="text-sm text-amber-400">
          {result.unrecognized_holes.length} hole(s) on this board weren't recognized as mounting
          holes and were skipped -- no standoff was drilled for them.
        </p>
      )}
      {result && (
        <>
          <p className="text-sm text-neutral-400">Generated: {result.glb_path}</p>
          <EnclosureViewer glbPath={result.glb_path} />
          <button
            type="button"
            className="self-start rounded border border-neutral-700 px-2 py-0.5 text-xs"
            onClick={() => open(result.step_path)}
          >
            Open .step
          </button>
        </>
      )}
    </div>
  )
}

export default App
