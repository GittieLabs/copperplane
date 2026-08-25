import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const runReviewMock = vi.fn()
const isOpenableSourceMock = vi.fn()
const openSourceMock = vi.fn()
const sourceChipLabelMock = vi.fn()

vi.mock('../lib/chat', () => ({
  runReview: (...args: unknown[]) => runReviewMock(...args),
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
    screen.getByText(/General engineering practice/)
    screen.getByText('1 finding')
  })

  it('TEST-003: an empty findings list shows an honest "nothing stood out", not silence or an error', async () => {
    runReviewMock.mockResolvedValueOnce([])

    render(<ReviewPanel area="overview" scope="project" scopeId="weather-pcb:overview" title="Review this project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))

    await waitFor(() => screen.getByText('Nothing stood out.'))
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

  it('TEST-007: switching scope/scopeId resets a stale prior review -- no leaking findings across parts/projects', async () => {
    runReviewMock.mockResolvedValueOnce([
      { severity: 'info', title: 'A', detail: 'a detail', sources: [], general_practice: false, area: 'components' },
    ])
    const { rerender } = render(
      <ReviewPanel area="components" scope="part" scopeId="ATtiny85" title="Review this part" />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Run Review' }))
    await waitFor(() => screen.getByText('A'))

    rerender(<ReviewPanel area="components" scope="part" scopeId="ESP32-S3" title="Review this part" />)

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

    render(
      <ReviewPanel
        area="schematic"
        scope="project"
        scopeId="weather-pcb:schematic"
        title="Review the schematic"
        menuCommand={{ area: 'schematic', command: 'run_review', nonce: 0 }}
      />,
    )

    await waitFor(() => expect(runReviewMock).toHaveBeenCalledWith('project', 'weather-pcb:schematic', 'schematic', undefined))
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
    const { rerender } = render(
      <ReviewPanel
        area="pcb"
        scope="project"
        scopeId="weather-pcb:pcb"
        title="Review the board"
        menuCommand={{ area: 'pcb', command: 'run_review', nonce: 0 }}
      />,
    )
    await waitFor(() => expect(runReviewMock).toHaveBeenCalledTimes(1))

    rerender(
      <ReviewPanel
        area="pcb"
        scope="project"
        scopeId="weather-pcb:pcb"
        title="Review the board"
        menuCommand={{ area: 'pcb', command: 'run_review', nonce: 1 }}
      />,
    )
    await waitFor(() => expect(runReviewMock).toHaveBeenCalledTimes(2))
  })
})
