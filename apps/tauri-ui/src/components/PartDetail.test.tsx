import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
const renderSymbolPreviewMock = vi.fn()
const renderFootprintPreviewMock = vi.fn()
const listLibrariesMock = vi.fn()
const tagObjectMock = vi.fn()
const generateDesignGuidanceMock = vi.fn()
const cacheDatasheetMock = vi.fn()
const loadPartMock = vi.fn()
const addProjectPartReferenceMock = vi.fn()
const listProjectsMock = vi.fn()
const setProjectFootprintOverrideMock = vi.fn()
const attachFootprintToProjectOverrideMock = vi.fn()
const attachCommunityFootprintToProjectOverrideMock = vi.fn()
const generateFootprintForProjectOverrideMock = vi.fn()
const suggestFootprintQueryMock = vi.fn()

vi.mock('../lib/library', () => ({
  listLibraries: (...args: unknown[]) => listLibrariesMock(...args),
  tagObject: (...args: unknown[]) => tagObjectMock(...args),
}))

vi.mock('../lib/projects', () => ({
  addProjectPartReference: (...args: unknown[]) => addProjectPartReferenceMock(...args),
  listProjects: (...args: unknown[]) => listProjectsMock(...args),
  setProjectFootprintOverride: (...args: unknown[]) => setProjectFootprintOverrideMock(...args),
}))

vi.mock('../lib/partDetail', () => ({
  extractPartDetail: (...args: unknown[]) => extractPartDetailMock(...args),
  saveConfirmedPart: (...args: unknown[]) => saveConfirmedPartMock(...args),
  exportSymbol: (...args: unknown[]) => exportSymbolMock(...args),
  getConnectionGuidance: (...args: unknown[]) => getConnectionGuidanceMock(...args),
  generateDesignGuidance: (...args: unknown[]) => generateDesignGuidanceMock(...args),
  loadPart: (...args: unknown[]) => loadPartMock(...args),
}))

vi.mock('../lib/components', () => ({
  cacheDatasheet: (...args: unknown[]) => cacheDatasheetMock(...args),
}))

vi.mock('../lib/footprints', () => ({
  searchFootprints: (...args: unknown[]) => searchFootprintsMock(...args),
  attachFootprintToPart: (...args: unknown[]) => attachFootprintToPartMock(...args),
  generateFootprintFromPart: (...args: unknown[]) => generateFootprintFromPartMock(...args),
  exportFootprint: (...args: unknown[]) => exportFootprintMock(...args),
  searchCommunityFootprints: (...args: unknown[]) => searchCommunityFootprintsMock(...args),
  importCommunityFootprint: (...args: unknown[]) => importCommunityFootprintMock(...args),
  attachCommunityFootprintToPart: (...args: unknown[]) => attachCommunityFootprintToPartMock(...args),
  renderSymbolPreview: (...args: unknown[]) => renderSymbolPreviewMock(...args),
  renderFootprintPreview: (...args: unknown[]) => renderFootprintPreviewMock(...args),
  attachFootprintToProjectOverride: (...args: unknown[]) => attachFootprintToProjectOverrideMock(...args),
  attachCommunityFootprintToProjectOverride: (...args: unknown[]) =>
    attachCommunityFootprintToProjectOverrideMock(...args),
  generateFootprintForProjectOverride: (...args: unknown[]) => generateFootprintForProjectOverrideMock(...args),
  suggestFootprintQuery: (...args: unknown[]) => suggestFootprintQueryMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => openMock(...args),
}))

