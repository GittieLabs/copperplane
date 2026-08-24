import { open } from '@tauri-apps/plugin-shell'
import { useEffect, useState } from 'react'
import type { Area } from '../lib/areas'
import { loadChatThread, promoteChatTurn, sendChatMessage, type ChatScope, type ChatTurn, type SourceRef } from '../lib/chat'
import { cacheDatasheet } from '../lib/components'
import { loadPart } from '../lib/partDetail'

/** SPEC-318 §2.2/§2.7: the one shared chat panel every area mounts --
 * Overview, Components, Schematic, PCB, Enclosure each supply their
 * own `scope`/`scopeId`/`title`/`promotionTargets`, but the collapse
 * behavior, thread loading, send flow, source-chip rendering, and
 * promote-to-note action all live here once. Deliberately not mounted
 * anywhere real yet (CTX-318.1) -- Phase 2 (Components) is the first
 * real integration. */

export interface PromotionTarget {
  label: string
  scope: ChatScope
  id: string
}

export interface AgentChatProps {
  /** SPEC-316's own Area union -- also the real `area` param chat.send
   * routes on, and the localStorage key this panel's own collapsed
   * state persists under. */
  area: Area
  scope: ChatScope
  scopeId: string
  /** The header text this area's own caller supplies -- AgentChat
   * itself has no per-area copy hardcoded into it. */
  title: string
  /** Optional project context enrichment for a Part-scoped chat opened
   * from inside a project (SPEC-318 §3's own named, legitimate "no
   * project open" state when omitted -- never an error). */
  projectName?: string
  /** Where "Save as note" can promote an assistant turn to -- e.g. a
   * Part-scoped chat offers `[{label: 'This part', scope: 'part', id:
   * partId}]`, and additionally offers the current project when one is
   * open. An empty array hides the action entirely. */
  promotionTargets: PromotionTarget[]
}

function collapsedStorageKey(area: Area): string {
  return `agent-chat-collapsed:${area}`
}

function sourceChipLabel(ref: SourceRef): string {
  switch (ref.kind) {
    case 'datasheet_page':
      return `Datasheet page ${ref.page}`
    case 'guidance_item':
      return `Design guidance: ${ref.category}`
    case 'connection_guidance':
      return `Pin ${ref.pin_number} guidance`
    case 'part_field':
      return `Part: ${ref.field}`
    case 'project_intent':
      return 'Project intent'
    case 'chat_turn':
      return 'Earlier answer'
    case 'note':
      return 'Saved note'
    case 'check_finding':
      return 'Check finding'
    default:
      return 'Source'
  }
}

/** Only these two kinds carry (or can resolve) a real, direct
 * open-the-document target -- `connection_guidance`/`part_field`/
 * `project_intent`/`chat_turn`/`note` all cite pre-assembled context or
 * a conversational fact with no document location to jump to, and
 * `check_finding` never actually resolves today (its own backend
 * resolver is still the deliberate `_resolve_deferred` stub). */
function isOpenableSource(ref: SourceRef): boolean {
  return ref.kind === 'datasheet_page' || ref.kind === 'guidance_item'
}

