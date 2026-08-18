import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const submitJobMock = vi.fn()
const dispatchToolMock = vi.fn()
const listProjectsMock = vi.fn()
const listLibraryPartsMock = vi.fn()
const saveProjectMock = vi.fn()
const loadConversationMock = vi.fn()
const appendConversationTurnMock = vi.fn()
const getCapabilitiesMock = vi.fn()
const shellOpenMock = vi.fn()
const listOpenBoardsMock = vi.fn()
const checkBoardMock = vi.fn()
const openKicadMock = vi.fn()
const checkSchematicMock = vi.fn()
const pickSchematicFileMock = vi.fn()
const listProjectSchematicsMock = vi.fn()

vi.mock('./lib/ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
  dispatchTool: (...args: unknown[]) => dispatchToolMock(...args),
}))

vi.mock('./lib/projects', () => ({
  listProjects: (...args: unknown[]) => listProjectsMock(...args),
  listLibraryParts: (...args: unknown[]) => listLibraryPartsMock(...args),
  saveProject: (...args: unknown[]) => saveProjectMock(...args),
  loadConversation: (...args: unknown[]) => loadConversationMock(...args),
  appendConversationTurn: (...args: unknown[]) => appendConversationTurnMock(...args),
}))

vi.mock('./lib/settings', () => ({
  getCapabilities: (...args: unknown[]) => getCapabilitiesMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => shellOpenMock(...args),
}))

vi.mock('./components/EnclosureViewer', () => ({
  EnclosureViewer: () => null,
}))

vi.mock('./lib/boardAdvisor', () => ({
  listOpenBoards: (...args: unknown[]) => listOpenBoardsMock(...args),
  checkBoard: (...args: unknown[]) => checkBoardMock(...args),
  openKicad: (...args: unknown[]) => openKicadMock(...args),
  checkSchematic: (...args: unknown[]) => checkSchematicMock(...args),
  pickSchematicFile: (...args: unknown[]) => pickSchematicFileMock(...args),
  listProjectSchematics: (...args: unknown[]) => listProjectSchematicsMock(...args),
}))

const { default: App } = await import('./App')

/** Builds a fake JobHandle whose `result` resolves/rejects on demand --
 * enough for these tests without a real daemon round-trip. A pre-built
 * rejected promise needs a synchronous no-op `.catch` attached here, or
 * Node reports it as an unhandled rejection before the caller's own
 * `await` ever gets a chance to observe it -- attaching a handler
 * doesn't consume the rejection for other observers, it just satisfies
 * this check. */
function fakeJobHandle<T>(result: Promise<T>) {
  result.catch(() => {})
  return { jobId: 'job_1', result, onUpdate: () => () => {}, cancel: vi.fn() }
}

/** These tests exercise the Overview area of a single, already-existing
 * project -- SPEC-305's shell selects a project's Overview by default
 * once `project.list` resolves, so waiting for the chat input is the
 * real signal that the shell finished loading, not an arbitrary delay. */
async function renderAppOnOverview() {
  render(<App />)
  await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
}

