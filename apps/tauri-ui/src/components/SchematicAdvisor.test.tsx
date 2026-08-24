import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const checkSchematicMock = vi.fn()
const pickSchematicFileMock = vi.fn()
const listProjectSchematicsMock = vi.fn()
const openKicadMock = vi.fn()

vi.mock('../lib/boardAdvisor', () => ({
  checkSchematic: (...args: unknown[]) => checkSchematicMock(...args),
  pickSchematicFile: (...args: unknown[]) => pickSchematicFileMock(...args),
  listProjectSchematics: (...args: unknown[]) => listProjectSchematicsMock(...args),
  openKicad: (...args: unknown[]) => openKicadMock(...args),
}))

// CTX-318.3: AgentChat has its own dedicated test file (AgentChat.test.tsx)
// -- stubbed here, matching PartDetail.test.tsx's own precedent (CTX-318.2),
// so SchematicAdvisor's tests stay focused on its own wiring (does it mount
// AgentChat with the real scope/area/targets) and never need to mock
// AgentChat's own internal chat.* IPC calls.
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

const { SchematicAdvisor } = await import('./SchematicAdvisor')

const CLEAN_RESULT = { violations: [], summary: '', truncated_count: 0, source_path: '/real/board.kicad_sch' }

const VIOLATION_RESULT = {
  violations: [
    {
      description: 'Pin not connected',
      severity: 'warning',
      type: 'pin_not_connected',
      items: [],
      sheet_path: '/sub',
      explanation: 'A pin has no real connection.',
      suggested_fix: 'Wire the pin or mark it no-connect.',
    },
  ],
  summary: 'One warning found.',
  truncated_count: 0,
  source_path: '/real/board.kicad_sch',
}

const ONE_SCHEMATIC_FOUND = {
  status: 'schematics_found' as const,
  candidates: [{ path: '/real/board.kicad_sch', label: 'board.kicad_sch' }],
}

beforeEach(() => {
  checkSchematicMock.mockReset()
  pickSchematicFileMock.mockReset()
  listProjectSchematicsMock.mockReset().mockResolvedValue({ status: 'no_schematic_found' })
  openKicadMock.mockReset().mockResolvedValue(undefined)
})

