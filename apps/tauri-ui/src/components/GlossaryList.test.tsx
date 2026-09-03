import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { GlossaryList } from './GlossaryList'

/** SPEC-334: "it would be helpful to have a glossary of terms for Kicad." */
describe('GlossaryList', () => {
  it('lists the vocabulary', () => {
    render(<GlossaryList />)

    expect(screen.getByText('THT')).toBeTruthy()
    expect(screen.getByText('DIP')).toBeTruthy()
    expect(screen.getByText('QFN')).toBeTruthy()
  })

  it('filters by term and by meaning, so a half-remembered word finds it', () => {
    render(<GlossaryList />)

    fireEvent.change(screen.getByPlaceholderText('THT, QFN, 0805…'), {
      target: { value: 'heatsink' },
    })

    // TO-220 is the one that bolts to a heatsink, and nobody looks it up by name.
    expect(screen.getByText('TO')).toBeTruthy()
    expect(screen.queryByText('DIP')).toBeNull()
  })

  it('explains an unmatched search rather than showing an empty list', () => {
    render(<GlossaryList />)

    fireEvent.change(screen.getByPlaceholderText('THT, QFN, 0805…'), {
      target: { value: 'zzzz' },
    })

    expect(screen.getByText(/Nothing here matches/)).toBeTruthy()
  })

  it('lists the height letters once, not multiplied across every family', () => {
    render(<GlossaryList />)

    expect(screen.getByText('The letters in front of a package name')).toBeTruthy()
    expect(screen.queryByText('VQFN')).toBeNull()
    expect(screen.queryByText('TQFN')).toBeNull()
  })
})
