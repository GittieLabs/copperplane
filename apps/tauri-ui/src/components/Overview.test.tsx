import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()
const dispatchToolMock = vi.fn()
const loadConversationMock = vi.fn()
const appendConversationTurnMock = vi.fn()
const setProjectIntentMock = vi.fn()
const suggestPartsMock = vi.fn()
const projectStageMock = vi.fn()
const projectConsiderationsMock = vi.fn()
const setProjectGuidedPathMock = vi.fn()

vi.mock('../lib/ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
  dispatchTool: (...args: unknown[]) => dispatchToolMock(...args),
}))

vi.mock('../lib/projects', () => ({
  loadConversation: (...args: unknown[]) => loadConversationMock(...args),
  appendConversationTurn: (...args: unknown[]) => appendConversationTurnMock(...args),
  setProjectIntent: (...args: unknown[]) => setProjectIntentMock(...args),
  setProjectGuidedPath: (...args: unknown[]) => setProjectGuidedPathMock(...args),
}))

// CTX-318.5: AgentChat has its own dedicated test file (AgentChat.test.tsx)
// -- stubbed here, matching PartDetail.test.tsx's own precedent (CTX-318.2),
// so Overview's tests stay focused on its own wiring (does it mount
// AgentChat with the real scope/area/targets) and never need to mock
// AgentChat's own internal chat.* IPC calls.
vi.mock('../lib/considerations', () => ({
  projectConsiderations: (...args: unknown[]) => projectConsiderationsMock(...args),
}))

vi.mock('../lib/projectStage', () => ({
  projectStage: (...args: unknown[]) => projectStageMock(...args),
}))

vi.mock('../lib/suggestedParts', () => ({
  suggestParts: (...args: unknown[]) => suggestPartsMock(...args),
}))

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

// CTX-319.5: ReviewPanel has its own dedicated test file
// (ReviewPanel.test.tsx) -- stubbed here, matching AgentChat's own
// precedent immediately above.
vi.mock('./ReviewPanel', () => ({
  ReviewPanel: ({
    area,
    scope,
    scopeId,
    title,
    projectName,
  }: {
    area: string
    scope: string
    scopeId: string
    title: string
    projectName?: string
  }) => (
    <p>
      ReviewPanel stub: area={area} scope={scope} scopeId={scopeId} title="{title}"
      {projectName && ` projectName=${projectName}`}
    </p>
  ),
}))

const { Overview } = await import('./Overview')

beforeEach(() => {
  submitJobMock.mockReset()
  dispatchToolMock.mockReset()
  loadConversationMock.mockReset().mockResolvedValue([])
  appendConversationTurnMock.mockReset().mockResolvedValue(undefined)
  setProjectIntentMock.mockReset()
  suggestPartsMock.mockReset()
  projectStageMock.mockReset().mockRejectedValue(new Error('no reading by default'))
  setProjectGuidedPathMock.mockReset().mockResolvedValue({ name: 'weather-pcb' })
  projectConsiderationsMock.mockReset().mockRejectedValue(new Error('none by default'))
})

async function renderOverview(project: { name: string; intent?: string | null } | null = { name: 'weather-pcb' }) {
  const onProjectUpdated = vi.fn()
  render(<Overview projectName="weather-pcb" project={project} onProjectUpdated={onProjectUpdated} />)
  await waitFor(() => screen.getByText(/AgentChat stub/))
  return { onProjectUpdated }
}

