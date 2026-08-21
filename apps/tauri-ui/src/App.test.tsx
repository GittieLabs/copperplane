import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const submitJobMock = vi.fn()
const dispatchToolMock = vi.fn()
const listProjectsMock = vi.fn()
const listLibraryPartsMock = vi.fn()
const saveProjectMock = vi.fn()
const loadProjectMock = vi.fn()
const pickProjectDirectoryMock = vi.fn()
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
const saveDialogMock = vi.fn()
const openProjectFromDirectoryMock = vi.fn()
const listenMock = vi.fn()
const listLibrariesMock = vi.fn()
const syncLibraryMenuMock = vi.fn()
const setDesignMenuEnabledMock = vi.fn()
const loadPartMock = vi.fn()

vi.mock('./lib/ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
  dispatchTool: (...args: unknown[]) => dispatchToolMock(...args),
  MENU_SAVE_PROJECT_EVENT: 'menu://save-project',
  MENU_OPEN_PROJECT_EVENT: 'menu://open-project',
  MENU_OPEN_SETTINGS_EVENT: 'menu://open-settings',
  MENU_OPEN_DEFAULT_LIBRARY_EVENT: 'menu://open-library-default',
  MENU_MANAGE_LIBRARIES_EVENT: 'menu://manage-libraries',
  MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT: 'menu://design/schematic/open-kicad',
  MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT: 'menu://design/schematic/pick-manually',
  MENU_DESIGN_PCB_OPEN_KICAD_EVENT: 'menu://design/pcb/open-kicad',
  MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT: 'menu://design/enclosure/open-kicad',
  MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT: 'menu://design/enclosure/pick-pcb',
  MENU_DESIGN_ENCLOSURE_GENERATE_EVENT: 'menu://design/enclosure/generate',
  MENU_OPEN_LIBRARY_EVENT: 'menu://open-library',
}))

vi.mock('@tauri-apps/api/event', () => ({
  listen: (...args: unknown[]) => listenMock(...args),
}))

vi.mock('./lib/projects', () => ({
  listProjects: (...args: unknown[]) => listProjectsMock(...args),
  listLibraryParts: (...args: unknown[]) => listLibraryPartsMock(...args),
  saveProject: (...args: unknown[]) => saveProjectMock(...args),
  loadProject: (...args: unknown[]) => loadProjectMock(...args),
  pickProjectDirectory: (...args: unknown[]) => pickProjectDirectoryMock(...args),
  openProjectFromDirectory: (...args: unknown[]) => openProjectFromDirectoryMock(...args),
  loadConversation: (...args: unknown[]) => loadConversationMock(...args),
  appendConversationTurn: (...args: unknown[]) => appendConversationTurnMock(...args),
}))

vi.mock('./lib/settings', () => ({
  getCapabilities: (...args: unknown[]) => getCapabilitiesMock(...args),
}))

vi.mock('./lib/library', () => ({
  listLibraries: (...args: unknown[]) => listLibrariesMock(...args),
}))

vi.mock('./lib/menu', () => ({
  syncLibraryMenu: (...args: unknown[]) => syncLibraryMenuMock(...args),
  setDesignMenuEnabled: (...args: unknown[]) => setDesignMenuEnabledMock(...args),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: (...args: unknown[]) => shellOpenMock(...args),
}))

// CTX-312.1: EnclosurePanel's own real `exportEnclosure`/`getProjectDirectory`
// flow (`lib/enclosure.ts`) isn't otherwise mocked in this file (unlike
// `EnclosurePanel.test.tsx`, which mocks `../lib/enclosure` wholesale) --
// completing a real Export click-through here needs this plugin's real
// `save()` mocked too, matching the same real dialog `pickExportDestination`
// calls in the actual app.
vi.mock('@tauri-apps/plugin-dialog', () => ({
  save: (...args: unknown[]) => saveDialogMock(...args),
}))

