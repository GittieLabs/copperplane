import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const openExternalMock = vi.fn()

vi.mock('../lib/externalLinks', () => ({
  GITHUB_REPO_URL: 'https://github.com/GittieLabs/copperplane',
  openExternal: (...a: unknown[]) => openExternalMock(...a),
}))

const { NoProjectLanding } = await import('./NoProjectLanding')

beforeEach(() => {
  openExternalMock.mockReset()
})

/** CTX-336.1 Phase 3. SPEC-336 §1: launch "opens the alphabetically first
 *  project, not the most recently used one. Stable, and meaningless." */
describe('NoProjectLanding', () => {
  it('says what the app is, in terms of what the user gets', () => {
    render(<NoProjectLanding projects={[]} onCreateProject={() => {}} onOpenProject={() => {}} />)

    expect(screen.getByText('Copperplane')).toBeTruthy()
    expect(screen.getByText(/sizing an\s+enclosure that actually fits/)).toBeTruthy()
  })

  it('offers to create a project', () => {
    const onCreateProject = vi.fn()
    render(
      <NoProjectLanding projects={[]} onCreateProject={onCreateProject} onOpenProject={() => {}} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'New project' }))
    expect(onCreateProject).toHaveBeenCalled()
  })

  it('does not offer to open a project when there are none', () => {
    /** A button that opens an empty list is how a first run starts with a
     *  dead end. */
    render(<NoProjectLanding projects={[]} onCreateProject={() => {}} onOpenProject={() => {}} />)

    expect(screen.queryByRole('button', { name: /Open a project/ })).toBeNull()
    expect(screen.getByText(/No projects yet/)).toBeTruthy()
  })

  it('opens the project the user picks, from a list on this view', () => {
    /** The first version took no argument and set a message telling the user
     *  to use the rail -- a message rendered only inside the project view, so
     *  clicking the button did nothing whatsoever. Reported from the built
     *  app: "I clicked open a project and nothing happened." */
    const onOpenProject = vi.fn()
    render(
      <NoProjectLanding
        projects={['alpha', 'beta', 'gamma']}
        onCreateProject={() => {}}
        onOpenProject={onOpenProject}
      />,
    )

    expect(screen.getByText('(3)')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Open a project/ }))
    fireEvent.click(screen.getByRole('button', { name: 'beta' }))

    expect(onOpenProject).toHaveBeenCalledWith('beta')
  })

  it('does not show the project list until it is asked for', () => {
    render(
      <NoProjectLanding projects={['alpha']} onCreateProject={() => {}} onOpenProject={() => {}} />,
    )

    expect(screen.queryByRole('button', { name: 'alpha' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Open a project/ }))
    expect(screen.getByRole('button', { name: 'alpha' })).toBeTruthy()
  })

  it('every action on this view does something', () => {
    /** The guard for the class of bug, not just the instance: a control here
     *  must be wired to a handler, never to a message that renders elsewhere. */
    const onCreateProject = vi.fn()
    const onOpenProject = vi.fn()
    render(
      <NoProjectLanding
        projects={['alpha']}
        onCreateProject={onCreateProject}
        onOpenProject={onOpenProject}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'New project' }))
    expect(onCreateProject).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /Open a project/ }))
    fireEvent.click(screen.getByRole('button', { name: 'alpha' }))
    expect(onOpenProject).toHaveBeenCalledWith('alpha')
  })

  it('does not claim there are no projects while it is still looking', () => {
    /** The list is read off disk; asserting "none" before it lands is a
     *  false statement about the user's own files. */
    render(
      <NoProjectLanding projects={[]} loading onCreateProject={() => {}} onOpenProject={() => {}} />,
    )

    expect(screen.queryByText(/No projects yet/)).toBeNull()
    expect(screen.getByText(/Loading your projects/)).toBeTruthy()
  })

  it('opens the repo in the real browser, not in an app window', () => {
    render(<NoProjectLanding projects={[]} onCreateProject={() => {}} onOpenProject={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: /Source and documentation/ }))
    expect(openExternalMock).toHaveBeenCalledWith('https://github.com/GittieLabs/copperplane')
  })

  it('promises nothing about a docs site that does not exist', () => {
    /** SPEC-336 §3: "a link that 404s on first run is worse than no link."
     *  Settled 2026-09-03: provider docs only, no Copperplane docs site. */
    const { container } = render(
      <NoProjectLanding projects={[]} onCreateProject={() => {}} onOpenProject={() => {}} />,
    )

    expect(container.textContent).not.toMatch(/docs\.copperplane|copperplane\.(io|dev|com)/)
  })
})
