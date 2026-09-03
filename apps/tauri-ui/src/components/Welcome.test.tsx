import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Welcome } from './Welcome'

/** CTX-336.1 Phase 4, SPEC-336 steps 1-3. */
describe('Welcome', () => {
  it('offers both real paths', () => {
    const guided = vi.fn()
    const manual = vi.fn()
    render(<Welcome onChooseGuided={guided} onChooseManual={manual} onSkip={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Guide me through it' }))
    fireEvent.click(screen.getByRole('button', { name: /set it up myself/ }))

    expect(guided).toHaveBeenCalled()
    expect(manual).toHaveBeenCalled()
  })

  it('shows the managed path, disabled, and says why and roughly when', () => {
    /** SPEC-336 §3: "A disabled 'Managed' path invites clicking. It must say
     *  *why* it is disabled and roughly when, or it reads as broken rather
     *  than forthcoming." */
    render(<Welcome onChooseGuided={() => {}} onChooseManual={() => {}} onSkip={() => {}} />)

    expect(screen.getByText('Coming soon')).toBeTruthy()
    expect(screen.getByText(/hosted service\s+is still being built/)).toBeTruthy()
    const signIn = screen.getByRole('button', { name: 'Sign in' })
    expect(signIn.getAttribute('aria-disabled')).toBe('true')
    expect((signIn as HTMLButtonElement).disabled).toBe(true)
  })

  it('lets a user leave without configuring anything', () => {
    /** "A user may also be unsure about providing an api key and really want
     *  to see more before deciding." */
    const skip = vi.fn()
    render(<Welcome onChooseGuided={() => {}} onChooseManual={() => {}} onSkip={skip} />)

    fireEvent.click(screen.getByRole('button', { name: /Skip for now/ }))
    expect(skip).toHaveBeenCalled()
  })

  it('says where an API key is kept, before asking for one', () => {
    render(<Welcome onChooseGuided={() => {}} onChooseManual={() => {}} onSkip={() => {}} />)

    expect(screen.getByText(/keychain/)).toBeTruthy()
  })
})
