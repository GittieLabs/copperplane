import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const loadChatThreadMock = vi.fn()
const sendChatMessageMock = vi.fn()
const promoteChatTurnMock = vi.fn()
const cacheDatasheetMock = vi.fn()
const loadPartMock = vi.fn()
const openMock = vi.fn()

vi.mock('../lib/chat', () => ({
  loadChatThread: (...args: unknown[]) => loadChatThreadMock(...args),
  sendChatMessage: (...args: unknown[]) => sendChatMessageMock(...args),
  promoteChatTurn: (...args: unknown[]) => promoteChatTurnMock(...args),
}))

vi.mock('../lib/components', () => ({
  cacheDatasheet: (...args: unknown[]) => cacheDatasheetMock(...args),
}))

vi.mock('../lib/partDetail', () => ({
  loadPart: (...args: unknown[]) => loadPartMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => openMock(...args),
}))

const { AgentChat } = await import('./AgentChat')

const ASSISTANT_TURN = {
  turn_id: 't2',
  role: 'assistant' as const,
  content: 'Add a 100nF ceramic capacitor near VCC.',
  timestamp: '2026-08-24T00:00:00Z',
  agent: 'chat_components',
  sources: [{ kind: 'guidance_item', part_id: 'ATtiny85', category: 'power', quote: 'Add a 100nF cap.' }],
  sources_dropped: 0,
  general_practice: false,
  tool_calls: [],
  provenance: { provider: 'anthropic', model: 'claude-sonnet-5' },
  promoted_note_id: null,
}

beforeEach(() => {
  loadChatThreadMock.mockReset().mockResolvedValue([])
  sendChatMessageMock.mockReset()
  promoteChatTurnMock.mockReset()
  cacheDatasheetMock.mockReset()
  loadPartMock.mockReset()
  openMock.mockReset()
  localStorage.clear()
})