export function AgentChat({ area, scope, scopeId, title, projectName, promotionTargets }: AgentChatProps) {
  const [collapsed, setCollapsed] = useState(() => {
    const stored = localStorage.getItem(collapsedStorageKey(area))
    return stored === null ? true : stored === 'true'
  })
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [openingSourceKey, setOpeningSourceKey] = useState<string | null>(null)
  const [openSourceError, setOpenSourceError] = useState<string | null>(null)
  const [promptingTurnId, setPromptingTurnId] = useState<string | null>(null)
  const [promoting, setPromoting] = useState(false)
  const [promoteError, setPromoteError] = useState<string | null>(null)
  const [promotedByTurn, setPromotedByTurn] = useState<Record<string, string[]>>({})

  // CTX-318.1: loads on mount and whenever the real identity changes --
  // chat.load_thread is real, cheap local file I/O (not an LLM call,
  // confirmed against daemon.ASYNC_ROUTES), so there's no real cost to
  // loading it regardless of collapsed state, and keying on
  // [scope, scopeId] (matching this codebase's own established
  // identity-reset convention) is what keeps this correct if the same
  // mounted instance's scope ever changes -- e.g. a project-scoped
  // chat when the user switches projects while its own area's parent
  // component stays mounted (SPEC-318 §2.2's own mount-always pattern).
  useEffect(() => {
    let cancelled = false
    setTurns([])
    setLoaded(false)
    setLoadError(null)
    loadChatThread(scope, scopeId)
      .then((loadedTurns) => {
        if (cancelled) return
        setTurns(loadedTurns)
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
  }, [scope, scopeId])

  function handleToggle(isOpen: boolean) {
    setCollapsed(!isOpen)
    localStorage.setItem(collapsedStorageKey(area), String(!isOpen))
  }

  async function handleSend() {
    const message = draft.trim()
    if (!message) return
    setDraft('')
    setSending(true)
    setSendError(null)
    // A lightweight, local-only echo of the user's own turn -- CTX-206.6's
    // chat.send persists the real user turn server-side, but its own
    // response only ever returns the assistant turn, so this is never
    // replaced by anything the server sends back.
    const optimisticUserTurn: ChatTurn = {
      turn_id: `optimistic-${turns.length}-${message.length}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      agent: null,
      sources: [],
      sources_dropped: 0,
      general_practice: false,
      tool_calls: [],
      provenance: null,
      promoted_note_id: null,
    }
    setTurns((prev) => [...prev, optimisticUserTurn])
    try {
      const assistantTurn = await sendChatMessage(scope, scopeId, area, message, projectName)
      setTurns((prev) => [...prev, assistantTurn])
    } catch (err) {
      setSendError(err instanceof Error ? err.message : String(err))
    } finally {
      setSending(false)
    }
  }

  /** Generalizes PartDetail.tsx's own `handleOpenCitation` -- that one
   * is hardcoded to the single Part already open in that view.
   * `datasheet_page` already carries its own real `page`; `guidance_item`
   * doesn't (the chunk index's own SourceRef for it deliberately omits
   * one -- see CTX-206.7), so this resolves it by loading the real Part
   * and matching `category`+`quote` against its stored `design_guidance`
   * before falling through to the same cache-then-open flow. */
  async function handleOpenSource(ref: SourceRef, key: string) {
    if (!ref.part_id) return
    setOpeningSourceKey(key)
    setOpenSourceError(null)
    try {
      const part = await loadPart(ref.part_id)
      let page = ref.page
      if (ref.kind === 'guidance_item' && page === undefined) {
        const items = part.design_guidance?.categories[ref.category ?? ''] ?? []
        page = items.find((item) => item.quote === ref.quote)?.page
      }
      if (page === undefined) {
        throw new Error('Could not resolve a real page for this source.')
      }
      const path = await cacheDatasheet(part.part_id, part.datasheet_url)
      await open(`${path}#page=${page}`)
    } catch (err) {
      setOpenSourceError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningSourceKey(null)
    }
  }

  async function handlePromote(turn: ChatTurn, target: PromotionTarget) {
    setPromoting(true)
    setPromoteError(null)
    try {
      await promoteChatTurn(scope, scopeId, turn.turn_id, target.scope, target.id)
      setPromotedByTurn((prev) => ({
        ...prev,
        [turn.turn_id]: [...(prev[turn.turn_id] ?? []), `${target.scope}:${target.id}`],
      }))
    } catch (err) {
      setPromoteError(err instanceof Error ? err.message : String(err))
    } finally {
      setPromoting(false)
    }
  }

  return (
    <details
      className="rounded border border-line-subtle"
      open={!collapsed}
      onToggle={(e) => handleToggle((e.target as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-fg-muted">{title}</summary>
      <div className="flex flex-col gap-3 border-t border-line-subtle p-3">
        {loadError && <p className="text-sm text-danger">{loadError}</p>}
        {!loadError && !loaded && <p className="text-xs text-fg-muted">Loading…</p>}

        {turns.map((turn) => (
          <div key={turn.turn_id} className="flex flex-col gap-1">
            <p className={turn.role === 'user' ? 'text-sm text-fg' : 'text-sm text-fg-secondary'}>
              <span className="mr-1 text-xs font-medium uppercase text-fg-muted">
                {turn.role === 'user' ? 'You' : 'Assistant'}
              </span>
              {turn.content}
            </p>
            {turn.role === 'assistant' && turn.general_practice && (
              <p className="text-xs font-medium text-warning">
                General engineering practice -- not from this part's own data.
              </p>
            )}
            {turn.role === 'assistant' && turn.sources.length > 0 && (
              <details className="text-xs">
                <summary className="cursor-pointer text-fg-muted">
                  {turn.sources.length} source{turn.sources.length === 1 ? '' : 's'}
                  {turn.sources_dropped > 0 && ` (${turn.sources_dropped} dropped)`}
                </summary>
                <ul className="mt-1 flex flex-wrap gap-1">
                  {turn.sources.map((ref, i) => {
                    const key = `${turn.turn_id}-${ref.kind}-${i}`
                    const openable = isOpenableSource(ref)
                    return (
                      <li key={key}>
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-0.5 text-xs disabled:opacity-50"
                          onClick={openable ? () => void handleOpenSource(ref, key) : undefined}
                          disabled={!openable || openingSourceKey === key}
                          title={openable ? 'Open the real source' : undefined}
                        >
                          {openable && openingSourceKey === key ? '…' : sourceChipLabel(ref)}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </details>
            )}
            {turn.role === 'assistant' && promotionTargets.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                {promptingTurnId === turn.turn_id ? (
                  <>
                    {promotionTargets.map((target) => {
                      const alreadyPromoted = (promotedByTurn[turn.turn_id] ?? []).includes(
                        `${target.scope}:${target.id}`,
                      )
                      return (
                        <button
                          key={`${target.scope}:${target.id}`}
                          type="button"
                          className="rounded border border-line px-2 py-0.5 text-xs disabled:opacity-50"
                          onClick={() => void handlePromote(turn, target)}
                          disabled={promoting || alreadyPromoted}
                        >
                          {alreadyPromoted ? `Saved to ${target.label}` : `Save to ${target.label}`}
                        </button>
                      )
                    })}
                    <button
                      type="button"
                      className="text-xs text-fg-muted"
                      onClick={() => setPromptingTurnId(null)}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="text-xs text-fg-muted underline"
                    onClick={() => setPromptingTurnId(turn.turn_id)}
                  >
                    Save as note
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

        {/* SPEC-318 §3: AgentFlow 0.9.0 has no streaming of any kind
            (verified directly against the installed source) -- this is
            a real, honest static state, never a typing indicator that
            would imply token-by-token progress the app cannot deliver.
            CTX-318.1's own Plan Drift names real, per-tool-call progress
            text as deferred, separately-scoped follow-up work. */}
        {sending && <p className="text-xs text-fg-muted">Thinking…</p>}

        {openSourceError && <p className="text-xs text-danger">{openSourceError}</p>}
        {promoteError && <p className="text-xs text-danger">{promoteError}</p>}
        {sendError && <p className="text-sm text-danger">{sendError}</p>}

        <div className="flex gap-2">
          <input
            className="flex-1 rounded border border-line bg-surface px-3 py-2 text-sm"
            placeholder="Ask a question…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !sending) void handleSend()
            }}
            disabled={sending}
          />
          <button
            type="button"
            className="rounded border border-line px-3 py-1 text-xs font-medium disabled:opacity-50"
            onClick={() => void handleSend()}
            disabled={sending || draft.trim().length === 0}
          >
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </div>
    </details>
  )
}
