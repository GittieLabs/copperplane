import { useState, useEffect } from 'react'
import { submitJob } from '../lib/ipc'
import {
  appendConversationTurn,
  loadConversation,
  setProjectIntent,
  type ConversationTurn,
  type Project,
} from '../lib/projects'
import { AgentChat } from './AgentChat'
import { suggestParts, type SuggestionResult } from '../lib/suggestedParts'

type Status = 'pending' | 'done' | 'error'

/** CTX-207.1 (SPEC-207 §2.2): `llm.chat`'s real job result shape -- a
 * bare string before this. `usage`/`model` aren't rendered anywhere yet
 * (no surface for them exists until SPEC-320), but the daemon's own
 * per-call token accounting reaches the frontend for the first time. */
interface LlmChatResult {
  text: string
  usage: { input_tokens: number; output_tokens: number } | null
  model: string | null
}

type ChatMessage =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'chat'; status: Status; text?: string; error?: string }

let nextMessageId = 1
function newMessageId(): string {
  return `msg_${nextMessageId++}`
}

/** SPEC-305 §2: Overview re-houses the existing chat surface unchanged
 * in substance, scoped to the selected project instead of one global
 * `chatHistory`. Persists every turn to `SPEC-304`'s conversation log,
 * feeding `SPEC-313`'s activity feed. Switching projects resets all of
 * this state so no conversation leaks across the boundary (SPEC-305 §3's
 * own named hazard).
 *
 * CTX-318.5: extracted out of `App.tsx` (SPEC-318 §2.7) and migrated to
 * the mount-always pattern every other area already follows. Also gains
 * the project intent editor (SPEC-318 §2.4) and a second, separately-
 * scoped `AgentChat` panel (`area="overview"`).
 *
 * CTX-318.6: `parseCommand`'s `generate`/`inject` branches are gone --
 * `kicad.generate_component` moved to Components (a real "Generate
 * directly from a part number" fallback in `ComponentDiscovery`, next to
 * search) and `SPEC-108`'s inject flow moved to `PartDetail`, once a Part
 * is confirmed/saved (`PRODUCT-PLAN.md` §7's own disposition table).
 * This surface is now unconditionally a plain `llm.chat` turn -- exactly
 * what `parseCommand` already fell through to for anything that didn't
 * match `generate <part>` or `inject`, so no user-visible behavior
 * changes for a plain question. */
