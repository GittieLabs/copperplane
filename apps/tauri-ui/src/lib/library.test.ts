import { beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()

vi.mock('./ipc', () => ({ dispatch: dispatchMock }))

const {
  listLibraries, createLibrary, tagObject, listParts, listSymbols, listFootprints,
  loadPart, loadSymbol, loadFootprint,
} = await import('./library')

beforeEach(() => {
  dispatchMock.mockReset()
})

function ok(result: unknown) {
  return { result }
}

describe('listLibraries', () => {
  it('dispatches library.list_libraries and returns the real summaries', async () => {
    const libraries = [
      { id: 'default', name: 'Default', part_count: 3, symbol_count: 1, footprint_count: 2 },
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 1, symbol_count: 0, footprint_count: 1 },
    ]
    dispatchMock.mockResolvedValueOnce(ok(libraries))

    await expect(listLibraries()).resolves.toEqual(libraries)
    expect(dispatchMock).toHaveBeenCalledWith('library.list_libraries', {})
  })
})

describe('createLibrary', () => {
  it('dispatches library.create_library with the real name', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ id: 'esp32-boards', name: 'ESP32 Boards' }))

    await expect(createLibrary('ESP32 Boards')).resolves.toEqual({ id: 'esp32-boards', name: 'ESP32 Boards' })
    expect(dispatchMock).toHaveBeenCalledWith('library.create_library', { name: 'ESP32 Boards' })
  })
})

describe('tagObject', () => {
  it('dispatches library.tag_object with kind, object_id, and library_ids', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ library_ids: ['default', 'esp32-boards'] }))

    await tagObject('part', 'ATtiny85', ['esp32-boards'])

    expect(dispatchMock).toHaveBeenCalledWith('library.tag_object', {
      kind: 'part', object_id: 'ATtiny85', library_ids: ['esp32-boards'],
    })
  })
})

describe('listParts/listSymbols/listFootprints', () => {
  it('pass a real library_id filter through, or null when omitted', async () => {
    dispatchMock.mockResolvedValueOnce(ok(['ATtiny85']))
    await listParts('esp32-boards')
    expect(dispatchMock).toHaveBeenCalledWith('library.list_parts', { library_id: 'esp32-boards' })

    dispatchMock.mockResolvedValueOnce(ok(['ATtiny85']))
    await listParts()
    expect(dispatchMock).toHaveBeenCalledWith('library.list_parts', { library_id: null })

    dispatchMock.mockResolvedValueOnce(ok(['Sym1']))
    await listSymbols('esp32-boards')
    expect(dispatchMock).toHaveBeenCalledWith('library.list_symbols', { library_id: 'esp32-boards' })

    dispatchMock.mockResolvedValueOnce(ok(['Fp1']))
    await listFootprints('esp32-boards')
    expect(dispatchMock).toHaveBeenCalledWith('library.list_footprints', { library_id: 'esp32-boards' })
  })
})

describe('loadPart/loadSymbol/loadFootprint', () => {
  it('dispatch the real load routes with the correct id param', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ part_id: 'ATtiny85', manufacturer: 'Microchip' }))
    await expect(loadPart('ATtiny85')).resolves.toEqual({ part_id: 'ATtiny85', manufacturer: 'Microchip' })
    expect(dispatchMock).toHaveBeenCalledWith('library.load_part', { part_id: 'ATtiny85' })

    dispatchMock.mockResolvedValueOnce(ok({ symbol_id: 'Sym1' }))
    await loadSymbol('Sym1')
    expect(dispatchMock).toHaveBeenCalledWith('library.load_symbol', { symbol_id: 'Sym1' })

    dispatchMock.mockResolvedValueOnce(ok({ footprint_id: 'Fp1' }))
    await loadFootprint('Fp1')
    expect(dispatchMock).toHaveBeenCalledWith('library.load_footprint', { footprint_id: 'Fp1' })
  })
})
