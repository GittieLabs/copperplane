import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const runReviewMock = vi.fn()
const loadStoredReviewMock = vi.fn()
const isOpenableSourceMock = vi.fn()
const openSourceMock = vi.fn()
const sourceChipLabelMock = vi.fn()

vi.mock('../lib/chat', () => ({
  runReview: (...args: unknown[]) => runReviewMock(...args),
  loadStoredReview: (...args: unknown[]) => loadStoredReviewMock(...args),
}))

// CTX-319.2: openSource's own real resolution logic has its own
// dedicated test file (lib/sourceRefs.test.ts) -- stubbed here,
// matching this codebase's own established convention (AgentChat
// mocking loadPart/cacheDatasheet directly before this module existed),
// so ReviewPanel's tests stay focused on whether it wires clicks/
// disabled-state correctly, not on re-verifying resolution internals.
vi.mock('../lib/sourceRefs', () => ({
  isOpenableSource: (...args: unknown[]) => isOpenableSourceMock(...args),
  openSource: (...args: unknown[]) => openSourceMock(...args),
  sourceChipLabel: (...args: unknown[]) => sourceChipLabelMock(...args),
}))

const { ReviewPanel } = await import('./ReviewPanel')

beforeEach(() => {
  runReviewMock.mockReset()
  // SPEC-339: the panel asks for a kept review on mount. "Nothing kept" is the
  // default here so every pre-existing test still describes a fresh area.
  loadStoredReviewMock.mockReset().mockResolvedValue(null)
  isOpenableSourceMock.mockReset().mockReturnValue(false)
  openSourceMock.mockReset()
  sourceChipLabelMock.mockReset().mockImplementation((ref: { kind: string }) => `Source: ${ref.kind}`)
})