describe('AgentChat', () => {
  it('TEST-001: starts collapsed by default and loads the real thread on mount', async () => {
    loadChatThreadMock.mockResolvedValueOnce([ASSISTANT_TURN])

    render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )

    expect(loadChatThreadMock).toHaveBeenCalledWith('part', 'ATtiny85')
    const details = screen.getByText('Ask about this part').closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    // Collapsed by default doesn't mean unloaded -- the turn is real,
    // already-fetched content, just not visible until expanded.
    await waitFor(() => screen.getByText('Add a 100nF ceramic capacitor near VCC.'))
  })

  it('TEST-002: expanding and collapsing persists per area across a remount', async () => {
    const { unmount } = render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))
    await waitFor(() => {
      const details = screen.getByText('Ask about this part').closest('details') as HTMLDetailsElement
      expect(details.open).toBe(true)
    })
    unmount()

    render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )

    const details = screen.getByText('Ask about this part').closest('details') as HTMLDetailsElement
    expect(details.open).toBe(true)
  })

  it('TEST-003: reloads the thread when scopeId changes -- switching Parts never shows a stale thread', async () => {
    loadChatThreadMock.mockResolvedValueOnce([]).mockResolvedValueOnce([ASSISTANT_TURN])
    const { rerender } = render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )
    await waitFor(() => expect(loadChatThreadMock).toHaveBeenCalledTimes(1))

    rerender(
      <AgentChat area="components" scope="part" scopeId="ESP32-S3" title="Ask about this part" promotionTargets={[]} />,
    )

    await waitFor(() => expect(loadChatThreadMock).toHaveBeenLastCalledWith('part', 'ESP32-S3'))
  })

  it('TEST-004: sending a message shows Thinking, then renders the real returned turn without re-fetching the thread', async () => {
    sendChatMessageMock.mockResolvedValueOnce(ASSISTANT_TURN)
    render(
      <AgentChat
        area="components"
        scope="part"
        scopeId="ATtiny85"
        title="Ask about this part"
        projectName="weather-pcb"
        promotionTargets={[]}
      />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))
    fireEvent.change(screen.getByPlaceholderText('Ask a question…'), { target: { value: 'how do I decouple this?' } })

    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    screen.getByText('how do I decouple this?')
    screen.getByText('Thinking…')
    await waitFor(() => screen.getByText('Add a 100nF ceramic capacitor near VCC.'))
    expect(sendChatMessageMock).toHaveBeenCalledWith(
      'part', 'ATtiny85', 'components', 'how do I decouple this?', 'weather-pcb',
    )
    expect(loadChatThreadMock).toHaveBeenCalledTimes(1)
  })

  it('TEST-005: a general_practice turn is visually marked', async () => {
    loadChatThreadMock.mockResolvedValueOnce([{ ...ASSISTANT_TURN, general_practice: true, sources: [] }])
    render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))

    await waitFor(() => screen.getByText(/Includes general engineering practice/))
  })

  it('TEST-006: a guidance_item source chip resolves its real page from the part\'s own design_guidance before opening', async () => {
    loadChatThreadMock.mockResolvedValueOnce([ASSISTANT_TURN])
    loadPartMock.mockResolvedValueOnce({
      part_id: 'ATtiny85',
      datasheet_url: 'https://example.com/attiny85.pdf',
      design_guidance: {
        categories: { power: [{ quote: 'Add a 100nF cap.', page: 4, category: 'power' }] },
      },
    })
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')
    render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))
    await waitFor(() => screen.getByText('1 source'))
    fireEvent.click(screen.getByText('1 source'))

    fireEvent.click(screen.getByRole('button', { name: 'Design guidance: power' }))

    await waitFor(() => expect(openMock).toHaveBeenCalledWith('/real/library/datasheets/ATtiny85.pdf#page=4'))
    expect(loadPartMock).toHaveBeenCalledWith('ATtiny85')
    expect(cacheDatasheetMock).toHaveBeenCalledWith('ATtiny85', 'https://example.com/attiny85.pdf')
  })

  it('TEST-007: a datasheet_page source chip opens directly using its own real page', async () => {
    loadChatThreadMock.mockResolvedValueOnce([{
      ...ASSISTANT_TURN,
      sources: [{ kind: 'datasheet_page', part_id: 'ATtiny85', page: 7, content_hash: 'abc' }],
    }])
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', datasheet_url: 'https://example.com/attiny85.pdf' })
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')
    render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))
    await waitFor(() => screen.getByText('1 source'))
    fireEvent.click(screen.getByText('1 source'))

    fireEvent.click(screen.getByRole('button', { name: 'Datasheet page 7' }))

    await waitFor(() => expect(openMock).toHaveBeenCalledWith('/real/library/datasheets/ATtiny85.pdf#page=7'))
  })

  it('TEST-008: a non-openable source kind (e.g. project_intent) renders as a real, disabled, non-interactive chip', async () => {
    loadChatThreadMock.mockResolvedValueOnce([{
      ...ASSISTANT_TURN,
      sources: [{ kind: 'project_intent', project_name: 'weather-pcb' }],
    }])
    render(
      <AgentChat area="overview" scope="project" scopeId="weather-pcb:overview" title="Ask about this project" promotionTargets={[]} />,
    )
    fireEvent.click(screen.getByText('Ask about this project'))
    await waitFor(() => screen.getByText('1 source'))
    fireEvent.click(screen.getByText('1 source'))

    const chip = screen.getByRole('button', { name: 'Project intent' }) as HTMLButtonElement
    expect(chip.disabled).toBe(true)
  })

  it('TEST-009: Save as note reveals real targets, promotes, and marks that target saved', async () => {
    loadChatThreadMock.mockResolvedValueOnce([ASSISTANT_TURN])
    promoteChatTurnMock.mockResolvedValueOnce({ note_id: 'n1', text: ASSISTANT_TURN.content, sources: [] })
    render(
      <AgentChat
        area="components"
        scope="part"
        scopeId="ATtiny85"
        title="Ask about this part"
        promotionTargets={[
          { label: 'This part', scope: 'part', id: 'ATtiny85' },
          { label: 'This project', scope: 'project', id: 'weather-pcb' },
        ]}
      />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))
    await waitFor(() => screen.getByText('Save as note'))

    fireEvent.click(screen.getByText('Save as note'))
    fireEvent.click(screen.getByRole('button', { name: 'Save to This part' }))

    await waitFor(() => screen.getByRole('button', { name: 'Saved to This part' }))
    expect(promoteChatTurnMock).toHaveBeenCalledWith('part', 'ATtiny85', 't2', 'part', 'ATtiny85')
    // The second target is untouched -- promoting to one target never
    // implies the other was promoted too.
    screen.getByRole('button', { name: 'Save to This project' })
  })

  it('TEST-010: no promotion targets means no Save as note action at all', async () => {
    loadChatThreadMock.mockResolvedValueOnce([ASSISTANT_TURN])
    render(
      <AgentChat area="components" scope="part" scopeId="ATtiny85" title="Ask about this part" promotionTargets={[]} />,
    )
    fireEvent.click(screen.getByText('Ask about this part'))
    await waitFor(() => screen.getByText('Add a 100nF ceramic capacitor near VCC.'))

    expect(screen.queryByText('Save as note')).toBeNull()
  })
})