describe('Overview: CTX-318.5 AgentChat wiring', () => {
  it('mounts AgentChat scoped to the project overview area, offering only "this project"', async () => {
    await renderOverview()

    const stub = screen.getByText(/AgentChat stub/)
    expect(stub.textContent).toContain('area=overview')
    expect(stub.textContent).toContain('scope=project')
    expect(stub.textContent).toContain('scopeId=weather-pcb:overview')
    expect(stub.textContent).toContain('title="Ask about this project"')
    expect(stub.textContent).toContain('projectName=weather-pcb')
    expect(stub.textContent).toContain('targets=[this project:project:weather-pcb]')
  })

  it('re-scopes AgentChat when the project changes', async () => {
    const { rerender } = render(<Overview projectName="project-a" project={{ name: 'project-a' }} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))

    rerender(<Overview projectName="project-b" project={{ name: 'project-b' }} />)

    await waitFor(() => expect(screen.getByText(/AgentChat stub/).textContent).toContain('scopeId=project-b:overview'))
  })

  it('CTX-207.1: renders the real reply text out of llm.chat\'s {text, usage, model} result, not the whole object', async () => {
    submitJobMock.mockResolvedValue({
      result: Promise.resolve({
        text: 'Sure, here is an answer.',
        usage: { input_tokens: 12, output_tokens: 6 },
        model: 'claude-sonnet-5',
      }),
    })
    await renderOverview()

    fireEvent.change(screen.getByPlaceholderText(/ask a question about this project/), {
      target: { value: 'what should I do next?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => screen.getByText('Sure, here is an answer.'))
    expect(screen.queryByText(/\[object Object\]/)).toBeNull()
  })

  it('the plain llm.chat surface still coexists alongside the new AgentChat panel (CTX-318.6 only removed the generate/inject branches)', async () => {
    await renderOverview()

    screen.getByPlaceholderText(/ask a question about this project/)
    screen.getByText(/AgentChat stub/)
  })
})

describe('Overview: the per-area cards and project review are gone', () => {
  /* "The PCB, Schematic, Enclosure and Components cards offer no value. We do
     the PCB and Schematic reviews on demand and stating one has run doesn't
     add anything here. The enclosure and components don't even have checks."
     And: "The Run Review on the overview doesn't do anything and is
     unneccessary."

     Removed rather than reworked -- what belongs on an opened project is
     SPEC-335's question, not another guess at a card grid. */
  it('shows no per-area status cards', async () => {
    await renderOverview()

    expect(screen.queryByTestId('status-card-pcb')).toBeNull()
    expect(screen.queryByText(/Not yet checked this session/)).toBeNull()
  })

  it('offers no project-level Run Review', async () => {
    await renderOverview()

    expect(screen.queryByText(/ReviewPanel stub/)).toBeNull()
  })

  it('keeps what the overview is actually for -- intent and the project chat', async () => {
    await renderOverview()

    expect(screen.getByPlaceholderText(/ask a question about this project/)).toBeTruthy()
    expect(screen.getByText(/AgentChat stub/)).toBeTruthy()
  })
})

describe('Overview: CTX-318.5 project intent editor', () => {
  it('shows an honest "not stated yet" message and an Add button when no intent exists', async () => {
    await renderOverview({ name: 'weather-pcb', intent: null })

    screen.getByText(/Not stated yet/)
    screen.getByRole('button', { name: 'Add' })
  })

  it('shows the real stored intent and an Edit button when one exists', async () => {
    await renderOverview({ name: 'weather-pcb', intent: 'A macropad from scratch' })

    screen.getByText('A macropad from scratch')
    screen.getByRole('button', { name: 'Edit' })
  })

  it('clicking Add opens a textarea pre-filled with the current (empty) intent', async () => {
    await renderOverview({ name: 'weather-pcb', intent: null })

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => screen.getByPlaceholderText(/I want to build/))
    const textarea = screen.getByPlaceholderText(/I want to build/) as HTMLTextAreaElement
    expect(textarea.value).toBe('')
  })

  it('Save calls the real setProjectIntent, reports the updated project back to the caller, and reflects it once the caller re-passes the new project prop', async () => {
    setProjectIntentMock.mockResolvedValueOnce({ name: 'weather-pcb', intent: 'A macropad from scratch' })
    // A small stateful wrapper -- mirrors what App.tsx really does
    // (`onProjectUpdated={setCurrentProject}`), since `Overview` itself
    // deliberately has no local copy of `intent`; the parent-owned
    // `project` prop is the only source of truth.
    function Wrapper() {
      const [project, setProject] = useState<{ name: string; intent?: string | null }>({
        name: 'weather-pcb',
        intent: null,
      })
      return <Overview projectName="weather-pcb" project={project} onProjectUpdated={setProject} />
    }
    render(<Wrapper />)
    await waitFor(() => screen.getByText(/AgentChat stub/))

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => screen.getByPlaceholderText(/I want to build/))
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), {
      target: { value: 'A macropad from scratch' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(setProjectIntentMock).toHaveBeenCalledWith('weather-pcb', 'A macropad from scratch'))
    await waitFor(() => screen.getByText('A macropad from scratch'))
    screen.getByRole('button', { name: 'Edit' })
  })

  it('Cancel discards the draft and leaves the stored intent untouched', async () => {
    await renderOverview({ name: 'weather-pcb', intent: 'Original intent' })

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await waitFor(() => screen.getByPlaceholderText(/I want to build/))
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), { target: { value: 'Something else' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(setProjectIntentMock).not.toHaveBeenCalled()
    screen.getByText('Original intent')
  })

  it('a genuine save failure shows the real error, not a crash, and stays in edit mode', async () => {
    setProjectIntentMock.mockRejectedValueOnce(new Error('Lost connection to the daemon.'))
    await renderOverview({ name: 'weather-pcb', intent: null })

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => screen.getByPlaceholderText(/I want to build/))
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), { target: { value: 'A macropad' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => screen.getByText('Lost connection to the daemon.'))
    screen.getByRole('button', { name: 'Save' })
  })

  it('switching to a different real project resets any in-progress edit', async () => {
    const { rerender } = render(<Overview projectName="project-a" project={{ name: 'project-a', intent: null }} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await screen.findByPlaceholderText(/I want to build/)
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), { target: { value: 'Half-typed' } })

    rerender(<Overview projectName="project-b" project={{ name: 'project-b', intent: null }} />)

    await waitFor(() => screen.getByRole('button', { name: 'Add' }))
    expect(screen.queryByPlaceholderText(/I want to build/)).toBeNull()
  })
})