describe('ReviewPanel', () => {
  it('TEST-001: Run Review calls runReview with the real scope/scopeId/area/projectName and shows a real in-progress state', async () => {
    runReviewMock.mockImplementation(() => new Promise(() => {}))

    render(
      <ReviewPanel area="components" scope="part" scopeId="ATtiny85" title="Review this part" projectName="weather-pcb" />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))

    expect(runReviewMock).toHaveBeenCalledWith('part', 'ATtiny85', 'components', 'weather-pcb')
    await waitFor(() => expect((screen.getByRole('button', { name: 'Reviewing…' }) as HTMLButtonElement).disabled).toBe(true))
  })

  it('TEST-002: a real finding renders its severity, title, and detail', async () => {
    runReviewMock.mockResolvedValueOnce([{
      severity: 'warning', title: 'No project intent set',
      detail: 'Agents will answer generically until one is added.',
      sources: [], general_practice: true, area: 'overview',
    }])

    render(<ReviewPanel area="overview" scope="project" scopeId="weather-pcb:overview" title="Review this project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))

    await waitFor(() => screen.getByText('No project intent set'))
    screen.getByText('Agents will answer generically until one is added.')
    screen.getByText('Warning')
    screen.getByText(/Includes general engineering practice/)
    screen.getByText('1 finding')
  })

  it('TEST-003: an empty findings list shows an honest "reviewed, nothing worth flagging", not silence or an error', async () => {
    runReviewMock.mockResolvedValueOnce([])

    render(<ReviewPanel area="overview" scope="project" scopeId="weather-pcb:overview" title="Review this project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))

    await waitFor(() => screen.getByText('Reviewed — nothing worth flagging.'))
  })

  it('TEST-004: multiple findings all render, each with its own severity', async () => {
    runReviewMock.mockResolvedValueOnce([
      { severity: 'warning', title: 'A', detail: 'a detail', sources: [], general_practice: false, area: 'pcb' },
      { severity: 'suggestion', title: 'B', detail: 'b detail', sources: [], general_practice: false, area: 'pcb' },
      { severity: 'info', title: 'C', detail: 'c detail', sources: [], general_practice: false, area: 'pcb' },
    ])

    render(<ReviewPanel area="pcb" scope="project" scopeId="weather-pcb:pcb" title="Review the board" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))

    await waitFor(() => screen.getByText('3 findings'))
    screen.getByText('A')
    screen.getByText('B')
    screen.getByText('C')
  })

  it('TEST-005: a genuine review failure shows the real error, not silence', async () => {
    runReviewMock.mockRejectedValueOnce(new Error('Lost connection to the daemon.'))

    render(<ReviewPanel area="overview" scope="project" scopeId="weather-pcb:overview" title="Review this project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))

    await waitFor(() => screen.getByText('Lost connection to the daemon.'))
  })

  it('TEST-006: Dismiss clears the findings without re-running the review', async () => {
    runReviewMock.mockResolvedValueOnce([
      { severity: 'info', title: 'A', detail: 'a detail', sources: [], general_practice: false, area: 'overview' },
    ])

    render(<ReviewPanel area="overview" scope="project" scopeId="weather-pcb:overview" title="Review this project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))
    await waitFor(() => screen.getByText('A'))

    fireEvent.click(screen.getByText('Dismiss'))

    expect(screen.queryByText('A')).toBeNull()
    expect(runReviewMock).toHaveBeenCalledTimes(1)
  })

  it('TEST-007: a different scope gets fresh state, because the caller keys it', async () => {
    /* CTX-339.1 moved this guarantee from an effect inside the component to a
       `key` at every mount site. The effect version reset state AFTER the
       commit, which CTX-318.7 showed silently undoes a click landing in the
       same window -- and it now has a second job, loading a kept review, that
       must not be a reset at all.

       Rendering with a key is what a real caller does; TEST-007b asserts every
       caller actually does it, because this contract is only as good as the
       mount sites honouring it. */
    runReviewMock.mockResolvedValueOnce([
      { severity: 'info', title: 'A', detail: 'a detail', sources: [], general_practice: false, area: 'components' },
    ])
    const { rerender } = render(
      <ReviewPanel key="ATtiny85" area="components" scope="part" scopeId="ATtiny85" title="Review this part" />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))
    await waitFor(() => screen.getByText('A'))

    rerender(
      <ReviewPanel key="ESP32-S3" area="components" scope="part" scopeId="ESP32-S3" title="Review this part" />,
    )

    expect(screen.queryByText('A')).toBeNull()
  })

  it('TEST-008: an openable source chip calls the shared openSource, a non-openable one renders disabled', async () => {
    isOpenableSourceMock.mockImplementation((ref: { kind: string }) => ref.kind === 'datasheet_page')
    runReviewMock.mockResolvedValueOnce([{
      severity: 'info', title: 'A', detail: 'a detail', area: 'components', general_practice: false,
      sources: [
        { kind: 'datasheet_page', part_id: 'ATtiny85', page: 4 },
        { kind: 'project_intent' },
      ],
    }])

    render(<ReviewPanel area="components" scope="part" scopeId="ATtiny85" title="Review this part" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))
    await waitFor(() => screen.getByText('A'))

    const openable = screen.getByRole('button', { name: 'Source: datasheet_page' }) as HTMLButtonElement
    const notOpenable = screen.getByRole('button', { name: 'Source: project_intent' }) as HTMLButtonElement
    expect(notOpenable.disabled).toBe(true)

    fireEvent.click(openable)

    await waitFor(() => expect(openSourceMock).toHaveBeenCalledWith({ kind: 'datasheet_page', part_id: 'ATtiny85', page: 4 }))
  })
})

describe('ReviewPanel: CTX-319.6 menuCommand wiring', () => {
  it('TEST-009: a matching run_review menuCommand runs the real review, same as clicking the button', async () => {
    runReviewMock.mockResolvedValueOnce([])
    const props = {
      area: 'schematic' as const,
      scope: 'project' as const,
      scopeId: 'weather-pcb:schematic',
      title: 'Review the schematic',
    }
    const { rerender } = render(<ReviewPanel {...props} menuCommand={null} />)

    rerender(
      <ReviewPanel {...props} menuCommand={{ area: 'schematic', command: 'run_review', nonce: 1 }} />,
    )

    await waitFor(() => expect(runReviewMock).toHaveBeenCalledWith('project', 'weather-pcb:schematic', 'schematic', undefined))
  })

  it('TEST-009b: mounting with a menuCommand already set does NOT run a review', async () => {
    /* The reason this component is keyed now is that a remount would otherwise
       replay whatever menuCommand was last set -- so switching project would
       fire a real, billed LLM call nobody asked for. SPEC-339 is explicit that
       nothing re-runs on its own. */
    render(
      <ReviewPanel
        area="schematic"
        scope="project"
        scopeId="weather-pcb:schematic"
        title="Review the schematic"
        menuCommand={{ area: 'schematic', command: 'run_review', nonce: 7 }}
      />,
    )

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(runReviewMock).not.toHaveBeenCalled()
  })

  it('TEST-010: a menuCommand for a different area is ignored', async () => {
    render(
      <ReviewPanel
        area="schematic"
        scope="project"
        scopeId="weather-pcb:schematic"
        title="Review the schematic"
        menuCommand={{ area: 'pcb', command: 'run_review', nonce: 0 }}
      />,
    )

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(runReviewMock).not.toHaveBeenCalled()
  })

  it('TEST-011: the same command fired twice (nonce bumped) re-triggers the review both times', async () => {
    runReviewMock.mockResolvedValue([])
    const props = {
      area: 'pcb' as const,
      scope: 'project' as const,
      scopeId: 'weather-pcb:pcb',
      title: 'Review the board',
    }
    const { rerender } = render(<ReviewPanel {...props} menuCommand={null} />)

    rerender(<ReviewPanel {...props} menuCommand={{ area: 'pcb', command: 'run_review', nonce: 1 }} />)
    await waitFor(() => expect(runReviewMock).toHaveBeenCalledTimes(1))

    rerender(<ReviewPanel {...props} menuCommand={{ area: 'pcb', command: 'run_review', nonce: 2 }} />)
    await waitFor(() => expect(runReviewMock).toHaveBeenCalledTimes(2))
  })
})

