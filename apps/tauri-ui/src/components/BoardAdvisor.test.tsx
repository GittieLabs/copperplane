import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const checkBoardMock = vi.fn()
const checkSchematicMock = vi.fn()
const pickSchematicFileMock = vi.fn()

vi.mock('../lib/boardAdvisor', () => ({
  checkBoard: (...args: unknown[]) => checkBoardMock(...args),
  checkSchematic: (...args: unknown[]) => checkSchematicMock(...args),
  pickSchematicFile: (...args: unknown[]) => pickSchematicFileMock(...args),
}))

const { BoardAdvisor } = await import('./BoardAdvisor')

const CLEAN_RESULT = { violations: [], summary: '', truncated_count: 0, source_path: '/real/board.kicad_pcb' }

const VIOLATION_RESULT = {
  violations: [
    {
      description: 'Board has malformed outline (no edges found on Edge.Cuts layer)',
      severity: 'error',
      type: 'invalid_outline',
      items: [],
      explanation: 'The board has no outline drawn on the Edge.Cuts layer.',
      suggested_fix: 'Draw a closed shape on the Edge.Cuts layer around your board.',
    },
  ],
  summary: 'One error found.',
  truncated_count: 0,
  source_path: '/real/board.kicad_pcb',
}

// CTX-309.3: checkBoard's real, structured envelope always carries a
// status field now -- these two mirror the same shapes above, tagged.
const CLEAN_BOARD_RESULT = { ...CLEAN_RESULT, status: 'ok' as const }
const VIOLATION_BOARD_RESULT = { ...VIOLATION_RESULT, status: 'ok' as const }

beforeEach(() => {
  checkBoardMock.mockReset()
  checkSchematicMock.mockReset()
  pickSchematicFileMock.mockReset()
})

describe('BoardAdvisor', () => {
  it('Check Board calls checkBoard with no path (auto-resolve) and shows a real violation', async () => {
    checkBoardMock.mockResolvedValueOnce(VIOLATION_BOARD_RESULT)

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))

    await waitFor(() => screen.getByText(/Board has malformed outline/))
    expect(checkBoardMock).toHaveBeenCalledWith(undefined)
    screen.getByText('ERROR')
    screen.getByText(/no outline drawn on the Edge.Cuts layer/)
    screen.getByText(/Draw a closed shape on the Edge.Cuts layer/)
  })

  it('a clean board shows an honest "no violations" message, not an empty section', async () => {
    checkBoardMock.mockResolvedValueOnce(CLEAN_BOARD_RESULT)

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))

    await waitFor(() => screen.getByText('No violations found.'))
  })

  it('a genuine connection failure still shows the real error, not a crash', async () => {
    checkBoardMock.mockRejectedValueOnce(
      new Error('Lost connection to KiCad mid-request. It may have been closed.'),
    )

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))

    await waitFor(() => screen.getByText(/Lost connection to KiCad/))
  })

  it('CTX-309.3: no board open shows a real, concrete walkthrough, not a raw error', async () => {
    checkBoardMock.mockResolvedValueOnce({ status: 'no_board_open' })

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))

    await waitFor(() => screen.getByText('No board is currently open in KiCad.'))
    screen.getByText(/PCB Editor/)
    screen.getByText(/Preferences → Plugins/)
    screen.getByRole('button', { name: 'Try Again' })
  })

  it('CTX-309.3: Try Again re-invokes checkBoard with no path', async () => {
    checkBoardMock.mockResolvedValueOnce({ status: 'no_board_open' })
    checkBoardMock.mockResolvedValueOnce(CLEAN_BOARD_RESULT)

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))
    await waitFor(() => screen.getByRole('button', { name: 'Try Again' }))

    fireEvent.click(screen.getByRole('button', { name: 'Try Again' }))

    await waitFor(() => screen.getByText('No violations found.'))
    expect(checkBoardMock).toHaveBeenCalledTimes(2)
  })

  it('CTX-309.3: more than one board open shows a real, clickable candidate list', async () => {
    checkBoardMock.mockResolvedValueOnce({
      status: 'needs_selection',
      candidates: [
        { path: '/boards/a/board_a.kicad_pcb', label: 'board_a.kicad_pcb' },
        { path: '/boards/b/board_b.kicad_pcb', label: 'board_b.kicad_pcb' },
      ],
    })

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))

    await waitFor(() => screen.getByText('More than one board is open in KiCad. Pick one to check:'))
    screen.getByText('board_a.kicad_pcb')
    screen.getByText('board_b.kicad_pcb')
  })

  it('CTX-309.3: clicking a candidate re-invokes checkBoard with its real path', async () => {
    checkBoardMock.mockResolvedValueOnce({
      status: 'needs_selection',
      candidates: [{ path: '/boards/a/board_a.kicad_pcb', label: 'board_a.kicad_pcb' }],
    })
    checkBoardMock.mockResolvedValueOnce(CLEAN_BOARD_RESULT)

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))
    await waitFor(() => screen.getByText('board_a.kicad_pcb'))

    fireEvent.click(screen.getByText('board_a.kicad_pcb'))

    await waitFor(() => expect(checkBoardMock).toHaveBeenLastCalledWith('/boards/a/board_a.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))
  })

  it('Check Schematic picks a file first, then calls checkSchematic with the real picked path', async () => {
    pickSchematicFileMock.mockResolvedValueOnce('/real/board.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce({ ...CLEAN_RESULT, source_path: '/real/board.kicad_sch' })

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))

    await waitFor(() => expect(checkSchematicMock).toHaveBeenCalledWith('/real/board.kicad_sch'))
  })

  it('closing the file picker (null) is a silent no-op, not an error', async () => {
    pickSchematicFileMock.mockResolvedValueOnce(null)

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))

    await waitFor(() => expect(pickSchematicFileMock).toHaveBeenCalled())
    expect(checkSchematicMock).not.toHaveBeenCalled()
  })

  it('a violation tagged with a real sheet_path shows it', async () => {
    pickSchematicFileMock.mockResolvedValueOnce('/real/board.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce({
      violations: [{
        description: 'Pin not connected', severity: 'warning', type: 'pin_not_connected', items: [],
        sheet_path: '/sub', explanation: 'A pin has no real connection.', suggested_fix: 'Wire the pin or mark it no-connect.',
      }],
      summary: 'One warning found.',
      truncated_count: 0,
      source_path: '/real/board.kicad_sch',
    })

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))

    await waitFor(() => screen.getByText(/Pin not connected/))
    screen.getByText('(/sub)', { exact: false })
    screen.getByText('WARNING')
  })

  it('a truncated_count > 0 tells the user violations were left out, not silently dropped', async () => {
    checkBoardMock.mockResolvedValueOnce({ ...VIOLATION_BOARD_RESULT, truncated_count: 5 })

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))

    await waitFor(() => screen.getByText(/\+5 more violation\(s\) not shown\./))
  })

  it('Board and Schematic results are independent -- checking one does not clear the other', async () => {
    checkBoardMock.mockResolvedValueOnce(CLEAN_BOARD_RESULT)
    pickSchematicFileMock.mockResolvedValueOnce('/real/board.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce(VIOLATION_RESULT)

    render(<BoardAdvisor />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Board' }))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))
    await waitFor(() => screen.getByText(/Board has malformed outline/))

    screen.getByText('No violations found.')
  })
})
