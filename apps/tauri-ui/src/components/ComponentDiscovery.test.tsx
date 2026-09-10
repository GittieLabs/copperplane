import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const searchComponentsMock = vi.fn()
const cacheDatasheetMock = vi.fn()
const writeTextMock = vi.fn()
const openMock = vi.fn()
const listPartsMock = vi.fn()
const loadPartMock = vi.fn()
const searchFootprintsMock = vi.fn()

vi.mock('../lib/components', () => ({
  searchComponents: (...args: unknown[]) => searchComponentsMock(...args),
  cacheDatasheet: (...args: unknown[]) => cacheDatasheetMock(...args),
}))

vi.mock('../lib/footprints', () => ({
  searchFootprints: (...args: unknown[]) => searchFootprintsMock(...args),
}))

vi.mock('../lib/library', () => ({
  listParts: (...args: unknown[]) => listPartsMock(...args),
}))

vi.mock('../lib/partDetail', () => ({
  loadPart: (...args: unknown[]) => loadPartMock(...args),
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
  PartDetail: ({
    candidate,
    initialPart,
    currentProject,
  }: {
    candidate?: { part_number: string }
    initialPart?: { part_id: string }
    currentProject?: { name: string } | null
  }) => (
    <p>
      PartDetail stub for {candidate?.part_number ?? initialPart?.part_id}
      {currentProject && ` (project: ${currentProject.name})`}
    </p>
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
  loadPartMock.mockReset()
  searchFootprintsMock.mockReset().mockResolvedValue([])
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

    /* CTX-306.8: the link no longer hands the raw URL to the OS. It fetches
       first and opens the LOCAL cached path, because `datasheet_url` is a model
       guess -- the prompt asks for a "best real guess" -- and opening it blind
       drops the user into a browser error page with nothing in the app saying
       why. PartDetail.handleOpenCitation has always worked this way. */
    cacheDatasheetMock.mockResolvedValueOnce('/cache/ATtiny85.pdf')
    fireEvent.click(screen.getByRole('button', { name: /view datasheet/ }))
    await waitFor(() =>
      expect(cacheDatasheetMock).toHaveBeenCalledWith('ATtiny85', 'https://example.com/attiny85.pdf'),
    )
    await waitFor(() => expect(openMock).toHaveBeenCalledWith('/cache/ATtiny85.pdf'))
  })

  it('says the datasheet URL is unverified before anything has fetched it', async () => {
    // `confidence` describes the part identity, not the URL -- but sitting
    // directly above this link it reads as covering both.
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'CR2032', manufacturer: 'Panasonic', package: 'Coin Cell 20.0mm x 3.2mm',
        datasheet_url: 'https://industrial.panasonic.com/cdbs/www-data/pdf/AAA4000/AAA4000C417.pdf',
        confidence: 'high', rationale: 'Exact match.',
      },
    ])
    render(<ComponentDiscovery projectName="test-project" />)
    search('Cr2032')

    await waitFor(() => screen.getByText('CR2032', { exact: false }))
    screen.getByRole('button', { name: 'view datasheet (unverified)' })
  })

  it('reports a dead datasheet URL in the app, and never opens it', async () => {
    /* The real report: a CR2032 search produced a Panasonic URL that 404s.
       Clicking it opened a browser error page and the app said nothing. Note
       that 404 returns Content-Type: application/pdf with Content-Length: 0 --
       a content-type check passes it, only the status catches it. */
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'CR2032', manufacturer: 'Panasonic', package: 'Coin Cell 20.0mm x 3.2mm',
        datasheet_url: 'https://industrial.panasonic.com/cdbs/www-data/pdf/AAA4000/AAA4000C417.pdf',
        confidence: 'high', rationale: 'Exact match.',
      },
    ])
    render(<ComponentDiscovery projectName="test-project" />)
    search('Cr2032')

    await waitFor(() => screen.getByText('CR2032', { exact: false }))
    cacheDatasheetMock.mockRejectedValueOnce(
      new Error("Datasheet fetch for 'CR2032' failed: HTTP Error 404: Not Found"),
    )
    fireEvent.click(screen.getByRole('button', { name: /view datasheet/ }))

    // CTX-306.8's two real guarantees, unchanged by SPEC-212's rework of the
    // wording: the failure surfaces IN the app, and the invented URL is never
    // handed to the browser. The "best guess" phrasing was replaced by an
    // explanation of the actual cause plus a working search link -- see the
    // SPEC-212 block at the end of this file.
    expect(await screen.findByText(/HTTP Error 404/)).toBeTruthy()
    expect(screen.getByText(/one document per family rather than per part/)).toBeTruthy()
    expect(openMock).not.toHaveBeenCalled()
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

  it('answers a footprint-shaped query from KiCad’s own libraries', async () => {
    // SPEC-334 §2. The two namespaces were never connected, so this query
    // went to an LLM that guessed at a manufacturer part number. Reported:
    // "I have a hunch that the component I searched for ... is a kicad only
    // reference name and would not be searchable with our component search."
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'Connector_PinHeader_2.54mm', footprint_name: 'PinHeader_1x04_P2.54mm_Vertical', source: 'kicad_library' },
    ])
    searchComponentsMock.mockResolvedValueOnce([])

    render(<ComponentDiscovery projectName="test-project" />)
    search('PinHeader_1x04_P2.54mm_Vertical')

    expect(await screen.findByText('PinHeader_1x04_P2.54mm_Vertical')).toBeTruthy()
    expect(screen.getByText(/Connector_PinHeader_2.54mm/)).toBeTruthy()
    // Said plainly, because a footprint is not something you can order.
    expect(screen.getByText(/not parts/i)).toBeTruthy()
  })

  it('searches KiCad’s libraries on every query, rather than classifying first', async () => {
    // Deliberately not a router: a classifier is a new thing that can be
    // wrong, and silently so. This search is free, instant and cannot
    // hallucinate, so it runs always and an ambiguous query gets both
    // answers instead of a coin flip.
    searchFootprintsMock.mockResolvedValueOnce([])
    searchComponentsMock.mockResolvedValueOnce([
      { part_number: 'NE555P', manufacturer: 'TI', package: 'DIP-8', datasheet_url: 'https://e.invalid/d.pdf', confidence: 'high', rationale: 'r' },
    ])

    render(<ComponentDiscovery projectName="test-project" />)
    search('NE555P')

    await waitFor(() => expect(searchFootprintsMock).toHaveBeenCalledWith('NE555P'))
    expect(searchComponentsMock).toHaveBeenCalledWith('NE555P')
  })

  it('still shows KiCad footprint hits when the part search fails outright', async () => {
    // The case that used to be worst: an expensive call that returns a
    // confident guess, or nothing. The free answer must survive it.
    searchFootprintsMock.mockResolvedValueOnce([
      { library: 'Package_DIP', footprint_name: 'DIP-8_W7.62mm', source: 'kicad_library' },
    ])
    searchComponentsMock.mockRejectedValueOnce(new Error('provider is unreachable'))

    render(<ComponentDiscovery projectName="test-project" />)
    search('DIP-8_W7.62mm')

    expect(await screen.findByText('DIP-8_W7.62mm')).toBeTruthy()
    expect(screen.getByText('provider is unreachable')).toBeTruthy()
  })

  it('a missing footprint library never blocks the search the user asked for', async () => {
    searchFootprintsMock.mockRejectedValueOnce(new Error('no fp-lib-table'))
    searchComponentsMock.mockResolvedValueOnce([
      { part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', datasheet_url: 'https://e.invalid/d.pdf', confidence: 'high', rationale: 'r' },
    ])

    render(<ComponentDiscovery projectName="test-project" />)
    search('ATtiny85')

    expect(await screen.findByText('ATtiny85')).toBeTruthy()
    expect(screen.queryByText(/no fp-lib-table/)).toBeNull()
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

  it('CTX-304.3: forwards currentProject through to PartDetail unchanged', async () => {
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
        datasheet_url: 'https://example.com/attiny85.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])
    cacheDatasheetMock.mockResolvedValueOnce('/storage/library/datasheets/ATtiny85.pdf')

    render(<ComponentDiscovery projectName="test-project" currentProject={{ name: 'weather-pcb' }} />)
    search('atiny85')
    await waitFor(() => screen.getByRole('button', { name: 'This one' }))
    fireEvent.click(screen.getByRole('button', { name: 'This one' }))

    await waitFor(() => screen.getByText('PartDetail stub for ATtiny85 (project: weather-pcb)'))
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

  it('CTX-306.4: shows a real, persistent Project Parts list from currentProject.parts', async () => {
    loadPartMock.mockImplementation((partId: string) =>
      Promise.resolve({ part_id: partId, manufacturer: 'Microchip', package: 'DIP-8' }),
    )

    render(
      <ComponentDiscovery
        projectName="test-project"
        currentProject={{ name: 'test-project', parts: ['ATtiny85', 'ESP32-S3'] }}
      />,
    )

    await waitFor(() => screen.getByText('Project Parts'))
    await waitFor(() => screen.getByText('ATtiny85', { exact: false }))
    screen.getByText('ESP32-S3', { exact: false })
    expect(loadPartMock).toHaveBeenCalledWith('ATtiny85')
    expect(loadPartMock).toHaveBeenCalledWith('ESP32-S3')
  })

  it('CTX-306.4: a part referenced by the project but no longer loadable is silently omitted, not an error', async () => {
    loadPartMock.mockImplementation((partId: string) =>
      partId === 'ATtiny85'
        ? Promise.resolve({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8' })
        : Promise.reject(new Error('No Part found.')),
    )

    render(
      <ComponentDiscovery
        projectName="test-project"
        currentProject={{ name: 'test-project', parts: ['ATtiny85', 'deleted-part'] }}
      />,
    )

    await waitFor(() => screen.getByText('ATtiny85', { exact: false }))
    expect(screen.queryByText('deleted-part', { exact: false })).toBeNull()
  })

  it('CTX-306.4: no Project Parts section at all when the project has no real parts yet', async () => {
    render(<ComponentDiscovery projectName="test-project" currentProject={{ name: 'test-project', parts: [] }} />)

    expect(screen.queryByText('Project Parts')).toBeNull()
    expect(loadPartMock).not.toHaveBeenCalled()
  })

  it('CTX-306.4: opening a project part shows its detail with a real back-navigation to the list', async () => {
    loadPartMock.mockResolvedValue({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8' })

    render(
      <ComponentDiscovery
        projectName="test-project"
        currentProject={{ name: 'test-project', parts: ['ATtiny85'] }}
      />,
    )

    await waitFor(() => screen.getByRole('button', { name: 'Open' }))
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))

    // CTX-308.11: real bug found via live testing -- this assertion used to
    // read 'PartDetail stub for ATtiny85' with no project suffix, because
    // currentProject was never actually forwarded to PartDetail here (only
    // the `confirmed`-candidate render site below did). That silently
    // hid every currentProject-gated feature (CTX-308.9's per-project
    // footprint override among them) from a Part reopened via the Project
    // Parts list -- the most common way to revisit an already-saved part.
    await waitFor(() => screen.getByText('PartDetail stub for ATtiny85 (project: test-project)'))
    screen.getByRole('button', { name: '← Back to project parts' })

    fireEvent.click(screen.getByRole('button', { name: '← Back to project parts' }))

    await waitFor(() => screen.getByText('Project Parts'))
    expect(screen.queryByText('PartDetail stub for ATtiny85 (project: test-project)')).toBeNull()
  })

  it('CTX-306.5: real bug -- a "← Back to project parts" link on search results clears the stale search so the Project Parts list comes back', async () => {
    loadPartMock.mockResolvedValue({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8' })
    searchComponentsMock.mockResolvedValueOnce([
      {
        part_number: 'ESP32-S3', manufacturer: 'Espressif', package: 'QFN-56',
        datasheet_url: 'https://example.com/esp32.pdf', confidence: 'high', rationale: 'Exact match.',
      },
    ])

    render(
      <ComponentDiscovery
        projectName="test-project"
        currentProject={{ name: 'test-project', parts: ['ATtiny85'] }}
      />,
    )

    await waitFor(() => screen.getByText('Project Parts'))
    search('esp32')
    await waitFor(() => screen.getByText('Did you mean:'))
    expect(screen.queryByText('Project Parts')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '← Back to project parts' }))

    await waitFor(() => screen.getByText('Project Parts'))
    expect(screen.queryByText('Did you mean:')).toBeNull()
  })

})

describe('ComponentDiscovery: CTX-318.6 Generate directly from a part number', () => {
  it('the fallback is collapsed by default, next to search', async () => {
    render(<ComponentDiscovery projectName="test-project" />)

    screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" })
    expect(screen.queryByPlaceholderText(/exact part number/)).toBeNull()
  })

  it('opens a real input, and confirming routes straight to PartDetail with no search or datasheet cache involved', async () => {
    render(<ComponentDiscovery projectName="test-project" />)

    fireEvent.click(
      screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" }),
    )
    fireEvent.change(screen.getByPlaceholderText(/exact part number/), { target: { value: 'ATtiny85' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }))

    await waitFor(() => screen.getByText(/Confirmed: ATtiny85/))
    screen.getByText('PartDetail stub for ATtiny85')
    expect(searchComponentsMock).not.toHaveBeenCalled()
    expect(cacheDatasheetMock).not.toHaveBeenCalled()
  })

  it('an honest "no datasheet known" message, distinct from a real cache failure', async () => {
    render(<ComponentDiscovery projectName="test-project" />)

    fireEvent.click(
      screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" }),
    )
    fireEvent.change(screen.getByPlaceholderText(/exact part number/), { target: { value: 'ATtiny85' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }))

    await waitFor(() => screen.getByText(/No datasheet known for this part/))
    expect(screen.queryByText(/couldn't be cached automatically/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Open datasheet externally' })).toBeNull()
  })

  it('Generate is disabled for an empty part number, and Cancel discards the draft', async () => {
    render(<ComponentDiscovery projectName="test-project" />)

    fireEvent.click(
      screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" }),
    )
    expect((screen.getByRole('button', { name: 'Generate' }) as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(screen.getByPlaceholderText(/exact part number/), { target: { value: 'ATtiny85' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByPlaceholderText(/exact part number/)).toBeNull()
    screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" })
  })

  it('switching to a different real project resets any in-progress draft', async () => {
    const { rerender } = render(<ComponentDiscovery projectName="project-a" />)
    fireEvent.click(
      screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" }),
    )
    fireEvent.change(screen.getByPlaceholderText(/exact part number/), { target: { value: 'Half-typed' } })

    rerender(<ComponentDiscovery projectName="project-b" />)

    expect(screen.queryByPlaceholderText(/exact part number/)).toBeNull()
    screen.getByRole('button', { name: "Can't find it via search? Generate directly from a part number…" })
  })
})

describe('ComponentDiscovery: SPEC-328 carrying a suggestion over', () => {
  it('runs a search carried over from the Overview tab, not just filling the box', async () => {
    /* SPEC-328 §5: "Each entry can be carried straight into the existing part
     * search." A user who clicked "Search for this" has already asked --
     * making them click Search again would be asking twice. */
    searchComponentsMock.mockResolvedValue([
      { part_number: 'DS3231', manufacturer: 'Maxim', package: 'SOIC-16',
        datasheet_url: 'https://e.invalid/d.pdf', confidence: 'high', rationale: 'r' },
    ])

    render(
      <ComponentDiscovery projectName="test-project" searchSeed={{ term: 'RTC module I2C', at: 1 }} />,
    )

    await waitFor(() => expect(searchComponentsMock).toHaveBeenCalledWith('RTC module I2C'))
    expect(await screen.findByText('DS3231')).toBeTruthy()
  })

  it('re-runs when the same category is carried over twice', async () => {
    /* The seed carries a timestamp, not just a term. A user going back to
     * Overview and clicking the same suggestion again must get a search, not
     * a component that decides nothing changed. */
    searchComponentsMock.mockResolvedValue([])

    const { rerender } = render(
      <ComponentDiscovery projectName="test-project" searchSeed={{ term: 'RTC module I2C', at: 1 }} />,
    )
    await waitFor(() => expect(searchComponentsMock).toHaveBeenCalledTimes(1))

    rerender(
      <ComponentDiscovery projectName="test-project" searchSeed={{ term: 'RTC module I2C', at: 2 }} />,
    )
    await waitFor(() => expect(searchComponentsMock).toHaveBeenCalledTimes(2))
  })

  it('does nothing when no suggestion was carried over', async () => {
    render(<ComponentDiscovery projectName="test-project" />)

    // No seed, no search. Asserted directly rather than by waiting on some
    // other mock -- what this test is about is that nothing ran.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(searchComponentsMock).not.toHaveBeenCalled()
  })
})

describe('ComponentDiscovery: SPEC-212 a datasheet that cannot resolve', () => {
  const CANDIDATE = {
    part_number: 'CFR-25JB-52-220R', manufacturer: 'Yageo', package: 'Axial (THT)',
    datasheet_url: 'https://yageo.invalid/CFR-25JB-52-220R.pdf',
    confidence: 'medium' as const, rationale: 'a 220R carbon film resistor',
  }

  it('replaces the dead link with a live one rather than a wall of red', async () => {
    /* Reported from the running app: "part of this seems to work" -- every
     * result carried a failed datasheet fetch. SPEC-212 measured why: 3 of 3
     * resolve for an IC and 0 of 3 for passives, because a passive's
     * datasheet is a family document with no per-part URL to guess. Offering
     * the same button again invites a retry of something that cannot work. */
    searchComponentsMock.mockResolvedValue([CANDIDATE])
    cacheDatasheetMock.mockRejectedValue(new Error('HTTP Error 404: Not Found'))

    render(<ComponentDiscovery projectName="test-project" />)
    search('220 ohm resistor')
    await screen.findByText('CFR-25JB-52-220R')

    fireEvent.click(screen.getByRole('button', { name: /view datasheet/ }))

    const fallback = await screen.findByRole('button', { name: /search the web for this datasheet/ })
    expect(fallback).toBeTruthy()
    // Says why, in terms of the actual cause, not a stack trace.
    expect(screen.getByText(/one document per family rather than per part/)).toBeTruthy()
  })

  it('opens a neutral search carrying the part number and manufacturer', async () => {
    searchComponentsMock.mockResolvedValue([CANDIDATE])
    cacheDatasheetMock.mockRejectedValue(new Error('HTTP Error 404: Not Found'))

    render(<ComponentDiscovery projectName="test-project" />)
    search('220 ohm resistor')
    await screen.findByText('CFR-25JB-52-220R')
    fireEvent.click(screen.getByRole('button', { name: /view datasheet/ }))
    fireEvent.click(await screen.findByRole('button', { name: /search the web/ }))

    await waitFor(() => expect(openMock).toHaveBeenCalled())
    const url = decodeURIComponent(openMock.mock.calls.at(-1)![0] as string)
    expect(url).toContain('CFR-25JB-52-220R')
    expect(url).toContain('Yageo')
    expect(url).toContain('datasheet')
  })

  it('leaves a datasheet that does resolve completely alone', async () => {
    /* SPEC-212 §1: the guess works for ICs and costs nothing. This must not
     * become a worse experience for the case that was already fine. */
    searchComponentsMock.mockResolvedValue([
      { ...CANDIDATE, part_number: 'ATtiny85-20PU', manufacturer: 'Microchip' },
    ])
    cacheDatasheetMock.mockResolvedValue('/cache/ATtiny85-20PU.pdf')

    render(<ComponentDiscovery projectName="test-project" />)
    search('ATtiny85')
    await screen.findByText('ATtiny85-20PU')
    fireEvent.click(screen.getByRole('button', { name: /view datasheet/ }))

    await waitFor(() => expect(openMock).toHaveBeenCalledWith('/cache/ATtiny85-20PU.pdf'))
    expect(screen.queryByRole('button', { name: /search the web/ })).toBeNull()
    expect(screen.queryByText(/one document per family/)).toBeNull()
  })
})
