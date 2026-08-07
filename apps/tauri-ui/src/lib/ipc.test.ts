import { beforeEach, describe, expect, it, vi } from 'vitest'

type DaemonEventListener = (event: { payload: string }) => void

const invokeMock = vi.fn()
let capturedListener: DaemonEventListener | null = null
const listenMock = vi.fn(async (_eventName: string, listener: DaemonEventListener) => {
  capturedListener = listener
  return vi.fn()
})

vi.mock('@tauri-apps/api/core', () => ({ invoke: invokeMock }))
vi.mock('@tauri-apps/api/event', () => ({ listen: listenMock }))

const { dispatch } = await import('./ipc')

beforeEach(() => {
  invokeMock.mockReset()
  listenMock.mockClear()
  // Note: `capturedListener` is intentionally NOT reset here. The ipc
  // module only ever calls `listen()` once (guarded by its own internal
  // `unlisten` state), so it's captured on the first test and reused —
  // nulling it out here would silently break every test after the first.
})

/** The request `id` is an internal, ever-incrementing counter, so tests
 * read it back off the actual `invoke` call rather than assuming a value. */
function idFromInvokeCall(callIndex = 0): number {
  const { request } = invokeMock.mock.calls[callIndex][1] as { request: string }
  return JSON.parse(request).id
}

function respondOnNextTick(buildResult: (id: number) => unknown) {
  invokeMock.mockImplementationOnce(async (_cmd: string, { request }: { request: string }) => {
    const { id } = JSON.parse(request)
    queueMicrotask(() => {
      capturedListener?.({ payload: JSON.stringify(buildResult(id)) })
    })
  })
}

describe('dispatch', () => {
  it('resolves with the daemon response matching the request id', async () => {
    respondOnNextTick((id) => ({
      jsonrpc: '2.0',
      id,
      result: { symbol_created: 'BME280_symbol.kicad_sym' },
    }))

    const response = await dispatch('kicad.generate_component', { query: 'bme280' })

    expect(response.result).toEqual({ symbol_created: 'BME280_symbol.kicad_sym' })
    const id = idFromInvokeCall()
    expect(invokeMock).toHaveBeenCalledWith('dispatch_to_daemon', {
      request: JSON.stringify({ jsonrpc: '2.0', method: 'kicad.generate_component', params: { query: 'bme280' }, id }),
    })
  })

  it('drops a non-JSON stdout line instead of using eval, and still resolves on the next valid line', async () => {
    invokeMock.mockImplementationOnce(async (_cmd: string, { request }: { request: string }) => {
      const { id } = JSON.parse(request)
      queueMicrotask(() => {
        capturedListener?.({ payload: 'not valid json; alert(1)' })
        capturedListener?.({ payload: JSON.stringify({ jsonrpc: '2.0', id, result: 'fine' }) })
      })
    })

    const response = await dispatch('kicad.generate_component')

    expect(response.result).toBe('fine')
  })

  it('rejects a second dispatch while one is already in flight, without calling invoke again', async () => {
    // invoke() resolves immediately, same as the real command (it only
    // writes to stdin) — what keeps this request "in flight" is that its
    // response never arrives during this test, same as the real daemon
    // taking a while to process a long-running command.
    invokeMock.mockImplementationOnce(async () => {})

    const first = dispatch('kicad.generate_component')
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalledTimes(1))

    await expect(dispatch('kicad.generate_component')).rejects.toThrow(/in flight/)
    expect(invokeMock).toHaveBeenCalledTimes(1)

    // Unstick the first call so it doesn't leak into later tests.
    const id = idFromInvokeCall()
    capturedListener?.({ payload: JSON.stringify({ jsonrpc: '2.0', id, result: null }) })
    await first
  })

  it('allows a new dispatch once the in-flight one has settled', async () => {
    respondOnNextTick((id) => ({ jsonrpc: '2.0', id, result: 'first' }))
    await dispatch('kicad.generate_component')

    respondOnNextTick((id) => ({ jsonrpc: '2.0', id, result: 'second' }))
    const second = await dispatch('kicad.generate_component')

    expect(second.result).toBe('second')
  })
})
