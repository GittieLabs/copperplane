import { beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()
const submitJobMock = vi.fn()

vi.mock('./ipc', () => ({ dispatch: dispatchMock, submitJob: submitJobMock }))

const { loadChatThread, listChatThreads, promoteChatTurn, searchContext, sendChatMessage } =
  await import('./chat')

beforeEach(() => {
  dispatchMock.mockReset()
  submitJobMock.mockReset()
})

function ok(result: unknown) {
  return { jsonrpc: '2.0' as const, id: 1, result }
}

function fail(message: string) {
  return { jsonrpc: '2.0' as const, id: 1, error: { code: -32000, message } }
}

function fakeHandle<T>(result: T) {
  return { jobId: 'job_1', result: Promise.resolve(result), onUpdate: vi.fn(), cancel: vi.fn() }
}

const REAL_TURN = {
  turn_id: 't1',
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

describe('loadChatThread', () => {
  it('dispatches chat.load_thread with the real scope/scope_id and resolves the real turns', async () => {
    dispatchMock.mockResolvedValueOnce(ok([REAL_TURN]))

    await expect(loadChatThread('part', 'ATtiny85')).resolves.toEqual([REAL_TURN])
    expect(dispatchMock).toHaveBeenCalledWith('chat.load_thread', { scope: 'part', scope_id: 'ATtiny85' })
  })

  it('throws on a daemon error rather than silently returning an empty thread', async () => {
    dispatchMock.mockResolvedValueOnce(fail("'not-a-real-scope' is not a real chat scope"))

    await expect(loadChatThread('part', 'ATtiny85')).rejects.toThrow('not a real chat scope')
  })
})

describe('listChatThreads', () => {
  it('dispatches chat.list_threads with the real project name', async () => {
    dispatchMock.mockResolvedValueOnce(ok(['overview', 'schematic']))

    await expect(listChatThreads('weather-pcb')).resolves.toEqual(['overview', 'schematic'])
    expect(dispatchMock).toHaveBeenCalledWith('chat.list_threads', { project_name: 'weather-pcb' })
  })
})

describe('promoteChatTurn', () => {
  it('dispatches chat.promote_turn with the real scope/turn/target and resolves the real note', async () => {
    const note = { note_id: 'n1', text: 'Add a 100nF ceramic capacitor near VCC.', sources: REAL_TURN.sources }
    dispatchMock.mockResolvedValueOnce(ok(note))

    const result = await promoteChatTurn('part', 'ATtiny85', 't1', 'project', 'weather-pcb')

    expect(result).toEqual(note)
    expect(dispatchMock).toHaveBeenCalledWith('chat.promote_turn', {
      scope: 'part',
      scope_id: 'ATtiny85',
      turn_id: 't1',
      target_scope: 'project',
      target_id: 'weather-pcb',
    })
  })
})

describe('searchContext', () => {
  it('dispatches context.search with the real query and optional scope filters', async () => {
    const results = [{ body: 'Microchip', source_ref: { kind: 'part_field', part_id: 'ATtiny85', field: 'manufacturer' }, kind: 'part_field', score: 1 }]
    dispatchMock.mockResolvedValueOnce(ok(results))

    const result = await searchContext('Microchip', { partId: 'ATtiny85', limit: 5 })

    expect(result).toEqual(results)
    expect(dispatchMock).toHaveBeenCalledWith('context.search', {
      query: 'Microchip',
      part_id: 'ATtiny85',
      project_name: undefined,
      limit: 5,
    })
  })
})

describe('sendChatMessage', () => {
  it('submits chat.send as a real job and resolves the real returned turn', async () => {
    submitJobMock.mockResolvedValueOnce(fakeHandle(REAL_TURN))

    const result = await sendChatMessage('part', 'ATtiny85', 'components', 'how do I decouple this?', 'weather-pcb')

    expect(result).toEqual(REAL_TURN)
    expect(submitJobMock).toHaveBeenCalledWith('chat.send', {
      scope: 'part',
      scope_id: 'ATtiny85',
      area: 'components',
      message: 'how do I decouple this?',
      project_name: 'weather-pcb',
    })
  })

  it('passes project_name: null when no project is open -- a legitimate state, not an error', async () => {
    submitJobMock.mockResolvedValueOnce(fakeHandle(REAL_TURN))

    await sendChatMessage('part', 'ATtiny85', 'components', 'hi')

    expect(submitJobMock).toHaveBeenCalledWith('chat.send', expect.objectContaining({ project_name: null }))
  })
})