// CTX-318.2: AgentChat has its own dedicated test file (AgentChat.test.tsx)
// -- stubbed here, matching ComponentDiscovery.test.tsx's own precedent
// for PartDetail, so PartDetail's tests stay focused on PartDetail's own
// wiring (does it mount AgentChat with the real scope/area/targets) and
// never need to mock AgentChat's own internal chat.* IPC calls.
vi.mock('./AgentChat', () => ({
  AgentChat: ({
    area,
    scope,
    scopeId,
    title,
    projectName,
    promotionTargets,
  }: {
    area: string
    scope: string
    scopeId: string
    title: string
    projectName?: string
    promotionTargets: { label: string; scope: string; id: string }[]
  }) => (
    <p>
      AgentChat stub: area={area} scope={scope} scopeId={scopeId} title="{title}"
      {projectName && ` projectName=${projectName}`}
      {' '}targets=[{promotionTargets.map((t) => `${t.label}:${t.scope}:${t.id}`).join(', ')}]
    </p>
  ),
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
  // CTX-306.6: Find Footprint now runs both real searches from one
  // "Search" action -- default both to a real, empty result so a test
  // that only configures one of them doesn't hit the other's
  // unconfigured mock (which resolves to `undefined`, not `[]`).
  searchFootprintsMock.mockReset().mockResolvedValue([])
  attachFootprintToPartMock.mockReset()
  generateFootprintFromPartMock.mockReset()
  exportFootprintMock.mockReset()
  getConnectionGuidanceMock.mockReset()
  searchCommunityFootprintsMock.mockReset().mockResolvedValue([])
  importCommunityFootprintMock.mockReset()
  attachCommunityFootprintToPartMock.mockReset()
  // CTX-306.7: both preview routes fire automatically as soon as a
  // symbol/footprint id exists -- default to a real, resolved SVG so
  // pre-existing tests (none of which know these routes exist) don't
  // hit an unconfigured mock's `undefined` result.
  renderSymbolPreviewMock.mockReset().mockResolvedValue('<svg data-testid="symbol-preview-svg"></svg>')
  renderFootprintPreviewMock.mockReset().mockResolvedValue('<svg data-testid="footprint-preview-svg"></svg>')
  listLibrariesMock.mockReset()
  tagObjectMock.mockReset()
  generateDesignGuidanceMock.mockReset()
  cacheDatasheetMock.mockReset()
  // CTX-306.3: default to "not saved yet" so every pre-existing test in
  // this file (none of which knows loadPart exists) still falls through
  // to real extraction exactly as before.
  loadPartMock.mockReset().mockRejectedValue(new Error('No Part found.'))
  addProjectPartReferenceMock.mockReset()
  listProjectsMock.mockReset().mockResolvedValue([])
  setProjectFootprintOverrideMock.mockReset()
  attachFootprintToProjectOverrideMock.mockReset()
  attachCommunityFootprintToProjectOverrideMock.mockReset()
  generateFootprintForProjectOverrideMock.mockReset()
  suggestFootprintQueryMock.mockReset()
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

  it('CTX-306.3: a candidate already saved to the library hydrates directly and never re-extracts', async () => {
    loadPartMock.mockResolvedValueOnce(SAVED_PART_NO_FOOTPRINT)

    render(<PartDetail candidate={CANDIDATE} />)

    await waitFor(() => screen.getByText('Find Footprint'))
    expect(loadPartMock).toHaveBeenCalledWith('ATtiny85')
    expect(extractPartDetailMock).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Save to Library' })).toBeNull()
  })

  it('CTX-306.3: a genuinely new candidate still extracts and shows Save to Library', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })

    render(<PartDetail candidate={CANDIDATE} />)

    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    expect(loadPartMock).toHaveBeenCalledWith('ATtiny85')
    expect(extractPartDetailMock).toHaveBeenCalledWith('ATtiny85')
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

  it('CTX-304.3: a successful save with a project open also links the part to the project', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: { part_id: 'ATtiny85' },
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })
    addProjectPartReferenceMock.mockResolvedValueOnce({ name: 'weather-pcb', parts: ['ATtiny85'] })

    render(<PartDetail candidate={CANDIDATE} currentProject={{ name: 'weather-pcb' }} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))

    await waitFor(() => screen.getByText('Saved to library.'))
    expect(addProjectPartReferenceMock).toHaveBeenCalledWith('weather-pcb', 'ATtiny85')
    expect(screen.queryByText(/couldn't link it/)).toBeNull()
  })

  it("CTX-304.3: with no project open, save behaves exactly as before -- no linkage call, no warning", async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: { part_id: 'ATtiny85' },
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))

    await waitFor(() => screen.getByText('Saved to library.'))
    expect(addProjectPartReferenceMock).not.toHaveBeenCalled()
    expect(screen.queryByText(/couldn't link it/)).toBeNull()
  })

  it('CTX-304.3: a linkage failure shows a real, non-blocking warning without hiding the already-succeeded save', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: { part_id: 'ATtiny85' },
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })
    addProjectPartReferenceMock.mockRejectedValueOnce(new Error("Project 'weather-pcb' not found."))

    render(<PartDetail candidate={CANDIDATE} currentProject={{ name: 'weather-pcb' }} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))

    await waitFor(() => screen.getByText('Saved to library.'))
    await waitFor(() => screen.getByText(/couldn't link it to project "weather-pcb"/))
    screen.getByText(/Project 'weather-pcb' not found\./)
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

  it('a real "Open symbol" failure (e.g. no OS file association) shows an error, not a silent no-op', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: { part_id: 'ATtiny85' },
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })
    exportSymbolMock.mockResolvedValueOnce('/storage/library/symbols/SOIC-8_0pin.kicad_sym')
    openMock.mockRejectedValueOnce(new Error('No application associated with this file type.'))

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))
    await waitFor(() => screen.getByRole('button', { name: 'Export Symbol (.kicad_sym)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Export Symbol (.kicad_sym)' }))
    await waitFor(() => screen.getByRole('button', { name: 'Open symbol' }))

    fireEvent.click(screen.getByRole('button', { name: 'Open symbol' }))

    await waitFor(() => screen.getByText(/No application associated with this file type/))
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

  it('CTX-306.6: real user feedback -- the footprint search box auto-fills with the part\'s own package', async () => {
    await saveAndReachFootprintSection()

    const input = screen.getByPlaceholderText(/search by footprint or package name/) as HTMLInputElement
    expect(input.value).toBe('SOIC-8')
  })

  it('CTX-306.6: one Search action runs both real searches and combines results into one list, labeled by source', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module', source: 'kicad_library' },
    ])
    searchCommunityFootprintsMock.mockResolvedValueOnce([
      {
        owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: 'footprints/x.pretty/C_0201.kicad_mod',
        kind: 'footprint', license: 'CC-BY-4.0', blob_sha: 'abc', download_url: 'https://example.com/C_0201.kicad_mod',
      },
    ])
    await saveAndReachFootprintSection()

    expect(screen.queryByRole('button', { name: 'Search community libraries' })).toBeNull()
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => screen.getByText('MP1584EN_5V_Module'))
    screen.getByText(/C_0201\.kicad_mod/)
    expect(searchFootprintsMock).toHaveBeenCalledWith('x')
    expect(searchCommunityFootprintsMock).toHaveBeenCalledWith('x')
  })

  it('CTX-306.6: real user feedback -- Generate from datasheet dimensions now follows the search results, not sandwiched between two searches', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module', source: 'kicad_library' },
    ])
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByText('MP1584EN_5V_Module'))

    const resultsPosition = screen.getByText('MP1584EN_5V_Module').compareDocumentPosition(
      screen.getByRole('button', { name: 'Generate from datasheet dimensions' }),
    )
    // Node.DOCUMENT_POSITION_FOLLOWING === 4 -- the Generate button comes
    // after the result in document order.
    expect(resultsPosition & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('TEST-002: searching renders real candidates from kicad.search_footprints', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module', source: 'kicad_library' },
    ])
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
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

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'x' } })
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
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
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

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'nonexistent' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => screen.getByText('No match in any known source.'))
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

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'C_0201' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

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

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'Capacitor' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
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

  it('CTX-306.4: Add to project… opens a real picker and calls addProjectPartReference for each chosen project', async () => {
    listProjectsMock.mockResolvedValueOnce(['weather-pcb', 'doorbell'])
    addProjectPartReferenceMock.mockResolvedValue({ name: 'weather-pcb', parts: ['ATtiny85'] })
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Add to project…' }))

    await waitFor(() => screen.getByText('doorbell'))
    fireEvent.click(screen.getByLabelText('weather-pcb'))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(addProjectPartReferenceMock).toHaveBeenCalledWith('weather-pcb', 'ATtiny85'))
    expect(addProjectPartReferenceMock).not.toHaveBeenCalledWith('doorbell', 'ATtiny85')
    await waitFor(() => screen.getByText('Added to project.'))
  })

  it('CTX-306.4: a failed project link shows which project failed without crashing', async () => {
    listProjectsMock.mockResolvedValueOnce(['weather-pcb'])
    addProjectPartReferenceMock.mockRejectedValueOnce(new Error("Project 'weather-pcb' not found."))
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Add to project…' }))
    await waitFor(() => screen.getByText('weather-pcb'))
    fireEvent.click(screen.getByLabelText('weather-pcb'))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => screen.getByText("Couldn't add to: weather-pcb."))
  })

  it('CTX-306.4: "Add to project..." works from a reopened, already-saved Part the same as a freshly-saved one', async () => {
    loadPartMock.mockResolvedValueOnce(SAVED_PART_NO_FOOTPRINT)
    listProjectsMock.mockResolvedValueOnce(['weather-pcb'])
    addProjectPartReferenceMock.mockResolvedValueOnce({ name: 'weather-pcb', parts: ['ATtiny85'] })

    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Add to project…' }))

    fireEvent.click(screen.getByRole('button', { name: 'Add to project…' }))
    await waitFor(() => screen.getByText('weather-pcb'))
    fireEvent.click(screen.getByLabelText('weather-pcb'))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(addProjectPartReferenceMock).toHaveBeenCalledWith('weather-pcb', 'ATtiny85'))
  })

  it('CTX-306.5: with a currentProject, Add to project skips the picker and adds directly, no Confirm step', async () => {
    addProjectPartReferenceMock.mockResolvedValueOnce({ name: 'weather-pcb', parts: ['ATtiny85'] })
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: SAVED_PART_NO_FOOTPRINT,
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })

    render(<PartDetail candidate={CANDIDATE} currentProject={{ name: 'weather-pcb', parts: [] }} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }))
    await waitFor(() => screen.getByText('Saved to library.'))

    // The auto-link-on-save (CTX-304.3) already fired once -- reset the
    // mock's call history so this test's own assertion is unambiguous
    // about the manual button below.
    addProjectPartReferenceMock.mockClear()
    addProjectPartReferenceMock.mockResolvedValueOnce({ name: 'weather-pcb', parts: ['ATtiny85'] })

    expect(screen.queryByRole('button', { name: 'Add to project…' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Add to project "weather-pcb"' }))

    await waitFor(() => expect(addProjectPartReferenceMock).toHaveBeenCalledWith('weather-pcb', 'ATtiny85'))
    expect(listProjectsMock).not.toHaveBeenCalled()
    await waitFor(() => screen.getByText('✓ In project "weather-pcb"'))
  })

  it('CTX-306.5: a part already listed on currentProject.parts shows as already added, no button at all', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    saveConfirmedPartMock.mockResolvedValueOnce({
      part: SAVED_PART_NO_FOOTPRINT,
      symbol: { symbol_id: 'SOIC-8_0pin', reference_prefix: 'U', pins: [] },
    })

    render(<PartDetail candidate={CANDIDATE} currentProject={{ name: 'weather-pcb', parts: ['ATtiny85'] }} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Save to Library' }))
    await waitFor(() => screen.getByText('✓ In project "weather-pcb"'))

    expect(screen.queryByRole('button', { name: /Add to project/ })).toBeNull()
  })

  it('CTX-306.5: without a currentProject, the multi-project picker still appears (the Library view)', async () => {
    await saveAndReachFootprintSection()

    screen.getByRole('button', { name: 'Add to project…' })
    expect(screen.queryByText(/✓ In project/)).toBeNull()
  })

  it('CTX-306.5: Add to library… and Add to project… render on the same row', async () => {
    await saveAndReachFootprintSection()

    const libraryButton = screen.getByRole('button', { name: 'Add to library…' })
    const projectButton = screen.getByRole('button', { name: 'Add to project…' })
    expect(libraryButton.parentElement).toBe(projectButton.parentElement)
  })

  it('CTX-306.5: the pin table stays open by default for a real, small part', async () => {
    extractPartDetailMock.mockResolvedValueOnce({
      part_number: 'ATtiny85', package: 'DIP-8',
      pins: [{ number: '1', name: 'RESET', electrical_type: 'bidirectional' }],
    })

    render(<PartDetail candidate={CANDIDATE} />)

    await waitFor(() => screen.getByText('RESET'))
    const details = screen.getByText('1 pin').closest('details') as HTMLDetailsElement
    expect(details.open).toBe(true)
  })

  it('CTX-306.5: the pin table collapses by default for a real, many-pin part (ESP32-S3 scale)', async () => {
    const manyPins = Array.from({ length: 54 }, (_, i) => ({
      number: String(i + 1), name: `GPIO${i}`, electrical_type: 'bidirectional',
    }))
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ESP32-S3', package: 'QFN-56', pins: manyPins })

    render(<PartDetail candidate={{ ...CANDIDATE, part_number: 'ESP32-S3' }} />)

    await waitFor(() => screen.getByText('54 pins'))
    const details = screen.getByText('54 pins').closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
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
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
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

  it('a real "Open footprint" failure shows an error, not a silent no-op', async () => {
    generateFootprintFromPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'generated__ATtiny85',
    })
    exportFootprintMock.mockResolvedValueOnce('/storage/library/footprints.pretty/generated__ATtiny85.kicad_mod')
    openMock.mockRejectedValueOnce(new Error('No application associated with this file type.'))
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate from datasheet dimensions' }))
    await waitFor(() => screen.getByRole('button', { name: 'Export Footprint (.kicad_mod)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Export Footprint (.kicad_mod)' }))
    await waitFor(() => screen.getByRole('button', { name: 'Open footprint' }))

    fireEvent.click(screen.getByRole('button', { name: 'Open footprint' }))

    await waitFor(() => screen.getByText(/No application associated with this file type/))
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
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
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
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
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
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
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

  const DESIGN_GUIDANCE = {
    generated_at: '2026-08-20T00:00:00+00:00',
    content_hash: 'abc123',
    document_revision: null,
    categories: {
      absolute_maximum_ratings: [],
      recommended_operating_conditions: [],
      power: [],
      decoupling: [
        { quote: 'A 100 nF decoupling capacitor should be placed close to VCC.', page: 4, category: 'decoupling' },
      ],
      reset: [],
      clock_oscillator: [],
      layout: [],
      typical_application: [],
    },
    category_summaries: {},
  }

  // CTX-205.7, SPEC-205 §2.1.1: a real plain-language summary alongside
  // decoupling's own citations -- the same category as DESIGN_GUIDANCE
  // above, so these tests exercise the "summary present" branch while
  // the tests above continue to exercise the "no summary yet" fallback
  // (a pre-CTX-205.7 record) with no changes to their own assertions.
  const DESIGN_GUIDANCE_WITH_SUMMARY = {
    ...DESIGN_GUIDANCE,
    category_summaries: { decoupling: 'Add a small capacitor near VCC to keep the supply steady.' },
  }

  it('CTX-205.4: Generate Design Requirements calls generateDesignGuidance and renders real cited guidance', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByRole('button', { name: 'Generate Design Requirements' }))

    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))

    await waitFor(() => screen.getByText(/A 100 nF decoupling capacitor/))
    expect(generateDesignGuidanceMock).toHaveBeenCalledWith('ATtiny85')
    screen.getByText('Decoupling')
    screen.getByRole('button', { name: 'Page 4' })
  })

  it('CTX-205.4: a category with no real items renders an honest empty state, not an omitted section', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))
    await waitFor(() => screen.getByText(/A 100 nF decoupling capacitor/))

    screen.getByText('Reset')
    const noGuidanceMessages = screen.getAllByText('No guidance found for this category.')
    expect(noGuidanceMessages.length).toBeGreaterThan(0)
  })

  it('CTX-205.4: a generate failure shows the real error, not a crash', async () => {
    generateDesignGuidanceMock.mockRejectedValueOnce(new Error('Could not read the cached datasheet.'))
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByRole('button', { name: 'Generate Design Requirements' }))

    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))

    await waitFor(() => screen.getByText(/Could not read the cached datasheet/))
  })

  it('CTX-205.4: once generated, Regenerate calls generateDesignGuidance again', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))
    await waitFor(() => screen.getByText(/A 100 nF decoupling capacitor/))

    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate' }))

    await waitFor(() => expect(generateDesignGuidanceMock).toHaveBeenCalledTimes(2))
  })

  it('CTX-205.4: clicking a citation chip resolves the real cached datasheet path and opens it at that page', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))
    await waitFor(() => screen.getByText(/A 100 nF decoupling capacitor/))

    fireEvent.click(screen.getByRole('button', { name: 'Page 4' }))

    await waitFor(() =>
      expect(cacheDatasheetMock).toHaveBeenCalledWith('ATtiny85', 'https://example.com/attiny85.pdf'),
    )
    await waitFor(() => expect(openMock).toHaveBeenCalledWith('/real/library/datasheets/ATtiny85.pdf#page=4'))
  })

  it('CTX-205.4: a citation-open failure shows the real error, not a crash', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    cacheDatasheetMock.mockRejectedValueOnce(new Error('Datasheet fetch failed.'))
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))
    await waitFor(() => screen.getByText(/A 100 nF decoupling capacitor/))

    fireEvent.click(screen.getByRole('button', { name: 'Page 4' }))

    await waitFor(() => screen.getByText(/Datasheet fetch failed/))
  })

  it('CTX-205.7: a category with a real summary shows it as the primary text, with citations collapsed below', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      design_guidance: DESIGN_GUIDANCE_WITH_SUMMARY,
    })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))

    await waitFor(() => screen.getByText(/Add a small capacitor near VCC/))
    const details = screen.getByText('1 citation').closest('details') as HTMLDetailsElement | null
    expect(details).not.toBeNull()
    expect(details?.open).toBe(false)
  })

  it('CTX-205.7: clicking the citations toggle reveals the underlying cited items', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      design_guidance: DESIGN_GUIDANCE_WITH_SUMMARY,
    })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))
    await waitFor(() => screen.getByText(/Add a small capacitor near VCC/))

    fireEvent.click(screen.getByText('1 citation'))

    const details = screen.getByText('1 citation').closest('details') as HTMLDetailsElement | null
    expect(details?.open).toBe(true)
    screen.getByRole('button', { name: 'Page 4' })
  })

  it('CTX-205.7: a category with no summary yet falls back to citations open by default', async () => {
    generateDesignGuidanceMock.mockResolvedValueOnce({ ...SAVED_PART_NO_FOOTPRINT, design_guidance: DESIGN_GUIDANCE })
    await saveAndReachFootprintSection()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Design Requirements' }))

    await waitFor(() => screen.getByText(/A 100 nF decoupling capacitor/))
    const details = screen.getByText('Citations').closest('details') as HTMLDetailsElement | null
    expect(details?.open).toBe(true)
  })
})

