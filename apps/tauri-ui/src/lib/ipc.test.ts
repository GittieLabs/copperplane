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

const {
  dispatch,
  submitJob,
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
} = await import('./ipc')

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

/** Submits an async job whose ack response carries the given job_id, and
 * returns the handle once that ack has resolved -- notifications for it
 * can then be delivered via `capturedListener` in the test body. */
async function submitJobWithId(jobId: string) {
  respondOnNextTick((id) => ({ jsonrpc: '2.0', id, result: { job_id: jobId } }))
  return submitJob('freecad.generate_enclosure', { width: 1, depth: 1, height: 1 })
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

  it('TEST-005: two concurrent dispatches both resolve correctly, matched by id', async () => {
    // Neither invoke() call resolves the request itself (same as the real
    // command, which only writes to stdin) -- both stay "in flight"
    // simultaneously until their responses arrive out of submission order,
    // proving id-matching (not a single-in-flight guard) is what keeps
    // concurrent dispatches correct post-CTX-105.2.
    invokeMock.mockImplementation(async () => {})

    const first = dispatch('kicad.generate_component', { query: 'first' })
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalledTimes(1))
    const second = dispatch('kicad.generate_component', { query: 'second' })
    await vi.waitFor(() => expect(invokeMock).toHaveBeenCalledTimes(2))

    const firstId = idFromInvokeCall(0)
    const secondId = idFromInvokeCall(1)

    // Resolve out of order: second's response arrives before first's.
    capturedListener?.({ payload: JSON.stringify({ jsonrpc: '2.0', id: secondId, result: 'second' }) })
    capturedListener?.({ payload: JSON.stringify({ jsonrpc: '2.0', id: firstId, result: 'first' }) })

    expect((await first).result).toBe('first')
    expect((await second).result).toBe('second')
  })
})

describe('submitJob', () => {
  it('TEST-001: routes a job.* notification (no id field) to its job instead of dropping it', async () => {
    const handle = await submitJobWithId('job-abc')
    const updates: unknown[] = []
    handle.onUpdate((update) => updates.push(update))

    capturedListener?.({
      payload: JSON.stringify({ jsonrpc: '2.0', method: 'job.progress', params: { job_id: 'job-abc', status: 'running' } }),
    })

    expect(updates).toEqual([{ status: 'running' }])
  })

  it('TEST-002: result resolves with the job.completed payload after job.progress fires first', async () => {
    const handle = await submitJobWithId('job-def')
    const statuses: string[] = []
    handle.onUpdate((update) => statuses.push(update.status))

    capturedListener?.({
      payload: JSON.stringify({ jsonrpc: '2.0', method: 'job.progress', params: { job_id: 'job-def' } }),
    })
    capturedListener?.({
      payload: JSON.stringify({
        jsonrpc: '2.0',
        method: 'job.completed',
        params: { job_id: 'job-def', result: '/tmp/enclosure.glb' },
      }),
    })

    await expect(handle.result).resolves.toBe('/tmp/enclosure.glb')
    expect(statuses).toEqual(['running', 'completed'])
  })

  it('TEST-003: result rejects on job.failed', async () => {
    const handle = await submitJobWithId('job-fail')

    capturedListener?.({
      payload: JSON.stringify({
        jsonrpc: '2.0',
        method: 'job.failed',
        params: { job_id: 'job-fail', error: 'freecadcmd exited with code 1' },
      }),
    })

    await expect(handle.result).rejects.toThrow('freecadcmd exited with code 1')
  })

  it('TEST-003: result rejects on job.cancelled', async () => {
    const handle = await submitJobWithId('job-cancel')

    capturedListener?.({
      payload: JSON.stringify({ jsonrpc: '2.0', method: 'job.cancelled', params: { job_id: 'job-cancel' } }),
    })

    await expect(handle.result).rejects.toThrow(/cancelled/)
  })

  it('TEST-004: cancel() dispatches job.cancel with the job\'s own job_id', async () => {
    const handle = await submitJobWithId('job-to-cancel')

    respondOnNextTick((id) => ({ jsonrpc: '2.0', id, result: { job_id: 'job-to-cancel', cancelling: true } }))
    await handle.cancel()

    const cancelCallIndex = invokeMock.mock.calls.length - 1
    const { request } = invokeMock.mock.calls[cancelCallIndex][1] as { request: string }
    const parsed = JSON.parse(request)
    expect(parsed.method).toBe('job.cancel')
    expect(parsed.params).toEqual({ job_id: 'job-to-cancel' })
  })
})

// CTX-316.1: these string values must stay in sync with their own
// same-named `const` in `core/tauri-rust/src/menu.rs` -- this test's
// only job is to catch a future accidental rename on one side only.
describe('MENU_* event constants', () => {
  it('TEST-012: every real menu event constant has the expected string value', () => {
    expect(MENU_SAVE_PROJECT_EVENT).toBe('menu://save-project')
    expect(MENU_OPEN_PROJECT_EVENT).toBe('menu://open-project')
    expect(MENU_OPEN_SETTINGS_EVENT).toBe('menu://open-settings')
    expect(MENU_OPEN_DEFAULT_LIBRARY_EVENT).toBe('menu://open-library-default')
    expect(MENU_MANAGE_LIBRARIES_EVENT).toBe('menu://manage-libraries')
    expect(MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT).toBe('menu://design/schematic/open-kicad')
    expect(MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT).toBe('menu://design/schematic/pick-manually')
    expect(MENU_DESIGN_PCB_OPEN_KICAD_EVENT).toBe('menu://design/pcb/open-kicad')
    expect(MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT).toBe('menu://design/enclosure/open-kicad')
    expect(MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT).toBe('menu://design/enclosure/pick-pcb')
    expect(MENU_DESIGN_ENCLOSURE_GENERATE_EVENT).toBe('menu://design/enclosure/generate')
  })
})
