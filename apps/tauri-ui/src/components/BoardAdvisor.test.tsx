import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const checkBoardMock = vi.fn()
const checkSchematicMock = vi.fn()
const pickSchematicFileMock = vi.fn()
const listOpenBoardsMock = vi.fn()
const openKicadMock = vi.fn()

vi.mock('../lib/boardAdvisor', () => ({
  checkBoard: (...args: unknown[]) => checkBoardMock(...args),
  checkSchematic: (...args: unknown[]) => checkSchematicMock(...args),
  pickSchematicFile: (...args: unknown[]) => pickSchematicFileMock(...args),
  listOpenBoards: (...args: unknown[]) => listOpenBoardsMock(...args),
  openKicad: (...args: unknown[]) => openKicadMock(...args),
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

const ONE_BOARD_OPEN = {
  status: 'boards_found' as const,
  candidates: [{ path: '/real/board.kicad_pcb', label: 'board.kicad_pcb' }],
}

beforeEach(() => {
  checkBoardMock.mockReset()
  checkSchematicMock.mockReset()
  pickSchematicFileMock.mockReset()
  listOpenBoardsMock.mockReset().mockResolvedValue({ status: 'no_board_open' })
  openKicadMock.mockReset().mockResolvedValue(undefined)
})

describe('BoardAdvisor: Board (DRC) -- CTX-309.4 list-first flow', () => {
  it('scans for open boards as soon as the screen mounts, with no click required', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)

    render(<BoardAdvisor projectName="test-project" />)

    await waitFor(() => expect(listOpenBoardsMock).toHaveBeenCalledTimes(1))
    screen.getByText('Board open in KiCad:')
  })

  it('a single open board is still shown as a real, explicit item to click -- never auto-checked', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)

    render(<BoardAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText('board.kicad_pcb'))
    expect(checkBoardMock).not.toHaveBeenCalled()
  })

  it('clicking a listed board calls checkBoard with its real explicit path and shows the result', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce(VIOLATION_RESULT)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))

    fireEvent.click(screen.getByText('board.kicad_pcb'))

    await waitFor(() => expect(checkBoardMock).toHaveBeenCalledWith('/real/board.kicad_pcb'))
    await waitFor(() => screen.getByText(/Board has malformed outline/))
    screen.getByText('ERROR')
    screen.getByText(/no outline drawn on the Edge.Cuts layer/)
  })

  it('a clean board shows an honest "no violations" message, not an empty section', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce(CLEAN_RESULT)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))

    await waitFor(() => screen.getByText('No violations found.'))
  })

  it('while checking, shows real feedback naming the board being checked, not a bare "Checking…"', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockImplementation(() => new Promise(() => {}))

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))

    await waitFor(() => screen.getByText(/Running DRC checks on board\.kicad_pcb/))
  })

  it('the clicked board stays visibly selected (aria-pressed) once a result comes back, instead of showing its path a second time', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce(CLEAN_RESULT)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))

    await waitFor(() => screen.getByText('No violations found.'))
    expect(screen.getByRole('button', { name: /board\.kicad_pcb/ }).getAttribute('aria-pressed')).toBe('true')
    // the picked board's own real path is already shown once, highlighted, in the
    // list item above -- it must not be repeated a second time under the result.
    expect(screen.getAllByText('/real/board.kicad_pcb')).toHaveLength(1)
  })

  it('a genuine DRC failure after picking a board shows the real error, not a crash', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockRejectedValueOnce(new Error('Lost connection to KiCad mid-request. It may have been closed.'))

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))

    await waitFor(() => screen.getByText(/Lost connection to KiCad/))
  })

  it('more than one board open shows every real candidate as a clickable item', async () => {
    listOpenBoardsMock.mockResolvedValue({
      status: 'boards_found',
      candidates: [
        { path: '/boards/a/board_a.kicad_pcb', label: 'board_a.kicad_pcb' },
        { path: '/boards/b/board_b.kicad_pcb', label: 'board_b.kicad_pcb' },
      ],
    })

    render(<BoardAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText('Boards open in KiCad — pick one to check:'))
    screen.getByText('board_a.kicad_pcb')
    screen.getByText('board_b.kicad_pcb')
  })

  it('offers a real way to open a different board without leaving the app: Switch to KiCad', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText(/Don't see the board you want/))

    fireEvent.click(screen.getByRole('button', { name: 'Switch to KiCad' }))

    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))
  })

  it('clicking one of several candidates checks only that real board', async () => {
    listOpenBoardsMock.mockResolvedValue({
      status: 'boards_found',
      candidates: [
        { path: '/boards/a/board_a.kicad_pcb', label: 'board_a.kicad_pcb' },
        { path: '/boards/b/board_b.kicad_pcb', label: 'board_b.kicad_pcb' },
      ],
    })
    checkBoardMock.mockResolvedValueOnce(CLEAN_RESULT)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board_b.kicad_pcb'))
    fireEvent.click(screen.getByText('board_b.kicad_pcb'))

    await waitFor(() => expect(checkBoardMock).toHaveBeenCalledWith('/boards/b/board_b.kicad_pcb'))
    expect(checkBoardMock).toHaveBeenCalledTimes(1)
  })

  it('no board open shows a real, concrete walkthrough plus Open KiCad and Refresh actions', async () => {
    render(<BoardAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText('No board is currently open in KiCad.'))
    screen.getByText(/PCB Editor/)
    screen.getByText(/Preferences → Plugins/)
    screen.getByRole('button', { name: 'Open KiCad' })
    screen.getByRole('button', { name: 'Refresh' })
  })

  it('Open KiCad calls the real open_kicad command', async () => {
    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Open KiCad' }))

    fireEvent.click(screen.getByRole('button', { name: 'Open KiCad' }))

    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))
  })

  it('a failed Open KiCad shows the real error, not a silent no-op', async () => {
    openKicadMock.mockRejectedValueOnce(new Error('Could not launch KiCad: No such file or directory'))

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Open KiCad' }))
    fireEvent.click(screen.getByRole('button', { name: 'Open KiCad' }))

    await waitFor(() => screen.getByText(/Could not launch KiCad/))
  })

  it('Refresh re-scans for open boards, picking up a board opened since the last scan', async () => {
    listOpenBoardsMock.mockResolvedValueOnce({ status: 'no_board_open' })
    listOpenBoardsMock.mockResolvedValueOnce(ONE_BOARD_OPEN)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Refresh' }))

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => screen.getByText('board.kicad_pcb'))
    expect(listOpenBoardsMock).toHaveBeenCalledTimes(2)
  })

  it('a genuine connection failure scanning for open boards shows the same calm guidance as no_board_open, not a red server error', async () => {
    listOpenBoardsMock.mockReset().mockRejectedValue(
      new Error('Could not connect to KiCad. Ensure KiCad 9 or later is running with the IPC API enabled (Preferences > Plugins).'),
    )

    render(<BoardAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText("KiCad doesn't appear to be running yet."))
    expect(screen.queryByText(/Could not connect to KiCad/)).toBeNull()
    screen.getByRole('button', { name: 'Open KiCad' })
    screen.getByRole('button', { name: 'Refresh' })
  })

  it('Open KiCad works from the connection-failure state too, not just no_board_open', async () => {
    listOpenBoardsMock.mockReset().mockRejectedValue(new Error('Could not connect to KiCad.'))

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Open KiCad' }))

    fireEvent.click(screen.getByRole('button', { name: 'Open KiCad' }))

    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))
  })

  it('a truncated_count > 0 tells the user violations were left out, not silently dropped', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce({ ...VIOLATION_RESULT, truncated_count: 5 })

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))

    await waitFor(() => screen.getByText(/\+5 more violation\(s\) not shown\./))
  })

  it('a completed check survives being re-rendered with the same projectName -- App.tsx keeps this component mounted across tab switches, this just confirms the state isn\'t reset along the way', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce(CLEAN_RESULT)

    const { rerender } = render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    // simulates App.tsx re-rendering this same, still-mounted instance
    // while a *different* area tab happens to be selected -- no new
    // scan, no lost result.
    rerender(<BoardAdvisor projectName="test-project" />)

    screen.getByText('No violations found.')
    expect(listOpenBoardsMock).toHaveBeenCalledTimes(1)
  })

  it('switching to a real, different project resets the previous project\'s board selection and result', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce(CLEAN_RESULT)

    const { rerender } = render(<BoardAdvisor projectName="project-a" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    rerender(<BoardAdvisor projectName="project-b" />)

    expect(screen.queryByText('No violations found.')).toBeNull()
  })
})

