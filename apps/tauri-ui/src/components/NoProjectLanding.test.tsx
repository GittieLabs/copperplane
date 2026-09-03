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
    render(<NoProjectLanding projectCount={0} onCreateProject={() => {}} onOpenProject={() => {}} />)

    expect(screen.getByText('Copperplane')).toBeTruthy()
    expect(screen.getByText(/sizing an\s+enclosure that actually fits/)).toBeTruthy()
  })

  it('offers to create a project', () => {
    const onCreateProject = vi.fn()
    render(
      <NoProjectLanding projectCount={0} onCreateProject={onCreateProject} onOpenProject={() => {}} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'New project' }))
    expect(onCreateProject).toHaveBeenCalled()
  })

  it('does not offer to open a project when there are none', () => {
    /** A button that opens an empty list is how a first run starts with a
     *  dead end. */
    render(<NoProjectLanding projectCount={0} onCreateProject={() => {}} onOpenProject={() => {}} />)

    expect(screen.queryByRole('button', { name: /Open a project/ })).toBeNull()
    expect(screen.getByText(/No projects yet/)).toBeTruthy()
  })

  it('offers to open one, with a count, when projects exist', () => {
    const onOpenProject = vi.fn()
    render(
      <NoProjectLanding projectCount={3} onCreateProject={() => {}} onOpenProject={onOpenProject} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Open a project/ }))
    expect(onOpenProject).toHaveBeenCalled()
    expect(screen.getByText('(3)')).toBeTruthy()
  })

  it('does not claim there are no projects while it is still looking', () => {
    /** The list is read off disk; asserting "none" before it lands is a
     *  false statement about the user's own files. */
    render(
      <NoProjectLanding projectCount={0} loading onCreateProject={() => {}} onOpenProject={() => {}} />,
    )

    expect(screen.queryByText(/No projects yet/)).toBeNull()
    expect(screen.getByText(/Loading your projects/)).toBeTruthy()
  })

  it('opens the repo in the real browser, not in an app window', () => {
    render(<NoProjectLanding projectCount={0} onCreateProject={() => {}} onOpenProject={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: /Source and documentation/ }))
    expect(openExternalMock).toHaveBeenCalledWith('https://github.com/GittieLabs/copperplane')
  })

  it('promises nothing about a docs site that does not exist', () => {
    /** SPEC-336 §3: "a link that 404s on first run is worse than no link."
     *  Settled 2026-09-03: provider docs only, no Copperplane docs site. */
    const { container } = render(
      <NoProjectLanding projectCount={0} onCreateProject={() => {}} onOpenProject={() => {}} />,
    )

    expect(container.textContent).not.toMatch(/docs\.copperplane|copperplane\.(io|dev|com)/)
  })
})
