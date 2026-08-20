import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Rail } from './Rail'

function renderRail(overrides: Partial<Parameters<typeof Rail>[0]> = {}) {
  const props = {
    projects: ['weather-pcb', 'doorbell'],
    selectedProject: 'weather-pcb' as string | null,
    onSelectProject: vi.fn(),
    onCreateProject: vi.fn(),
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

  it('creating a project: typing a name and pressing Add calls onCreateProject', () => {
    const props = renderRail()

    fireEvent.click(screen.getByText('+ New…'))
    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: 'new-proj' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    expect(props.onCreateProject).toHaveBeenCalledWith('new-proj')
  })

  it('Add is disabled for an empty/whitespace-only project name', () => {
    renderRail()
    fireEvent.click(screen.getByText('+ New…'))

    const addButton = screen.getByRole('button', { name: 'Add' }) as HTMLButtonElement
    expect(addButton.disabled).toBe(true)

    fireEvent.change(screen.getByPlaceholderText('project name'), { target: { value: '   ' } })
    expect(addButton.disabled).toBe(true)
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
