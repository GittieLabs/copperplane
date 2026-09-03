import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const submitJobMock = vi.fn()
const writeTextMock = vi.fn()
const dispatchToolMock = vi.fn()
const listProjectsMock = vi.fn()
const listLibraryPartsMock = vi.fn()
const saveProjectMock = vi.fn()
const loadProjectMock = vi.fn()
const pickProjectDirectoryMock = vi.fn()
const loadConversationMock = vi.fn()
const appendConversationTurnMock = vi.fn()
const getCapabilitiesMock = vi.fn()
const getConfigMock = vi.fn()
const updateConfigMock = vi.fn()
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

/** SPEC-336 removed the auto-open. `App` used to select `names[0]` from a
 *  sorted project list on launch, so every test below simply rendered and
 *  found itself inside a project. Launch now lands on `NoProjectLanding` and
 *  decides nothing on the user's behalf, so a test that means to exercise a
 *  project has to open one -- exactly as a person now does.
 *
 *  Renders and opens the first project in the rail. A no-op when there are
 *  none, so the empty-state tests keep working unchanged. */
async function renderAppOpen(projectName?: string) {
  const utils = render(<App />)
  const name = projectName ?? (await listProjectsMock.mock.results[0]?.value ?? [])[0]
  if (name) {
    const button = await screen
      .findByRole('button', { name }, { timeout: 300 })
      .catch(() => null)
    if (button) fireEvent.click(button)
  }
  return utils
}

vi.mock('@tauri-apps/plugin-clipboard-manager', () => ({
  writeText: (...args: unknown[]) => writeTextMock(...args),
}))

