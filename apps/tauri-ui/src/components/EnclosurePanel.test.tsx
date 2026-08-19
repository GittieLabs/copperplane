import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const generateEnclosureMock = vi.fn()
const pickPcbFileMock = vi.fn()
const listOpenBoardsMock = vi.fn()
const openKicadMock = vi.fn()
const shellOpenMock = vi.fn()
const exportEnclosureMock = vi.fn()
const pickExportDestinationMock = vi.fn()
const getProjectDirectoryMock = vi.fn()

vi.mock('../lib/enclosure', () => ({
  generateEnclosure: (...args: unknown[]) => generateEnclosureMock(...args),
  pickPcbFile: (...args: unknown[]) => pickPcbFileMock(...args),
  exportEnclosure: (...args: unknown[]) => exportEnclosureMock(...args),
  pickExportDestination: (...args: unknown[]) => pickExportDestinationMock(...args),
  getProjectDirectory: (...args: unknown[]) => getProjectDirectoryMock(...args),
}))

vi.mock('../lib/boardAdvisor', () => ({
  listOpenBoards: (...args: unknown[]) => listOpenBoardsMock(...args),
  openKicad: (...args: unknown[]) => openKicadMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => shellOpenMock(...args),
}))

const enclosureViewerSpy = vi.fn()
vi.mock('./EnclosureViewer', () => ({
  EnclosureViewer: (props: unknown) => {
    enclosureViewerSpy(props)
    return null
  },
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
  enclosureViewerSpy.mockReset()
  exportEnclosureMock.mockReset()
  pickExportDestinationMock.mockReset()
  getProjectDirectoryMock.mockReset().mockResolvedValue('/projects/test-project')
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

  it('submitting Board mode includes pcb_path, omits width/depth/project_name', async () => {
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
    // CTX-311.13: Generate no longer persists anything -- project_name
    // was removed from EnclosureParams entirely, real fix for a real,
    // confirmed live bug (see lib/enclosure.ts's own EnclosureResult
    // docstring).
    expect(params).not.toHaveProperty('project_name')
  })
})

describe('EnclosurePanel: Manual mode', () => {
  it('Generate is always enabled -- real numeric defaults are always present', async () => {
    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))

    const generateButton = screen.getByRole('button', { name: 'Generate Enclosure' }) as HTMLButtonElement
    expect(generateButton.disabled).toBe(false)
  })

  it('submitting Manual mode includes width, depth, height -- no project_name', async () => {
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(generateEnclosureMock).toHaveBeenCalled())
    expect(generateEnclosureMock).toHaveBeenCalledWith({
      width: 50,
      depth: 30,
      height: 20,
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

  it('CTX-311.1: a no_mounting_holes_found result renders its own real warning', async () => {
    generateEnclosureMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.resolve({ ...fakeResult, no_mounting_holes_found: true })),
    )

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => screen.getByText(/No mounting holes were found on this board/))
  })

  it('CTX-311.13: no longer shows the internal Generated: <path> label', async () => {
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => screen.getByRole('button', { name: 'Open .step' }))
    expect(screen.queryByText(/Generated:/)).toBeNull()
  })
})

