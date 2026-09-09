import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listHousesMock = vi.fn()
const cloneHouseMock = vi.fn()
const saveHouseMock = vi.fn()
const deleteHouseMock = vi.fn()
const resetHouseMock = vi.fn()
const exportHousesMock = vi.fn()
const importHousesMock = vi.fn()
const genericProfileMock = vi.fn()

vi.mock('../lib/fabricationReview', () => ({
  listHouses: listHousesMock,
  cloneHouse: cloneHouseMock,
  saveHouse: saveHouseMock,
  deleteHouse: deleteHouseMock,
  resetHouse: resetHouseMock,
  exportHouses: exportHousesMock,
  importHouses: importHousesMock,
  genericProfile: genericProfileMock,
}))

const { HouseLibrary } = await import('./HouseLibrary')

function house(overrides: Record<string, unknown> = {}) {
  return {
    house_id: 'acme',
    house_name: 'Acme PCB',
    min_drill: 0.3,
    min_track_width: 0.15,
    provenance: {
      min_drill: { source_url: '', recorded_on: '2026-09-09', confirmed_by_user: false },
      min_track_width: { source_url: '', recorded_on: '2026-09-09', confirmed_by_user: false },
    },
    ...overrides,
  }
}

beforeEach(() => {
  for (const m of [
    listHousesMock, cloneHouseMock, saveHouseMock, deleteHouseMock,
    resetHouseMock, exportHousesMock, importHousesMock, genericProfileMock,
  ]) {
    m.mockReset()
  }
  listHousesMock.mockResolvedValue([])
  saveHouseMock.mockResolvedValue(house())
  genericProfileMock.mockResolvedValue({
    house_name: 'Standard 2-layer process',
    is_template: true,
    min_drill: 0.3,
    provenance: {},
  })
})

function renderLibrary(chosenId: string | null = null) {
  const onChoose = vi.fn()
  render(<HouseLibrary chosenId={chosenId} onChoose={onChoose} onClose={vi.fn()} />)
  return onChoose
}