vi.mock('./lib/ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
  dispatchTool: (...args: unknown[]) => dispatchToolMock(...args),
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
  MENU_DESIGN_SCHEMATIC_RUN_REVIEW_EVENT: 'menu://design/schematic/run-review',
  MENU_DESIGN_PCB_RUN_REVIEW_EVENT: 'menu://design/pcb/run-review',
  MENU_DESIGN_ENCLOSURE_RUN_REVIEW_EVENT: 'menu://design/enclosure/run-review',
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
  getConfig: (...args: unknown[]) => getConfigMock(...args),
  updateConfig: (...args: unknown[]) => updateConfigMock(...args),
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

// CTX-318.3: SchematicAdvisor and BoardAdvisor are NOT mocked in this file
// (only their underlying `lib/boardAdvisor` calls are) -- both real
// components stay mounted here (App.tsx keeps them mounted across every
// area tab, hidden via CSS), and both now mount a real AgentChat of their
// own. Left unmocked, this collided for real: the real AgentChat's own
// "Send" button and message input made `sendMessage`'s `getByRole('button',
// { name: 'Send' })` / `getByPlaceholderText` ambiguous the instant both
// Schematic and PCB AgentChat panels were simultaneously in the DOM -- the
// same AgentChat-rendered-unmocked trap already caught and fixed in
// PartDetail.test.tsx (CTX-318.2), recurring here for a third time.
vi.mock('./components/AgentChat', () => ({
  AgentChat: ({ area, scopeId }: { area: string; scopeId: string }) => (
    <p>AgentChat stub: area={area} scopeId={scopeId}</p>
  ),
}))

// CTX-319.3: same real reason as the AgentChat stub immediately above --
// SchematicAdvisor/BoardAdvisor are real and unmocked here, and now both
// mount a real ReviewPanel too. Stubbed module-level so it (and every
// future consumer) is covered without a fix per area, matching what
// CTX-318.4 already confirmed about this exact stub pattern.
vi.mock('./components/ReviewPanel', () => ({
  ReviewPanel: ({
    area,
    scopeId,
    menuCommand,
  }: {
    area: string
    scopeId: string
    menuCommand?: { area: string; command: string; nonce: number } | null
  }) => (
    <p>
      ReviewPanel stub: area={area} scopeId={scopeId}
      {menuCommand && ` menuCommand=${menuCommand.area}:${menuCommand.command}:${menuCommand.nonce}`}
    </p>
  ),
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
  // SPEC-336: onboarding is "already dismissed" by default, so the existing
  // tests exercise the app rather than the welcome screen. The first-run
  // tests below set this deliberately.
  getConfigMock.mockReset().mockResolvedValue({ onboarding_completed: true })
  updateConfigMock.mockReset().mockImplementation(async (patch: object) => ({ ...patch }))
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
  await renderAppOpen()
  await waitFor(() => screen.getByPlaceholderText(/ask a question/))
}

function sendMessage(text: string) {
  fireEvent.change(screen.getByPlaceholderText(/ask a question/), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
}

describe('App: Overview plain chat', () => {
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

  it('TEST-004: an unrecognized message is a plain chat turn against llm.chat, rendering the real reply, and persists both turns', async () => {
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.resolve({ text: 'Pin 3 is a GPIO pin.', usage: null, model: null })),
    )

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
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.resolve({ text: 'Got it, 42.', usage: null, model: null })),
    )
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve({ text: '42.', usage: null, model: null })))

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

  it('TEST-007: a fresh install with no projects shows the empty state, not a broken chat surface', async () => {
    listProjectsMock.mockResolvedValueOnce([])

    await renderAppOpen()

    await waitFor(() => screen.getByRole('button', { name: 'New project' }))
    expect(screen.queryByPlaceholderText(/ask a question/)).toBeNull()
  })

  it('TEST-008b: the Components area tab renders the real ComponentDiscovery search box, not a placeholder', async () => {
    await renderAppOnOverview()

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))

    await waitFor(() => screen.getByPlaceholderText(/search for a part/))
    // Scoped to this area on purpose. Every area stays mounted (hidden), so a
    // global search for "not built yet" also matches the Enclosure tab's own
    // deliberately-disabled review panel -- which says nothing about whether
    // Components rendered.
    expect(
      within(screen.getByTestId('components-area')).queryByText(/not built yet/),
    ).toBeNull()
  })

  it('TEST-008: loads an existing project\'s persisted conversation into view on first render', async () => {
    loadConversationMock.mockResolvedValueOnce([
      { role: 'user', content: 'hello from before' },
      { role: 'assistant', content: 'hi again' },
    ])

    await renderAppOpen()

    await waitFor(() => screen.getByText('> hello from before'))
    screen.getByText('hi again')
    expect(loadConversationMock).toHaveBeenCalledWith('test-project')
  })

  it('Overview shows the project chat, and no per-area status cards', async () => {
    await renderAppOnOverview()

    // CTX-313.1's dashboard was removed: the cards said "Not yet checked this
    // session" for two areas whose checks run on demand on their own tabs, and
    // for two that have no check at all.
    expect(screen.queryByTestId('status-card-pcb')).toBeNull()
    expect(screen.queryByTestId('status-card-enclosure')).toBeNull()
    expect(screen.getByPlaceholderText(/ask a question/)).toBeTruthy()
  })
})

/** CTX-318.5: Overview finishes CTX-306.2's own always-mounted pattern
 * migration -- it was "simply never included when that fix was made."
 * A half-typed question in the old chat input, and a half-edited intent
 * draft, must both survive switching to another area tab and back, and
 * both must still reset on a genuine project switch (this file's own
 * established convention for every other area). */