export function Overview({
  projectName,
  project,
  onProjectUpdated,
  onCarryToSearch,
}: {
  projectName: string
  project: Project | null
  onProjectUpdated?: (project: Project) => void
  /** SPEC-328 §5: "Each entry can be carried straight into the existing part
   *  search." Owned by App, which is what knows about area tabs -- Overview
   *  should not have to know that Components is a sibling tab. */
  onCarryToSearch?: (searchTerm: string) => void
}) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatHistory, setChatHistory] = useState<ConversationTurn[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setInput('')
    setMessages([])
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

    // SPEC-201's llm.chat, with this project's prior plain-chat turns as
    // real multi-turn context, persisted to SPEC-304's conversation log
    // instead of living only in React state.
    const id = newMessageId()
    setMessages((prev) => [...prev, { id, kind: 'chat', status: 'pending' }])
    try {
      const handle = await submitJob<LlmChatResult>('llm.chat', {
        prompt: text,
        history: chatHistory,
      })
      const reply = (await handle.result).text
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'chat' ? { ...m, status: 'done', text: reply } : m)))
      // CTX-313.1: stamped once per turn and reused for both the local
      // state and the persisted call, so the Overview activity feed's
      // merge/sort sees the same value the UI already rendered.
      const userTurn: ConversationTurn = { role: 'user', content: text, timestamp: new Date().toISOString() }
      const assistantTurn: ConversationTurn = { role: 'assistant', content: reply, timestamp: new Date().toISOString() }
      setChatHistory((prev) => [...prev, userTurn, assistantTurn])
      await appendConversationTurn(projectName, userTurn)
      await appendConversationTurn(projectName, assistantTurn)
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      setMessages((prev) => prev.map((m) => (m.id === id && m.kind === 'chat' ? { ...m, status: 'error', error } : m)))
    }
  }

  if (!loaded) {
    return <p className="text-sm text-fg-muted">Loading conversation…</p>
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-3">
      {loadError && <p className="text-sm text-danger">{loadError}</p>}
      {/* Keyed, not reset by an effect. `key` is React's own answer to
          "reset state when a prop changes", and the difference is not
          stylistic: an effect writes state AFTER the commit that put the
          editor on screen, so a click landing in that window is silently
          undone and the editor can never open. That raced in CI and
          reproduced locally in roughly one full-suite run in eight --
          probe output at the failure read "startEditing clicked" and then
          "reset effect ran". A remount has no such window. */}
      <IntentEditor
        key={projectName}
        projectName={projectName}
        project={project}
        onProjectUpdated={onProjectUpdated}
      />
      {/* SPEC-328 Phase 4: directly beneath the sentence it reads from, so it
          is obviously about that sentence and not a separate feature. */}
      <SuggestedParts
        projectName={projectName}
        project={project}
        onCarryToSearch={onCarryToSearch}
      />
      {/* The four per-area status cards were removed. They said "Not yet
          checked this session" for PCB and Schematic -- which the on-demand
          checks make irrelevant, since a check runs when asked and its result
          is on that area's own tab -- and for Enclosure and Components, which
          have no check at all. "We essentially built a guess at what the
          future would need and it's time to remove this work and re-imagine
          if there are glanceable/summarizable content that we would want to
          see when we open a project." What replaces them is SPEC-335's
          question, not a card grid guessed at again. */}
      <div className="flex flex-col gap-2">
        {messages.map((message) => (
          <ChatMessageView key={message.id} message={message} />
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-line bg-surface px-3 py-2 text-sm"
          placeholder="ask a question about this project"
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
      {/* The Overview Run Review was removed: it reviewed a project whose
          only real check results live on the PCB and Schematic tabs, where
          the review already runs against a live check. "The Run Review on the
          overview doesn't do anything and is unneccessary." */}
      {/* SPEC-318 §5: a second, separately-scoped chat panel -- the real
          project agent, grounded in project intent/last_results/
          export_history/referenced Parts (§2.3's Overview row), with
          real sources, distinct from the plain llm.chat surface above. */}
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
 * state resets on a real project switch so a half-edited draft for one
 * project never bleeds into the next -- by remounting on a `key`, never
 * by an effect. See the mount site for what the effect version cost. */
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

/** SPEC-328 Phase 4 and 5: what kinds of part this project needs.
 *
 *  Deliberately NOT a new conversational shape. `SPEC-328` §2 warned that the
 *  app already has a per-area chat and a four-step wizard and "adding a fifth
 *  shape would be a mistake", so this hangs off the intent the user has
 *  already written: one action, a list, and a way into the search that exists.
 *
 *  Every honest state this can be in is a state it renders. A vague brief
 *  comes back as a question rather than a list, because `CTX-328.1` Phase 1
 *  measured that as the real behaviour and rendering an empty list beside a
 *  question would make the question look like a footnote. */
function SuggestedParts({
  projectName,
  project,
  onCarryToSearch,
}: {
  projectName: string
  project: Project | null
  onCarryToSearch?: (searchTerm: string) => void
}) {
  const [result, setResult] = useState<SuggestionResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const intent = project?.intent ?? null
  /* SPEC-328 Phase 5: once a real KiCad project is attached, these are at best
     advisory and at worst contradict what is actually on the board. The board
     is the thing that exists; a list of categories is what someone intended
     before it did. */
  const hasRealProject = Boolean(project?.kicad_project_path)

  useEffect(() => {
    // A suggestion set belongs to the project it was asked about. Carrying one
    // project's list into another is the stale-result bug CTX-326.3 and
    // CTX-306.4 both shipped once already.
    setResult(null)
    setError(null)
  }, [projectName, intent])

  async function run() {
    setRunning(true)
    setError(null)
    try {
      setResult(await suggestParts(projectName))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  if (!intent) return null

  return (
    <div className="flex flex-col gap-2 rounded border border-line bg-surface p-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs font-medium uppercase text-fg-muted">What parts you'll need</p>
        <button
          type="button"
          className="shrink-0 text-xs text-fg-tertiary hover:text-fg-bright disabled:opacity-50"
          onClick={() => void run()}
          disabled={running}
        >
          {running ? 'Thinking…' : result ? 'Ask again' : 'Suggest parts'}
        </button>
      </div>

      {hasRealProject && (
        <p className="text-xs text-warning">
          This project already has a KiCad design. These are what the description asks for, not what
          is on your board — check them against the Components tab rather than the other way round.
        </p>
      )}

      {error && <p className="text-xs text-danger">{error}</p>}

      {!result && !running && !error && (
        <p className="text-xs text-fg-muted">
          Turns what you wrote above into the kinds of component to look for.
        </p>
      )}

      {result && !result.ready && (
        <p className="text-sm text-fg-secondary">{result.question}</p>
      )}

      {result?.ready && result.suggestions.length > 0 && (
        <>
          <ul className="flex flex-col gap-2">
            {result.suggestions.map((s) => (
              <li key={s.category} className="flex items-start justify-between gap-3">
                <div className="flex flex-col">
                  <span className="text-sm text-fg-bright">{s.category}</span>
                  <span className="text-xs text-fg-tertiary">{s.why}</span>
                </div>
                <button
                  type="button"
                  className="shrink-0 text-xs text-fg-tertiary underline hover:text-fg-bright"
                  onClick={() => onCarryToSearch?.(s.search_term)}
                >
                  Search for this
                </button>
              </li>
            ))}
          </ul>
          {/* Rendered from the record, never retyped here -- SPEC-328 §3's
              framing travels with the data so a second surface cannot lose
              it. */}
          <p className="text-xs text-fg-muted">{result.caveat}</p>
        </>
      )}

      {result?.ready && result.rejected.length > 0 && (
        <p className="text-xs text-fg-muted">
          {result.rejected.length} suggestion{result.rejected.length === 1 ? ' was' : 's were'} left
          out for naming a specific part rather than a kind of part.
        </p>
      )}
    </div>
  )
}

/** Renders a plain chat turn -- a user turn, or the model's real text
 * response. Per-message state, not one global pending boolean (SPEC-302
 * §3's own named risk). */
function ChatMessageView({ message }: { message: ChatMessage }) {
  if (message.kind === 'user') {
    return <p className="text-sm text-fg">{'> '}{message.text}</p>
  }

  if (message.status === 'pending') return <p className="text-sm text-fg-tertiary">Thinking…</p>
  if (message.status === 'error') return <p className="text-sm text-danger">{message.error}</p>
  return <p className="text-sm text-fg-bright">{message.text}</p>
}
