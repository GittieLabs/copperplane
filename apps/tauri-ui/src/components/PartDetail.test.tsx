import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const extractPartDetailMock = vi.fn()
const saveConfirmedPartMock = vi.fn()
const exportSymbolMock = vi.fn()
const openMock = vi.fn()
const searchFootprintsMock = vi.fn()
const attachFootprintToPartMock = vi.fn()

vi.mock('../lib/partDetail', () => ({
  extractPartDetail: (...args: unknown[]) => extractPartDetailMock(...args),
  saveConfirmedPart: (...args: unknown[]) => saveConfirmedPartMock(...args),
  exportSymbol: (...args: unknown[]) => exportSymbolMock(...args),
}))

vi.mock('../lib/footprints', () => ({
  searchFootprints: (...args: unknown[]) => searchFootprintsMock(...args),
  attachFootprintToPart: (...args: unknown[]) => attachFootprintToPartMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => openMock(...args),
}))

const { PartDetail } = await import('./PartDetail')

const CANDIDATE = {
  part_number: 'ATtiny85',
  manufacturer: 'Microchip',
  package: 'DIP-8',
  datasheet_url: 'https://example.com/attiny85.pdf',
  confidence: 'high' as const,
  rationale: 'Exact match.',
}

beforeEach(() => {
  extractPartDetailMock.mockReset()
  saveConfirmedPartMock.mockReset()
  exportSymbolMock.mockReset()
  openMock.mockReset()
  searchFootprintsMock.mockReset()
  attachFootprintToPartMock.mockReset()
})

const SAVED_PART_NO_FOOTPRINT = {
  part_id: 'ATtiny85',
  manufacturer: 'Microchip',
  package: 'SOIC-8',
  pins: [],
  datasheet_url: 'https://example.com/attiny85.pdf',
  symbol_id: 'SOIC-8_0pin',
  footprint_id: null,
  provenance: {},
}

async function saveAndReachFootprintSection() {
  extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
  saveConfirmedPartMock.mockResolvedValueOnce({
    part: SAVED_PART_NO_FOOTPRINT,
    symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
  })

  render(<PartDetail candidate={CANDIDATE} />)
  await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))
  await waitFor(() => screen.getByText('Find Footprint'))
}

describe('PartDetail', () => {
  it('re-extracts real pin data for the confirmed candidate and renders the pin table with type and source', async () => {
    extractPartDetailMock.mockResolvedValueOnce({
      part_number: 'ATtiny85',
      package: 'SOIC-8',
      pins: [
        { number: '1', name: 'RESET', electrical_type: 'bidirectional' },
        { number: '2', name: 'GND', electrical_type: 'ground' },
      ],
    })

    render(<PartDetail candidate={CANDIDATE} />)

    await waitFor(() => screen.getByText('RESET'))
    screen.getByText('bidirectional')
    screen.getAllByText('llm_extraction')
    expect(extractPartDetailMock).toHaveBeenCalledWith('ATtiny85')
  })

  it('an extraction failure shows the real error, not a silent empty table', async () => {
    extractPartDetailMock.mockRejectedValueOnce(new Error("Package 'X' is not in the known reference table."))

    render(<PartDetail candidate={CANDIDATE} />)

    await waitFor(() => screen.getByText("Package 'X' is not in the known reference table."))
  })

  it('Save to Library calls saveConfirmedPart with the candidate and extraction, then reveals Export Symbol', async () => {
    extractPartDetailMock.mockResolvedValueOnce({
      part_number: 'ATtiny85',
      package: 'SOIC-8',
      pins: [{ number: '1', name: 'RESET', electrical_type: 'bidirectional' }],
    })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: { part_id: 'ATtiny85' },
      symbol: { symbol_id: 'SOIC-8_1pin', reference_prefix: 'U', pins: [] },
    })

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))

    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))

    await waitFor(() => screen.getByText('Saved to library.'))
    expect(saveConfirmedPartMock).toHaveBeenCalledWith(
      CANDIDATE,
      { part_number: 'ATtiny85', package: 'SOIC-8', pins: [{ number: '1', name: 'RESET', electrical_type: 'bidirectional' }] },
    )
    screen.getByRole('button', { name: 'Export Symbol (.kicad_sym)' })
  })

  it('a save failure shows the real error and does not reveal Export Symbol', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockRejectedValueOnce(new Error('Part is missing provenance for required field(s): package.'))

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))

    await waitFor(() => screen.getByText(/missing provenance/))
    expect(screen.queryByRole('button', { name: 'Export Symbol (.kicad_sym)' })).toBeNull()
  })

  it('Export Symbol writes the real file and "Open symbol" opens it via the shell plugin', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: { part_id: 'ATtiny85' },
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })
    exportSymbolMock.mockResolvedValueOnce('/storage/library/symbols/SOIC-8_0pin.kicad_sym')

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))
    await waitFor(() => screen.getByRole('button', { name: 'Export Symbol (.kicad_sym)' }))

    fireEvent.click(screen.getByRole('button', { name: 'Export Symbol (.kicad_sym)' }))

    await waitFor(() => screen.getByText(/Exported: \/storage\/library\/symbols\/SOIC-8_0pin\.kicad_sym/))
    expect(exportSymbolMock).toHaveBeenCalledWith('SOIC-8_0pin')

    fireEvent.click(screen.getByRole('button', { name: 'Open symbol' }))
    expect(openMock).toHaveBeenCalledWith('/storage/library/symbols/SOIC-8_0pin.kicad_sym')
  })

  it('TEST-001: the Find Footprint section only appears once a part is saved and has no footprint_id yet', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: SAVED_PART_NO_FOOTPRINT,
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    expect(screen.queryByText('Find Footprint')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))

    await waitFor(() => screen.getByText('Find Footprint'))
    expect(searchFootprintsMock).not.toHaveBeenCalled()
  })

  it('TEST-002: searching renders real candidates from kicad.search_footprints', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' },
    ])
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => screen.getByText('MP1584EN_5V_Module'))
    screen.getByText('MyPCBLibs')
    expect(searchFootprintsMock).toHaveBeenCalledWith('MP1584')
  })

  it('TEST-003: selecting a candidate calls attachFootprintToPart and shows the linked footprint', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' },
    ])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs:MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))

    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))

    await waitFor(() => screen.getByText('Footprint linked: MyPCBLibs:MP1584EN_5V_Module'))
    expect(attachFootprintToPartMock).toHaveBeenCalledWith(SAVED_PART_NO_FOOTPRINT, 'MyPCBLibs', 'MP1584EN_5V_Module')
    expect(screen.queryByText('Find Footprint')).toBeNull()
  })

  it('TEST-004: zero search results renders an honest empty state, not an error', async () => {
    searchFootprintsMock.mockResolvedValueOnce([])
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'nonexistent' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => screen.getByText("No match in this machine's own configured KiCad libraries."))
  })
})