vi.mock('./components/EnclosureViewer', () => ({
  EnclosureViewer: () => null,
}))

// CTX-316.1: only App.tsx's own view/prop wiring is under test here --
// Settings/LibraryArea's own real internals are covered by their own
// dedicated test files, not re-exercised through App.test.tsx.
vi.mock('./components/Settings', () => ({
  Settings: () => <div data-testid="settings-mock" />,
}))
vi.mock('./components/LibraryArea', () => ({
  LibraryArea: ({
    initialLibraryId,
    onSelectPart,
  }: {
    initialLibraryId?: string
    onSelectPart?: (partId: string) => void
  }) => (
    <div data-testid="library-area-mock" data-initial-library-id={initialLibraryId ?? ''}>
      {/* CTX-315.4: stands in for a real Part row's click -- App.tsx's own
       * routing from a Library click to the partDetail view is what's
       * under test here, not LibraryArea's own rendering (covered by
       * LibraryArea.test.tsx). */}
      <button type="button" onClick={() => onSelectPart?.('ATtiny85')}>
        select-part-mock
      </button>
    </div>
  ),
}))
vi.mock('./components/PartDetail', () => ({
  PartDetail: ({ initialPart }: { initialPart: { part_id: string } }) => (
    <div data-testid="part-detail-mock" data-part-id={initialPart.part_id} />
  ),
}))
vi.mock('./lib/partDetail', () => ({
  loadPart: (...args: unknown[]) => loadPartMock(...args),
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

// CTX-316.2: App.tsx now calls `listLibraries()` unconditionally on every
// mount to sync the native Library menu -- every test in this file renders
// `<App />`, so a real default here (not per-describe) keeps that new
// effect from rejecting in every single test that doesn't care about it.
beforeEach(() => {
  listLibrariesMock.mockReset().mockResolvedValue([])
  syncLibraryMenuMock.mockReset().mockResolvedValue(undefined)
  setDesignMenuEnabledMock.mockReset().mockResolvedValue(undefined)
  loadPartMock.mockReset()
})

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
    loadProjectMock.mockReset().mockImplementation((name: string) => Promise.resolve({ name, schema_version: 1 }))
    listenMock.mockReset().mockResolvedValue(() => {})
    openProjectFromDirectoryMock.mockReset()
    pickProjectDirectoryMock.mockReset()
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
    expect(appendConversationTurnMock).toHaveBeenCalledWith(
      'test-project',
      expect.objectContaining({ role: 'user', content: 'what does pin 3 do?', timestamp: expect.any(String) }),
    )
    expect(appendConversationTurnMock).toHaveBeenCalledWith(
      'test-project',
      expect.objectContaining({ role: 'assistant', content: 'Pin 3 is a GPIO pin.', timestamp: expect.any(String) }),
    )
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
        expect.objectContaining({ role: 'user', content: 'my favorite number is 42' }),
        expect.objectContaining({ role: 'assistant', content: 'Got it, 42.' }),
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

  it('CTX-313.1 TEST-007: Overview renders the real per-project dashboard alongside the existing, still-functional chat surface', async () => {
    await renderAppOnOverview()

    expect(screen.getByTestId('status-card-pcb').textContent).toContain('Not yet checked this session')
    expect(screen.getByTestId('status-card-enclosure').textContent).toContain('Not yet checked this session')
    expect(screen.getByPlaceholderText(/generate ATtiny85/)).toBeTruthy()
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
    loadProjectMock.mockReset().mockImplementation((name: string) => Promise.resolve({ name, schema_version: 1 }))
    listenMock.mockReset().mockResolvedValue(() => {})
    openProjectFromDirectoryMock.mockReset()
    pickProjectDirectoryMock.mockReset()
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    loadConversationMock.mockReset().mockResolvedValue([])
    listOpenBoardsMock.mockReset().mockResolvedValue(ONE_BOARD_OPEN)
    checkBoardMock.mockReset().mockResolvedValue(CLEAN_RESULT)
    openKicadMock.mockReset()
  })

  // CTX-311.5: EnclosurePanel now also stays mounted (matching BoardAdvisor/
  // SchematicAdvisor's own always-mounted pattern) and lists the same real
  // open boards via the same mocked listOpenBoards -- 'board.kicad_pcb'
  // appears in both panels' own pickers now, so PCB-tab queries must be
  // scoped to the real pcb-area container, not the whole document.
  function pcbArea() {
    return within(screen.getByTestId('pcb-area'))
  }

  async function renderAppOnPcb() {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    fireEvent.click(screen.getByRole('button', { name: 'PCB' }))
    await waitFor(() => pcbArea().getByText('board.kicad_pcb'))
  }

  it('a finished check is still shown after switching to another area and back to PCB', async () => {
    await renderAppOnPcb()
    fireEvent.click(pcbArea().getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    // CTX-311.5: EnclosurePanel now also stays mounted from the very
    // first render (it mirrors BoardAdvisor's own always-mounted
    // pattern), and calls listOpenBoards on its own initial mount too --
    // the real baseline call count here is no longer a fixed "1". What
    // this test actually verifies is that switching *away and back*
    // doesn't trigger a fresh scan, so it must compare against the real
    // count already reached, not a hardcoded literal.
    const callsBeforeSwitching = listOpenBoardsMock.mock.calls.length

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))
    fireEvent.click(screen.getByRole('button', { name: 'PCB' }))

    screen.getByText('No violations found.')
    expect(listOpenBoardsMock).toHaveBeenCalledTimes(callsBeforeSwitching)
  })

  it('switching to a different real project resets the previous project\'s check result', async () => {
    listProjectsMock.mockReset().mockResolvedValue(['project-a', 'project-b'])

    await renderAppOnPcb()
    fireEvent.click(pcbArea().getByText('board.kicad_pcb'))
    await waitFor(() => screen.getByText('No violations found.'))

    fireEvent.click(screen.getByRole('button', { name: 'project-b' }))
    fireEvent.click(screen.getByRole('button', { name: 'PCB' }))

    expect(screen.queryByText('No violations found.')).toBeNull()
  })
})