describe('HouseLibrary', () => {
  it('offers a starting point rather than an empty list with no way forward', async () => {
    renderLibrary()
    expect(await screen.findByText(/no board houses yet/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Start from standard 2-layer/i })).toBeTruthy()
  })

  it('says nothing is attributed to a vendor who did not publish it', async () => {
    // CTX-114.1 Deviation 6. The empty state is where a user decides what to
    // trust, so it is where this belongs.
    renderLibrary()
    expect(await screen.findByText(/did not publish it/i)).toBeTruthy()
  })

  it('always shows the standard numbers, read-only, so there is a way back', async () => {
    // Reported: "i can edit or remove any board settings." Nothing set
    // is_bundled anywhere, so the read-only rule protected nothing and there
    // were no default settings in the library to return to.
    listHousesMock.mockResolvedValue([])
    renderLibrary()

    expect(await screen.findByText('Standard 2-layer process')).toBeTruthy()
    expect(screen.getByText(/comes with the app, read-only/)).toBeTruthy()
    expect(screen.getByText(/always something to go back to/)).toBeTruthy()
  })

  it('offers only Clone on the standard numbers — never Edit, Remove or Use', async () => {
    listHousesMock.mockResolvedValue([])
    renderLibrary()

    await screen.findByText('Standard 2-layer process')
    expect(screen.getByRole('button', { name: 'Clone' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Remove' })).toBeNull()
    // SPEC-342 §2.5: a template is never what a board gets checked against.
    expect(screen.queryByRole('button', { name: /Use for this project/ })).toBeNull()
  })

  it('still shows the standard numbers once the user has houses of their own', async () => {
    listHousesMock.mockResolvedValue([house({ cloned_from: 'x' })])
    renderLibrary()

    expect(await screen.findByText('Standard 2-layer process')).toBeTruthy()
    expect(screen.getByText('Acme PCB')).toBeTruthy()
  })

  it('marks a house that is a copy of another', async () => {
    listHousesMock.mockResolvedValue([
      house(),
      house({ house_id: 'acme-2', house_name: 'My Acme', cloned_from: 'acme' }),
    ])
    renderLibrary()

    await screen.findByText('My Acme')
    expect(screen.getByText(/· a copy/)).toBeTruthy()
  })

  it('offers Edit and Remove on every house, because every house is editable', async () => {
    // SPEC-342 §2.6, simplified: the template is the only read-only thing.
    // Houses ship as an importable file, so any of them can be got back by
    // importing again -- locking one protects nothing.
    listHousesMock.mockResolvedValue([house()])
    renderLibrary()

    await screen.findByText('Acme PCB')
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Remove' })).toBeTruthy()
  })

  it('lets a project use a house, and says which one it already uses', async () => {
    listHousesMock.mockResolvedValue([house()])
    const onChoose = renderLibrary('acme')

    expect(await screen.findByText(/in use here/)).toBeTruthy()
    // No "use" button for the one already in use.
    expect(screen.queryByRole('button', { name: /Use for this project/ })).toBeNull()

    expect(onChoose).not.toHaveBeenCalled()
  })

  it('chooses a house that is not the current one', async () => {
    listHousesMock.mockResolvedValue([house()])
    const onChoose = renderLibrary(null)

    fireEvent.click(await screen.findByRole('button', { name: /Use for this project/ }))
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ house_id: 'acme' }))
  })

  it('says a clone starts unconfirmed, because it did not inherit a check', async () => {
    listHousesMock.mockResolvedValue([house()])
    cloneHouseMock.mockResolvedValue(house({ house_id: 'acme-copy' }))
    renderLibrary()

    await screen.findByText('Acme PCB')
    // Two Clone buttons now: the standard numbers, and this house.
    fireEvent.click(screen.getAllByRole('button', { name: 'Clone' })[1])

    await waitFor(() => expect(cloneHouseMock).toHaveBeenCalled())
    expect(await screen.findByText(/unconfirmed until you check it/i)).toBeTruthy()
  })

  it('picks a free name instead of failing when the copy already exists', async () => {
    // Reported: "how would i rename this board?" -- the second click on Clone
    // (or on the template) hit "already exists. Rename this one" and there was
    // nothing in the UI that could rename anything. Cloning means "make another
    // one", so a name collision is never the right answer here.
    listHousesMock.mockResolvedValue([
      house(),
      house({ house_id: 'acme-pcb-copy', house_name: 'Acme PCB (copy)', cloned_from: 'acme' }),
    ])
    cloneHouseMock.mockResolvedValue(house({ house_id: 'acme-pcb-copy-2' }))
    renderLibrary()

    await screen.findByText('Acme PCB')
    fireEvent.click(screen.getAllByRole('button', { name: 'Clone' })[1])

    await waitFor(() => expect(cloneHouseMock).toHaveBeenCalled())
    const [, name, id] = cloneHouseMock.mock.calls[0]
    expect(name).toBe('Acme PCB (copy) 2')
    expect(id).toBe('acme-pcb-copy-2')
  })

  it('renames a house, keeping its id so projects using it are not orphaned', async () => {
    listHousesMock.mockResolvedValue([house({ cloned_from: 'acme' })])
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'JLCPCB 2-layer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(saveHouseMock).toHaveBeenCalled())
    const [saved, overwrite] = saveHouseMock.mock.calls[0]
    expect(saved.house_name).toBe('JLCPCB 2-layer')
    expect(saved.house_id).toBe('acme')
    expect(overwrite).toBe(true)
  })

  it('refuses a blank name rather than saving a house nothing can identify', async () => {
    listHousesMock.mockResolvedValue([house({ cloned_from: 'acme' })])
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText(/needs a name/i)).toBeTruthy()
    expect(saveHouseMock).not.toHaveBeenCalled()
  })

  it('saves an edit to a house the user owns', async () => {
    listHousesMock.mockResolvedValue([house({ cloned_from: 'acme' })])
    saveHouseMock.mockResolvedValue(house({ cloned_from: 'acme', min_drill: 0.25 }))
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Minimum drill'), { target: { value: '0.25' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(saveHouseMock).toHaveBeenCalled())
    const [saved] = saveHouseMock.mock.calls[0]
    expect(saved.min_drill).toBe(0.25)
  })

  it('refuses a measurement that is not a positive number', async () => {
    listHousesMock.mockResolvedValue([house({ cloned_from: 'acme' })])
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Minimum drill'), { target: { value: '-1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText(/positive measurement/i)).toBeTruthy()
    expect(saveHouseMock).not.toHaveBeenCalled()
  })

  it('offers reset only on a copy, since there is nothing else to go back to', async () => {
    listHousesMock.mockResolvedValue([house()])
    const { unmount } = render(
      <HouseLibrary chosenId={null} onChoose={vi.fn()} onClose={vi.fn()} />,
    )
    await screen.findByText('Acme PCB')
    expect(screen.queryByRole('button', { name: /Reset to shipped/ })).toBeNull()
    unmount()

    listHousesMock.mockResolvedValue([house({ house_id: 'acme-mine', cloned_from: 'acme' })])
    renderLibrary()
    expect(await screen.findByRole('button', { name: /Reset to shipped/ })).toBeTruthy()
  })

  it('resets a copy back to the house it came from', async () => {
    listHousesMock.mockResolvedValue([house({ house_id: 'acme-mine', cloned_from: 'acme' })])
    resetHouseMock.mockResolvedValue(house({ house_name: 'Acme PCB' }))
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: /Reset to shipped/ }))

    await waitFor(() => expect(resetHouseMock).toHaveBeenCalledWith('acme-mine'))
    expect(await screen.findByText(/as it shipped/i)).toBeTruthy()
  })

  it('says which projects still show a removed house’s numbers', async () => {
    listHousesMock.mockResolvedValue([house()])
    deleteHouseMock.mockResolvedValue({ still_referenced_by: ['weather-pcb'] })
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))

    expect(await screen.findByText(/weather-pcb still shows the numbers/)).toBeTruthy()
  })

  it('asks what to do when an import collides, rather than deciding for the user', async () => {
    listHousesMock.mockResolvedValue([house()])
    importHousesMock.mockResolvedValue({
      imported: [],
      skipped_existing: ['acme'],
      renamed: [],
      rejected: [],
    })
    Object.assign(navigator, {
      clipboard: { readText: vi.fn().mockResolvedValue('{"houses":[]}'), writeText: vi.fn() },
    })
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: /Import from clipboard/ }))

    // Nothing changed yet; the user picks, because only they know whether the
    // copy they have is one they edited.
    expect(await screen.findByText(/Nothing has been changed yet/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Keep both' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Replace mine' })).toBeTruthy()
  })

  it('brings both in when the user says keep both', async () => {
    listHousesMock.mockResolvedValue([house()])
    importHousesMock
      .mockResolvedValueOnce({ imported: [], skipped_existing: ['acme'], renamed: [], rejected: [] })
      .mockResolvedValueOnce({
        imported: ['acme-2'],
        skipped_existing: [],
        renamed: [{ from: 'acme', to: 'acme-2' }],
        rejected: [],
      })
    Object.assign(navigator, {
      clipboard: { readText: vi.fn().mockResolvedValue('{"houses":[]}'), writeText: vi.fn() },
    })
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: /Import from clipboard/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Keep both' }))

    await waitFor(() => expect(importHousesMock).toHaveBeenCalledTimes(2))
    expect(importHousesMock.mock.calls[1][1]).toBe('rename')
    expect(await screen.findByText(/brought in alongside/)).toBeTruthy()
  })

  it('surfaces a failure instead of leaving the list looking unchanged', async () => {
    listHousesMock.mockResolvedValue([house()])
    deleteHouseMock.mockRejectedValue(new Error('storage is unavailable'))
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
    expect(await screen.findByText(/storage is unavailable/)).toBeTruthy()
  })
})
