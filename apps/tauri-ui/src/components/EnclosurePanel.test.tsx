import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const generateEnclosureMock = vi.fn()
const pickPcbFileMock = vi.fn()
const listOpenBoardsMock = vi.fn()
const openKicadMock = vi.fn()
const shellOpenMock = vi.fn()

vi.mock('../lib/enclosure', () => ({
  generateEnclosure: (...args: unknown[]) => generateEnclosureMock(...args),
  pickPcbFile: (...args: unknown[]) => pickPcbFileMock(...args),
}))

vi.mock('../lib/boardAdvisor', () => ({
  listOpenBoards: (...args: unknown[]) => listOpenBoardsMock(...args),
  openKicad: (...args: unknown[]) => openKicadMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => shellOpenMock(...args),
}))

vi.mock('./EnclosureViewer', () => ({
  EnclosureViewer: () => null,
}))

const { EnclosurePanel } = await import('./EnclosurePanel')

/** Real user feedback exercising the actual running app: the old
 * "From board" mode's five geometry fields rendered as an unlabeled
 * stack of numbers (each label was an HTML `placeholder`, which never
 * shows once a real default value is already filled in), and neither
 * "From board" nor "Import board file…" ever reused a board already
 * open in KiCad. Redesigned into a single "Board" mode (list-first,
 * mirrors BoardAdvisor) plus a demoted "Manual (no PCB)" mode. */
function fakeJobHandle<T>(result: Promise<T>) {
  result.catch(() => {})
  return { jobId: 'job_1', result, onUpdate: () => () => {}, cancel: vi.fn() }
}

const ONE_BOARD_OPEN = {
  status: 'boards_found' as const,
  candidates: [{ path: '/real/board.kicad_pcb', label: 'board.kicad_pcb' }],
}

const fakeResult = {
  glb_path: '/tmp/enclosure.glb',
  step_path: '/tmp/enclosure.step',
  unrecognized_holes: [] as { x_mm: number; y_mm: number; diameter_mm: number; recognized: false }[],
}

beforeEach(() => {
  generateEnclosureMock.mockReset()
  pickPcbFileMock.mockReset()
  listOpenBoardsMock.mockReset().mockResolvedValue({ status: 'no_board_open' })
  openKicadMock.mockReset().mockResolvedValue(undefined)
  shellOpenMock.mockReset()
})

describe('EnclosurePanel: mode selection', () => {
  it('Board is the default mode, not Manual', async () => {
    render(<EnclosurePanel projectName="test-project" />)

    await waitFor(() => screen.getByText('No board is currently open in KiCad.'))
    expect(screen.queryByLabelText(/Width \(mm\)/)).toBeNull()
  })

  it('switching to Manual shows real visible labels, not just placeholder text', async () => {
    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))

    screen.getByText('Width (mm)')
    screen.getByText('Depth (mm)')
    screen.getByText('Height (mm)')
    screen.getByText(/A plain rectangular box, not based on any real board/)
  })
})