/** CTX-311.5: real user feedback exercising the actual running app --
 * navigating away from the Enclosure tab and back lost a just-generated
 * enclosure, since EnclosurePanel was the only area conditionally
 * mounted/unmounted (`{view.area === 'enclosure' && ...}`) rather than
 * always-mounted and hidden via CSS like BoardAdvisor/SchematicAdvisor
 * already were. Same persistence pattern, same test shape as those. */
describe('App: Enclosure tab persists across area switches', () => {
  const ONE_BOARD_OPEN = {
    status: 'boards_found' as const,
    candidates: [{ path: '/real/board.kicad_pcb', label: 'board.kicad_pcb' }],
  }
  const ENCLOSURE_RESULT = {
    glb_path: '/tmp/enclosure.glb',
    step_path: '/tmp/enclosure.step',
    unrecognized_holes: [] as { x_mm: number; y_mm: number; diameter_mm: number; recognized: false }[],
  }

  beforeEach(() => {
    loadProjectMock.mockReset().mockImplementation((name: string) => Promise.resolve({ name, schema_version: 1 }))
    listenMock.mockReset().mockResolvedValue(() => {})
    openProjectFromDirectoryMock.mockReset()
    pickProjectDirectoryMock.mockReset()
    saveProjectMock.mockReset().mockImplementation((project: unknown) => Promise.resolve(project))
    saveDialogMock.mockReset()
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    loadConversationMock.mockReset().mockResolvedValue([])
    listOpenBoardsMock.mockReset().mockResolvedValue(ONE_BOARD_OPEN)
    submitJobMock.mockReset()
  })

  function enclosureArea() {
    return within(screen.getByTestId('enclosure-area'))
  }

  it('a just-generated enclosure is still shown after switching to another area and back', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(ENCLOSURE_RESULT)))

    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    fireEvent.click(screen.getByRole('button', { name: 'Enclosure' }))
    await waitFor(() => enclosureArea().getByText('board.kicad_pcb'))
    fireEvent.click(enclosureArea().getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => enclosureArea().getByRole('button', { name: 'Export…' }))

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))
    fireEvent.click(screen.getByRole('button', { name: 'Enclosure' }))

    enclosureArea().getByRole('button', { name: 'Export…' })
    expect(submitJobMock).toHaveBeenCalledTimes(1)
  })

  it('CTX-312.1: a real successful Export immediately persists a real export_history entry, not deferred to a separate Save click', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(ENCLOSURE_RESULT)))
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve({ dest_path: '/real/dest/combined.step' })))
    saveDialogMock.mockResolvedValueOnce('/real/dest/combined.step')

    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    fireEvent.click(screen.getByRole('button', { name: 'Enclosure' }))
    await waitFor(() => enclosureArea().getByText('board.kicad_pcb'))
    fireEvent.click(enclosureArea().getByRole('button', { name: 'Generate Enclosure' }))
    await waitFor(() => enclosureArea().getByRole('button', { name: 'Export…' }))

    fireEvent.click(enclosureArea().getByRole('button', { name: 'Export…' }))
    fireEvent.click(enclosureArea().getByRole('button', { name: 'Choose location…' }))

    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(
        expect.objectContaining({
          export_history: [
            expect.objectContaining({ area: 'enclosure', dest_path: '/real/dest/combined.step' }),
          ],
        }),
      ),
    )
  })

  it('CTX-312.1: "Link to folder…" links the real picked directory and saves it', async () => {
    pickProjectDirectoryMock.mockResolvedValueOnce('/real/PCBs/test-project')

    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    fireEvent.click(screen.getByRole('button', { name: 'Link to folder…' }))

    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(
        expect.objectContaining({ directory: '/real/PCBs/test-project' }),
      ),
    )
    await waitFor(() => screen.getByRole('button', { name: 'Linked: /real/PCBs/test-project' }))
    // CTX-312.2: real user feedback -- a successful link/save previously
    // gave no visible confirmation at all, reading as "nothing happened."
    screen.getByText('Linked to /real/PCBs/test-project')
  })

  it('CTX-312.1: cancelling the folder picker never calls saveProject', async () => {
    pickProjectDirectoryMock.mockResolvedValueOnce(null)

    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    fireEvent.click(screen.getByRole('button', { name: 'Link to folder…' }))

    await waitFor(() => expect(pickProjectDirectoryMock).toHaveBeenCalled())
    expect(saveProjectMock).not.toHaveBeenCalled()
  })

  it('CTX-312.1: "Save Project" saves the current real project state on demand', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    await waitFor(() => {
      const button = screen.getByRole('button', { name: 'Save Project' }) as HTMLButtonElement
      expect(button.disabled).toBe(false)
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save Project' }))

    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(expect.objectContaining({ name: 'test-project' })),
    )
    // CTX-312.2: real user feedback -- a successful save previously gave
    // no visible confirmation at all, reading as "nothing happened."
    await waitFor(() => screen.getByText('Project saved.'))
  })

  it('CTX-312.3: the real native menu\'s own Save Project event runs the same real handleSaveProject flow as the button', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    // The menu-event listener effect re-subscribes whenever `currentProject`
    // changes (so `handleSaveProject`'s own closure is never stale) --
    // waiting for the button to become enabled is the real signal that the
    // *latest* subscription (the one with a real, loaded project) is in
    // place, not an earlier one registered while it was still null.
    await waitFor(() => {
      const button = screen.getByRole('button', { name: 'Save Project' }) as HTMLButtonElement
      expect(button.disabled).toBe(false)
    })

    const [, menuHandler] = listenMock.mock.calls.findLast(([event]) => event === 'menu://save-project')!
    await act(async () => {
      menuHandler()
    })

    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(expect.objectContaining({ name: 'test-project' })),
    )
    await waitFor(() => screen.getByText('Project saved.'))
  })

  it('CTX-312.3: the real native menu\'s own Open Project… event picks a real linked folder and selects it', async () => {
    pickProjectDirectoryMock.mockResolvedValueOnce('/real/PCBs/other-project')
    openProjectFromDirectoryMock.mockResolvedValueOnce({
      name: 'other-project', directory: '/real/PCBs/other-project',
    })

    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    await waitFor(() => {
      const button = screen.getByRole('button', { name: 'Save Project' }) as HTMLButtonElement
      expect(button.disabled).toBe(false)
    })

    const [, menuHandler] = listenMock.mock.calls.findLast(([event]) => event === 'menu://open-project')!
    await act(async () => {
      menuHandler()
    })

    await waitFor(() => expect(openProjectFromDirectoryMock).toHaveBeenCalledWith('/real/PCBs/other-project'))
    // The Rail prefixes "> " onto whichever project is currently
    // selected (Rail.tsx) -- opening a project also selects it, so the
    // real accessible name here is "> other-project", not the bare name.
    await waitFor(() => screen.getByRole('button', { name: '> other-project' }))
  })

  it('CTX-316.1: the Settings… menu event shows the real Settings screen', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    const [, menuHandler] = listenMock.mock.calls.findLast(([event]) => event === 'menu://open-settings')!
    act(() => menuHandler())

    await waitFor(() => screen.getByTestId('settings-mock'))
  })

  it('CTX-316.1: the Default Library menu event opens Library deep-linked to Default', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    const [, menuHandler] = listenMock.mock.calls.findLast(
      ([event]) => event === 'menu://open-library-default',
    )!
    act(() => menuHandler())

    await waitFor(() => {
      const el = screen.getByTestId('library-area-mock')
      expect(el.getAttribute('data-initial-library-id')).toBe('default')
    })
  })

  it('CTX-316.1: the Manage Libraries… menu event opens Library with no deep link', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    const [, menuHandler] = listenMock.mock.calls.findLast(
      ([event]) => event === 'menu://manage-libraries',
    )!
    act(() => menuHandler())

    await waitFor(() => {
      const el = screen.getByTestId('library-area-mock')
      expect(el.getAttribute('data-initial-library-id')).toBe('')
    })
  })

  it('CTX-316.1: a Design menu event switches to the matching area and runs the real handler', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))
    // Starts on Overview -- confirms the PCB area really was hidden
    // before the menu event, not just already active.
    expect(screen.getByTestId('pcb-area').className).toContain('hidden')

    const [, menuHandler] = listenMock.mock.calls.findLast(
      ([event]) => event === 'menu://design/pcb/open-kicad',
    )!
    act(() => menuHandler())

    await waitFor(() => expect(screen.getByTestId('pcb-area').className).not.toContain('hidden'))
    await waitFor(() => expect(openKicadMock).toHaveBeenCalled())
  })

  it('CTX-305.4: every area wrapper stretches full width when active, not just visible', async () => {
    // Real regression: these wrappers previously had no width class at
    // all when active (just `undefined`), which silently shrank them to
    // content width under <main>'s `flex-col items-center` -- the exact
    // class of bug CTX-305.2 already fixed once, reintroduced here by
    // CTX-306.2's own always-mounted wrapper divs. `not.toContain('hidden')`
    // alone (as the test above checks) would not have caught this --
    // asserting the real class value does.
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    for (const [label, testId] of [
      ['Components', 'components-area'],
      ['Schematic', 'schematic-area'],
      ['PCB', 'pcb-area'],
      ['Enclosure', 'enclosure-area'],
    ] as const) {
      fireEvent.click(screen.getByRole('button', { name: label }))
      await waitFor(() => expect(screen.getByTestId(testId).className).toBe('w-full'))
    }
  })

  it('CTX-316.1: a Design menu event with no project open is a real, silent no-op', async () => {
    listProjectsMock.mockResolvedValueOnce([])
    // openKicadMock isn't reset by this describe's own beforeEach --
    // clearing it here isolates this assertion from calls other tests
    // in this same describe block may have already made.
    openKicadMock.mockClear()

    render(<App />)
    await waitFor(() => screen.getByText('Create a project on the left to get started.'))

    const [, menuHandler] = listenMock.mock.calls.findLast(
      ([event]) => event === 'menu://design/pcb/open-kicad',
    )!
    act(() => menuHandler())

    expect(openKicadMock).not.toHaveBeenCalled()
    screen.getByText('Create a project on the left to get started.')
  })

  it('TEST-008: calls syncLibraryMenu with the real fetched library list on mount', async () => {
    const libraries = [{ id: 'default', name: 'Default', part_count: 0, symbol_count: 0, footprint_count: 0 }]
    listLibrariesMock.mockReset().mockResolvedValueOnce(libraries)

    render(<App />)

    await waitFor(() => expect(syncLibraryMenuMock).toHaveBeenCalledWith(libraries))
  })

  it('TEST-009: calls setDesignMenuEnabled(true) once a project is selected, and (false) when none is', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    await waitFor(() => expect(setDesignMenuEnabledMock).toHaveBeenCalledWith(true))

    fireEvent.click(screen.getByRole('button', { name: '⚙ Settings' }))

    await waitFor(() => expect(setDesignMenuEnabledMock).toHaveBeenCalledWith(false))
  })

  it('TEST-010: the Open Library menu event sets view to library with the real payload as initialLibraryId', async () => {
    render(<App />)
    await waitFor(() => screen.getByPlaceholderText(/generate ATtiny85/))

    const [, menuHandler] = listenMock.mock.calls.findLast(([event]) => event === 'menu://open-library')!
    act(() => menuHandler({ payload: 'esp32-boards' }))

    await waitFor(() => {
      const el = screen.getByTestId('library-area-mock')
      expect(el.getAttribute('data-initial-library-id')).toBe('esp32-boards')
    })
  })

  it('CTX-315.4: selecting a Part in the Library loads its real full record and shows Part Detail', async () => {
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8' })

    await renderAppOnOverview()
    fireEvent.click(screen.getByRole('button', { name: '0 parts' }))
    await waitFor(() => screen.getByTestId('library-area-mock'))

    fireEvent.click(screen.getByRole('button', { name: 'select-part-mock' }))

    await waitFor(() => expect(loadPartMock).toHaveBeenCalledWith('ATtiny85'))
    await waitFor(() => {
      const el = screen.getByTestId('part-detail-mock')
      expect(el.getAttribute('data-part-id')).toBe('ATtiny85')
    })
  })

  it('CTX-315.4: "← Library" from Part Detail returns to the Library view', async () => {
    loadPartMock.mockResolvedValueOnce({ part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8' })

    await renderAppOnOverview()
    fireEvent.click(screen.getByRole('button', { name: '0 parts' }))
    fireEvent.click(screen.getByRole('button', { name: 'select-part-mock' }))
    await waitFor(() => screen.getByTestId('part-detail-mock'))

    fireEvent.click(screen.getByRole('button', { name: '← Library' }))

    await waitFor(() => screen.getByTestId('library-area-mock'))
    expect(screen.queryByTestId('part-detail-mock')).toBeNull()
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
    loadProjectMock.mockReset().mockImplementation((name: string) => Promise.resolve({ name, schema_version: 1 }))
    listenMock.mockReset().mockResolvedValue(() => {})
    openProjectFromDirectoryMock.mockReset()
    pickProjectDirectoryMock.mockReset()
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
