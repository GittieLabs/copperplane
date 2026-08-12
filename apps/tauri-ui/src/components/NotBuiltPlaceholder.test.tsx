import { render, screen } from '@testing-library/react'
import { describe, it } from 'vitest'
import { NotBuiltPlaceholder } from './NotBuiltPlaceholder'

describe('NotBuiltPlaceholder', () => {
  it('SPEC-305: names the owning spec, never a bare "not built" with no context', () => {
    render(
      <NotBuiltPlaceholder
        specId="SPEC-306"
        title="Components"
        description="Search and disambiguate a part number."
      />,
    )

    screen.getByText('Components — not built yet')
    screen.getByText('Search and disambiguate a part number.')
    screen.getByText('Coming in SPEC-306')
  })
})