function sendMessage(text: string) {
  fireEvent.change(screen.getByPlaceholderText(/generate ATtiny85/), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
}

describe('App: chat & command surface', () => {
  beforeEach(() => {
    submitJobMock.mockReset()
    dispatchToolMock.mockReset()
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    saveProjectMock.mockReset()
    loadConversationMock.mockReset().mockResolvedValue([])
    appendConversationTurnMock.mockReset().mockResolvedValue(undefined)
  })

  it('TEST-001: "generate <part>" calls kicad.generate_component and renders the schema', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))

    await renderAppOnOverview()
    sendMessage('generate ATtiny85')

    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))
    expect(submitJobMock).toHaveBeenLastCalledWith('kicad.generate_component', {
      part_number: 'ATtiny85',
    })
    screen.getByText('Generated ATtiny85 (SOIC-8)')
  })

  it('TEST-002: "inject" with a schema already generated proposes the write via agent.dispatch_tool and awaits confirmation, mutating nothing yet', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))
    dispatchToolMock.mockResolvedValueOnce({
      kind: 'pending_confirmation',
      tool: 'kicad.inject_component',
      input: { schema, x_mm: 50, y_mm: 50 },
    })

    await renderAppOnOverview()
    sendMessage('generate ATtiny85')
    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))

    sendMessage('inject')

    await waitFor(() => screen.getByText('This will write into the board KiCad currently has open. Confirm?'))
    expect(dispatchToolMock).toHaveBeenLastCalledWith('kicad.inject_component', {
      schema,
      x_mm: 50,
      y_mm: 50,
    })
    expect(screen.queryByText('Injected into the open board.')).toBeNull()
  })

  it('TEST-002b: confirming the pending write re-dispatches with confirmed: true and reports success (SPEC-204/CTX-108.4)', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))
    dispatchToolMock.mockResolvedValueOnce({
      kind: 'pending_confirmation',
      tool: 'kicad.inject_component',
      input: { schema, x_mm: 50, y_mm: 50 },
    })
    dispatchToolMock.mockResolvedValueOnce({
      kind: 'dispatched',
      handle: fakeJobHandle(Promise.resolve({ part_number: 'ATtiny85', package: 'SOIC-8', pins: 8 })),
    })

    await renderAppOnOverview()
    sendMessage('generate ATtiny85')
    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))
    sendMessage('inject')
    await waitFor(() => screen.getByText('This will write into the board KiCad currently has open. Confirm?'))

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => screen.getByText('Injected into the open board.'))
    expect(dispatchToolMock).toHaveBeenLastCalledWith(
      'kicad.inject_component',
      { schema, x_mm: 50, y_mm: 50 },
      true,
    )
  })

  it('TEST-002c: cancelling the pending write never calls the daemon again and mutates nothing', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))
    dispatchToolMock.mockResolvedValueOnce({
      kind: 'pending_confirmation',
      tool: 'kicad.inject_component',
      input: { schema, x_mm: 50, y_mm: 50 },
    })

    await renderAppOnOverview()
    sendMessage('generate ATtiny85')
    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))
    sendMessage('inject')
    await waitFor(() => screen.getByText('This will write into the board KiCad currently has open. Confirm?'))

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => screen.getByText('Cancelled — board not modified.'))
    expect(dispatchToolMock).toHaveBeenCalledTimes(1)
  })

  it('TEST-003: "inject" with nothing generated yet shows a clean message, never calls the route', async () => {
    await renderAppOnOverview()
    sendMessage('inject')

    await waitFor(() => screen.getByText('Nothing to inject yet — generate a component first.'))
    expect(dispatchToolMock).not.toHaveBeenCalled()
  })

  it('TEST-004: an unrecognized message is a plain chat turn against llm.chat, rendering the real reply, and persists both turns', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve('Pin 3 is a GPIO pin.')))

    await renderAppOnOverview()
    sendMessage('what does pin 3 do?')

    await waitFor(() => screen.getByText('Pin 3 is a GPIO pin.'))
    expect(submitJobMock).toHaveBeenLastCalledWith('llm.chat', {
      prompt: 'what does pin 3 do?',
      history: [],
    })
    expect(appendConversationTurnMock).toHaveBeenCalledWith('test-project', {
      role: 'user',
      content: 'what does pin 3 do?',
    })
    expect(appendConversationTurnMock).toHaveBeenCalledWith('test-project', {
      role: 'assistant',
      content: 'Pin 3 is a GPIO pin.',
    })
  })

  it('TEST-005: a second plain chat turn sends the first turn back as history', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve('Got it, 42.')))
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve('42.')))

    await renderAppOnOverview()
    sendMessage('my favorite number is 42')
    await waitFor(() => screen.getByText('Got it, 42.'))

    sendMessage('what is my favorite number?')
    await waitFor(() => screen.getByText('42.'))

    expect(submitJobMock).toHaveBeenLastCalledWith('llm.chat', {
      prompt: 'what is my favorite number?',
      history: [
        { role: 'user', content: 'my favorite number is 42' },
        { role: 'assistant', content: 'Got it, 42.' },
      ],
    })
  })

  it('TEST-006: a generate failure shows the real error, not a generic message', async () => {
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.reject(new Error("Package 'FOO-1' is not in the known reference table."))),
    )

    await renderAppOnOverview()
    sendMessage('generate FOO-1')

    await waitFor(() => screen.getByText("Package 'FOO-1' is not in the known reference table."))
  })

  it('TEST-007: a fresh install with no projects shows the empty state, not a broken chat surface', async () => {
    listProjectsMock.mockResolvedValueOnce([])

    render(<App />)

    await waitFor(() => screen.getByText('Create a project on the left to get started.'))
    expect(screen.queryByPlaceholderText(/generate ATtiny85/)).toBeNull()
  })

  it('TEST-008b: the Components area tab renders the real ComponentDiscovery search box, not a placeholder', async () => {
    await renderAppOnOverview()

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))

    await waitFor(() => screen.getByPlaceholderText(/search for a part/))
    expect(screen.queryByText(/not built yet/)).toBeNull()
  })

  it('TEST-008: loads an existing project\'s persisted conversation into view on first render', async () => {
    loadConversationMock.mockResolvedValueOnce([
      { role: 'user', content: 'hello from before' },
      { role: 'assistant', content: 'hi again' },
    ])

    render(<App />)

    await waitFor(() => screen.getByText('> hello from before'))
    screen.getByText('hi again')
    expect(loadConversationMock).toHaveBeenCalledWith('test-project')
  })
})