describe('EnclosurePanel: Board mode -- list-first picker', () => {
  it('scans for open boards as soon as the screen mounts', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)

    render(<EnclosurePanel projectName="test-project" />)

    await waitFor(() => expect(listOpenBoardsMock).toHaveBeenCalledTimes(1))
  })

  it('exactly one open board is auto-selected -- Generate is enabled without an extra click', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)

    render(<EnclosurePanel projectName="test-project" />)

    await waitFor(() => screen.getByText('board.kicad_pcb'))
    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(false)
    expect(screen.getByRole('button', { name: /board\.kicad_pcb/ }).getAttribute('aria-pressed')).toBe('true')
  })

  it('more than one open board shows the real list with nothing auto-selected', async () => {
    listOpenBoardsMock.mockResolvedValue({
      status: 'boards_found',
      candidates: [
        { path: '/boards/a/board_a.kicad_pcb', label: 'board_a.kicad_pcb' },
        { path: '/boards/b/board_b.kicad_pcb', label: 'board_b.kicad_pcb' },
      ],
    })

    render(<EnclosurePanel projectName="test-project" />)

    await waitFor(() => screen.getByText('board_a.kicad_pcb'))
    screen.getByText('board_b.kicad_pcb')
    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(true)
  })

  it('clicking a candidate selects it and enables Generate', async () => {
    listOpenBoardsMock.mockResolvedValue({
      status: 'boards_found',
      candidates: [
        { path: '/boards/a/board_a.kicad_pcb', label: 'board_a.kicad_pcb' },
        { path: '/boards/b/board_b.kicad_pcb', label: 'board_b.kicad_pcb' },
      ],
    })

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('board_b.kicad_pcb'))
    fireEvent.click(screen.getByText('board_b.kicad_pcb'))

    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(false)
  })

  it('no board open shows guidance with Open KiCad, Refresh, and a manual file picker', async () => {
    render(<EnclosurePanel projectName="test-project" />)

    await waitFor(() => screen.getByText('No board is currently open in KiCad.'))
    screen.getByRole('button', { name: 'Open KiCad' })
    screen.getByRole('button', { name: 'Refresh' })
    screen.getByRole('button', { name: 'Choose a .kicad_pcb file…' })
  })

  it('a connection failure shows the same calm guidance, not a red server error, with the same manual fallback', async () => {
    listOpenBoardsMock.mockReset().mockRejectedValue(new Error('Could not connect to KiCad.'))

    render(<EnclosurePanel projectName="test-project" />)

    await waitFor(() => screen.getByText("KiCad doesn't appear to be running yet."))
    screen.getByRole('button', { name: 'Choose a .kicad_pcb file…' })
  })

  it('picking a file manually from the guidance state selects it and enables Generate', async () => {
    pickPcbFileMock.mockResolvedValueOnce('/manual/board.kicad_pcb')

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Choose a .kicad_pcb file…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Choose a .kicad_pcb file…' }))

    await waitFor(() => screen.getByText('Manually picked: /manual/board.kicad_pcb'))
    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(false)
  })

  it('cancelling the manual file picker (null) is a silent no-op', async () => {
    pickPcbFileMock.mockResolvedValueOnce(null)

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Choose a .kicad_pcb file…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Choose a .kicad_pcb file…' }))

    await waitFor(() => expect(pickPcbFileMock).toHaveBeenCalled())
    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(true)
  })

  it('picking a different file overrides an auto-selected open board', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    pickPcbFileMock.mockResolvedValueOnce('/manual/other.kicad_pcb')

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Choose a different file…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Choose a different file…' }))

    await waitFor(() => screen.getByText('Manually picked: /manual/other.kicad_pcb'))
  })

  it('Open KiCad calls the real open_kicad command', async () => {
    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Open KiCad' }))
    fireEvent.click(screen.getByRole('button', { name: 'Open KiCad' }))

    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))
  })

  it('Refresh re-scans for open boards', async () => {
    listOpenBoardsMock.mockResolvedValueOnce({ status: 'no_board_open' })
    listOpenBoardsMock.mockResolvedValueOnce(ONE_BOARD_OPEN)

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Refresh' }))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => screen.getByText('board.kicad_pcb'))
    expect(listOpenBoardsMock).toHaveBeenCalledTimes(2)
  })

  it('geometry fields show real visible labels, required/optional status, and explanations', async () => {
    render(<EnclosurePanel projectName="test-project" />)

    screen.getByText(/Height \(mm\)/)
    screen.getByText('(required)')
    screen.getByText('How tall the enclosure is inside, above the board.')
    screen.getByText(/Wall thickness \(mm\)/)
    screen.getByText('How thick the outer walls are.')
    screen.getByText(/Clearance \(mm\)/)
    screen.getByText(/Fillet radius \(mm\)/)
    screen.getByText(/Standoff height \(mm\)/)
    screen.getByText(/rectangular box sized to your board's bounding box/)
  })

  it('submitting Board mode includes pcb_path, omits width/depth, includes project_name', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(generateEnclosureMock).toHaveBeenCalled())
    const params = generateEnclosureMock.mock.calls[0][0]
    expect(params.pcb_path).toBe('/real/board.kicad_pcb')
    expect(params).not.toHaveProperty('width')
    expect(params).not.toHaveProperty('depth')
    expect(params.project_name).toBe('test-project')
  })
})

describe('EnclosurePanel: Manual mode', () => {
  it('Generate is always enabled -- real numeric defaults are always present', async () => {
    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))

    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(false)
  })

  it('submitting Manual mode includes width, depth, height, and project_name', async () => {
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(generateEnclosureMock).toHaveBeenCalled())
    expect(generateEnclosureMock).toHaveBeenCalledWith({
      width: 50,
      depth: 30,
      height: 20,
      project_name: 'test-project',
    })
  })
})

describe('EnclosurePanel: results (unchanged behavior)', () => {
  it('a non-empty unrecognized_holes result renders a real warning naming the count', async () => {
    generateEnclosureMock.mockResolvedValueOnce(
      fakeJobHandle(
        Promise.resolve({
          ...fakeResult,
          unrecognized_holes: [{ x_mm: 1, y_mm: 1, diameter_mm: 1, recognized: false as const }],
        }),
      ),
    )

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => screen.getByText(/1 hole\(s\) on this board weren't recognized/))
  })

  it('a real step_path result renders an Open button that calls shell open with that exact path', async () => {
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => screen.getByRole('button', { name: 'Open .step' }))
    fireEvent.click(screen.getByRole('button', { name: 'Open .step' }))

    expect(shellOpenMock).toHaveBeenCalledWith('/tmp/enclosure.step')
  })
})
