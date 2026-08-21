import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const searchComponentsMock = vi.fn()
const cacheDatasheetMock = vi.fn()
const writeTextMock = vi.fn()
const openMock = vi.fn()
const listPartsMock = vi.fn()

vi.mock('../lib/components', () => ({
  searchComponents: (...args: unknown[]) => searchComponentsMock(...args),
  cacheDatasheet: (...args: unknown[]) => cacheDatasheetMock(...args),
}))

vi.mock('../lib/library', () => ({
  listParts: (...args: unknown[]) => listPartsMock(...args),
}))

vi.mock('@tauri-apps/plugin-clipboard-manager', () => ({
  writeText: (...args: unknown[]) => writeTextMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => openMock(...args),
}))

// PartDetail (SPEC-307) has its own dedicated test file; stubbed here so
// ComponentDiscovery's tests stay focused on search/confirm/cache and
// don't need to mock PartDetail's own real extraction call.
vi.mock('./PartDetail', () => ({
  PartDetail: ({ candidate }: { candidate: { part_number: string } }) => (
    <p>PartDetail stub for {candidate.part_number}</p>
  ),
}))

const { ComponentDiscovery } = await import('./ComponentDiscovery')

function search(query: string) {
  fireEvent.change(screen.getByPlaceholderText(/search for a part/), { target: { value: query } })
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
}

beforeEach(() => {
  searchComponentsMock.mockReset()
  cacheDatasheetMock.mockReset()
  writeTextMock.mockReset()
  openMock.mockReset()
  listPartsMock.mockReset().mockResolvedValue([])
})

