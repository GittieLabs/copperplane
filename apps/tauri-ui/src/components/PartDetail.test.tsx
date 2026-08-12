import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const extractPartDetailMock = vi.fn()
const saveConfirmedPartMock = vi.fn()
const exportSymbolMock = vi.fn()
const openMock = vi.fn()

vi.mock('../lib/partDetail', () => ({
  extractPartDetail: (...args: unknown[]) => extractPartDetailMock(...args),
  saveConfirmedPart: (...args: unknown[]) => saveConfirmedPartMock(...args),
  exportSymbol: (...args: unknown[]) => exportSymbolMock(...args),
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
})

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
})
