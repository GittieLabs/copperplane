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

  it('marks which houses came with the app and which are the user’s copies', async () => {
    listHousesMock.mockResolvedValue([
      house({ is_bundled: true }),
      house({ house_id: 'acme-mine', house_name: 'My Acme', cloned_from: 'acme' }),
    ])
    renderLibrary()

    expect(await screen.findByText(/came with the app, read-only/)).toBeTruthy()
    expect(screen.getByText(/your copy/)).toBeTruthy()
  })

  it('offers Clone but not Edit on a house that came with the app', async () => {
    // Requested directly: "we should only allow edits on a cloned template ...
    // you can clone any template though. allowing edits to template bundled
    // with the app would prevent us from getting back to default settings."
    listHousesMock.mockResolvedValue([house({ is_bundled: true })])
    renderLibrary()

    expect(await screen.findByRole('button', { name: 'Clone' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    // Removing it would lose the known-good copy just as surely as editing it.
    expect(screen.queryByRole('button', { name: 'Remove' })).toBeNull()
  })

  it('offers Edit on a house the user owns', async () => {
    listHousesMock.mockResolvedValue([house({ cloned_from: 'acme' })])
    renderLibrary()

    expect(await screen.findByRole('button', { name: 'Edit' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Remove' })).toBeTruthy()
  })

  it('offers Edit on an imported house, which is not bundled', async () => {
    // An imported house can be imported again, so there is no reason to lock
    // it -- the read-only rule is about recovery, not about origin.
    listHousesMock.mockResolvedValue([house({ is_bundled: false })])
    renderLibrary()
    expect(await screen.findByRole('button', { name: 'Edit' })).toBeTruthy()
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

    fireEvent.click(await screen.findByRole('button', { name: 'Clone' }))

    await waitFor(() => expect(cloneHouseMock).toHaveBeenCalled())
    expect(await screen.findByText(/unconfirmed until you check it/i)).toBeTruthy()
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
    listHousesMock.mockResolvedValue([house({ is_bundled: true })])
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

  it('reports an import that skipped an existing house rather than merging it', async () => {
    listHousesMock.mockResolvedValue([house()])
    importHousesMock.mockResolvedValue({
      imported: ['bravo'],
      skipped_existing: ['acme'],
      rejected: [],
    })
    Object.assign(navigator, {
      clipboard: { readText: vi.fn().mockResolvedValue('{"houses":[]}'), writeText: vi.fn() },
    })
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: /Import from clipboard/ }))

    expect(await screen.findByText(/already in your library and left alone/)).toBeTruthy()
  })

  it('surfaces a failure instead of leaving the list looking unchanged', async () => {
    listHousesMock.mockResolvedValue([house()])
    deleteHouseMock.mockRejectedValue(new Error('storage is unavailable'))
    renderLibrary()

    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
    expect(await screen.findByText(/storage is unavailable/)).toBeTruthy()
  })
})
