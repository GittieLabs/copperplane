import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()

vi.mock('./ipc', () => ({ submitJob: submitJobMock }))

const { generateEnclosure } = await import('./enclosure')

beforeEach(() => {
  submitJobMock.mockReset()
})

describe('generateEnclosure', () => {
  it('submits freecad.generate_enclosure with the real params, unchanged', async () => {
    const fakeHandle = { jobId: 'job_1', result: Promise.resolve({}), onUpdate: vi.fn(), cancel: vi.fn() }
    submitJobMock.mockResolvedValueOnce(fakeHandle)

    const params = { height: 20, width: 50, depth: 30 }
    await expect(generateEnclosure(params)).resolves.toBe(fakeHandle)

    expect(submitJobMock).toHaveBeenCalledWith('freecad.generate_enclosure', params)
  })
})