describe('Overview: SPEC-328 suggested parts', () => {
  const READY = {
    ready: true,
    question: null,
    suggestions: [
      { category: 'real-time clock', search_term: 'RTC module I2C', why: 'So the log has timestamps.' },
      { category: 'low-dropout regulator', search_term: '3.3V LDO low quiescent', why: 'To run a month on one charge.' },
    ],
    rejected: [],
    caveat: 'These are kinds of component to start from, not parts to order.',
  }

  async function renderWith(project: Record<string, unknown>, onCarryToSearch?: (t: string) => void) {
    render(
      <Overview
        projectName="weather-pcb"
        project={project as never}
        onCarryToSearch={onCarryToSearch}
      />,
    )
    await waitFor(() => screen.getByText(/AgentChat stub/))
  }

  it('offers nothing until the user has said what they are building', async () => {
    // SPEC-328 §3: "An empty Overview tab is not a crisis." There is nothing
    // to suggest from, so there is nothing to offer.
    await renderWith({ name: 'weather-pcb', intent: null })

    expect(screen.queryByRole('button', { name: 'Suggest parts' })).toBeNull()
  })

  // TEST-007
  it('007_asks through the surface that is already there, not a new one', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a battery-powered temperature logger' })
    suggestPartsMock.mockResolvedValue(READY)

    fireEvent.click(screen.getByRole('button', { name: 'Suggest parts' }))

    expect(await screen.findByText('real-time clock')).toBeTruthy()
    expect(screen.getByText('So the log has timestamps.')).toBeTruthy()
    expect(suggestPartsMock).toHaveBeenCalledWith('weather-pcb')
  })

  it('renders the caveat from the record rather than its own copy', async () => {
    // SPEC-328 §3's framing travels with the data. If this component retyped
    // it, a second surface rendering the same record would lose it.
    await renderWith({ name: 'weather-pcb', intent: 'a logger' })
    suggestPartsMock.mockResolvedValue({ ...READY, caveat: 'CAVEAT FROM THE RECORD' })

    fireEvent.click(screen.getByRole('button', { name: 'Suggest parts' }))

    expect(await screen.findByText('CAVEAT FROM THE RECORD')).toBeTruthy()
  })

  // TEST-008
  it('008_carries a suggestion into the existing part search', async () => {
    const onCarryToSearch = vi.fn()
    await renderWith({ name: 'weather-pcb', intent: 'a logger' }, onCarryToSearch)
    suggestPartsMock.mockResolvedValue(READY)

    fireEvent.click(screen.getByRole('button', { name: 'Suggest parts' }))
    await screen.findByText('real-time clock')
    fireEvent.click(screen.getAllByRole('button', { name: 'Search for this' })[0])

    // The SEARCH TERM, not the category -- "real-time clock" is what to call
    // it, "RTC module I2C" is what finds one.
    expect(onCarryToSearch).toHaveBeenCalledWith('RTC module I2C')
  })

  it('shows a vague brief as a question, never as an empty list', async () => {
    // CTX-328.1 Phase 1 measured this as the real behaviour for "a robot".
    // Rendering an empty list beside the question would make the question
    // look like a footnote on a result.
    await renderWith({ name: 'weather-pcb', intent: 'a robot' })
    suggestPartsMock.mockResolvedValue({
      ready: false, question: 'What should the robot actually do?',
      suggestions: [], rejected: [], caveat: 'c',
    })

    fireEvent.click(screen.getByRole('button', { name: 'Suggest parts' }))

    expect(await screen.findByText('What should the robot actually do?')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Search for this' })).toBeNull()
  })

  it('says how many suggestions were left out, rather than quietly filtering', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a logger' })
    suggestPartsMock.mockResolvedValue({
      ...READY, rejected: [{ value: 'DS3231', reason: 'looks like a specific part number' }],
    })

    fireEvent.click(screen.getByRole('button', { name: 'Suggest parts' }))

    expect(await screen.findByText(/1 suggestion was left out/)).toBeTruthy()
  })

  it('surfaces a failure instead of looking like it found nothing', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a logger' })
    suggestPartsMock.mockRejectedValue(new Error('no provider configured'))

    fireEvent.click(screen.getByRole('button', { name: 'Suggest parts' }))

    expect(await screen.findByText('no provider configured')).toBeTruthy()
  })

  // TEST-009
  it('009_marks suggestions advisory once a real KiCad project is attached', async () => {
    /* SPEC-328 §2: "Once a real KiCad project is attached, the parts list is
     * at best advisory and at worst contradicts what is actually on the
     * board." The board is the thing that exists; this list is what someone
     * intended before it did. */
    await renderWith({
      name: 'weather-pcb', intent: 'a logger',
      kicad_project_path: '/real/weather.kicad_pro',
    })

    expect(await screen.findByText(/not what is on your board/)).toBeTruthy()
  })

  it('says nothing about the board when no KiCad project is attached', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a logger' })

    expect(screen.queryByText(/not what is on your board/)).toBeNull()
  })
})