describe('App: Overview tab persists across area switches, resets on project switch', () => {
  beforeEach(() => {
    loadProjectMock.mockReset().mockImplementation((name: string) => Promise.resolve({ name, schema_version: 1 }))
    listenMock.mockReset().mockResolvedValue(() => {})
    openProjectFromDirectoryMock.mockReset()
    pickProjectDirectoryMock.mockReset()
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    loadConversationMock.mockReset().mockResolvedValue([])
  })

  it('a half-typed question in the old chat input survives switching to another area and back', async () => {
    await renderAppOnOverview()

    fireEvent.change(screen.getByPlaceholderText(/ask a question/), { target: { value: 'half-typed question' } })
    fireEvent.click(screen.getByRole('button', { name: 'Components' }))
    await waitFor(() => screen.getByPlaceholderText(/search for a part/))
    fireEvent.click(screen.getByRole('button', { name: 'Overview' }))

    expect((screen.getByPlaceholderText(/ask a question/) as HTMLInputElement).value).toBe('half-typed question')
  })

  it('switching to a different real project resets the previous project\'s half-typed question', async () => {
    listProjectsMock.mockReset().mockResolvedValue(['project-a', 'project-b'])
    await renderAppOnOverview()
    fireEvent.change(screen.getByPlaceholderText(/ask a question/), { target: { value: 'half-typed question' } })

    fireEvent.click(screen.getByText('project-b'))

    await waitFor(() =>
      expect((screen.getByPlaceholderText(/ask a question/) as HTMLInputElement).value).toBe(''),
    )
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
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
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
    // SPEC-326 §2.7: picking a board now also measures its components, so the
    // enclosure height can start from what the parts need instead of an
    // arbitrary 20. That call must not consume the mockResolvedValueOnce
    // queue the generate/export assertions below depend on, so it is answered
    // by route rather than by position.
    submitJobMock.mockImplementation((method: string) =>
      method === 'kicad.component_envelopes'
        ? Promise.resolve(fakeJobHandle(Promise.reject(new Error('not measured in this test'))))
        : Promise.resolve(fakeJobHandle(Promise.resolve(ENCLOSURE_RESULT))),
    )
  })

  function enclosureArea() {
    return within(screen.getByTestId('enclosure-area'))
  }

  it('a just-generated enclosure is still shown after switching to another area and back', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(ENCLOSURE_RESULT)))

    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
    fireEvent.click(screen.getByRole('button', { name: 'Enclosure' }))
    await waitFor(() => enclosureArea().getByText('board.kicad_pcb'))
    fireEvent.click(enclosureArea().getByRole('button', { name: 'Generate Enclosure' }))

    await waitFor(() => enclosureArea().getByRole('button', { name: 'Export…' }))

    fireEvent.click(screen.getByRole('button', { name: 'Components' }))
    fireEvent.click(screen.getByRole('button', { name: 'Enclosure' }))

    enclosureArea().getByRole('button', { name: 'Export…' })
    // Generated exactly once -- the measurement call is a separate route and
    // is deliberately not counted here.
    expect(
      submitJobMock.mock.calls.filter(([m]) => m === 'freecad.generate_enclosure'),
    ).toHaveLength(1)
  })

  it('CTX-312.1: a real successful Export immediately persists a real export_history entry, not deferred to a separate Save click', async () => {
    // Answered by route, not by position: the board measurement added in
    // SPEC-326 §2.7 fires before Generate and would otherwise consume the
    // first queued response.
    submitJobMock.mockImplementation((method: string) => {
      if (method === 'kicad.component_envelopes') {
        return Promise.resolve(fakeJobHandle(Promise.reject(new Error('not measured in this test'))))
      }
      if (method === 'freecad.export_enclosure') {
        return Promise.resolve(fakeJobHandle(Promise.resolve({ dest_path: '/real/dest/combined.step' })))
      }
      return Promise.resolve(fakeJobHandle(Promise.resolve(ENCLOSURE_RESULT)))
    })
    saveDialogMock.mockResolvedValueOnce('/real/dest/combined.step')

    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
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

    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    fireEvent.click(screen.getByRole('button', { name: 'Choose project folder…' }))

    await waitFor(() =>
      expect(saveProjectMock).toHaveBeenCalledWith(
        expect.objectContaining({ directory: '/real/PCBs/test-project' }),
      ),
    )
    // Once a folder exists the header stops printing its path and offers to
    // copy it instead -- the path is long and was only clutter.
    await waitFor(() =>
      within(screen.getByTestId('project-header')).getByRole('button', { name: 'Copy project path' }),
    )
    // CTX-312.2: real user feedback -- a successful link/save previously
    // gave no visible confirmation at all, reading as "nothing happened."
    screen.getByText('Linked to /real/PCBs/test-project')
  })

  it('CTX-312.1: cancelling the folder picker never calls saveProject', async () => {
    pickProjectDirectoryMock.mockResolvedValueOnce(null)

    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    fireEvent.click(screen.getByRole('button', { name: 'Choose project folder…' }))

    await waitFor(() => expect(pickProjectDirectoryMock).toHaveBeenCalled())
    expect(saveProjectMock).not.toHaveBeenCalled()
  })



  it('CTX-312.3: the real native menu\'s own Open Project… event picks a real linked folder and selects it', async () => {
    pickProjectDirectoryMock.mockResolvedValueOnce('/real/PCBs/other-project')
    openProjectFromDirectoryMock.mockResolvedValueOnce({
      name: 'other-project', directory: '/real/PCBs/other-project',
    })

    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
    // Waiting on the project NAME in the header: the Save Project button used
    // to serve as this signal, and no longer exists.
    await waitFor(() => screen.getByText('test-project'))

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
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    const [, menuHandler] = listenMock.mock.calls.findLast(([event]) => event === 'menu://open-settings')!
    act(() => menuHandler())

    await waitFor(() => screen.getByTestId('settings-mock'))
  })

  it('CTX-316.1: the Default Library menu event opens Library deep-linked to Default', async () => {
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

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
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

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
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
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

  it('CTX-319.6: a Design > PCB > Run Review menu event switches to PCB and forwards the real menuCommand to ReviewPanel', async () => {
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
    expect(screen.getByTestId('pcb-area').className).toContain('hidden')

    const [, menuHandler] = listenMock.mock.calls.findLast(
      ([event]) => event === 'menu://design/pcb/run-review',
    )!
    act(() => menuHandler())

    await waitFor(() => expect(screen.getByTestId('pcb-area').className).not.toContain('hidden'))
    await waitFor(() =>
      expect(within(screen.getByTestId('pcb-area')).getByText(/ReviewPanel stub/).textContent).toContain(
        'menuCommand=pcb:run_review:0',
      ),
    )
  })

  it('CTX-305.4: every area wrapper stretches full width when active, not just visible', async () => {
    // Real regression: these wrappers previously had no width class at
    // all when active (just `undefined`), which silently shrank them to
    // content width under <main>'s `flex-col items-center` -- the exact
    // class of bug CTX-305.2 already fixed once, reintroduced here by
    // CTX-306.2's own always-mounted wrapper divs. `not.toContain('hidden')`
    // alone (as the test above checks) would not have caught this --
    // asserting the real class value does.
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    for (const [label, testId] of [
      ['Overview', 'overview-area'],
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

    await renderAppOpen()
    await waitFor(() => screen.getByRole('button', { name: 'New project' }))

    const [, menuHandler] = listenMock.mock.calls.findLast(
      ([event]) => event === 'menu://design/pcb/open-kicad',
    )!
    act(() => menuHandler())

    expect(openKicadMock).not.toHaveBeenCalled()
    screen.getByRole('button', { name: 'New project' })
  })

  it('TEST-008: calls syncLibraryMenu with the real fetched library list on mount', async () => {
    const libraries = [{ id: 'default', name: 'Default', part_count: 0, symbol_count: 0, footprint_count: 0 }]
    listLibrariesMock.mockReset().mockResolvedValueOnce(libraries)

    await renderAppOpen()

    await waitFor(() => expect(syncLibraryMenuMock).toHaveBeenCalledWith(libraries))
  })

  it('TEST-009: calls setDesignMenuEnabled(true) once a project is selected, and (false) when none is', async () => {
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    await waitFor(() => expect(setDesignMenuEnabledMock).toHaveBeenCalledWith(true))

    fireEvent.click(screen.getByRole('button', { name: '⚙ Settings' }))

    await waitFor(() => expect(setDesignMenuEnabledMock).toHaveBeenCalledWith(false))
  })

  it('TEST-010: the Open Library menu event sets view to library with the real payload as initialLibraryId', async () => {
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

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
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))
    fireEvent.click(screen.getByRole('button', { name: 'Schematic' }))
    await waitFor(() => screen.getByText('board.kicad_sch'))
  }

  it('the Schematic tab renders the real SchematicAdvisor, not a not-built placeholder', async () => {
    await renderAppOnSchematic()

    // Scoped for the same reason as TEST-008b above.
    expect(
      within(screen.getByTestId('schematic-area')).queryByText(/not built yet/),
    ).toBeNull()
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

describe('App: the project header', () => {
  /* "showing the complete paths to the linked project or project folder could
     show a long string and only clutters the screen. Neither offers enough
     value to be statically shown." So: the KiCad project by FILE NAME, its
     full path on hover, and the project folder behind a copy button. */
  async function renderLinked() {
    loadProjectMock.mockResolvedValue({
      name: 'test-project',
      directory: '/real/PCBs/test-project',
      kicad_project_path: '/elsewhere/Blinky/Blinky.kicad_pro',
    })
    await renderAppOpen()
    await waitFor(() => screen.getByText('test-project'))
    return within(screen.getByTestId('project-header'))
  }

  it('shows the KiCad project by name, not by path', async () => {
    const header = await renderLinked()

    expect(header.getByText('Blinky')).toBeTruthy()
    expect(header.queryByText('/elsewhere/Blinky/Blinky.kicad_pro')).toBeNull()
  })

  it('keeps the full path available without spending a line on it', async () => {
    const header = await renderLinked()

    expect(
      header.getByTitle('/elsewhere/Blinky/Blinky.kicad_pro'),
    ).toBeTruthy()
  })

  it('does not print the project folder path at all', async () => {
    const header = await renderLinked()

    expect(header.queryByText('/real/PCBs/test-project')).toBeNull()
    expect(header.getByRole('button', { name: 'Copy project path' })).toBeTruthy()
  })

  it('copies the project folder path', async () => {
    writeTextMock.mockResolvedValue(undefined)
    const header = await renderLinked()

    fireEvent.click(header.getByRole('button', { name: 'Copy project path' }))

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledWith('/real/PCBs/test-project'))
    await waitFor(() => header.getByText('Copied'))
  })

  it('names what the button changes, rather than saying "folder"', async () => {
    const header = await renderLinked()

    // "Change folder…" sat beside two different paths and could be read as
    // either. This one sits on the KiCad project line and says Change.
    expect(header.getByRole('button', { name: 'Change' })).toBeTruthy()
  })

  it('offers to link a KiCad project when none is linked', async () => {
    loadProjectMock.mockResolvedValue({ name: 'test-project', directory: '/real/PCBs/test-project' })
    await renderAppOpen()

    await waitFor(() => screen.getByText('test-project'))
    const header = within(screen.getByTestId('project-header'))
    expect(header.getByText('none yet')).toBeTruthy()
    expect(header.getByRole('button', { name: 'Link' })).toBeTruthy()
  })

  it('offers a folder only while the project has none', async () => {
    loadProjectMock.mockResolvedValue({ name: 'test-project' })
    await renderAppOpen()

    await waitFor(() => screen.getByText('test-project'))
    const header = within(screen.getByTestId('project-header'))
    expect(header.getByRole('button', { name: 'Choose project folder…' })).toBeTruthy()
    expect(header.queryByRole('button', { name: 'Copy project path' })).toBeNull()
  })

  it('has no Save Project button -- every field persists as it changes', async () => {
    await renderLinked()

    expect(screen.queryByRole('button', { name: 'Save Project' })).toBeNull()
  })
})

describe('App: loading the project list', () => {
  /* Reported: "The projects can take some time to load and in the meantime,
     we are left with an empty main content section and no indication that
     projects are loading... I am not certain that we would not run into a
     race condition that mixes a new project with an existing but just loaded
     project."

     The race was real. handleCreateProject appends to `projects`, and the
     in-flight listProjects() then REPLACED that state with the list as it was
     before the new project existed -- so the project vanished from the rail. */

  it('says the projects are loading instead of showing a blank area', async () => {
    let release: (v: string[]) => void = () => {}
    listProjectsMock.mockReturnValue(new Promise<string[]>((r) => { release = r }))
    await renderAppOpen()

    expect(await screen.findByText('Loading your projects…')).toBeTruthy()

    await act(async () => { release([]) })
    await waitFor(() => screen.getByRole('button', { name: 'New project' }))
  })

  it('does not offer to create a project until the list has loaded', async () => {
    let release: (v: string[]) => void = () => {}
    listProjectsMock.mockReturnValue(new Promise<string[]>((r) => { release = r }))
    await renderAppOpen()

    await waitFor(() => {
      const button = screen.getByRole('button', { name: '+ New…' }) as HTMLButtonElement
      expect(button.disabled).toBe(true)
    })

    await act(async () => { release([]) })
    await waitFor(() => {
      const button = screen.getByRole('button', { name: '+ New…' }) as HTMLButtonElement
      expect(button.disabled).toBe(false)
    })
  })

  it('never drops a project created while the list was still in flight', async () => {
    let release: (v: string[]) => void = () => {}
    listProjectsMock.mockReturnValue(new Promise<string[]>((r) => { release = r }))
    await renderAppOpen()
    await waitFor(() => screen.getByText('Loading your projects…'))

    // The defence in depth: even if creation happens mid-flight, the list
    // that arrives afterwards merges rather than replaces.
    await act(async () => { release(['older-project']) })

    // Queried by role: a selected project renders as '> ' + name, two text
    // nodes, so an exact text match misses it.
    await waitFor(() => screen.getByRole('button', { name: /older-project/ }))
  })
})

describe('App: creating a project owns the main area', () => {
  /* SPEC-335: "We should make creating a project do everything in the main
     content area and not show our tabbed view until the project is
     submitted." */
  async function openWizard() {
    listProjectsMock.mockResolvedValue([])
    await renderAppOpen()
    await waitFor(() => screen.getByRole('button', { name: 'New project' }))
    fireEvent.click(screen.getByRole('button', { name: '+ New…' }))
    await waitFor(() => screen.getByText(/step 1 of 4/))
  }

  it('opens the wizard in the main area, not an inline sidebar form', async () => {
    await openWizard()

    // The title appears twice by design -- as the heading and as the current
    // item in the step list -- so this asks for the heading specifically.
    expect(screen.getByRole('heading', { name: 'Name your project' })).toBeTruthy()
  })

  it('does not show the tabbed project view while the wizard is open', async () => {
    await openWizard()

    // The tabs belong to a project that does not exist yet.
    expect(screen.queryByRole('button', { name: 'Overview' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Schematic' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Enclosure' })).toBeNull()
  })

  it('creates no project when the wizard is cancelled', async () => {
    await openWizard()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => screen.getByRole('button', { name: 'New project' }))
    expect(saveProjectMock).not.toHaveBeenCalled()
  })

  it('shows the tabbed view only once the wizard completes', async () => {
    await openWizard()
    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'blinky' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    // Both remaining steps are skippable -- SPEC-336's no-trapping rule.
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))

    // The last step creates the project on whichever tab is chosen.
    await waitFor(() => screen.getByRole('button', { name: 'overview' }))
    fireEvent.click(screen.getByRole('button', { name: 'overview' }))

    await waitFor(() => expect(saveProjectMock).toHaveBeenCalledWith({ name: 'blinky' }))
    await waitFor(() => screen.getByRole('button', { name: 'Overview' }))
  })
})

describe('App: an unlinked project says what is unavailable', () => {
  beforeEach(() => {
    // The banner lives on a loaded project, so the list has to resolve first.
    listProjectsMock.mockReset().mockResolvedValue(['test-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    saveProjectMock.mockReset().mockImplementation(async (p: unknown) => p)
  })

  /* SPEC-335 Phase 5, following SPEC-336's no-trapping rule: skipping the
     KiCad link is allowed, so the app has to say what that costs rather than
     leaving the user to discover it by watching features fail one at a time. */
  it('shows a banner naming what cannot run, with a way to fix it', async () => {
    loadProjectMock.mockResolvedValue({ name: 'test-project', directory: '/d' })
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    await waitFor(() => screen.getByText(/No KiCad project linked, so board and schematic checks/))
    expect(screen.getByRole('button', { name: 'Link one' })).toBeTruthy()
  })

  it('says nothing once a project is linked', async () => {
    loadProjectMock.mockResolvedValue({
      name: 'test-project', directory: '/d', kicad_project_path: '/p/Blinky.kicad_pro',
    })
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    expect(screen.queryByText(/No KiCad project linked/)).toBeNull()
  })

  it('cannot be dismissed into silence', async () => {
    // A banner that can be dismissed forever returns the user to an
    // unexplained broken app with no route back.
    loadProjectMock.mockResolvedValue({ name: 'test-project', directory: '/d' })
    await renderAppOpen()
    await waitFor(() => screen.getByPlaceholderText(/ask a question/))

    await waitFor(() => screen.getByText(/No KiCad project linked/))
    expect(screen.queryByRole('button', { name: /Dismiss|Ignore/ })).toBeNull()
  })
})

/** CTX-336.1 Phase 3-4: the launch view, closing a project, and first run.
 *
 *  SPEC-336 §1 on the behaviour these replace: launch "opens the
 *  alphabetically first project, not the most recently used one. Stable, and
 *  meaningless", and the maintainer's concern that it "could have moved, is
 *  corrupted, or isn't the project the user expected to open." */
describe('App: launch, closing a project, and first run', () => {
  beforeEach(() => {
    listProjectsMock.mockReset().mockResolvedValue(['alpha-project', 'zeta-project'])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    loadProjectMock.mockReset().mockResolvedValue({ name: 'alpha-project' })
    loadConversationMock.mockReset().mockResolvedValue([])
    getCapabilitiesMock.mockReset().mockResolvedValue({
      kicad_available: true, kicad_socket_path_checked: '/tmp/kicad/api.sock',
      freecad_available: true, freecad_path_checked: '/f/freecadcmd', freecad_error: null,
      kicad_cli_available: true, kicad_cli_path_checked: '/k/kicad-cli',
      kicad_cli_path_source: 'install', kicad_cli_error: null,
      llm_providers: ['anthropic'], log_path: '/l', python_version: '3.11.9',
      storage_root: '/s', github_token_configured: false,
      configured_secret_refs: ['anthropic_api_key'],
    })
  })

  it('TEST-006: lands on the launch view rather than opening a project', async () => {
    render(<App />)

    // The landing view, not `alpha-project` -- which is exactly what the old
    // `names[0]` would have picked out of this sorted list.
    expect(await screen.findByRole('button', { name: 'New project' })).toBeTruthy()
    expect(screen.queryByPlaceholderText(/ask a question/)).toBeNull()
    expect(loadProjectMock).not.toHaveBeenCalled()
  })

  it('still opens a project when the user picks one', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'zeta-project' }))

    expect(await screen.findByPlaceholderText(/ask a question/)).toBeTruthy()
  })

  it('TEST-007: closing a project returns to the launch view and writes nothing', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'alpha-project' }))
    await screen.findByPlaceholderText(/ask a question/)
    saveProjectMock.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Close project' }))

    expect(await screen.findByRole('button', { name: 'New project' })).toBeTruthy()
    expect(screen.queryByPlaceholderText(/ask a question/)).toBeNull()
    // Nothing to flush: every project edit already writes through.
    expect(saveProjectMock).not.toHaveBeenCalled()
  })

  it('shows the welcome screen on a genuinely first run', async () => {
    getConfigMock.mockResolvedValue({})

    render(<App />)

    expect(await screen.findByText('Welcome to Copperplane')).toBeTruthy()
    // And not the landing view underneath it.
    expect(screen.queryByRole('button', { name: 'New project' })).toBeNull()
  })

  it('does not show the welcome screen again once it has been dismissed', async () => {
    render(<App />)

    expect(await screen.findByRole('button', { name: 'New project' })).toBeTruthy()
    expect(screen.queryByText('Welcome to Copperplane')).toBeNull()
  })

  it('records the dismissal when the user skips, so it does not reappear', async () => {
    getConfigMock.mockResolvedValue({})
    render(<App />)
    await screen.findByText('Welcome to Copperplane')

    fireEvent.click(screen.getByRole('button', { name: /Skip for now/ }))

    await waitFor(() =>
      expect(updateConfigMock).toHaveBeenCalledWith({ onboarding_completed: true }),
    )
    expect(await screen.findByRole('button', { name: 'New project' })).toBeTruthy()
  })

  it('an unreadable config does not trap the user in the wizard', async () => {
    /** Failing toward "already onboarded" is the safe direction: the banner
     *  still tells them what is missing, and the wizard is still reachable. */
    getConfigMock.mockRejectedValue(new Error('config.json is corrupt'))

    render(<App />)

    expect(await screen.findByRole('button', { name: 'New project' })).toBeTruthy()
    expect(screen.queryByText('Welcome to Copperplane')).toBeNull()
  })

  it('shows a requirements banner for what is actually missing, and routes back to setup', async () => {
    getCapabilitiesMock.mockResolvedValue({
      kicad_available: false, kicad_socket_path_checked: '/tmp/kicad/api.sock',
      freecad_available: true, freecad_path_checked: '/f/freecadcmd', freecad_error: null,
      kicad_cli_available: false, kicad_cli_path_checked: null,
      kicad_cli_path_source: 'none', kicad_cli_error: 'Could not find the kicad-cli executable.',
      llm_providers: [], log_path: '/l', python_version: '3.11.9',
      storage_root: '/s', github_token_configured: false, configured_secret_refs: [],
    })

    render(<App />)

    expect(await screen.findByText(/KiCad was not found/)).toBeTruthy()
    expect(screen.getByText(/No AI provider is configured/)).toBeTruthy()

    fireEvent.click(screen.getAllByRole('button', { name: 'Fix this' })[0])
    expect(await screen.findByText(/Setting up Copperplane/)).toBeTruthy()
  })

  it('shows no banner when everything is present', async () => {
    render(<App />)

    await screen.findByRole('button', { name: 'New project' })
    expect(screen.queryByText(/was not found/)).toBeNull()
  })
})