describe('ReviewPanel: a review that already ran (SPEC-339)', () => {
  const KEPT = {
    findings: [{
      severity: 'warning' as const, title: 'Kept finding', detail: 'from last time',
      sources: [], general_practice: false, area: 'schematic', origin: 'kicad' as const,
    }],
    ran_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    stale_reason: null as null,
    source: { path: '/p/Blink.kicad_sch' },
  }

  function renderPanel() {
    render(
      <ReviewPanel area="schematic" scope="project" scopeId="p:schematic" title="Review the schematic" />,
    )
  }

  it('TEST-201: shows what the last review found, without re-running it', async () => {
    /* The whole point. Opening Settings and coming back used to destroy the
       review and cost another ERC run plus another real LLM call for a file
       nobody had touched. */
    loadStoredReviewMock.mockResolvedValueOnce(KEPT)
    renderPanel()

    await waitFor(() => screen.getByText('Kept finding'))
    expect(runReviewMock).not.toHaveBeenCalled()
  })

  it('TEST-202: says when it ran', async () => {
    loadStoredReviewMock.mockResolvedValueOnce(KEPT)
    renderPanel()

    await waitFor(() => screen.getByText('Reviewed 5 minutes ago.'))
  })

  it('TEST-203: a changed file is named, with when the review ran', async () => {
    loadStoredReviewMock.mockResolvedValueOnce({ ...KEPT, stale_reason: 'source_changed' })
    renderPanel()

    const note = await screen.findByText(/Blink\.kicad_sch has been saved since this review ran/)
    expect(note.textContent).toContain('5 minutes ago')
  })

  it('TEST-204: never tells the user to re-run -- that costs their money', async () => {
    loadStoredReviewMock.mockResolvedValueOnce({ ...KEPT, stale_reason: 'source_changed' })
    renderPanel()

    await screen.findByText(/has been saved since this review ran/)
    expect(screen.queryByText(/re-run/i)).toBeNull()
  })

  it('TEST-205: a checks-changed review says nothing in the design moved', async () => {
    /* Nothing on disk changed; the app simply knows more checks than it did.
       Saying "your file changed" there would be a lie the user cannot verify. */
    loadStoredReviewMock.mockResolvedValueOnce({ ...KEPT, stale_reason: 'checks_changed' })
    renderPanel()

    await screen.findByText(/before some of the checks this app makes existed/)
  })

  it('TEST-206: an area never reviewed shows no findings and no timestamp', async () => {
    /* "Nothing here" and "here is what we found, and the file has moved" are
       different sentences. The old UI said neither. */
    loadStoredReviewMock.mockResolvedValueOnce(null)
    renderPanel()

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByText(/Reviewed/)).toBeNull()
    expect(screen.queryByText(/finding/)).toBeNull()
  })

  it('TEST-207: a kept review that cannot be read is not shown as an error', async () => {
    loadStoredReviewMock.mockRejectedValueOnce(new Error('daemon is not up'))
    renderPanel()

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByText('daemon is not up')).toBeNull()
    screen.getByRole('button', { name: 'Run Review' })
  })
})

