import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const extractPartDetailMock = vi.fn()
const saveConfirmedPartMock = vi.fn()
const exportSymbolMock = vi.fn()
const openMock = vi.fn()
const searchFootprintsMock = vi.fn()
const attachFootprintToPartMock = vi.fn()
const generateFootprintFromPartMock = vi.fn()
const exportFootprintMock = vi.fn()
const getConnectionGuidanceMock = vi.fn()
const searchCommunityFootprintsMock = vi.fn()
const importCommunityFootprintMock = vi.fn()
const attachCommunityFootprintToPartMock = vi.fn()
const listLibrariesMock = vi.fn()
const tagObjectMock = vi.fn()

vi.mock('../lib/library', () => ({
  listLibraries: (...args: unknown[]) => listLibrariesMock(...args),
  tagObject: (...args: unknown[]) => tagObjectMock(...args),
}))

vi.mock('../lib/partDetail', () => ({
  extractPartDetail: (...args: unknown[]) => extractPartDetailMock(...args),
  saveConfirmedPart: (...args: unknown[]) => saveConfirmedPartMock(...args),
  exportSymbol: (...args: unknown[]) => exportSymbolMock(...args),
  getConnectionGuidance: (...args: unknown[]) => getConnectionGuidanceMock(...args),
}))

vi.mock('../lib/footprints', () => ({
  searchFootprints: (...args: unknown[]) => searchFootprintsMock(...args),
  attachFootprintToPart: (...args: unknown[]) => attachFootprintToPartMock(...args),
  generateFootprintFromPart: (...args: unknown[]) => generateFootprintFromPartMock(...args),
  exportFootprint: (...args: unknown[]) => exportFootprintMock(...args),
  searchCommunityFootprints: (...args: unknown[]) => searchCommunityFootprintsMock(...args),
  importCommunityFootprint: (...args: unknown[]) => importCommunityFootprintMock(...args),
  attachCommunityFootprintToPart: (...args: unknown[]) => attachCommunityFootprintToPartMock(...args),
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
  generateFootprintFromPartMock.mockReset()
  exportFootprintMock.mockReset()
  getConnectionGuidanceMock.mockReset()
  searchCommunityFootprintsMock.mockReset()
  importCommunityFootprintMock.mockReset()
  attachCommunityFootprintToPartMock.mockReset()
  listLibrariesMock.mockReset()
  tagObjectMock.mockReset()
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
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module', source: 'kicad_library' },
    ])
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => screen.getByText('MP1584EN_5V_Module'))
    screen.getByText('MyPCBLibs')
    expect(searchFootprintsMock).toHaveBeenCalledWith('MP1584')
  })

  it('TEST-004 (CTX-308.4): each candidate shows a real, distinguishing label for its source', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'Battery', footprint_name: 'BatteryHolder_X', source: 'kicad_library' },
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module', source: 'your_library' },
    ])
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => screen.getByText('BatteryHolder_X'))
    screen.getByText(/KiCad library/)
    screen.getByText(/previously saved/)
  })

  it('TEST-003: selecting a candidate calls attachFootprintToPart and shows the linked footprint', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' },
    ])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))

    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))

    await waitFor(() => screen.getByText('Footprint linked: MyPCBLibs__MP1584EN_5V_Module'))
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

  it('CTX-314.2: searching community libraries renders real candidates and importing a footprint attaches it to the Part', async () => {
    searchCommunityFootprintsMock.mockResolvedValueOnce([
      {
        owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: 'footprints/x.pretty/C_0201.kicad_mod',
        kind: 'footprint', license: 'CC-BY-4.0', blob_sha: 'abc', download_url: 'https://example.com/C_0201.kicad_mod',
      },
    ])
    const record = { footprint_id: 'sparkfun__SparkFun-KiCad-Libraries__C_0201', pad_count: 4, provenance: {} }
    importCommunityFootprintMock.mockResolvedValueOnce(record)
    attachCommunityFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'sparkfun__SparkFun-KiCad-Libraries__C_0201',
    })
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'C_0201' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search community libraries' }))

    await waitFor(() => screen.getByText(/C_0201\.kicad_mod/))
    screen.getByText(/sparkfun\/SparkFun-KiCad-Libraries/)
    expect(searchCommunityFootprintsMock).toHaveBeenCalledWith('C_0201')

    fireEvent.click(screen.getByRole('button', { name: 'Import' }))

    await waitFor(() => screen.getByText('Footprint linked: sparkfun__SparkFun-KiCad-Libraries__C_0201'))
    expect(importCommunityFootprintMock).toHaveBeenCalledWith(expect.objectContaining({ path: 'footprints/x.pretty/C_0201.kicad_mod' }))
    expect(attachCommunityFootprintToPartMock).toHaveBeenCalledWith(SAVED_PART_NO_FOOTPRINT, record)
  })

  it('CTX-314.2: a .kicad_sym candidate imports through a real two-step browse-then-import flow, not directly', async () => {
    searchCommunityFootprintsMock.mockResolvedValueOnce([
      {
        owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: 'symbols/SparkFun-Capacitor.kicad_sym',
        kind: 'symbol', license: 'CC-BY-4.0', blob_sha: 'def', download_url: 'https://example.com/SparkFun-Capacitor.kicad_sym',
      },
    ])
    importCommunityFootprintMock.mockResolvedValueOnce({
      symbols: [{ name: 'C_0402', pin_count: 2 }, { name: 'C_0603', pin_count: 2 }],
    })
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'Capacitor' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search community libraries' }))
    await waitFor(() => screen.getByText(/SparkFun-Capacitor\.kicad_sym/))

    fireEvent.click(screen.getByRole('button', { name: 'Import' }))

    await waitFor(() => screen.getByText(/contains 2 real/))
    screen.getByText('C_0402')
    screen.getByText('C_0603')
    expect(attachCommunityFootprintToPartMock).not.toHaveBeenCalled()

    importCommunityFootprintMock.mockResolvedValueOnce({ symbol_id: 'sparkfun__SparkFun-KiCad-Libraries__C_0402', pin_count: 2, provenance: {} })
    fireEvent.click(screen.getAllByRole('button', { name: 'Import' })[0])

    await waitFor(() => screen.getByText(/Imported symbol/))
    screen.getByText('sparkfun__SparkFun-KiCad-Libraries__C_0402')
    expect(importCommunityFootprintMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ path: 'symbols/SparkFun-Capacitor.kicad_sym' }), 'C_0402',
    )
    expect(attachCommunityFootprintToPartMock).not.toHaveBeenCalled()
  })

  it('CTX-315.2: Add to library… opens a real picker and calls tagObject with the chosen ids', async () => {
    listLibrariesMock.mockResolvedValueOnce([
      { id: 'default', name: 'Default', part_count: 3, symbol_count: 1, footprint_count: 1 },
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 1, symbol_count: 0, footprint_count: 0 },
    ])
    tagObjectMock.mockResolvedValueOnce({ library_ids: ['default', 'esp32-boards'] })
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Add to library…' }))

    await waitFor(() => screen.getByText('ESP32 Boards'))
    expect(screen.queryByText('Default')).toBeNull()

    fireEvent.click(screen.getByLabelText('ESP32 Boards'))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(tagObjectMock).toHaveBeenCalledWith('part', 'ATtiny85', ['esp32-boards']))
    await waitFor(() => screen.getByText('Added to library.'))
  })

  it('CTX-308.5: Generate from datasheet dimensions calls generateFootprintFromPart and shows an unverified badge', async () => {
    generateFootprintFromPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'generated__ATtiny85',
    })
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Generate from datasheet dimensions' }))

    await waitFor(() => screen.getByText('Footprint linked: generated__ATtiny85'))
    expect(generateFootprintFromPartMock).toHaveBeenCalledWith(SAVED_PART_NO_FOOTPRINT)
    screen.getByText(/generated from datasheet dimensions — unverified/)
    expect(screen.queryByText('Find Footprint')).toBeNull()
  })

  it('CTX-308.5: does not require a search first -- available immediately in Find Footprint', async () => {
    await saveAndReachFootprintSection()

    screen.getByRole('button', { name: 'Generate from datasheet dimensions' })
    expect(searchFootprintsMock).not.toHaveBeenCalled()
  })

  it('CTX-308.5: a generation failure (e.g. unsupported package) shows the real error, not a crash', async () => {
    generateFootprintFromPartMock.mockRejectedValueOnce(
      new Error("No pad-layout generator for package 'TQFP-32'."),
    )
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Generate from datasheet dimensions' }))

    await waitFor(() => screen.getByText(/No pad-layout generator for package 'TQFP-32'/))
    expect(screen.queryByText('Footprint linked:', { exact: false })).toBeNull()
  })

  it('a found footprint (not generated) never shows the unverified badge', async () => {
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' }])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))

    await waitFor(() => screen.getByText('Footprint linked: MyPCBLibs__MP1584EN_5V_Module'))
    expect(screen.queryByText(/unverified/)).toBeNull()
  })

  it('CTX-308.6: Export Footprint writes the real file and "Open footprint" opens it via the shell plugin', async () => {
    generateFootprintFromPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'generated__ATtiny85',
    })
    exportFootprintMock.mockResolvedValueOnce('/storage/library/footprints.pretty/generated__ATtiny85.kicad_mod')
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate from datasheet dimensions' }))
    await waitFor(() => screen.getByRole('button', { name: 'Export Footprint (.kicad_mod)' }))

    fireEvent.click(screen.getByRole('button', { name: 'Export Footprint (.kicad_mod)' }))

    await waitFor(() => screen.getByText(/Exported: \/storage\/library\/footprints\.pretty\/generated__ATtiny85\.kicad_mod/))
    expect(exportFootprintMock).toHaveBeenCalledWith('generated__ATtiny85')

    fireEvent.click(screen.getByRole('button', { name: 'Open footprint' }))
    expect(openMock).toHaveBeenCalledWith('/storage/library/footprints.pretty/generated__ATtiny85.kicad_mod')
  })

  it('CTX-308.6: an export failure (e.g. a found, not generated, footprint) shows the real error', async () => {
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' }])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    exportFootprintMock.mockRejectedValueOnce(
      new Error("Footprint 'MyPCBLibs__MP1584EN_5V_Module' has no pad geometry to export."),
    )
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))
    await waitFor(() => screen.getByRole('button', { name: 'Export Footprint (.kicad_mod)' }))

    fireEvent.click(screen.getByRole('button', { name: 'Export Footprint (.kicad_mod)' }))

    await waitFor(() => screen.getByText(/has no pad geometry to export/))
    expect(screen.queryByText('Exported:', { exact: false })).toBeNull()
  })

  it('CTX-308.7: Get Connection Guidance calls getConnectionGuidance and renders real per-pin guidance', async () => {
    getConnectionGuidanceMock.mockResolvedValueOnce({
      pin_guidance: [{ pin_number: '8', guidance: 'Add a 100nF ceramic decoupling capacitor from VCC to GND.' }],
      general_notes: 'Tie RESET high through a pull-up if unused.',
    })
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' }])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))
    await waitFor(() => screen.getByRole('button', { name: 'Get Connection Guidance' }))

    fireEvent.click(screen.getByRole('button', { name: 'Get Connection Guidance' }))

    await waitFor(() => screen.getByText(/Add a 100nF ceramic decoupling capacitor/))
    expect(getConnectionGuidanceMock).toHaveBeenCalledWith('ATtiny85')
    screen.getByText('Pin 8:')
    screen.getByText(/Tie RESET high through a pull-up/)
  })

  it('CTX-308.7: available once a footprint is linked, not gated on it being generated', async () => {
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' }])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search this machine's own KiCad libraries/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))

    await waitFor(() => screen.getByRole('button', { name: 'Get Connection Guidance' }))
  })

  it('CTX-308.7: a guidance failure shows the real error, not a crash', async () => {
    getConnectionGuidanceMock.mockRejectedValueOnce(new Error('Connection guidance did not return a JSON object.'))
    generateFootprintFromPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'generated__ATtiny85',
    })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate from datasheet dimensions' }))
    await waitFor(() => screen.getByRole('button', { name: 'Get Connection Guidance' }))

    fireEvent.click(screen.getByRole('button', { name: 'Get Connection Guidance' }))

    await waitFor(() => screen.getByText(/Connection guidance did not return a JSON object/))
  })

  it('CTX-308.7: an empty pin_guidance list renders an honest "no guidance" message, not an error', async () => {
    getConnectionGuidanceMock.mockResolvedValueOnce({ pin_guidance: [], general_notes: '' })
    generateFootprintFromPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'generated__ATtiny85',
    })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate from datasheet dimensions' }))
    await waitFor(() => screen.getByRole('button', { name: 'Get Connection Guidance' }))

    fireEvent.click(screen.getByRole('button', { name: 'Get Connection Guidance' }))

    await waitFor(() => screen.getByText('No pin-specific guidance for this part.'))
  })
})
