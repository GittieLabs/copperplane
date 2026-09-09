import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const genericProfileMock = vi.fn()
const setProjectProfileMock = vi.fn()
const listHousesMock = vi.fn()
const cloneHouseMock = vi.fn()
const saveHouseMock = vi.fn()

vi.mock('../lib/fabricationReview', () => ({
  genericProfile: genericProfileMock,
  setProjectProfile: setProjectProfileMock,
  // SPEC-342 section 2.5: the bundled numbers are a template, so starting from
  // them clones a house of the user's own rather than adopting the template.
  listHouses: listHousesMock,
  cloneHouse: cloneHouseMock,
  saveHouse: saveHouseMock,
}))

const { FabricationProfile } = await import('./FabricationProfile')

/** The real payload `fabrication.generic_profile` returned from the frozen
 *  sidecar: unbranded, every field unconfirmed, no source URL claiming a vendor
 *  published it. */
function genericFixture(recordedOn = '2026-09-08') {
  const fields = {
    min_track_width: 0.127,
    min_clearance: 0.127,
    min_annular_ring: 0.13,
    min_drill: 0.3,
    min_hole_to_hole: 0.5,
    min_silk_clearance: 0.15,
    min_text_height: 1.0,
    min_text_thickness: 0.15,
    min_edge_clearance: 0.2,
  }
  return {
    house_name: 'Generic 2-layer standard process (not a real vendor quote)',
    layer_count: 2,
    ...fields,
    provenance: Object.fromEntries(
      Object.keys(fields).map((key) => [
        key,
        { source_url: '', recorded_on: recordedOn, confirmed_by_user: false },
      ]),
    ),
  }
}

beforeEach(() => {
  genericProfileMock.mockReset()
  setProjectProfileMock.mockReset()
  listHousesMock.mockReset()
  cloneHouseMock.mockReset()
  saveHouseMock.mockReset()
  listHousesMock.mockResolvedValue([])
  saveHouseMock.mockResolvedValue(undefined)
  vi.useRealTimers()
})

describe('FabricationProfile', () => {
  // TEST-011
  it('gives a project with no linked board an empty state, not an error', () => {
    render(
      <FabricationProfile
        projectName="alpha"
        boardPath={null}
        profile={null}
        onProfileChange={vi.fn()}
      />,
    )
    const body = document.body.textContent ?? ''

    // SPEC-114 section 2.9: a profile can legitimately be chosen before a board
    // exists. That is an honest empty state.
    expect(body).toMatch(/no linked board yet/i)
    expect(body).not.toMatch(/error|failed/i)
    expect(screen.getByRole('button', { name: /standard 2-layer/i })).toBeTruthy()
  })

  // TEST-009
  it('clones the template into a house of the user’s own rather than adopting it', async () => {
    // SPEC-342 section 2.5: the template names no vendor, so it can never be a
    // project's board house. The daemon refuses it; this is the flow that makes
    // one click still do one thing.
    const template = { ...genericFixture(), is_template: true }
    const cloned = { ...genericFixture(), house_name: 'My standard 2-layer house' }
    genericProfileMock.mockResolvedValue(template)
    cloneHouseMock.mockResolvedValue(cloned)
    setProjectProfileMock.mockResolvedValue(undefined)
    const onChange = vi.fn()

    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={null}
        onProfileChange={onChange}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /standard 2-layer/i }))

    await waitFor(() => expect(onChange).toHaveBeenCalledWith(cloned))
    expect(cloneHouseMock).toHaveBeenCalled()
    expect(saveHouseMock).toHaveBeenCalledWith(cloned)
    // The template itself is never what the project checks against.
    expect(setProjectProfileMock).toHaveBeenCalledWith('alpha', cloned)
    expect(setProjectProfileMock).not.toHaveBeenCalledWith('alpha', template)
  })

  it('reuses an existing house instead of cloning a second copy', async () => {
    // The library is global: two projects starting the same way should share
    // one house they can edit once, not accumulate duplicates.
    const existing = { ...genericFixture(), house_id: 'my-standard-2-layer' }
    listHousesMock.mockResolvedValue([existing])
    setProjectProfileMock.mockResolvedValue(undefined)
    const onChange = vi.fn()

    render(
      <FabricationProfile
        projectName="beta"
        boardPath="/tmp/b.kicad_pcb"
        profile={null}
        onProfileChange={onChange}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /standard 2-layer/i }))

    await waitFor(() => expect(onChange).toHaveBeenCalledWith(existing))
    expect(cloneHouseMock).not.toHaveBeenCalled()
    expect(saveHouseMock).not.toHaveBeenCalled()
  })

  // TEST-008
  it('shows each value with its recorded date and confirmation state', () => {
    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={genericFixture() as never}
        onProfileChange={vi.fn()}
      />,
    )
    const body = document.body.textContent ?? ''
    expect(body).toContain('Minimum annular ring')
    expect(body).toContain('0.13 mm')
    expect(body).toContain('not confirmed')
    expect(body).toContain('recorded 2026-09-08')
  })

  it('names the process the numbers describe, next to the numbers', () => {
    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={genericFixture() as never}
        onProfileChange={vi.fn()}
      />,
    )
    // SPEC-340 section 3's mitigation for the too-strict-profile risk.
    expect(document.body.textContent).toMatch(/2-layer numbers/i)
  })

  it('says how many numbers did not come from the user’s own board house', () => {
    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={genericFixture() as never}
        onProfileChange={vi.fn()}
      />,
    )
    expect(document.body.textContent).toMatch(/9 of these came from a general standard process/i)
  })

  it('warns when the numbers are over a year old, without changing them', () => {
    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={genericFixture('2020-01-01') as never}
        onProfileChange={vi.fn()}
      />,
    )
    const body = document.body.textContent ?? ''
    expect(body).toMatch(/recorded over a year ago/i)
    // Reported, never silently repaired: the record still says what was checked.
    expect(body).toContain('recorded 2020-01-01')
  })

  // TEST-010
  it('omits a field the profile does not set rather than showing a guess', () => {
    const partial = genericFixture() as Record<string, unknown>
    partial.min_drill = null
    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={partial as never}
        onProfileChange={vi.fn()}
      />,
    )
    // An absent field produces no rule (SPEC-114 section 2.6), so showing a
    // number here would imply a limit the board house never published.
    expect(document.body.textContent).not.toContain('Minimum drill')
  })

  it('surfaces a store failure instead of pretending the choice was saved', async () => {
    genericProfileMock.mockResolvedValue({ ...genericFixture(), is_template: true })
    cloneHouseMock.mockResolvedValue(genericFixture())
    setProjectProfileMock.mockRejectedValue(new Error('min_drill must be positive'))
    const onChange = vi.fn()

    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={null}
        onProfileChange={onChange}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /standard 2-layer/i }))

    await waitFor(() => expect(document.body.textContent).toContain('min_drill must be positive'))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('clearing the choice returns to the empty state', async () => {
    setProjectProfileMock.mockResolvedValue(undefined)
    const onChange = vi.fn()

    render(
      <FabricationProfile
        projectName="alpha"
        boardPath="/tmp/b.kicad_pcb"
        profile={genericFixture() as never}
        onProfileChange={onChange}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /different house/i }))

    await waitFor(() => expect(onChange).toHaveBeenCalledWith(null))
    expect(setProjectProfileMock).toHaveBeenCalledWith('alpha', null)
  })
})
