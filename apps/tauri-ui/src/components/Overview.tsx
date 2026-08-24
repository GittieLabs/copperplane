import { useState, useEffect } from 'react'
import { submitJob, dispatchTool } from '../lib/ipc'
import { parseCommand } from '../lib/commands'
import {
  appendConversationTurn,
  loadConversation,
  setProjectIntent,
  type ConversationTurn,
  type Project,
} from '../lib/projects'
import { AgentChat } from './AgentChat'
import { OverviewDashboard } from './OverviewDashboard'

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

/** SPEC-305 §2: Overview re-houses the existing chat surface unchanged
 * in substance, scoped to the selected project instead of one global
 * `chatHistory`. Only plain chat turns persist to `SPEC-304`'s
 * conversation log (SPEC-302 §2's own named limitation) -- a
 * `generate`/`inject` command's own message isn't folded back into the
 * LLM's context or persisted in this pass. Switching projects resets
 * all of this state so no conversation leaks across the boundary
 * (SPEC-305 §3's own named hazard).
 *
 * CTX-318.5: extracted out of `App.tsx` (SPEC-318 §2.7) and migrated to
 * the mount-always pattern every other area already follows (`App.tsx`
 * now hides it with CSS instead of unmounting it) -- `CTX-306.2` records
 * Overview as the one area that was "simply never included when that fix
 * was made." Also gains the project intent editor (SPEC-318 §2.4) and a
 * second, separately-scoped `AgentChat` panel (`area="overview"`)
 * alongside this still-functional `parseCommand`-driven chat -- SPEC-318
 * §2.6 defers deleting `parseCommand` and rehoming `generate`/`inject` to
 * a later phase, so both chats coexist here for now. */
export function Overview({
  projectName,
  project,
  onProjectUpdated,
}: {
  projectName: string
  project: Project | null
  onProjectUpdated?: (project: Project) => void
}) {
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
      <IntentEditor projectName={projectName} project={project} onProjectUpdated={onProjectUpdated} />
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
      {/* SPEC-318 §5/§2.6: a second, separately-scoped chat panel --
          the above surface is the still-functional parseCommand-driven
          one this spec's later phase retires; this is the real project
          agent, grounded in project intent/last_results/export_history/
          referenced Parts (§2.3's Overview row), with real sources. */}
      <AgentChat
        area="overview"
        scope="project"
        scopeId={`${projectName}:overview`}
        title="Ask about this project"
        projectName={projectName}
        promotionTargets={[{ label: 'this project', scope: 'project', id: projectName }]}
      />
    </div>
  )
}

/** SPEC-318 §2.4: the project intent editor -- optional free text,
 * editable any time from Overview, injected into every agent's context
 * verbatim as the user's stated goal. Its own local `draft`/`editing`
 * state resets on a real project switch (keyed on `projectName`, same
 * pattern as `Overview`'s own chat-history effect) so a half-edited
 * draft for one project never bleeds into the next. */
function IntentEditor({
  projectName,
  project,
  onProjectUpdated,
}: {
  projectName: string
  project: Project | null
  onProjectUpdated?: (project: Project) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setEditing(false)
    setDraft('')
    setSaving(false)
    setError(null)
  }, [projectName])

  const intent = project?.intent ?? null

  function startEditing() {
    setDraft(intent ?? '')
    setError(null)
    setEditing(true)
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const updated = await setProjectIntent(projectName, draft.trim())
      onProjectUpdated?.(updated)
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    setError(null)
    setEditing(false)
  }

  return (
    <div className="flex flex-col gap-1 rounded border border-line bg-surface p-3 text-sm">
      <p className="text-xs font-medium uppercase text-fg-muted">What you're building</p>
      {!editing ? (
        <div className="flex items-start justify-between gap-2">
          {intent ? (
            <p className="text-sm text-fg-secondary">{intent}</p>
          ) : (
            <p className="text-sm text-fg-muted">
              Not stated yet — agents answer generically until you add one.
            </p>
          )}
          <button
            type="button"
            className="shrink-0 text-xs text-fg-tertiary hover:text-fg-bright"
            onClick={startEditing}
          >
            {intent ? 'Edit' : 'Add'}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <textarea
            className="rounded border border-line bg-surface px-2 py-1 text-sm"
            rows={3}
            placeholder="e.g. I want to build a macropad from scratch"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={saving}
          />
          {error && <p className="text-xs text-danger">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
              onClick={() => void handleSave()}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright disabled:opacity-50"
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
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
