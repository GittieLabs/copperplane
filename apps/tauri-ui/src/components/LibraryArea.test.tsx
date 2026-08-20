import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listLibrariesMock = vi.fn()
const createLibraryMock = vi.fn()
const listPartsMock = vi.fn()
const listSymbolsMock = vi.fn()
const listFootprintsMock = vi.fn()
const loadPartMock = vi.fn()
const loadSymbolMock = vi.fn()
const loadFootprintMock = vi.fn()

vi.mock('../lib/library', () => ({
  listLibraries: (...args: unknown[]) => listLibrariesMock(...args),
  createLibrary: (...args: unknown[]) => createLibraryMock(...args),
  listParts: (...args: unknown[]) => listPartsMock(...args),
  listSymbols: (...args: unknown[]) => listSymbolsMock(...args),
  listFootprints: (...args: unknown[]) => listFootprintsMock(...args),
  loadPart: (...args: unknown[]) => loadPartMock(...args),
  loadSymbol: (...args: unknown[]) => loadSymbolMock(...args),
  loadFootprint: (...args: unknown[]) => loadFootprintMock(...args),
}))

const { LibraryArea } = await import('./LibraryArea')

beforeEach(() => {
  listLibrariesMock.mockReset()
  createLibraryMock.mockReset()
  listPartsMock.mockReset().mockResolvedValue([])
  listSymbolsMock.mockReset().mockResolvedValue([])
  listFootprintsMock.mockReset().mockResolvedValue([])
  loadPartMock.mockReset()
  loadSymbolMock.mockReset()
  loadFootprintMock.mockReset()
})

const DEFAULT_ONLY = [
  { id: 'default', name: 'Default', part_count: 2, symbol_count: 1, footprint_count: 1 },
]

describe('LibraryArea: list view', () => {
  it('renders every real library with its own real counts', async () => {
    listLibrariesMock.mockResolvedValueOnce([
      ...DEFAULT_ONLY,
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 1, symbol_count: 0, footprint_count: 1 },
    ])

    render(<LibraryArea />)

    await waitFor(() => screen.getByText('Default'))
    screen.getByText('2 parts, 1 symbols, 1 footprints')
    screen.getByText('ESP32 Boards')
  })

  it('"+ New library" calls createLibrary and refreshes the real list', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)
    createLibraryMock.mockResolvedValueOnce({ id: 'esp32-boards', name: 'ESP32 Boards' })
    listLibrariesMock.mockResolvedValueOnce([
      ...DEFAULT_ONLY,
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 0, symbol_count: 0, footprint_count: 0 },
    ])

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('Default'))

    fireEvent.change(screen.getByPlaceholderText('new library name'), { target: { value: 'ESP32 Boards' } })
    fireEvent.click(screen.getByRole('button', { name: '+ New library' }))

    await waitFor(() => expect(createLibraryMock).toHaveBeenCalledWith('ESP32 Boards'))
    await waitFor(() => screen.getByText('ESP32 Boards'))
    expect(listLibrariesMock).toHaveBeenCalledTimes(2)
  })
})

describe('LibraryArea: detail view', () => {
  it('selecting a library shows its own two real sections with real identifying info', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)
    listPartsMock.mockResolvedValueOnce(['ATtiny85'])
    listSymbolsMock.mockResolvedValueOnce(['Sym1'])
    listFootprintsMock.mockResolvedValueOnce(['Fp1'])
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8' })
    loadSymbolMock.mockResolvedValueOnce({ symbol_id: 'Sym1', symbol_name: 'ATtiny85_sym' })
    loadFootprintMock.mockResolvedValueOnce({
      footprint_id: 'Fp1', footprint_name: 'C_0201', provenance: { license: 'CC-BY-4.0' },
    })

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('Default'))

    fireEvent.click(screen.getByText('Default'))

    await waitFor(() => screen.getByText('ATtiny85 · Microchip · SOIC-8'))
    screen.getByText('ATtiny85_sym')
    screen.getByText('C_0201 · CC-BY-4.0')
    expect(listPartsMock).toHaveBeenCalledWith('default')
  })

  it('an empty custom library renders a real, honest empty state, not an error', async () => {
    listLibrariesMock.mockResolvedValueOnce([
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 0, symbol_count: 0, footprint_count: 0 },
    ])

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('ESP32 Boards'))

    fireEvent.click(screen.getByText('ESP32 Boards'))

    await waitFor(() => screen.getByText('No parts or symbols in this library yet.'))
    screen.getByText('No footprints in this library yet.')
  })

  it('← Libraries returns to the list view', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('Default'))
    fireEvent.click(screen.getByText('Default'))
    await waitFor(() => screen.getByText('← Libraries'))

    fireEvent.click(screen.getByText('← Libraries'))

    await waitFor(() => screen.getByRole('button', { name: '+ New library' }))
  })
})
