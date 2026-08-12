import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()

vi.mock('./ipc', () => ({ submitJob: submitJobMock }))

const { searchComponents, cacheDatasheet } = await import('./components')

function fakeJobHandle<T>(result: Promise<T>) {
  result.catch(() => {})
  return { jobId: 'job_1', result, onUpdate: () => () => {}, cancel: vi.fn() }
}

beforeEach(() => {
  submitJobMock.mockReset()
})

describe('searchComponents', () => {
  it('submits component.search with the query and returns the real ranked candidates', async () => {
    const candidates = [
      {
        part_number: 'ATtiny85',
        manufacturer: 'Microchip',
        package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf',
        confidence: 'high' as const,
        rationale: 'Exact match.',
      },
    ]
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(candidates)))

    await expect(searchComponents('atiny85')).resolves.toEqual(candidates)
    expect(submitJobMock).toHaveBeenCalledWith('component.search', { query: 'atiny85' })
  })

  it('propagates a job failure rather than swallowing it', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.reject(new Error('Search did not return a non-empty list of candidates.'))))

    await expect(searchComponents('???')).rejects.toThrow('non-empty list')
  })
})

describe('cacheDatasheet', () => {
  it('submits component.cache_datasheet with part_number/datasheet_url and returns the real path', async () => {
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.resolve({ path: '/storage/library/datasheets/ATtiny85.pdf' })),
    )

    await expect(cacheDatasheet('ATtiny85', 'https://example.com/attiny85.pdf')).resolves.toBe(
      '/storage/library/datasheets/ATtiny85.pdf',
    )
    expect(submitJobMock).toHaveBeenCalledWith('component.cache_datasheet', {
      part_number: 'ATtiny85',
      datasheet_url: 'https://example.com/attiny85.pdf',
    })
  })

  it('propagates a fetch failure rather than swallowing it', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.reject(new Error("Datasheet fetch for 'X' failed"))))

    await expect(cacheDatasheet('X', 'https://example.com/x.pdf')).rejects.toThrow('Datasheet fetch')
  })
})