/** Real user feedback: switching away from the PCB tab and back threw
 * out a check that had just finished, with no reason to -- App.tsx now
 * keeps BoardAdvisor mounted (hidden via CSS) across every area tab
 * instead of unmounting it, and only resets its state on a genuine
 * project switch. */
describe('App: PCB tab persists across area switches, resets on project switch', () => {
  const ONE_BOARD_OPEN = {
    status: 'boards_found' as const,
    candidates: [{ path: '/real/board.kicad_pcb', label: 'board.kicad_pcb' }],
  }
  const CLEAN_RESULT = { violations: [], summary: '', truncated_count: 0, source_path: '/real/board.kicad_pcb' }

  beforeEach(() => {
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    loadConversationMock.mockReset().mockResolvedValue([])
    listOpenBoardsMock.mockReset().mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockReset().mockResolvedValue(CLEAN_RESULT)
    openKicadMock.mockReset()
  })

  async function renderAppOnPcb() {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    fireEvent.click(screen.getByRole('button', { name: 'PCB' }))
    await waitFor(() => screen.getByText('board.kicad_pcb'))
  }

  it('a finished check is still shown after switching to another area and back to PCB', async () => {
    await renderAppOnPcb()
    fireEvent.click(screen.getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))
    fireEvent.click(screen.getByRole('button', { name: 'PCB' }))

    screen.getByText('No violations found.')
    expect(listOpenBoardsMock).toHaveBeenCalledTimes(1)
  })

  it('switching to a different real project resets the previous project\'s check result', async () => {
    listProjectsMock.mockReset().mockResolvedValue(['project-a', 'project-b'])

    await renderAppOnPcb()
    fireEvent.click(screen.getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'project-b' }))
    fireEvent.click(screen.getByRole('button', { name: 'PCB' }))

    expect(screen.queryByText('No violations found.')).toBeNull()
  })
})

/** Real user feedback: the ERC check briefly lived under the "PCB" tab
 * alongside DRC, which SPEC-300's own original stage-machine design
 * never intended (ERC belongs to the "Schematic Advisor" stage). Moved
 * to its own Schematic tab -- same mount-persistence/project-reset
 * behavior as the PCB tab, for the same real reason. */
describe('App: Schematic tab persists across area switches, resets on project switch', () => {
  const ONE_SCHEMATIC_FOUND = {
    status: 'schematics_found' as const,
    candidates: [{ path: '/real/board.kicad_sch', label: 'board.kicad_sch' }],
  }
  const CLEAN_RESULT = { violations: [], summary: '', truncated_count: 0, source_path: '/real/board.kicad_sch' }

  beforeEach(() => {
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    loadConversationMock.mockReset().mockResolvedValue([])
    listProjectSchematicsMock.mockReset().mockResolvedValue(ONE_SCHEMATIC_FOUND)
    checkSchematicMock.mockReset().mockResolvedValue(CLEAN_RESULT)
    openKicadMock.mockReset()
  })

  async function renderAppOnSchematic() {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    fireEvent.click(screen.getByRole('button', { name: 'Schematic' }))
    await waitFor(() => screen.getByText('board.kicad_sch'))
  }

  it('the Schematic tab renders the real SchematicAdvisor, not a not-built placeholder', async () => {
    await renderAppOnSchematic()

    expect(screen.queryByText(/not built yet/)).toBeNull()
  })

  it('a finished check is still shown after switching to another area and back to Schematic', async () => {
    await renderAppOnSchematic()
    fireEvent.click(screen.getByText('board.kicad_sch'))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))
    fireEvent.click(screen.getByRole('button', { name: 'Schematic' }))

    screen.getByText('No violations found.')
    expect(listProjectSchematicsMock).toHaveBeenCalledTimes(1)
  })

  it('switching to a different real project resets the previous project\'s check result', async () => {
    listProjectsMock.mockReset().mockResolvedValue(['project-a', 'project-b'])

    await renderAppOnSchematic()
    fireEvent.click(screen.getByText('board.kicad_sch'))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'project-b' }))
    fireEvent.click(screen.getByRole('button', { name: 'Schematic' }))

    expect(screen.queryByText('No violations found.')).toBeNull()
  })
})