describe('BoardAdvisor: Schematic (ERC)', () => {
  it('explains why this is a manual file picker, unlike the live board list, instead of leaving the difference unexplained', async () => {
    render(<BoardAdvisor projectName="test-project" />)

    screen.getByText(/KiCad's live connection has no way to list open schematics/)
  })

  it('Check Schematic picks a file first, then calls checkSchematic with the real picked path', async () => {
    pickSchematicFileMock.mockResolvedValueOnce('/real/board.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce({ ...CLEAN_RESULT, source_path: '/real/board.kicad_sch' })

    render(<BoardAdvisor projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))

    await waitFor(() => expect(checkSchematicMock).toHaveBeenCalledWith('/real/board.kicad_sch'))
  })

  it('closing the file picker (null) is a silent no-op, not an error', async () => {
    pickSchematicFileMock.mockResolvedValueOnce(null)

    render(<BoardAdvisor projectName="test-project" />)
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

    render(<BoardAdvisor projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))

    await waitFor(() => screen.getByText(/Pin not connected/))
    screen.getByText('(/sub)', { exact: false })
    screen.getByText('WARNING')
  })

  it('Board and Schematic results are independent -- checking one does not clear the other', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockResolvedValueOnce(CLEAN_RESULT)
    pickSchematicFileMock.mockResolvedValueOnce('/real/board.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce(VIOLATION_RESULT)

    render(<BoardAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'Check Schematic…' }))
    await waitFor(() => screen.getByText(/Board has malformed outline/))

    screen.getByText('No violations found.')
  })
})