describe('Overview: SPEC-343 where you are', () => {
  function reading(over: Record<string, unknown> = {}) {
    return {
      state: 'nothing_checked', action: 'Check the schematic', area: 'schematic',
      evidence: 'a linked project with nothing checked yet', stale_areas: [],
      ...over,
    }
  }

  async function renderWith(readingValue: unknown, onGoToArea?: (a: string) => void) {
    projectStageMock.mockResolvedValue(readingValue)
    render(
      <Overview
        projectName="weather-pcb"
        project={{ name: 'weather-pcb', intent: 'a logger' } as never}
        onGoToArea={onGoToArea as never}
      />,
    )
    await waitFor(() => screen.getByText(/AgentChat stub/))
  }

  // TEST-005
  it('005_offers a link and never navigates by itself', async () => {
    /* SPEC-300's boundary -- nothing "decides which screen the user is on" --
     * applies here even though this is not an AI surface, because a user
     * cannot tell the difference between an app that moved them and an agent
     * that did. */
    const onGoToArea = vi.fn()
    await renderWith(reading(), onGoToArea)

    const action = await screen.findByRole('button', { name: 'Check the schematic' })
    expect(onGoToArea).not.toHaveBeenCalled()

    fireEvent.click(action)
    expect(onGoToArea).toHaveBeenCalledWith('schematic')
  })

  it('leads with the reading, not the action', async () => {
    // CTX-343.1 Phase 1: four of six actions are "press the button on the tab
    // this points at". The sentence is what no tab can say.
    await renderWith(reading({
      state: 'regressed', action: 'Re-check the pcb', area: 'pcb', stale_areas: ['pcb'],
      evidence: 'pcb changed since it was last checked',
    }))

    expect(await screen.findByText(/Your pcb changed after it was last checked/)).toBeTruthy()
  })

  it('shows the evidence, so a wrong reading is debuggable by whoever sees it', async () => {
    await renderWith(reading({ evidence: 'because I said so' }))

    expect(await screen.findByText('because I said so')).toBeTruthy()
  })

  it('offers no action in the complete state, and congratulates nobody', async () => {
    /* SPEC-343 §2.6 leaves open what to say when nothing is wrong, and §3 warns
     * generic praise is worse than silence. Until that is settled it states the
     * fact and stops. */
    await renderWith(reading({ state: 'complete', action: null, area: null,
                               evidence: 'everything has been checked' }))

    expect(await screen.findByText(/all been checked/)).toBeTruthy()
    expect(screen.queryByText(/well done|great|nice work|looks good/i)).toBeNull()
  })

  it('renders nothing at all when the reading cannot be computed', async () => {
    // Advisory. A reading that fails must not take the Overview tab with it.
    projectStageMock.mockRejectedValue(new Error('daemon unavailable'))
    render(<Overview projectName="weather-pcb" project={{ name: 'weather-pcb' } as never} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))

    expect(screen.queryByText('Where you are')).toBeNull()
    expect(screen.queryByText(/daemon unavailable/)).toBeNull()
  })
})


