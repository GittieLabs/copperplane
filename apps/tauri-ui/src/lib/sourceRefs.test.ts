import { beforeEach, describe, expect, it, vi } from 'vitest'

const cacheDatasheetMock = vi.fn()
const loadPartMock = vi.fn()
const openMock = vi.fn()

vi.mock('./components', () => ({
  cacheDatasheet: (...args: unknown[]) => cacheDatasheetMock(...args),
}))

vi.mock('./partDetail', () => ({
  loadPart: (...args: unknown[]) => loadPartMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => openMock(...args),
}))

const { sourceChipLabel, isOpenableSource, openSource } = await import('./sourceRefs')

beforeEach(() => {
  cacheDatasheetMock.mockReset()
  loadPartMock.mockReset()
  openMock.mockReset()
})

describe('sourceChipLabel', () => {
  it('labels every real SourceRef kind', () => {
    expect(sourceChipLabel({ kind: 'datasheet_page', page: 4 })).toBe('Datasheet page 4')
    expect(sourceChipLabel({ kind: 'guidance_item', category: 'power' })).toBe('Design guidance: power')
    expect(sourceChipLabel({ kind: 'connection_guidance', pin_number: '3' })).toBe('Pin 3 guidance')
    expect(sourceChipLabel({ kind: 'part_field', field: 'manufacturer' })).toBe('Part: manufacturer')
    expect(sourceChipLabel({ kind: 'project_intent' })).toBe('Project intent')
    expect(sourceChipLabel({ kind: 'chat_turn' })).toBe('Earlier answer')
    expect(sourceChipLabel({ kind: 'note' })).toBe('Saved note')
    expect(sourceChipLabel({ kind: 'check_finding' })).toBe('Check finding')
  })
})

describe('isOpenableSource', () => {
  it('only datasheet_page and guidance_item resolve to a real document target', () => {
    expect(isOpenableSource({ kind: 'datasheet_page' })).toBe(true)
    expect(isOpenableSource({ kind: 'guidance_item' })).toBe(true)
    expect(isOpenableSource({ kind: 'connection_guidance' })).toBe(false)
    expect(isOpenableSource({ kind: 'part_field' })).toBe(false)
    expect(isOpenableSource({ kind: 'project_intent' })).toBe(false)
    expect(isOpenableSource({ kind: 'chat_turn' })).toBe(false)
    expect(isOpenableSource({ kind: 'note' })).toBe(false)
    expect(isOpenableSource({ kind: 'check_finding' })).toBe(false)
  })
})

describe('openSource', () => {
  it('a guidance_item resolves its real page from the part\'s own design_guidance before opening', async () => {
    loadPartMock.mockResolvedValueOnce({
      part_id: 'ATtiny85',
      datasheet_url: 'https://example.com/attiny85.pdf',
      design_guidance: {
        categories: { power: [{ quote: 'Add a 100nF cap.', page: 4, category: 'power' }] },
      },
    })
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')

    await openSource({ kind: 'guidance_item', part_id: 'ATtiny85', category: 'power', quote: 'Add a 100nF cap.' })

    expect(loadPartMock).toHaveBeenCalledWith('ATtiny85')
    expect(cacheDatasheetMock).toHaveBeenCalledWith('ATtiny85', 'https://example.com/attiny85.pdf')
    expect(openMock).toHaveBeenCalledWith('/real/library/datasheets/ATtiny85.pdf#page=4')
  })

  it('a datasheet_page opens directly using its own real page, no design_guidance lookup', async () => {
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', datasheet_url: 'https://example.com/attiny85.pdf' })
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')

    await openSource({ kind: 'datasheet_page', part_id: 'ATtiny85', page: 7, content_hash: 'abc' })

    expect(openMock).toHaveBeenCalledWith('/real/library/datasheets/ATtiny85.pdf#page=7')
  })

  it('throws when the ref carries no part_id at all', async () => {
    await expect(openSource({ kind: 'guidance_item' })).rejects.toThrow(/no real part/)
    expect(loadPartMock).not.toHaveBeenCalled()
  })

  it('throws when a guidance_item\'s quote/category cannot be matched to a real stored page', async () => {
    loadPartMock.mockResolvedValueOnce({
      part_id: 'ATtiny85',
      datasheet_url: 'https://example.com/attiny85.pdf',
      design_guidance: { categories: { power: [{ quote: 'A different quote.', page: 4, category: 'power' }] } },
    })

    await expect(
      openSource({ kind: 'guidance_item', part_id: 'ATtiny85', category: 'power', quote: 'Add a 100nF cap.' }),
    ).rejects.toThrow(/Could not resolve a real page/)
    expect(cacheDatasheetMock).not.toHaveBeenCalled()
  })
})
