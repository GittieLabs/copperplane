import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()
const openDialogMock = vi.fn()

vi.mock('./ipc', () => ({ submitJob: submitJobMock }))
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: openDialogMock }))

const { generateEnclosure, pickPcbFile } = await import('./enclosure')

beforeEach(() => {
  submitJobMock.mockReset()
  openDialogMock.mockReset()
})

describe('generateEnclosure', () => {
  it('submits freecad.generate_enclosure with the real params, unchanged', async () => {
    const fakeHandle = { jobId: 'job_1', result: Promise.resolve({}), onUpdate: vi.fn(), cancel: vi.fn() }
    submitJobMock.mockResolvedValueOnce(fakeHandle)

    const params = { height: 20, width: 50, depth: 30 }
    await expect(generateEnclosure(params)).resolves.toBe(fakeHandle)

    expect(submitJobMock).toHaveBeenCalledWith('freecad.generate_enclosure', params)
  })

  it('submits freecad.generate_enclosure with pcb_path when given (SPEC-310 file mode)', async () => {
    const fakeHandle = { jobId: 'job_2', result: Promise.resolve({}), onUpdate: vi.fn(), cancel: vi.fn() }
    submitJobMock.mockResolvedValueOnce(fakeHandle)

    const params = { height: 20, pcb_path: '/real/board.kicad_pcb' }
    await expect(generateEnclosure(params)).resolves.toBe(fakeHandle)

    expect(submitJobMock).toHaveBeenCalledWith('freecad.generate_enclosure', params)
  })
})

describe('pickPcbFile', () => {
  it('filters to .kicad_pcb and returns the real picked path', async () => {
    openDialogMock.mockResolvedValueOnce('/real/board.kicad_pcb')

    await expect(pickPcbFile()).resolves.toBe('/real/board.kicad_pcb')

    expect(openDialogMock).toHaveBeenCalledWith({
      filters: [{ name: 'KiCad PCB', extensions: ['kicad_pcb'] }],
    })
  })

  it('returns null, not an error, when the dialog is cancelled', async () => {
    openDialogMock.mockResolvedValueOnce(null)

    await expect(pickPcbFile()).resolves.toBeNull()
  })
})