describe('Overview: SPEC-343 the toggle', () => {
  const READING = {
    state: 'nothing_checked', action: 'Check the schematic', area: 'schematic',
    evidence: 'nothing checked yet', stale_areas: [],
  }

  async function renderWith(project: Record<string, unknown>) {
    projectStageMock.mockResolvedValue(READING)
    render(<Overview projectName="weather-pcb" project={project as never} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))
  }

  // TEST-006
  it('006_turning it off leaves Overview as it was', async () => {
    /* SPEC-343 §2.6, settled: off means GONE, not diminished. A user who
     * switches something off and gets a smaller version of it is being
     * negotiated with. */
    await renderWith({ name: 'weather-pcb', intent: 'a logger', guided_path: false })

    expect(screen.queryByText('Where you are')).toBeNull()
    expect(screen.queryByText('Nothing has been checked yet.')).toBeNull()
    // The intent editor -- the rest of Overview -- is untouched.
    expect(screen.getByText("What you're building")).toBeTruthy()
  })

  it('leaves a way back, because an unfindable setting is not a setting', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a logger', guided_path: false })

    fireEvent.click(screen.getByRole('button', { name: /Show where this project stands/ }))

    await waitFor(() => expect(setProjectGuidedPathMock).toHaveBeenCalledWith('weather-pcb', true))
  })

  it('does not spend a route call on a reading nobody will see', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a logger', guided_path: false })

    expect(projectStageMock).not.toHaveBeenCalled()
  })

  it('is on when the project has never said otherwise', async () => {
    /* The default is not a coin toss: the people this is for are the ones who
     * will not go looking for a setting to switch it on. Defaulting off costs
     * them the whole feature; defaulting on costs a second-time user one click. */
    await renderWith({ name: 'weather-pcb', intent: 'a logger' })

    expect(await screen.findByText('Where you are')).toBeTruthy()
  })

  it('hides on request', async () => {
    await renderWith({ name: 'weather-pcb', intent: 'a logger', guided_path: true })
    await screen.findByText('Where you are')

    fireEvent.click(screen.getByRole('button', { name: 'Hide' }))

    await waitFor(() => expect(setProjectGuidedPathMock).toHaveBeenCalledWith('weather-pcb', false))
  })
})


