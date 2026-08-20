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
const syncLibraryMenuMock = vi.fn()

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

vi.mock('../lib/menu', () => ({
  syncLibraryMenu: (...args: unknown[]) => syncLibraryMenuMock(...args),
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
  syncLibraryMenuMock.mockReset().mockResolvedValue(undefined)
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

  it('real bug fix: Parts and Symbols render as two real, separately-labeled sections, not one merged list', async () => {
    // The real bug: a Symbol's own raw symbol_id (e.g. "DIP-8_8pin",
    // derived from a Part's package/pin-count) previously rendered as
    // a sibling under one combined "Datasheets / Pins" count, looking
    // like a second, unrelated entry rather than that same Part's own
    // generated symbol.
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)
    listPartsMock.mockResolvedValueOnce(['ATtiny85'])
    listSymbolsMock.mockResolvedValueOnce(['DIP-8_8pin'])
    listFootprintsMock.mockResolvedValueOnce([])
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip Technology', package: 'DIP-8' })
    loadSymbolMock.mockResolvedValueOnce({ symbol_id: 'DIP-8_8pin' })

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('Default'))
    fireEvent.click(screen.getByText('Default'))

    await waitFor(() => screen.getByText('Parts (1)'))
    screen.getByText('Symbols (1)')
    expect(screen.queryByText(/Datasheets \/ Pins/)).toBeNull()
  })

  it('CTX-315.4: clicking a Part with onSelectPart provided calls it with the real part_id', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)
    listPartsMock.mockResolvedValueOnce(['ATtiny85'])
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8' })
    const onSelectPart = vi.fn()

    render(<LibraryArea onSelectPart={onSelectPart} />)
    await waitFor(() => screen.getByText('Default'))
    fireEvent.click(screen.getByText('Default'))
    await waitFor(() => screen.getByText('ATtiny85 · Microchip · SOIC-8'))

    fireEvent.click(screen.getByRole('button', { name: 'ATtiny85 · Microchip · SOIC-8' }))

    expect(onSelectPart).toHaveBeenCalledWith('ATtiny85')
  })

  it('CTX-315.4: without onSelectPart, a Part row renders as plain, non-interactive text (no regression to the old behavior)', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)
    listPartsMock.mockResolvedValueOnce(['ATtiny85'])
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8' })

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('Default'))
    fireEvent.click(screen.getByText('Default'))

    await waitFor(() => screen.getByText('ATtiny85 · Microchip · SOIC-8'))
    expect(screen.queryByRole('button', { name: 'ATtiny85 · Microchip · SOIC-8' })).toBeNull()
  })

  it('an empty custom library renders a real, honest empty state, not an error', async () => {
    listLibrariesMock.mockResolvedValueOnce([
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 0, symbol_count: 0, footprint_count: 0 },
    ])

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('ESP32 Boards'))

    fireEvent.click(screen.getByText('ESP32 Boards'))

    await waitFor(() => screen.getByText('No parts in this library yet.'))
    screen.getByText('No symbols in this library yet.')
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

describe('LibraryArea: SPEC-316 initialLibraryId deep link', () => {
  it('TEST-010: an initialLibraryId matching a real library opens straight into its detail view', async () => {
    listLibrariesMock.mockResolvedValueOnce([
      ...DEFAULT_ONLY,
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 0, symbol_count: 0, footprint_count: 0 },
    ])
    listPartsMock.mockResolvedValueOnce(['ATtiny85'])
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8' })

    render(<LibraryArea initialLibraryId="default" />)

    await waitFor(() => screen.getByText('ATtiny85 · Microchip · SOIC-8'))
    expect(listPartsMock).toHaveBeenCalledWith('default')
    // Never landed on the list view at all.
    expect(screen.queryByRole('button', { name: '+ New library' })).toBeNull()
  })

  it('TEST-011: an initialLibraryId with no matching library falls back to the list view', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)

    render(<LibraryArea initialLibraryId="does-not-exist" />)

    await waitFor(() => screen.getByRole('button', { name: '+ New library' }))
    expect(listPartsMock).not.toHaveBeenCalled()
  })
})

describe('LibraryArea: SPEC-316 native menu sync', () => {
  it('CTX-316.2 TEST-011: refreshLibraries calls the real syncLibraryMenu after a successful list load', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)

    render(<LibraryArea />)

    await waitFor(() => expect(syncLibraryMenuMock).toHaveBeenCalledWith(DEFAULT_ONLY))
  })

  it('CTX-316.2: creating a library re-syncs the native menu with the fresh list', async () => {
    listLibrariesMock.mockResolvedValueOnce(DEFAULT_ONLY)
    createLibraryMock.mockResolvedValueOnce({ id: 'esp32-boards', name: 'ESP32 Boards' })
    const updatedList = [
      ...DEFAULT_ONLY,
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 0, symbol_count: 0, footprint_count: 0 },
    ]
    listLibrariesMock.mockResolvedValueOnce(updatedList)

    render(<LibraryArea />)
    await waitFor(() => screen.getByText('Default'))
    syncLibraryMenuMock.mockClear()

    fireEvent.change(screen.getByPlaceholderText('new library name'), { target: { value: 'ESP32 Boards' } })
    fireEvent.click(screen.getByRole('button', { name: '+ New library' }))

    await waitFor(() => expect(syncLibraryMenuMock).toHaveBeenCalledWith(updatedList))
  })
})