describe('SchematicAdvisor: list-first flow', () => {
  it('scans for a project schematic as soon as the screen mounts, with no click required', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)

    render(<SchematicAdvisor projectName="test-project" />)

    await waitFor(() => expect(listProjectSchematicsMock).toHaveBeenCalledTimes(1))
    screen.getByText('Schematic found for the board open in KiCad:')
  })

  it('a single found schematic is still shown as a real, explicit item to click -- never auto-checked', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)

    render(<SchematicAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText('board.kicad_sch'))
    expect(checkSchematicMock).not.toHaveBeenCalled()
  })

  it('clicking a listed schematic calls checkSchematic with its real explicit path and shows the result', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockResolvedValueOnce(VIOLATION_RESULT)

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))

    fireEvent.click(screen.getByText('board.kicad_sch'))

    await waitFor(() => expect(checkSchematicMock).toHaveBeenCalledWith('/real/board.kicad_sch'))
    await waitFor(() => screen.getByText(/Pin not connected/))
    screen.getByText('(/sub)', { exact: false })
    screen.getByText('WARNING')
  })

  it('a clean schematic shows an honest "no violations" message', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockResolvedValueOnce(CLEAN_RESULT)

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))

    await waitFor(() => screen.getByText('No violations found.'))
  })

  it('while checking, shows real feedback naming the schematic being checked', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockImplementation(() => new Promise(() => {}))

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))

    await waitFor(() => screen.getByText(/Running ERC checks on board\.kicad_sch/))
  })

  it('the clicked schematic stays visibly selected (aria-pressed), and its path is not repeated under the result', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockResolvedValueOnce(CLEAN_RESULT)

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))

    await waitFor(() => screen.getByText('No violations found.'))
    expect(screen.getByRole('button', { name: /board\.kicad_sch/ }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getAllByText('/real/board.kicad_sch')).toHaveLength(1)
  })

  it('a genuine ERC failure shows the real error, not a crash', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockRejectedValueOnce(new Error('Lost connection to KiCad mid-request. It may have been closed.'))

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))

    await waitFor(() => screen.getByText(/Lost connection to KiCad/))
  })

  it('more than one derived schematic shows every real candidate', async () => {
    listProjectSchematicsMock.mockResolvedValue({
      status: 'schematics_found',
      candidates: [
        { path: '/projects/a/a.kicad_sch', label: 'a.kicad_sch' },
        { path: '/projects/b/b.kicad_sch', label: 'b.kicad_sch' },
      ],
    })

    render(<SchematicAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText('Schematics found for the boards open in KiCad — pick one to check:'))
    screen.getByText('a.kicad_sch')
    screen.getByText('b.kicad_sch')
  })

  it('no schematic found shows a real walkthrough plus Open KiCad, Refresh, and manual pick', async () => {
    render(<SchematicAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText('No schematic could be found automatically.'))
    screen.getByRole('button', { name: 'Open KiCad' })
    screen.getByRole('button', { name: 'Refresh' })
    screen.getByRole('button', { name: 'Pick file manually…' })
  })

  it('Open KiCad calls the real open_kicad command', async () => {
    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Open KiCad' }))

    fireEvent.click(screen.getByRole('button', { name: 'Open KiCad' }))

    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))
  })

  it('Refresh re-scans for a derivable schematic', async () => {
    listProjectSchematicsMock.mockResolvedValueOnce({ status: 'no_schematic_found' })
    listProjectSchematicsMock.mockResolvedValueOnce(ONE_SCHEMATIC_FOUND)

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Refresh' }))

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => screen.getByText('board.kicad_sch'))
    expect(listProjectSchematicsMock).toHaveBeenCalledTimes(2)
  })

  it('a genuine connection failure shows the same calm guidance as no_schematic_found, not a red server error', async () => {
    listProjectSchematicsMock.mockReset().mockRejectedValue(
      new Error('Could not connect to KiCad. Ensure KiCad 9 or later is running with the IPC API enabled (Preferences > Plugins).'),
    )

    render(<SchematicAdvisor projectName="test-project" />)

    await waitFor(() => screen.getByText("KiCad doesn't appear to be running yet."))
    expect(screen.queryByText(/Could not connect to KiCad/)).toBeNull()
    screen.getByRole('button', { name: 'Open KiCad' })
  })

  it('a truncated_count > 0 tells the user violations were left out, not silently dropped', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockResolvedValueOnce({ ...VIOLATION_RESULT, truncated_count: 5 })

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))

    await waitFor(() => screen.getByText(/\+5 more violation\(s\) not shown\./))
  })

  it('a completed check survives being re-rendered with the same projectName', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockResolvedValueOnce(CLEAN_RESULT)

    const { rerender } = render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))
    await waitFor(() => screen.getByText('No violations found.'))

    rerender(<SchematicAdvisor projectName="test-project" />)

    screen.getByText('No violations found.')
    expect(listProjectSchematicsMock).toHaveBeenCalledTimes(1)
  })

  it('switching to a different real project resets the previous project\'s selection and result', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockResolvedValueOnce(CLEAN_RESULT)

    const { rerender } = render(<SchematicAdvisor projectName="project-a" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByText('board.kicad_sch'))
    await waitFor(() => screen.getByText('No violations found.'))

    rerender(<SchematicAdvisor projectName="project-b" />)

    expect(screen.queryByText('No violations found.')).toBeNull()
  })
})

