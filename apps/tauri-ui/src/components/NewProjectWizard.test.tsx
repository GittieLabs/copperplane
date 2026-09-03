import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const pickKicadProjectMock = vi.fn()
const openKicadMock = vi.fn()
const summariseIntentMock = vi.fn()
const runProjectReviewMock = vi.fn()

vi.mock('../lib/kicadProject', () => ({
  pickKicadProject: (...a: unknown[]) => pickKicadProjectMock(...a),
}))
vi.mock('../lib/boardAdvisor', () => ({
  openKicad: (...a: unknown[]) => openKicadMock(...a),
}))
vi.mock('../lib/newProjectWizard', async (importOriginal) => ({
  // nameProblem and WIZARD_STEPS are pure; only the LLM call is mocked.
  ...(await importOriginal<typeof import('../lib/newProjectWizard')>()),
  summariseIntent: (...a: unknown[]) => summariseIntentMock(...a),
}))
vi.mock('../lib/projectReview', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/projectReview')>()),
  runProjectReview: (...a: unknown[]) => runProjectReviewMock(...a),
}))

const { NewProjectWizard } = await import('./NewProjectWizard')
const { WIZARD_STEPS } = await import('../lib/newProjectWizard')

beforeEach(() => {
  pickKicadProjectMock.mockReset()
  openKicadMock.mockReset().mockResolvedValue(undefined)
  summariseIntentMock.mockReset()
  runProjectReviewMock.mockReset().mockResolvedValue(undefined)
})

function renderWizard(over: { existingProjects?: string[] } = {}) {
  const props = {
    onCancel: vi.fn(),
    onCreate: vi.fn(),
    existingProjects: [] as string[],
    ...over,
  }
  render(<NewProjectWizard {...props} />)
  return props
}

function nameIt(name = 'blinky') {
  fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: name } })
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
}

describe('NewProjectWizard: cancelling', () => {
  it('can be cancelled from the first step, writing nothing', () => {
    const props = renderWizard()
    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'half' } })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(props.onCancel).toHaveBeenCalled()
    expect(props.onCreate).not.toHaveBeenCalled()
  })

  it('can be cancelled from a later step, still writing nothing', () => {
    const props = renderWizard()
    nameIt()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(props.onCancel).toHaveBeenCalled()
    expect(props.onCreate).not.toHaveBeenCalled()
  })
})