describe('Overview: SPEC-343 what you got right', () => {
  function cleared(over: Record<string, unknown> = {}) {
    return {
      id: 'led_series_resistor', type: 'copperplane.led_series_resistor',
      domain: 'power', claim_class: 'computed', state: 'satisfied',
      trigger: { kind: 'net', ref: 'Net-(D1-A)', parts: 'D1' },
      explanation: "D1's anode reaches R1 on Net-(D1-A) — that resistor is what stops the LED "
        + 'drawing more current than the pin driving it can give.',
      ...over,
    }
  }

  async function renderWith(result: unknown) {
    projectConsiderationsMock.mockResolvedValue(result)
    render(<Overview projectName="weather-pcb" project={{ name: 'weather-pcb' } as never} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))
  }

  // TEST-006
  it('006_shows one cleared item and what was not checked', async () => {
    await renderWith({
      needs_attention: [], cleared: [cleared()],
      checked: ['component_without_value', 'led_series_resistor'],
      source_path: '/x.kicad_sch', reason: null,
    })

    expect(await screen.findByText(/D1's anode reaches R1/)).toBeTruthy()
    // The boundary, beside the reinforcement rather than instead of it.
    expect(screen.getByText(/does what you intended/)).toBeTruthy()
    expect(screen.getByText(/led series resistor/)).toBeTruthy()
  })

  it('shows one at a time, and counts the rest', async () => {
    /* SPEC-343 §2.7's first constraint. The complete state is where a finished
     * project sits forever, and a wall of "here is everything that is fine" is
     * the overload this spec exists to avoid. */
    await renderWith({
      needs_attention: [], cleared: [cleared(), cleared({ id: 'b' }), cleared({ id: 'c' })],
      checked: ['led_series_resistor'], source_path: '/x.kicad_sch', reason: null,
    })

    await screen.findByText(/D1's anode reaches R1/)
    expect(screen.getByText(/and 2 others like it/)).toBeTruthy()
  })

  it('says nothing at all when no pack cleared anything', async () => {
    /* SPEC-343 §2.7's second constraint: a pack whose trigger was absent has
     * taught nothing, so there is nothing to say and nothing is said. */
    await renderWith({
      needs_attention: [], cleared: [], checked: ['led_series_resistor'],
      source_path: '/x.kicad_sch', reason: null,
    })

    expect(screen.queryByText('What you got right')).toBeNull()
  })

  it('never congratulates -- it explains', async () => {
    /* The same assertion shape as the complete state's: catch the tempting
     * wrong answer rather than pin today's right one. */
    await renderWith({
      needs_attention: [], cleared: [cleared()],
      checked: ['led_series_resistor'], source_path: '/x.kicad_sch', reason: null,
    })

    await screen.findByText(/D1's anode reaches R1/)
    expect(screen.queryByText(/well done|nice work|great job|looks good|perfect/i)).toBeNull()
  })

  it('stays quiet when the packs cannot run', async () => {
    projectConsiderationsMock.mockRejectedValue(new Error('no schematic'))
    render(<Overview projectName="weather-pcb" project={{ name: 'weather-pcb' } as never} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))

    expect(screen.queryByText('What you got right')).toBeNull()
    expect(screen.queryByText(/no schematic/)).toBeNull()
  })
})

describe('Overview: SPEC-343 the reading goes stale when another tab changes it', () => {
  /* Reported from real use, 2026-09-11, and the first defect found by using
   * this surface as a user rather than proving the route works -- which is
   * exactly the gap `SPEC-211` §6 and `SPEC-343` §6 both recorded as open.
   *
   * Overview said "Nothing has been checked yet" and offered "Check the
   * schematic". The user followed it, ran the review on the Schematic tab, came
   * back, and the card had not moved. The project record on disk WAS correct --
   * `last_reviews: ['schematic']` -- and `project_stage.read` computed
   * "the schematic has been checked and the board has not" from it. Every layer
   * above the daemon was stale.
   *
   * The cause is structural rather than a missed dependency. `App.tsx` renders
   * every tab at once and hides the inactive ones with CSS, so Overview never
   * unmounts and its effects never re-run. Nothing refetches the project on
   * navigation, and the sibling tabs are given no way to say they changed it.
   *
   * So the fix is not "add a dependency" -- it is that the reading re-reads
   * when the tab becomes visible, which is the only moment that matters and the
   * only one that also covers a record changed outside the app entirely. */

  it('016_re-reads when the tab becomes visible again', async () => {
    projectStageMock.mockResolvedValue({
      state: 'nothing_checked', action: 'Check the schematic', area: 'schematic',
      evidence: 'a linked project with nothing checked yet', stale_areas: [],
    })
    const project = { name: 'weather-pcb', intent: 'a logger' } as never

    const { rerender } = render(
      <Overview projectName="weather-pcb" project={project} active />,
    )
    await waitFor(() => screen.getByText(/nothing checked yet/))

    // The user leaves for the Schematic tab and runs a review there. The record
    // changes underneath Overview, which is still mounted and still hidden.
    projectStageMock.mockResolvedValue({
      state: 'board_only', action: 'Check the board', area: 'pcb',
      evidence: 'the schematic has been checked and the board has not',
      stale_areas: [],
    })
    rerender(<Overview projectName="weather-pcb" project={project} active={false} />)

    // ...and comes back. Note `project` is the SAME object: App does not refetch
    // it, so nothing in the props has changed except visibility.
    rerender(<Overview projectName="weather-pcb" project={project} active />)

    await waitFor(() => screen.getByText(/the schematic has been checked/))
    expect(screen.queryByText(/nothing checked yet/)).toBeNull()
  })

  it('017_re-reads its considerations on return too, for the same reason', async () => {
    projectStageMock.mockResolvedValue({
      state: 'nothing_checked', action: 'Check the schematic', area: 'schematic',
      evidence: 'nothing checked yet', stale_areas: [],
    })
    projectConsiderationsMock.mockResolvedValue({
      needs_attention: [], cleared: [], checked: ['led series resistor'],
      source_path: '/p/x.kicad_sch', reason: null,
    })
    const project = { name: 'weather-pcb', intent: 'a logger' } as never

    const { rerender } = render(
      <Overview projectName="weather-pcb" project={project} active />,
    )
    await waitFor(() => expect(projectConsiderationsMock).toHaveBeenCalledTimes(1))

    rerender(<Overview projectName="weather-pcb" project={project} active={false} />)
    rerender(<Overview projectName="weather-pcb" project={project} active />)

    await waitFor(() => expect(projectConsiderationsMock).toHaveBeenCalledTimes(2))
  })

  it('018_does not re-read while it stays hidden', async () => {
    /* The other half. A hidden tab that polls is a route call nobody asked for,
     * and `project.considerations` runs a netlist export. */
    projectStageMock.mockResolvedValue({
      state: 'nothing_checked', action: 'Check the schematic', area: 'schematic',
      evidence: 'nothing checked yet', stale_areas: [],
    })
    const project = { name: 'weather-pcb', intent: 'a logger' } as never

    const { rerender } = render(
      <Overview projectName="weather-pcb" project={project} active={false} />,
    )
    rerender(<Overview projectName="weather-pcb" project={project} active={false} />)

    /* The effect is async, so asserting straight after `render` passes whether
     * or not the guard works -- measured: a plain mount reports zero calls at
     * that instant. Wait for something that DOES resolve, so a broken guard has
     * had every chance to fire before this asserts it did not. */
    await waitFor(() => screen.getByText(/AgentChat stub/))
    expect(projectStageMock).not.toHaveBeenCalled()
  })
})

describe('Overview: SPEC-343 §2.6 what needs attention', () => {
  /* The packs have been computing findings since 2026-09-10 and NOTHING
   * rendered them. `project.considerations` returned `needs_attention` on every
   * load and `WhatYouGotRight` read `cleared` and `checked` only — so R1's
   * placeholder value and the `+5V`-on-`VIN` finding were worked out each time
   * and shown to nobody.
   *
   * Found while writing `guides/what-it-notices.md`'s illustration: the page
   * described a surface that did not exist, and the screenshot could not be
   * taken because the app had nothing to photograph.
   *
   * §2.6 settles the shape: "it is there when they look, and something makes
   * them look... a count on the Overview tab: a signal that something changed,
   * which the user may ignore entirely. No modal, no redirect, no chat message
   * arriving unbidden, no stage advanced on their behalf." */

  function consideration(over = {}) {
    return {
      id: 'component_without_value',
      type: 'copperplane.component_without_value',
      domain: 'power',
      claim_class: 'computed',
      trigger: { kind: 'reference', ref: 'R1' },
      explanation: "R1 still has KiCad's placeholder value (R).",
      state: 'raised',
      source: null,
      ...over,
    }
  }

  async function renderWith(result: unknown) {
    projectStageMock.mockResolvedValue({
      state: 'board_only', action: 'Check the board', area: 'pcb',
      evidence: 'a result is on record for the schematic', stale_areas: [],
    })
    projectConsiderationsMock.mockResolvedValue(result)
    render(
      <Overview
        projectName="weather-pcb"
        project={{ name: 'weather-pcb', intent: 'a logger' } as never}
        active
      />,
    )
    await waitFor(() => screen.getByText(/AgentChat stub/))
  }

  const base = { needs_attention: [], cleared: [], checked: ['led series resistor'],
                 source_path: '/p/x.kicad_sch', reason: null }

  it('019_shows a finding the packs raised', async () => {
    await renderWith({ ...base, needs_attention: [consideration()] })

    await waitFor(() => screen.getByText(/placeholder value/))
  })

  it('020_names the thing on the board it is about', async () => {
    /* `SPEC-210` §2.2's safety property, made visible. A claim that cannot name
     * something the user can go and look at is "a best-practices essay wearing
     * a finding's clothes" -- so the surface has to show the name, not just the
     * sentence. */
    await renderWith({ ...base, needs_attention: [consideration()] })

    await waitFor(() => screen.getByText('R1'))
  })

  it('021_counts them, which is the signal SPEC-343 2.6 asked for', async () => {
    await renderWith({
      ...base,
      needs_attention: [
        consideration(),
        consideration({ id: 'regulated_rail_into_module_input',
                        trigger: { kind: 'net', ref: '+5V' },
                        explanation: 'A1 pin 8 is its VIN pin.' }),
      ],
    })

    await waitFor(() => screen.getByText('2'))
  })

  it('022_shows where a cited claim got its fact', async () => {
    /* `SPEC-210` §2.1: a cited claim must say where the fact came from, and
     * `considerations.make` refuses to build one without a source. Dropping it
     * at the last step would defeat the rule the daemon enforces. */
    await renderWith({
      ...base,
      needs_attention: [consideration({
        id: 'trace_too_narrow_for_current',
        claim_class: 'cited',
        trigger: { kind: 'net', ref: 'GND' },
        explanation: 'The narrowest trace on GND is 0.2mm.',
        source: { ref: 'IPC-2221', title: 'IPC-2221', note: 'IPC-2152 supersedes it.' },
      })],
    })

    await waitFor(() => screen.getByText(/IPC-2221/))
  })

  it('023_renders nothing at all when there is nothing to say', async () => {
    await renderWith({ ...base, needs_attention: [] })

    expect(screen.queryByText(/needs attention/i)).toBeNull()
  })

  it('024_stays quiet when the guided path is off', async () => {
    /* `SPEC-343` §2.6: "off means gone, not diminished." */
    projectStageMock.mockResolvedValue(null)
    projectConsiderationsMock.mockResolvedValue({
      ...base, needs_attention: [consideration()],
    })
    render(
      <Overview
        projectName="weather-pcb"
        project={{ name: 'weather-pcb', intent: 'a logger', guided_path: false } as never}
        active
      />,
    )
    await waitFor(() => screen.getByText(/AgentChat stub/))

    expect(screen.queryByText(/placeholder value/)).toBeNull()
  })

  it('025_never navigates by itself', async () => {
    /* `SPEC-300`'s boundary and §2.6 both: no redirect, no stage advanced on
     * the user's behalf. A finding names a place; the user goes there. */
    const onGoToArea = vi.fn()
    projectStageMock.mockResolvedValue({
      state: 'board_only', action: 'Check the board', area: 'pcb',
      evidence: 'a result is on record', stale_areas: [],
    })
    projectConsiderationsMock.mockResolvedValue({ ...base, needs_attention: [consideration()] })
    render(
      <Overview
        projectName="weather-pcb"
        project={{ name: 'weather-pcb', intent: 'a logger' } as never}
        onGoToArea={onGoToArea}
        active
      />,
    )
    await waitFor(() => screen.getByText(/placeholder value/))

    expect(onGoToArea).not.toHaveBeenCalled()
  })

  it('026_asks the daemon once, not once per card', async () => {
    /* `project.considerations` runs a kicad-cli netlist export. Two cards on
     * one tab reading the same route would pay for it twice on every visit. */
    /* Two DIFFERENT findings on purpose. Both cards render an explanation, so
     * reusing one sentence makes `getByText` match twice and the failure looks
     * like a routing bug rather than a duplicated fixture. */
    await renderWith({
      ...base,
      needs_attention: [consideration()],
      cleared: [consideration({
        id: 'led_series_resistor',
        trigger: { kind: 'net', ref: 'Net-(D1-A)' },
        explanation: "D1's anode reaches R1, which is what limits the current.",
      })],
    })
    await waitFor(() => screen.getByText(/placeholder value/))

    expect(projectConsiderationsMock).toHaveBeenCalledTimes(1)
  })
})