describe('ComponentDiscovery', () => {
  it('renders every returned candidate with its confidence label, and "view datasheet" opens it via the shell plugin', async () => {
    /** A plain <a target="_blank"> doesn't reliably escape the Tauri
     * webview -- found by real end-to-end testing -- so this is a
     * button calling tauri-plugin-shell's open(), not an anchor tag. */
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85',
        manufacturer: 'Microchip',
        package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf',
        confidence: 'high',
        rationale: 'Exact match.',
      },
    ])

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')

    await waitFor(() => screen.getByText('ATtiny85', { exact: false }))
    screen.getByText(/confidence: high/)
    expect(searchComponentsMock).toHaveBeenCalledWith('atiny85')

    fireEvent.click(screen.getByRole('button', { name: 'view datasheet' }))
    expect(openMock).toHaveBeenCalledWith('https://example.com/attiny85.pdf')
  })

  it('never auto-selects, even when exactly one high-confidence candidate is returned', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85',
        manufacturer: 'Microchip',
        package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf',
        confidence: 'high',
        rationale: 'Exact match.',
      },
    ])

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')

    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    expect(cacheDatasheetMock).not.toHaveBeenCalled()
  })

  it('a search failure shows the real error, not a silent empty list', async () => {
    searchComponentsMock.mockRejectedValueOnce(new Error('Search did not return a non-empty list of candidates.'))

    render(<ComponentDiscovery projectName="test-project" />)
    search('???')

    await waitFor(() => screen.getByText('Search did not return a non-empty list of candidates.'))
  })

  it('clicking "This one" caches the datasheet and renders a confirmed state naming SPEC-307 as not built yet', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85',
        manufacturer: 'Microchip',
        package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf',
        confidence: 'high',
        rationale: 'Exact match.',
      },
    ])
    cacheDatasheetMock.mockResolvedValueOnce('/storage/library/datasheets/ATtiny85.pdf')

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')
    await waitFor(() => screen.getByRole('button', { name: 'This one' }))

    fireEvent.click(screen.getByRole('button', { name: 'This one' }))

    await waitFor(() => screen.getByText(/Confirmed: ATtiny85/))
    screen.getByText(/Datasheet cached: \/storage\/library\/datasheets\/ATtiny85\.pdf/)
    screen.getByText('PartDetail stub for ATtiny85')
    expect(cacheDatasheetMock).toHaveBeenCalledWith('ATtiny85', 'https://example.com/attiny85.pdf')

    fireEvent.click(screen.getByRole('button', { name: 'Open datasheet' }))
    expect(openMock).toHaveBeenCalledWith('/storage/library/datasheets/ATtiny85.pdf')

    fireEvent.click(screen.getByRole('button', { name: 'Copy local path' }))
    await waitFor(() => screen.getByText('Copied.'))
    expect(writeTextMock).toHaveBeenCalledWith('/storage/library/datasheets/ATtiny85.pdf')
  })

  it('"Back to results" returns to the same candidate list without re-searching -- real usability gap found by manual testing', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85',
        manufacturer: 'Microchip',
        package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf',
        confidence: 'high',
        rationale: 'Exact match.',
      },
      {
        part_number: 'ATtiny85-20PU',
        manufacturer: 'Microchip',
        package: 'PDIP-8',
        datasheet_url: 'https://example.com/attiny85-20pu.pdf',
        confidence: 'high',
        rationale: 'A common variant.',
      },
    ])
    cacheDatasheetMock.mockResolvedValueOnce('/storage/library/datasheets/ATtiny85.pdf')

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')
    await waitFor(() => screen.getAllByRole('button', { name: 'This one' }))

    fireEvent.click(screen.getAllByRole('button', { name: 'This one' })[0])
    await waitFor(() => screen.getByText(/Confirmed: ATtiny85\b/))

    fireEvent.click(screen.getByRole('button', { name: 'Back to results' }))

    // The original two-candidate list is still there -- no second search call.
    screen.getByText('ATtiny85-20PU', { exact: false })
    expect(searchComponentsMock).toHaveBeenCalledTimes(1)
  })

  it('a failed datasheet cache still confirms the candidate -- caching is best-effort, not a gate', async () => {
    /** Real end-to-end verification found this: microchip.com sits behind
     * Akamai bot protection that rejects any plain HTTP client, so a
     * correctly-identified real part must still be confirmable even when
     * its datasheet can't be auto-cached. */
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85',
        manufacturer: 'Microchip',
        package: 'DIP-8',
        datasheet_url: 'https://www.microchip.com/en-us/product/ATtiny85',
        confidence: 'high',
        rationale: 'Exact match.',
      },
    ])
    cacheDatasheetMock.mockRejectedValueOnce(new Error('Datasheet fetch for \'ATtiny85\' failed: HTTP Error 403: Forbidden'))

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')
    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    fireEvent.click(screen.getByRole('button', { name: 'This one' }))

    await waitFor(() => screen.getByText(/Confirmed: ATtiny85/))
    screen.getByText(/Datasheet fetch for 'ATtiny85' failed/)
    expect(screen.queryByRole('button', { name: 'Copy local path' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Open datasheet externally' }))
    expect(openMock).toHaveBeenCalledWith('https://www.microchip.com/en-us/product/ATtiny85')
  })

  it('real bug fix: a confirmed candidate survives being re-rendered with the same projectName', async () => {
    // This is the exact real bug the user reported: switching tabs and
    // back used to unmount ComponentDiscovery entirely, losing a
    // confirmed candidate and everything PartDetail had done under it.
    // App.tsx now hides it with CSS instead of unmounting -- a
    // re-render with the same projectName (what a tab switch away and
    // back actually produces) must not reset anything.
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')

    const { rerender } = render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')
    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    fireEvent.click(screen.getByRole('button', { name: 'This one' }))
    await waitFor(() => screen.getByText(/Confirmed: ATtiny85/))

    rerender(<ComponentDiscovery projectName="test-project" />)

    screen.getByText(/Confirmed: ATtiny85/)
    screen.getByText('PartDetail stub for ATtiny85')
  })

  it('switching to a different real project resets the previous project\'s confirmed candidate', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])
    cacheDatasheetMock.mockResolvedValueOnce('/real/library/datasheets/ATtiny85.pdf')

    const { rerender } = render(<ComponentDiscovery projectName="project-a" />)
    search('atiny85')
    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    fireEvent.click(screen.getByRole('button', { name: 'This one' }))
    await waitFor(() => screen.getByText(/Confirmed: ATtiny85/))

    rerender(<ComponentDiscovery projectName="project-b" />)

    expect(screen.queryByText(/Confirmed: ATtiny85/)).toBeNull()
    screen.getByPlaceholderText(/search for a part/)
  })

  it('CTX-306.3: a candidate already saved to the library gets an "Already in your library" badge', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])
    listPartsMock.mockResolvedValueOnce(['ATtiny85'])

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')

    await waitFor(() => screen.getByText('Already in your library'))
    expect(listPartsMock).toHaveBeenCalled()
  })

  it('CTX-306.3: a genuinely new candidate gets no badge', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])
    listPartsMock.mockResolvedValueOnce(['SomeOtherPart'])

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')

    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    expect(screen.queryByText('Already in your library')).toBeNull()
  })

  it('CTX-306.3: a listParts failure is silent -- no badge, but results still render', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])
    listPartsMock.mockRejectedValueOnce(new Error('boom'))

    render(<ComponentDiscovery projectName="test-project" />)
    search('atiny85')

    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    expect(screen.queryByText('Already in your library')).toBeNull()
  })
})