describe('SchematicAdvisor: manual file-pick fallback', () => {
  it('the guidance state offers a manual picker that still runs a real check', async () => {
    pickSchematicFileMock.mockResolvedValueOnce('/manual/picked.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce({ ...CLEAN_RESULT, source_path: '/manual/picked.kicad_sch' })

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Pick file manually…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pick file manually…' }))

    await waitFor(() => expect(checkSchematicMock).toHaveBeenCalledWith('/manual/picked.kicad_sch'))
    await waitFor(() => screen.getByText('No violations found.'))
  })

  it('closing the file picker (null) is a silent no-op, not an error', async () => {
    pickSchematicFileMock.mockResolvedValueOnce(null)

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByRole('button', { name: 'Pick file manually…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pick file manually…' }))

    await waitFor(() => expect(pickSchematicFileMock).toHaveBeenCalled())
    expect(checkSchematicMock).not.toHaveBeenCalled()
  })

  it('a manually-picked file also available from the boards_found state shows its own real path under the result', async () => {
    listProjectSchematicsMock.mockResolvedValue(ONE_SCHEMATIC_FOUND)
    pickSchematicFileMock.mockResolvedValueOnce('/manual/other.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce({ ...CLEAN_RESULT, source_path: '/manual/other.kicad_sch' })

    render(<SchematicAdvisor projectName="test-project" />)
    await waitFor(() => screen.getByText('board.kicad_sch'))
    fireEvent.click(screen.getByRole('button', { name: 'Pick file manually…' }))

    await waitFor(() => screen.getByText('/manual/other.kicad_sch'))
  })
})

describe('SchematicAdvisor: SPEC-316 menuCommand', () => {
  it('TEST-007: a matching open_kicad menuCommand runs the real handleOpenKicad', async () => {
    render(<SchematicAdvisor projectName="test-project" menuCommand={{ area: 'schematic', command: 'open_kicad', nonce: 0 }} />)

    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))
  })

  it('TEST-007b: a matching pick_manually menuCommand runs the real handlePickManually', async () => {
    pickSchematicFileMock.mockResolvedValueOnce('/manual/other.kicad_sch')
    checkSchematicMock.mockResolvedValueOnce({ ...CLEAN_RESULT, source_path: '/manual/other.kicad_sch' })

    render(
      <SchematicAdvisor
        projectName="test-project"
        menuCommand={{ area: 'schematic', command: 'pick_manually', nonce: 0 }}
      />,
    )

    await waitFor(() => expect(pickSchematicFileMock).toHaveBeenCalledTimes(1))
    await waitFor(() => screen.getByText('/manual/other.kicad_sch'))
  })

  it('a menuCommand for a different area is ignored', async () => {
    render(<SchematicAdvisor projectName="test-project" menuCommand={{ area: 'pcb', command: 'open_kicad', nonce: 0 }} />)

    await waitFor(() => expect(listProjectSchematicsMock).toHaveBeenCalled())
    expect(openKicadMock).not.toHaveBeenCalled()
  })

  it('the same command fired twice (nonce bumped) re-triggers the handler both times', async () => {
    const { rerender } = render(
      <SchematicAdvisor projectName="test-project" menuCommand={{ area: 'schematic', command: 'open_kicad', nonce: 0 }} />,
    )
    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(1))

    rerender(
      <SchematicAdvisor projectName="test-project" menuCommand={{ area: 'schematic', command: 'open_kicad', nonce: 1 }} />,
    )
    await waitFor(() => expect(openKicadMock).toHaveBeenCalledTimes(2))
  })
})

describe('SchematicAdvisor: CTX-318.3 AgentChat wiring', () => {
  it('mounts AgentChat scoped to the project schematic area, offering only "this project"', async () => {
    render(<SchematicAdvisor projectName="weather-pcb" />)

    await waitFor(() => screen.getByText(/AgentChat stub/))
    const stub = screen.getByText(/AgentChat stub/)
    expect(stub.textContent).toContain('area=schematic')
    expect(stub.textContent).toContain('scope=project')
    expect(stub.textContent).toContain('scopeId=weather-pcb:schematic')
    expect(stub.textContent).toContain('title="Ask about the schematic"')
    expect(stub.textContent).toContain('projectName=weather-pcb')
    expect(stub.textContent).toContain('targets=[this project:project:weather-pcb]')
  })

  it('re-scopes AgentChat when the project changes', async () => {
    const { rerender } = render(<SchematicAdvisor projectName="project-a" />)
    await waitFor(() => screen.getByText(/AgentChat stub/))

    rerender(<SchematicAdvisor projectName="project-b" />)

    await waitFor(() => expect(screen.getByText(/AgentChat stub/).textContent).toContain('scopeId=project-b:schematic'))
  })
})