describe('EnclosurePanel: export (CTX-311.13)', () => {
  const fakeResultWithLid = {
    ...fakeResult,
    lid_glb_path: '/tmp/lid.glb',
    lid_step_path: '/tmp/lid.step',
  }

  async function renderWithResult(result: typeof fakeResult) {
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(result)))
    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))
    await waitFor(() => screen.getByRole('button', { name: 'Export…' }))
  }

  it('Combined and Lid options are disabled until a lid was actually generated', async () => {
    await renderWithResult(fakeResult)

    const partsSelect = screen.getByLabelText('Export parts') as HTMLSelectElement
    const combinedOption = Array.from(partsSelect.options).find((o) => o.value === 'combined')!
    const lidOption = Array.from(partsSelect.options).find((o) => o.value === 'lid')!
    expect(combinedOption.disabled).toBe(true)
    expect(lidOption.disabled).toBe(true)
  })

  it('Combined and Lid options are enabled once a lid was generated', async () => {
    await renderWithResult(fakeResultWithLid)

    const partsSelect = screen.getByLabelText('Export parts') as HTMLSelectElement
    const combinedOption = Array.from(partsSelect.options).find((o) => o.value === 'combined')!
    const lidOption = Array.from(partsSelect.options).find((o) => o.value === 'lid')!
    expect(combinedOption.disabled).toBe(false)
    expect(lidOption.disabled).toBe(false)
  })

  it('clicking Export defaults the save dialog to the real project directory plus a real filename', async () => {
    await renderWithResult(fakeResult)
    getProjectDirectoryMock.mockResolvedValueOnce('/projects/test-project')
    pickExportDestinationMock.mockResolvedValueOnce(null)

    fireEvent.click(screen.getByRole('button', { name: 'Export…' }))

    await waitFor(() => expect(pickExportDestinationMock).toHaveBeenCalled())
    expect(getProjectDirectoryMock).toHaveBeenCalledWith('test-project')
    expect(pickExportDestinationMock).toHaveBeenCalledWith('step', '/projects/test-project/body.step')
  })

  it('cancelling the save dialog (null) never calls exportEnclosure', async () => {
    await renderWithResult(fakeResult)
    pickExportDestinationMock.mockResolvedValueOnce(null)

    fireEvent.click(screen.getByRole('button', { name: 'Export…' }))

    await waitFor(() => expect(pickExportDestinationMock).toHaveBeenCalled())
    expect(exportEnclosureMock).not.toHaveBeenCalled()
  })

  it('a chosen destination calls exportEnclosure with the real source paths, parts, and format', async () => {
    await renderWithResult(fakeResultWithLid)
    pickExportDestinationMock.mockResolvedValueOnce('/chosen/combined.glb')
    exportEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve({ dest_path: '/chosen/combined.glb' })))

    fireEvent.change(screen.getByLabelText('Export parts'), { target: { value: 'combined' } })
    fireEvent.change(screen.getByLabelText('Export format'), { target: { value: 'glb' } })
    fireEvent.click(screen.getByRole('button', { name: 'Export…' }))

    await waitFor(() => expect(exportEnclosureMock).toHaveBeenCalled())
    expect(exportEnclosureMock).toHaveBeenCalledWith({
      parts: 'combined',
      fmt: 'glb',
      dest_path: '/chosen/combined.glb',
      glb_path: fakeResultWithLid.glb_path,
      step_path: fakeResultWithLid.step_path,
      lid_glb_path: fakeResultWithLid.lid_glb_path,
      lid_step_path: fakeResultWithLid.lid_step_path,
    })
  })

  it('a real export failure shows the error message, not a silent failure', async () => {
    await renderWithResult(fakeResult)
    pickExportDestinationMock.mockResolvedValueOnce('/chosen/body.step')
    exportEnclosureMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.reject(new Error('Disk is full'))),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Export…' }))

    await waitFor(() => screen.getByText('Disk is full'))
  })
})

describe('EnclosurePanel: lid (CTX-311.2/CTX-311.3)', () => {
  it('the lid checkbox only appears in Board mode -- lid requires board-driven mode on the daemon side', async () => {
    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('No board is currently open in KiCad.'))
    screen.getByLabelText('Add a lid')

    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    expect(screen.queryByLabelText('Add a lid')).toBeNull()
  })

  it('checking the lid box reveals an optional thickness field', async () => {
    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('No board is currently open in KiCad.'))

    expect(screen.queryByText(/Lid thickness/)).toBeNull()
    fireEvent.click(screen.getByLabelText('Add a lid'))
    screen.getByText(/Lid thickness \(mm\)/)
  })

  it('submitting with the lid box checked sends lid: true and the given thickness', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByLabelText('Add a lid'))
    fireEvent.change(screen.getByLabelText(/Lid thickness/), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(generateEnclosureMock).toHaveBeenCalled())
    const params = generateEnclosureMock.mock.calls[0][0]
    expect(params.lid).toBe(true)
    expect(params.lid_thickness_mm).toBe(3)
  })

  it('submitting with the lid box checked but no thickness given omits lid_thickness_mm -- the daemon defaults it', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByLabelText('Add a lid'))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(generateEnclosureMock).toHaveBeenCalled())
    const params = generateEnclosureMock.mock.calls[0][0]
    expect(params.lid).toBe(true)
    expect(params.lid_thickness_mm).toBeUndefined()
  })

  it('submitting with the lid box unchecked sends lid: false', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(generateEnclosureMock).toHaveBeenCalled())
    expect(generateEnclosureMock.mock.calls[0][0].lid).toBe(false)
  })

  it('a result with a real lid_glb_path passes it through to the viewer and shows a Show lid toggle', async () => {
    listOpenBoardsMock.mockResolvedValue(ONE_BOARD_OPEN)
    generateEnclosureMock.mockResolvedValueOnce(
      fakeJobHandle(
        Promise.resolve({ ...fakeResult, lid_glb_path: '/tmp/lid.glb', lid_step_path: '/tmp/lid.step' }),
      ),
    )

    render(<EnclosurePanel projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_pcb'))
    fireEvent.click(screen.getByLabelText('Add a lid'))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => screen.getByLabelText('Show lid'))
    expect(enclosureViewerSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({ glbPath: '/tmp/enclosure.glb', lidGlbPath: '/tmp/lid.glb', lidVisible: true }),
    )

    fireEvent.click(screen.getByLabelText('Show lid'))
    expect(enclosureViewerSpy).toHaveBeenLastCalledWith(expect.objectContaining({ lidVisible: false }))
  })

  it('a result with no lid_glb_path never shows a Show lid toggle', async () => {
    generateEnclosureMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(fakeResult)))

    render(<EnclosurePanel projectName="test-project" />)
    fireEvent.click(screen.getByRole('button', { name: 'Manual (no PCB)' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => expect(enclosureViewerSpy).toHaveBeenCalled())
    expect(screen.queryByLabelText('Show lid')).toBeNull()
  })
})
