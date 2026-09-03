import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { NewProjectWizard } from './NewProjectWizard'
import { WIZARD_STEPS } from '../lib/newProjectWizard'

/** SPEC-335 Phase 1: the shell. "There is not a way to cancel creating a new
 *  project. And the 'what are you building' field should be displayed in the
 *  main content prominantly... We should make creating a project do everything
 *  in the main content area and not show our tabbed view until the project is
 *  submitted." */
function renderWizard(over: Partial<Parameters<typeof NewProjectWizard>[0]> = {}) {
  const props = {
    onCancel: vi.fn(),
    onCreate: vi.fn(),
    existingProjects: [] as string[],
    ...over,
  }
  render(<NewProjectWizard {...props} />)
  return props
}

describe('NewProjectWizard: the shell', () => {
  it('can be cancelled from the very first step', () => {
    const props = renderWizard()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(props.onCancel).toHaveBeenCalled()
  })

  it('can be cancelled from a later step too', () => {
    const props = renderWizard()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(props.onCancel).toHaveBeenCalled()
  })

  it('writes nothing when cancelled -- there is no project to undo', () => {
    const props = renderWizard()
    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'half-typed' } })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    // The whole reason Cancel is safe at every step: the only write happens on
    // the last one.
    expect(props.onCreate).not.toHaveBeenCalled()
  })

  it('shows every step, and marks which one you are on', () => {
    renderWizard()

    for (const step of WIZARD_STEPS) {
      expect(screen.getAllByText(new RegExp(step.title)).length).toBeGreaterThan(0)
    }
    expect(screen.getByText(/step 1 of 4/)).toBeTruthy()
  })

  it('moves forward and back without writing anything', () => {
    const props = renderWizard()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText(/step 2 of 4/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText(/step 1 of 4/)).toBeTruthy()
    expect(props.onCreate).not.toHaveBeenCalled()
  })

  it('cannot go back past the first step', () => {
    renderWizard()

    expect((screen.getByRole('button', { name: 'Back' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('offers Create only on the last step', () => {
    renderWizard()

    expect(screen.queryByRole('button', { name: 'Create project' })).toBeNull()

    for (let i = 0; i < WIZARD_STEPS.length - 1; i++) {
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    }
    expect(screen.getByRole('button', { name: 'Create project' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Next' })).toBeNull()
  })

  it('creates the project once, on the last step', () => {
    const props = renderWizard()
    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'blinky' } })
    for (let i = 0; i < WIZARD_STEPS.length - 1; i++) {
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    }

    fireEvent.click(screen.getByRole('button', { name: 'Create project' }))

    expect(props.onCreate).toHaveBeenCalledWith('blinky')
    expect(props.onCreate).toHaveBeenCalledTimes(1)
  })

  it('will not create a project with no name', () => {
    renderWizard()
    for (let i = 0; i < WIZARD_STEPS.length - 1; i++) {
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    }

    expect(
      (screen.getByRole('button', { name: 'Create project' }) as HTMLButtonElement).disabled,
    ).toBe(true)
  })

  it('says a step is unbuilt rather than rendering an empty panel', () => {
    // A half-built wizard should read as unfinished, not broken.
    renderWizard()

    expect(screen.getByText(/not built yet/)).toBeTruthy()
  })
})