describe('ReviewPanel: findings this app found itself (SPEC-113)', () => {
  const OURS = {
    severity: 'warning' as const,
    title: "LED's footprint has more pads than its symbol has pins (D1)",
    detail: 'Device:LED has 2 pins; LED_THT:LED_D5.0mm-4_RGB has 4 numbered pads.',
    sources: [],
    general_practice: false,
    area: 'schematic',
    origin: 'copperplane' as const,
  }
  const KICAD = {
    severity: 'warning' as const,
    title: "Arduino's power input (VIN) has nothing feeding it",
    detail: 'ERC found that pin 8 on A1 is not driven.',
    sources: [],
    general_practice: false,
    area: 'schematic',
    origin: 'kicad' as const,
  }

  async function renderWith(findings: unknown[]) {
    runReviewMock.mockResolvedValueOnce(findings)
    render(<ReviewPanel area="schematic" scope="project" scopeId="p:schematic" title="Review the schematic" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))
    await waitFor(() => screen.getByText(/finding/))
  }

  it('TEST-101: says above the list how many no KiCad check reports', async () => {
    await renderWith([KICAD, OURS])

    screen.getByText('1 of these was found by Copperplane. ERC and DRC do not report it.')
  })

  it('TEST-102: counts them, and pluralises honestly', async () => {
    await renderWith([KICAD, OURS, { ...OURS, title: 'SW1' }])

    screen.getByText('2 of these were found by Copperplane. ERC and DRC do not report them.')
  })

  it('TEST-103: says nothing at all when every finding came from KiCad', async () => {
    await renderWith([KICAD])

    expect(screen.queryByText(/found by Copperplane/)).toBeNull()
  })

  it('TEST-104: marks the finding itself, not only the summary', async () => {
    /* The maintainer's report was that the distinction lived in one line of
       prose halfway down an explanation. A reader scanning the list has to be
       able to see it without reading. */
    await renderWith([KICAD, OURS])

    expect(screen.getAllByText('Not reported by ERC or DRC')).toHaveLength(1)
  })

  it('TEST-105: an unattributed finding is not claimed as ours', async () => {
    /* `origin` is null when the model cited nothing identifiable. That is a
       third state and must not be rendered as either checker's work. */
    await renderWith([{ ...KICAD, origin: null }])

    expect(screen.queryByText(/found by Copperplane/)).toBeNull()
    expect(screen.queryByText('Not reported by ERC or DRC')).toBeNull()
  })
})

describe('ReviewPanel: connected to the check above it (SPEC-340)', () => {
  const OURS = {
    severity: 'warning' as const,
    title: "SW1's symbol and footprint disagree about how many pins this part has",
    detail: 'Switch:SW_Push has 2; Button_Switch_THT:KSA_Tactile_SPST has 5 numbered pads.',
    sources: [],
    general_practice: false,
    area: 'pcb',
    origin: 'copperplane' as const,
  }

  async function renderWith(siblingCheck: unknown) {
    runReviewMock.mockResolvedValueOnce([OURS])
    render(
      <ReviewPanel
        area="pcb"
        scope="project"
        scopeId="p:pcb"
        title="Review the board"
        siblingCheck={siblingCheck as never}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))
    await waitFor(() => screen.getByText(/finding/))
  }

  it('names what the board check reported, so its own count is not the whole story', async () => {
    // Reported by a real click-through: this panel said "2 findings" on a board
    // whose DRC also had four errors and a missing connection, and neither card
    // mentioned the other.
    await renderWith({ label: 'The board check (DRC)', count: 5, where: 'Board (DRC) above' })
    expect(document.body.textContent).toContain('separately reports 5 problems')
    expect(document.body.textContent).toContain('Board (DRC) above')
    expect(document.body.textContent).toContain('does not repeat them')
  })

  it('says a check has not run rather than implying it found nothing', async () => {
    // "We could not check" and "we checked and it is clean" must never look the
    // same -- the rule _check_status_note already follows on the daemon side.
    await renderWith({ label: 'The board check (DRC)', count: null, where: 'Board (DRC) above' })
    expect(document.body.textContent).toContain('has not been run yet')
    expect(document.body.textContent).not.toContain('separately reports')
  })

  it('says nothing extra when there is no sibling check to point at', async () => {
    await renderWith(undefined)
    expect(document.body.textContent).not.toContain('separately reports')
    expect(document.body.textContent).not.toContain('has not been run yet')
  })
})