describe('PartDetail: CTX-306.7 visual symbol/footprint previews', () => {
  it('TEST-001: a symbol preview renders automatically once the part is saved, no click required', async () => {
    await saveAndReachFootprintSection()

    await waitFor(() => expect(renderSymbolPreviewMock).toHaveBeenCalledWith('SOIC-8_0pin'))
    await waitFor(() => screen.getByTestId('symbol-preview-svg'))
  })

  it('TEST-002: a symbol preview failure shows a non-blocking message, not an error state', async () => {
    renderSymbolPreviewMock.mockReset().mockRejectedValueOnce(new Error('kicad-cli not found'))

    await saveAndReachFootprintSection()

    await waitFor(() => screen.getByText('Symbol preview unavailable: kicad-cli not found'))
    // The rest of the surface (Save flow, Find Footprint) stays usable.
    screen.getByText('Find Footprint')
  })

  it('TEST-003: a footprint preview renders automatically once a footprint is linked', async () => {
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' },
    ])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))

    await waitFor(() => expect(renderFootprintPreviewMock).toHaveBeenCalledWith('MyPCBLibs__MP1584EN_5V_Module'))
    await waitFor(() => screen.getByTestId('footprint-preview-svg'))
  })

  it('TEST-004 (CTX-308.11): clicking the symbol preview opens an enlarged view, closable via its Close button', async () => {
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByTestId('symbol-preview-svg'))

    fireEvent.click(screen.getByRole('button', { name: 'View larger symbol preview' }))

    await waitFor(() => screen.getByRole('dialog', { name: 'Symbol preview' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('TEST-005 (CTX-308.11): clicking the footprint preview opens an enlarged view, closable via Escape', async () => {
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' }])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))
    await waitFor(() => screen.getByTestId('footprint-preview-svg'))

    fireEvent.click(screen.getByRole('button', { name: 'View larger footprint preview' }))
    await waitFor(() => screen.getByRole('dialog', { name: 'Footprint preview' }))

    fireEvent.keyDown(window, { key: 'Escape' })

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('TEST-006 (CTX-308.12): the enlarged view starts at 100% and has a real, definite-height scroll container', async () => {
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByTestId('symbol-preview-svg'))

    fireEvent.click(screen.getByRole('button', { name: 'View larger symbol preview' }))
    const dialog = await waitFor(() => screen.getByRole('dialog', { name: 'Symbol preview' }))

    within(dialog).getByText('100%')
    const scrollContainer = within(dialog).getByTestId('symbol-preview-svg').parentElement as HTMLElement
    expect(scrollContainer.className).toContain('overflow-auto')
    expect(scrollContainer.className).toContain('h-[70vh]')
    expect(scrollContainer.style.getPropertyValue('--zoom')).toBe('1')
  })

  it('TEST-007 (CTX-308.12): the zoom-in/out buttons change the displayed percentage and the real --zoom CSS variable', async () => {
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByTestId('symbol-preview-svg'))
    fireEvent.click(screen.getByRole('button', { name: 'View larger symbol preview' }))
    const dialog = await waitFor(() => screen.getByRole('dialog', { name: 'Symbol preview' }))
    const scrollContainer = () => within(dialog).getByTestId('symbol-preview-svg').parentElement as HTMLElement

    fireEvent.click(within(dialog).getByRole('button', { name: 'Zoom in' }))

    within(dialog).getByText('125%')
    expect(scrollContainer().style.getPropertyValue('--zoom')).toBe('1.25')

    fireEvent.click(within(dialog).getByRole('button', { name: 'Zoom out' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zoom out' }))

    within(dialog).getByText('75%')
  })

  it('TEST-008 (CTX-308.12): +/-/0 keyboard shortcuts zoom in, out, and reset', async () => {
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByTestId('symbol-preview-svg'))
    fireEvent.click(screen.getByRole('button', { name: 'View larger symbol preview' }))
    await waitFor(() => screen.getByRole('dialog', { name: 'Symbol preview' }))

    fireEvent.keyDown(window, { key: '+' })
    screen.getByText('125%')

    fireEvent.keyDown(window, { key: '-' })
    fireEvent.keyDown(window, { key: '-' })
    screen.getByText('75%')

    fireEvent.keyDown(window, { key: '0' })
    screen.getByText('100%')
  })

  it('TEST-009 (CTX-308.12): zoom is clamped and resets to 100% each time a preview is (re)opened', async () => {
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' }])
    attachFootprintToPartMock.mockResolvedValueOnce({
      ...SAVED_PART_NO_FOOTPRINT,
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    await saveAndReachFootprintSection()
    await waitFor(() => screen.getByTestId('symbol-preview-svg'))
    fireEvent.click(screen.getByRole('button', { name: 'View larger symbol preview' }))
    await waitFor(() => screen.getByRole('dialog', { name: 'Symbol preview' }))

    for (let i = 0; i < 20; i++) fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    screen.getByText('400%') // clamped at MAX_ZOOM, never runs past it
    expect((screen.getByRole('button', { name: 'Zoom in' }) as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'MP1584' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use this' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))
    await waitFor(() => screen.getByTestId('footprint-preview-svg'))
    fireEvent.click(screen.getByRole('button', { name: 'View larger footprint preview' }))

    await waitFor(() => screen.getByRole('dialog', { name: 'Footprint preview' }))
    screen.getByText('100%')
  })
})

describe('PartDetail: CTX-308.9 per-project footprint override', () => {
  const SAVED_PART_WITH_FOOTPRINT = {
    ...SAVED_PART_NO_FOOTPRINT,
    footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    design_guidance: null,
  }

  it('offers no override control without a project open, even with a global footprint already linked', async () => {
    render(<PartDetail initialPart={SAVED_PART_WITH_FOOTPRINT} />)

    await waitFor(() => screen.getByText('Footprint linked: MyPCBLibs__MP1584EN_5V_Module'))
    expect(screen.queryByRole('button', { name: /Use a different footprint/ })).toBeNull()
  })

  it('offers the override control once a project is open and a global default exists', async () => {
    render(
      <PartDetail
        initialPart={SAVED_PART_WITH_FOOTPRINT}
        currentProject={{ name: 'weather-pcb', parts: ['ATtiny85'], footprint_overrides: {} }}
      />,
    )

    await waitFor(() => screen.getByRole('button', { name: 'Use a different footprint for this project…' }))
  })

  it('picking a candidate in override mode calls attachFootprintToProjectOverride, never attachFootprintToPart, and tags the result as project-only', async () => {
    searchFootprintsMock.mockResolvedValueOnce([{ library: 'OtherLib', footprint_name: 'QFN-56' }])
    attachFootprintToProjectOverrideMock.mockResolvedValueOnce('OtherLib__QFN-56')
    render(
      <PartDetail
        initialPart={SAVED_PART_WITH_FOOTPRINT}
        currentProject={{ name: 'weather-pcb', parts: ['ATtiny85'], footprint_overrides: {} }}
      />,
    )
    await waitFor(() => screen.getByRole('button', { name: 'Use a different footprint for this project…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use a different footprint for this project…' }))
    await waitFor(() => screen.getByText('Choose a different footprint for this project'))

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), { target: { value: 'QFN' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByRole('button', { name: 'Use for this project' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use for this project' }))

    await waitFor(() => screen.getByText('Footprint linked: OtherLib__QFN-56'))
    expect(attachFootprintToProjectOverrideMock).toHaveBeenCalledWith(
      { name: 'weather-pcb', parts: ['ATtiny85'], footprint_overrides: {} },
      SAVED_PART_WITH_FOOTPRINT,
      'OtherLib',
      'QFN-56',
    )
    expect(attachFootprintToPartMock).not.toHaveBeenCalled()
    screen.getByText('(this project only)')
  })

  it('cancelling override mode returns to the linked view without calling anything', async () => {
    render(
      <PartDetail
        initialPart={SAVED_PART_WITH_FOOTPRINT}
        currentProject={{ name: 'weather-pcb', parts: ['ATtiny85'], footprint_overrides: {} }}
      />,
    )
    await waitFor(() => screen.getByRole('button', { name: 'Use a different footprint for this project…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use a different footprint for this project…' }))
    await waitFor(() => screen.getByText('Choose a different footprint for this project'))

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => screen.getByText('Footprint linked: MyPCBLibs__MP1584EN_5V_Module'))
    expect(screen.queryByText('Choose a different footprint for this project')).toBeNull()
  })

  it('shows an existing override and its Reset control, falling back to the global default once cleared', async () => {
    setProjectFootprintOverrideMock.mockResolvedValueOnce({
      name: 'weather-pcb',
      parts: ['ATtiny85'],
      footprint_overrides: {},
    })
    render(
      <PartDetail
        initialPart={SAVED_PART_WITH_FOOTPRINT}
        currentProject={{
          name: 'weather-pcb',
          parts: ['ATtiny85'],
          footprint_overrides: { ATtiny85: 'OtherLib__QFN-56' },
        }}
      />,
    )
    await waitFor(() => screen.getByText('Footprint linked: OtherLib__QFN-56'))
    screen.getByText('(this project only)')
    screen.getByRole('button', { name: 'Reset to default (MyPCBLibs__MP1584EN_5V_Module)' })

    fireEvent.click(screen.getByRole('button', { name: 'Reset to default (MyPCBLibs__MP1584EN_5V_Module)' }))

    await waitFor(() => screen.getByText('Footprint linked: MyPCBLibs__MP1584EN_5V_Module'))
    expect(setProjectFootprintOverrideMock).toHaveBeenCalledWith('weather-pcb', 'ATtiny85', null)
    expect(screen.queryByText('(this project only)')).toBeNull()
  })
})

describe('PartDetail: CTX-308.10 agent-guided footprint search', () => {
  it('TEST-001: fills the search box with the real suggested query, never runs the search itself', async () => {
    suggestFootprintQueryMock.mockResolvedValueOnce({
      query: 'QFN-56',
      alternates: ['QFN-56-1EP'],
      reasoning: 'Matches the QFN-56 package.',
    })
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Suggest a search term' }))

    await waitFor(() =>
      expect((screen.getByPlaceholderText(/search by footprint or package name/) as HTMLInputElement).value).toBe(
        'QFN-56',
      ),
    )
    expect(suggestFootprintQueryMock).toHaveBeenCalledWith('ATtiny85')
    screen.getByText(/Matches the QFN-56 package\./)
    screen.getByText(/QFN-56-1EP/)
    expect(searchFootprintsMock).not.toHaveBeenCalled()
    expect(searchCommunityFootprintsMock).not.toHaveBeenCalled()
  })

  it('TEST-002: a suggestion failure shows a non-blocking message, not an error state', async () => {
    suggestFootprintQueryMock.mockRejectedValueOnce(new Error('ANTHROPIC_API_KEY not set'))
    await saveAndReachFootprintSection()

    fireEvent.click(screen.getByRole('button', { name: 'Suggest a search term' }))

    await waitFor(() => screen.getByText("Couldn't get a suggestion: ANTHROPIC_API_KEY not set"))
    screen.getByRole('button', { name: 'Search' })
  })

  it('TEST-003: clicking Suggest overwrites text the user already typed -- unlike the passive package auto-fill, this is an explicit action', async () => {
    suggestFootprintQueryMock.mockResolvedValueOnce({ query: 'QFN-56', alternates: [], reasoning: 'n' })
    await saveAndReachFootprintSection()

    fireEvent.change(screen.getByPlaceholderText(/search by footprint or package name/), {
      target: { value: 'my own guess' },
    })
    expect((screen.getByPlaceholderText(/search by footprint or package name/) as HTMLInputElement).value).toBe(
      'my own guess',
    )

    fireEvent.click(screen.getByRole('button', { name: 'Suggest a search term' }))

    await waitFor(() =>
      expect((screen.getByPlaceholderText(/search by footprint or package name/) as HTMLInputElement).value).toBe(
        'QFN-56',
      ),
    )
  })
})

describe('PartDetail: CTX-315.4 initialPart (reopened from the Library)', () => {
  const SAVED_PART_WITH_PINS = {
    ...SAVED_PART_NO_FOOTPRINT,
    pins: [{ number: '1', name: 'RESET', electrical_type: 'bidirectional' }],
    design_guidance: null,
  }

  it('renders the already-saved Part directly, without re-running extraction', async () => {
    render(<PartDetail initialPart={SAVED_PART_WITH_PINS} />)

    await waitFor(() => screen.getByText('RESET'))
    screen.getByText('Microchip')
    expect(extractPartDetailMock).not.toHaveBeenCalled()
  })

  it('shows "Saved to library." immediately -- never the "Save to Library" button a fresh candidate gets', async () => {
    render(<PartDetail initialPart={SAVED_PART_WITH_PINS} />)

    await waitFor(() => screen.getByText('Saved to library.'))
    expect(screen.queryByRole('button', { name: 'Save to Library' })).toBeNull()
    screen.getByRole('button', { name: 'Export Symbol (.kicad_sym)' })
  })

  it('"Add to library..." still works from a reopened Part, the same as a freshly-saved one', async () => {
    listLibrariesMock.mockResolvedValueOnce([
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 0, symbol_count: 0, footprint_count: 0 },
    ])

    render(<PartDetail initialPart={SAVED_PART_WITH_PINS} />)
    await waitFor(() => screen.getByRole('button', { name: 'Add to library…' }))

    fireEvent.click(screen.getByRole('button', { name: 'Add to library…' }))

    await waitFor(() => screen.getByText('ESP32 Boards'))
  })
})

describe('PartDetail: CTX-318.2 AgentChat wiring', () => {
  const SAVED_PART = { ...SAVED_PART_NO_FOOTPRINT, design_guidance: null }

  it('mounts AgentChat scoped to the real part, offering only "this part" when no project is open', async () => {
    render(<PartDetail initialPart={SAVED_PART} />)

    await waitFor(() => screen.getByText(/AgentChat stub/))
    const stub = screen.getByText(/AgentChat stub/)
    expect(stub.textContent).toContain('area=components')
    expect(stub.textContent).toContain('scope=part')
    expect(stub.textContent).toContain('scopeId=ATtiny85')
    expect(stub.textContent).toContain('title="Ask about this part"')
    expect(stub.textContent).not.toContain('projectName=')
    expect(stub.textContent).toContain('targets=[this part:part:ATtiny85]')
  })

  it('also offers "this project" when a project is open', async () => {
    render(<PartDetail initialPart={SAVED_PART} currentProject={{ name: 'weather-pcb' }} />)

    await waitFor(() => screen.getByText(/AgentChat stub/))
    const stub = screen.getByText(/AgentChat stub/)
    expect(stub.textContent).toContain('projectName=weather-pcb')
    expect(stub.textContent).toContain('targets=[this part:part:ATtiny85, this project:project:weather-pcb]')
  })

  it('does not mount AgentChat before a Part is actually saved -- there is no part_id to scope it to yet', async () => {
    extractPartDetailMock.mockResolvedValueOnce({ part_number: 'ATtiny85', package: 'SOIC-8', pins: [] })
    render(<PartDetail candidate={CANDIDATE} />)
    await waitFor(() => screen.getByRole('button', { name: 'Save to Library' }))

    expect(screen.queryByText(/AgentChat stub/)).toBeNull()
  })
})