describe('NewProjectWizard: naming', () => {
  it('refuses a name that already exists rather than merging into it', () => {
    // save_project keys on the name, so a duplicate would write into the
    // existing project's record instead of creating a new one.
    renderWizard({ existingProjects: ['test 1'] })

    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'test 1' } })

    expect(screen.getByText(/already have a project called/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('allows a name that is merely similar', () => {
    renderWizard({ existingProjects: ['test 1'] })

    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'test 2' } })

    expect(screen.queryByText(/already have a project called/)).toBeNull()
    expect((screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('will not move on with an empty name', () => {
    renderWizard()

    expect((screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('NewProjectWizard: linking a KiCad project', () => {
  it('links a picked .kicad_pro', async () => {
    pickKicadProjectMock.mockResolvedValue('/p/Blinky.kicad_pro')
    renderWizard()
    nameIt()

    fireEvent.click(screen.getByRole('button', { name: 'Choose .kicad_pro…' }))

    await waitFor(() => screen.getByText('/p/Blinky.kicad_pro'))
  })

  it('offers to open KiCad for a user who has no project yet', async () => {
    renderWizard()
    nameIt()

    fireEvent.click(screen.getByRole('button', { name: 'Open KiCad to create one' }))

    await waitFor(() => expect(openKicadMock).toHaveBeenCalled())
  })

  it('can be skipped, and says what that costs', () => {
    // SPEC-336's rule: the app never traps a user mid-setup, and the manual
    // path has never gated anyone either.
    renderWizard()
    nameIt()

    expect(screen.getByText(/You can link one later/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Skip for now' })).toBeTruthy()
  })
})

describe('NewProjectWizard: intent by conversation', () => {
  it('summarises what the user described', async () => {
    summariseIntentMock.mockResolvedValue('A coin-cell LED badge.')
    renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))

    fireEvent.change(screen.getByPlaceholderText(/blinking LED badge/), {
      target: { value: 'a badge that blinks, powered by a CR2032' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }))

    await waitFor(() => expect(screen.getByDisplayValue('A coin-cell LED badge.')).toBeTruthy())
  })

  it('lets the user correct the summary before it is kept', async () => {
    summariseIntentMock.mockResolvedValue('Something wrong.')
    renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    fireEvent.change(screen.getByPlaceholderText(/blinking LED badge/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }))
    await waitFor(() => screen.getByDisplayValue('Something wrong.'))

    fireEvent.change(screen.getByDisplayValue('Something wrong.'), {
      target: { value: 'What I actually meant.' },
    })

    expect(screen.getByDisplayValue('What I actually meant.')).toBeTruthy()
  })

  it('keeps the user\'s own words when summarising fails', async () => {
    summariseIntentMock.mockRejectedValue(new Error('no api key'))
    renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    fireEvent.change(screen.getByPlaceholderText(/blinking LED badge/), {
      target: { value: 'my own description' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }))

    // A failed summary must not cost them what they typed.
    await waitFor(() => expect(screen.getByDisplayValue('my own description')).toBeTruthy())
    expect(screen.getByText(/your own words are kept as written/)).toBeTruthy()
  })
})

describe('NewProjectWizard: the review', () => {
  async function toReview() {
    const props = renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    await waitFor(() => expect(runProjectReviewMock).toHaveBeenCalled())
    return props
  }

  it('runs the checks when the review step is reached', async () => {
    await toReview()

    expect(runProjectReviewMock).toHaveBeenCalledTimes(1)
  })

  it('renders each check as it lands, not after all four', async () => {
    let emit: (u: unknown) => void = () => {}
    runProjectReviewMock.mockImplementation((_p: unknown, onUpdate: (u: unknown) => void) => {
      emit = onUpdate
      return new Promise(() => {})
    })
    await toReview()

    emit({ key: 'parity', label: 'Schematic and board agree', status: 'done',
           summary: 'Your schematic and board match.' })

    await waitFor(() => screen.getByText('Your schematic and board match.'))
    // The others are still waiting -- the first result did not have to queue
    // behind them.
    expect(screen.getAllByText('Waiting').length).toBeGreaterThan(0)
  })

  it('reports a failed check as itself, keeping the others', async () => {
    let emit: (u: unknown) => void = () => {}
    runProjectReviewMock.mockImplementation((_p: unknown, onUpdate: (u: unknown) => void) => {
      emit = onUpdate
      return new Promise(() => {})
    })
    await toReview()

    emit({ key: 'drc', label: 'Board check (DRC)', status: 'failed', error: 'kicad-cli not found' })
    emit({ key: 'erc', label: 'Schematic check (ERC)', status: 'done', summary: 'ERC found nothing.' })

    await waitFor(() => screen.getByText(/Could not run: kicad-cli not found/))
    expect(screen.getByText('ERC found nothing.')).toBeTruthy()
  })

  it('creates the project on the tab the user picks', async () => {
    const props = await toReview()

    fireEvent.click(screen.getByRole('button', { name: 'schematic' }))

    expect(props.onCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'blinky', openArea: 'schematic' }),
    )
  })

  it('offers every area as a landing tab', async () => {
    await toReview()

    for (const area of ['overview', 'components', 'schematic', 'pcb', 'enclosure']) {
      expect(screen.getByRole('button', { name: area })).toBeTruthy()
    }
  })

  it('carries the linked project and intent into the created project', async () => {
    pickKicadProjectMock.mockResolvedValue('/p/Blinky.kicad_pro')
    summariseIntentMock.mockResolvedValue('A coin-cell LED badge.')
    const props = renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Choose .kicad_pro…' }))
    await waitFor(() => screen.getByText('/p/Blinky.kicad_pro'))
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.change(screen.getByPlaceholderText(/blinking LED badge/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }))
    await waitFor(() => screen.getByDisplayValue('A coin-cell LED badge.'))
    // Both steps are done, so the forward action is "Use this" -- there is no
    // longer a "Skip for now", which is the point.
    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))
    await waitFor(() => expect(runProjectReviewMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'overview' }))

    expect(props.onCreate).toHaveBeenCalledWith({
      name: 'blinky',
      intent: 'A coin-cell LED badge.',
      kicadProjectPath: '/p/Blinky.kicad_pro',
      openArea: 'overview',
    })
  })
})

describe('NewProjectWizard: the shell', () => {
  it('shows every step and marks the current one', () => {
    renderWizard()

    for (const step of WIZARD_STEPS) {
      expect(screen.getAllByText(new RegExp(step.title)).length).toBeGreaterThan(0)
    }
    expect(screen.getByText(/step 1 of 4/)).toBeTruthy()
  })

  it('goes back without losing what was typed', () => {
    renderWizard()
    nameIt('blinky')

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))

    expect((screen.getByPlaceholderText('project name') as HTMLInputElement).value).toBe('blinky')
  })

  it('cannot go back past the first step', () => {
    renderWizard()

    expect((screen.getByRole('button', { name: 'Back' }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('NewProjectWizard: skipping is offered, never encouraged', () => {
  /* Reported: "The skip for now and next buttons are the same color but should
     not be... I don't want to encourage the skip step." And, on the intent
     step, skip was the ONLY way forward -- so a user who had just read a
     summary had no way to accept it. */
  it('offers a real forward action once a step is done, not a skip', async () => {
    pickKicadProjectMock.mockResolvedValue('/p/Blinky.kicad_pro')
    renderWizard()
    nameIt()

    fireEvent.click(screen.getByRole('button', { name: 'Choose .kicad_pro…' }))
    await waitFor(() => screen.getByText('/p/Blinky.kicad_pro'))

    expect(screen.getByRole('button', { name: 'Next' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Skip for now' })).toBeNull()
  })

  it('lets the user accept a summary rather than only skip past it', async () => {
    summariseIntentMock.mockResolvedValue('A coin-cell LED badge.')
    renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    fireEvent.change(screen.getByPlaceholderText(/blinking LED badge/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Summarise' }))
    await waitFor(() => screen.getByDisplayValue('A coin-cell LED badge.'))

    // This is what was missing entirely: an acknowledge action.
    expect(screen.getByRole('button', { name: 'Use this' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Skip for now' })).toBeNull()
  })

  it('keeps what the user typed even if they never pressed Summarise', async () => {
    const props = renderWizard()
    nameIt()
    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    fireEvent.change(screen.getByPlaceholderText(/blinking LED badge/), {
      target: { value: 'two alternating blinking leds' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Use this' }))
    await waitFor(() => expect(runProjectReviewMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'overview' }))

    expect(props.onCreate).toHaveBeenCalledWith(
      expect.objectContaining({ intent: 'two alternating blinking leds' }),
    )
  })

  it('does not style skip like the primary action', async () => {
    renderWizard()
    nameIt()

    const skip = screen.getByRole('button', { name: 'Skip for now' })
    const next = screen.getByRole('button', { name: 'Choose .kicad_pro…' })
    expect(skip.className).not.toContain('bg-accent')
    expect(skip.className).toContain('underline')
    expect(next.className).not.toBe(skip.className)
  })
})
