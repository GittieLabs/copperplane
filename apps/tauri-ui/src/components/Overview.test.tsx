import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()
const dispatchToolMock = vi.fn()
const loadConversationMock = vi.fn()
const appendConversationTurnMock = vi.fn()
const setProjectIntentMock = vi.fn()

vi.mock('../lib/ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
  dispatchTool: (...args: unknown[]) => dispatchToolMock(...args),
}))

vi.mock('../lib/projects', () => ({
  loadConversation: (...args: unknown[]) => loadConversationMock(...args),
  appendConversationTurn: (...args: unknown[]) => appendConversationTurnMock(...args),
  setProjectIntent: (...args: unknown[]) => setProjectIntentMock(...args),
}))

// CTX-318.5: AgentChat has its own dedicated test file (AgentChat.test.tsx)
// -- stubbed here, matching PartDetail.test.tsx's own precedent (CTX-318.2),
// so Overview's tests stay focused on its own wiring (does it mount
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

const { Overview } = await import('./Overview')

beforeEach(() => {
  submitJobMock.mockReset()
  dispatchToolMock.mockReset()
  loadConversationMock.mockReset().mockResolvedValue([])
  appendConversationTurnMock.mockReset().mockResolvedValue(undefined)
  setProjectIntentMock.mockReset()
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

  it('the old parseCommand-driven chat still coexists alongside the new AgentChat panel (SPEC-318 §2.6 defers deleting it)', async () => {
    await renderOverview()

    screen.getByPlaceholderText(/generate ATtiny85/)
    screen.getByText(/AgentChat stub/)
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
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), { target: { value: 'Something else' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(setProjectIntentMock).not.toHaveBeenCalled()
    screen.getByText('Original intent')
  })

  it('a genuine save failure shows the real error, not a crash, and stays in edit mode', async () => {
    setProjectIntentMock.mockRejectedValueOnce(new Error('Lost connection to the daemon.'))
    await renderOverview({ name: 'weather-pcb', intent: null })

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), { target: { value: 'A macropad' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => screen.getByText('Lost connection to the daemon.'))
    screen.getByRole('button', { name: 'Save' })
  })

  it('switching to a different real project resets any in-progress edit', async () => {
    const { rerender } = render(<Overview projectName="project-a" project={{ name: 'project-a', intent: null }} />)
    await waitFor(() => screen.getByText(/AgentChat stub/))
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    fireEvent.change(screen.getByPlaceholderText(/I want to build/), { target: { value: 'Half-typed' } })

    rerender(<Overview projectName="project-b" project={{ name: 'project-b', intent: null }} />)

    await waitFor(() => screen.getByRole('button', { name: 'Add' }))
    expect(screen.queryByPlaceholderText(/I want to build/)).toBeNull()
  })
})
