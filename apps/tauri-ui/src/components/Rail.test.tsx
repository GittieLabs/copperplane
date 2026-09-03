import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Rail } from './Rail'

function renderRail(overrides: Partial<Parameters<typeof Rail>[0]> = {}) {
  const props = {
    projects: ['weather-pcb', 'doorbell'],
    selectedProject: 'weather-pcb' as string | null,
    onSelectProject: vi.fn(),
    onStartNewProject: vi.fn(),
    libraryCount: 3,
    librarySelected: false,
    onSelectLibrary: vi.fn(),
    settingsSelected: false,
    onSelectSettings: vi.fn(),
    ...overrides,
  }
  render(<Rail {...props} />)
  return props
}

describe('Rail', () => {
  it('lists real projects and marks the selected one', () => {
    renderRail()

    screen.getByText(/weather-pcb/)
    screen.getByText('doorbell')
  })

  it('clicking a project calls onSelectProject with its name', () => {
    const props = renderRail()

    fireEvent.click(screen.getByText('doorbell'))

    expect(props.onSelectProject).toHaveBeenCalledWith('doorbell')
  })

  it('shows the real library count, not a placeholder', () => {
    renderRail({ libraryCount: 0 })
    screen.getByText('0 parts')
  })

  /* SPEC-335 moved creating a project out of this 192px column and into a
     wizard in the main content area, with a cancel it never had. The Rail's
     job is now only to open it -- the name field, the intent box and the Add
     button live in NewProjectWizard and are tested there. */
  it('+ New… opens the wizard rather than an inline form', () => {
    const props = renderRail()

    fireEvent.click(screen.getByText('+ New…'))

    expect(props.onStartNewProject).toHaveBeenCalled()
    expect(screen.queryByPlaceholderText('project name')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Add' })).toBeNull()
  })

  it('clicking the library count calls onSelectLibrary', () => {
    const props = renderRail()
    fireEvent.click(screen.getByText('3 parts'))
    expect(props.onSelectLibrary).toHaveBeenCalledTimes(1)
  })

  it('clicking Settings calls onSelectSettings', () => {
    const props = renderRail()
    fireEvent.click(screen.getByText('⚙ Settings'))
    expect(props.onSelectSettings).toHaveBeenCalledTimes(1)
  })

  it('when settingsSelected is true, no project shows as selected', () => {
    renderRail({ settingsSelected: true })
    // The selected-project ">" marker must not render for any project
    // while Settings is the active destination.
    expect(screen.queryByText('> weather-pcb')).toBeNull()
  })
})
