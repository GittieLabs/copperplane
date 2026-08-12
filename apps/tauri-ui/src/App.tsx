import { useState } from 'react'
import { submitJob, type JobHandle } from './lib/ipc'
import { parseCommand } from './lib/commands'
import { EnclosureViewer } from './components/EnclosureViewer'
import { Settings } from './components/Settings'

// SPEC-108's own Cross-Module Impacts section names a fixed placement
// position as enough for a first UI trigger ("even a hardcoded
// board-origin default for M1's demo"). A real position-picker UI is
// future work, not this command's job.
const _INJECT_DEFAULT_POSITION_MM = { x: 50, y: 50 }

type Status = 'pending' | 'done' | 'error'

/** Only plain chat turns feed `history` (SPEC-302 §2's own named
 * limitation) -- a `generate`/`inject` command's own message isn't
 * folded back into the LLM's context in this pass. */
interface HistoryTurn {
  role: 'user' | 'assistant'
  content: string
}

type ChatMessage =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'generate'; status: Status; partNumber: string; schema?: Record<string, unknown>; error?: string }
  | { id: string; kind: 'inject'; status: Status; error?: string }
  | { id: string; kind: 'chat'; status: Status; text?: string; error?: string }

let nextMessageId = 1
function newMessageId(): string {
  return `msg_${nextMessageId++}`
}

function App() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [latestSchema, setLatestSchema] = useState<Record<string, unknown> | null>(null)
  const [chatHistory, setChatHistory] = useState<HistoryTurn[]>([])
  // SPEC-303: a plain, temporary trigger -- SPEC-300's real rail shell
  // (SPEC-305) doesn't exist in code yet, same stopgap pattern CTX-108.3
  // used for kicad.inject_component. Not the permanent placement PR #48
  // describes (a fixed rail item beside Library); this just makes the
  // screen reachable at all.
  const [showSettings, setShowSettings] = useState(false)

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
      try {
        // SPEC-108: writes the most recently generated schema into
        // whatever board KiCad already has open. Mutates the real
        // board the instant it succeeds -- no confirmation step here
        // yet (SPEC-204, not written).
        const handle = await submitJob<Record<string, unknown>>('kicad.inject_component', {
          schema: latestSchema,
          x_mm: _INJECT_DEFAULT_POSITION_MM.x,
          y_mm: _INJECT_DEFAULT_POSITION_MM.y,
        })
        await handle.result
        setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'done' } : m)))
      } catch (err) {
        const error = err instanceof Error ? err.message : String(err)
        setMessages((prev) =>
          prev.map((m) => (m.id === id && m.kind === 'inject' ? { ...m, status: 'error', error } : m)),
        )
      }
      return
    }

    // Plain chat turn -- SPEC-201's llm.chat, with this conversation's
    // prior plain-chat turns as real multi-turn context (SPEC-302's own
    // backend addition to llm_providers.chat/daemon.llm_chat).
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
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'chat' ? { ...m, status: 'error', error } : m)))
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center gap-8 bg-neutral-950 p-8 text-neutral-100">
      <div className="flex w-full max-w-md items-center justify-between">
        <h1 className="text-2xl font-medium">Hardware Agent Studio</h1>
        <button
          type="button"
          className="rounded border border-neutral-700 px-3 py-1 text-sm"
          onClick={() => setShowSettings((prev) => !prev)}
        >
          {showSettings ? 'Back' : 'Settings'}
        </button>
      </div>

      {showSettings ? (
        <Settings />
      ) : (
        <>
          <div className="flex w-full max-w-md flex-col gap-3">
            <div className="flex flex-col gap-2">
              {messages.map((message) => (
                <ChatMessageView key={message.id} message={message} />
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
          <EnclosurePanel />
        </>
      )}
    </main>
  )
}

/** Renders what a message actually did -- a generate message shows the
 * real schema, an inject message shows success/failure exactly as
 * CTX-108.3's plain button did, a chat message shows the model's real
 * text response. Per-message state, not one global pending boolean
 * (SPEC-302 §3's own named risk). */
function ChatMessageView({ message }: { message: ChatMessage }) {
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
    if (message.status === 'error') return <p className="text-sm text-red-400">{message.error}</p>
    return <p className="text-sm text-emerald-400">Injected into the open board.</p>
  }

  // message.kind === 'chat'
  if (message.status === 'pending') return <p className="text-sm text-neutral-400">Thinking…</p>
  if (message.status === 'error') return <p className="text-sm text-red-400">{message.error}</p>
  return <p className="text-sm text-neutral-200">{message.text}</p>
}

/** Proves out CTX-105.2's job client against the one real async route
 * CTX-105.1 wired up (freecad.generate_enclosure): submit, watch progress,
 * cancel mid-flight, or land on a completed/failed result. Kept as its
 * own panel per SPEC-302's own design rationale -- enclosure generation
 * isn't part of this spec's "type to generate a footprint" promise. */
function EnclosurePanel() {
  const [dims, setDims] = useState({ width: 50, depth: 30, height: 20 })
  const [job, setJob] = useState<JobHandle<string> | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [glbPath, setGlbPath] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const running = status === 'running'

  async function handleGenerate() {
    setError(null)
    setGlbPath(null)
    setStatus('running')

    try {
      const handle = await submitJob<string>('freecad.generate_enclosure', dims)
      setJob(handle)
      handle.onUpdate((update) => setStatus(update.status))

      const path = await handle.result
      setGlbPath(path)
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
    <div className="flex w-full max-w-md flex-col gap-2 border-t border-neutral-800 pt-6">
      <h2 className="text-sm font-medium text-neutral-400">Enclosure Generator</h2>
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
      <div className="flex gap-2">
        <button
          type="button"
          className="flex-1 rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
          onClick={handleGenerate}
          disabled={running}
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
      {glbPath && (
        <>
          <p className="text-sm text-neutral-400">Generated: {glbPath}</p>
          <EnclosureViewer glbPath={glbPath} />
        </>
      )}
    </div>
  )
}

export default App