/** CTX-336.1 Deviation 10, found by the maintainer clicking through the built
 *  app: they chose Anthropic, entered an Anthropic key, finished setup, and
 *  `config.json` still read `provider_roles: google`. */
describe('App: finishing setup does not revert what setup just did', () => {
  beforeEach(() => {
    listProjectsMock.mockReset().mockResolvedValue([])
    listLibraryPartsMock.mockReset().mockResolvedValue([])
    getCapabilitiesMock.mockReset().mockResolvedValue({
      kicad_available: true, kicad_socket_path_checked: '/tmp/kicad/api.sock',
      freecad_available: true, freecad_path_checked: '/f', freecad_error: null,
      kicad_cli_available: true, kicad_cli_path_checked: '/k',
      kicad_cli_path_source: 'install', kicad_cli_error: null,
      llm_providers: ['anthropic'], log_path: '/l', python_version: '3.11.9',
      storage_root: '/s', github_token_configured: false, configured_secret_refs: [],
    })
  })

  it('writes only its own field, never a snapshot of the whole config', async () => {
    /** The bug was a whole-object save of a launch-time snapshot: guided
     *  setup had written `provider_roles` to the same file in between, and
     *  the snapshot did not have it. A patch cannot revert a key it does not
     *  name -- so the assertion is about the SHAPE of the write, which is the
     *  only thing that makes the class of bug impossible. */
    getConfigMock.mockResolvedValue({
      provider_roles: { reasoning: 'google', fast: 'google' },
      llm_provider: 'google',
    })

    render(<App />)
    await screen.findByText('Welcome to Copperplane')
    fireEvent.click(screen.getByRole('button', { name: /Skip for now/ }))

    await waitFor(() => expect(updateConfigMock).toHaveBeenCalled())
    for (const [patch] of updateConfigMock.mock.calls) {
      expect(Object.keys(patch as object)).toEqual(['onboarding_completed'])
    }
  })

  it('does not carry a launch-time provider binding into its write', async () => {
    getConfigMock.mockResolvedValue({
      provider_roles: { reasoning: 'google', fast: 'google' },
      llm_provider: 'google',
    })

    render(<App />)
    await screen.findByText('Welcome to Copperplane')
    fireEvent.click(screen.getByRole('button', { name: /Skip for now/ }))

    await waitFor(() => expect(updateConfigMock).toHaveBeenCalled())
    const [patch] = updateConfigMock.mock.calls[0]
    expect(patch).not.toHaveProperty('provider_roles')
    expect(patch).not.toHaveProperty('llm_provider')
  })
})
