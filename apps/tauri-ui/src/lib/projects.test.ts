import { beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()
const openDialogMock = vi.fn()

vi.mock('./ipc', () => ({ dispatch: dispatchMock }))
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: openDialogMock }))

const {
  listProjects,
  saveProject,
  loadProject,
  pickProjectDirectory,
  openProjectFromDirectory,
  listLibraryParts,
  loadConversation,
  appendConversationTurn,
  setProjectFootprintOverride,
} = await import('./projects')

beforeEach(() => {
  dispatchMock.mockReset()
  openDialogMock.mockReset()
})

function ok(result: unknown) {
  return { jsonrpc: '2.0' as const, id: 1, result }
}

function fail(message: string) {
  return { jsonrpc: '2.0' as const, id: 1, error: { code: -32000, message } }
}

describe('listProjects', () => {
  it('dispatches project.list and returns the real project names', async () => {
    dispatchMock.mockResolvedValueOnce(ok(['weather-pcb', 'doorbell']))

    await expect(listProjects()).resolves.toEqual(['weather-pcb', 'doorbell'])
    expect(dispatchMock).toHaveBeenCalledWith('project.list', {})
  })

  it('throws on a daemon error rather than silently returning an empty list', async () => {
    dispatchMock.mockResolvedValueOnce(fail('storage_root not configured'))

    await expect(listProjects()).rejects.toThrow('storage_root not configured')
  })
})

describe('saveProject / loadProject', () => {
  it('saveProject dispatches project.save with the project payload', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ name: 'weather-pcb' }))

    await expect(saveProject({ name: 'weather-pcb' })).resolves.toEqual({ name: 'weather-pcb' })
    expect(dispatchMock).toHaveBeenCalledWith('project.save', { project: { name: 'weather-pcb' } })
  })

  it('loadProject dispatches project.load with the project name', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ name: 'weather-pcb' }))

    await loadProject('weather-pcb')
    expect(dispatchMock).toHaveBeenCalledWith('project.load', { name: 'weather-pcb' })
  })

  it('openProjectFromDirectory dispatches project.open_from_directory with the real directory', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ name: 'weather-pcb', directory: '/real/PCBs/weather-pcb' }))

    const result = await openProjectFromDirectory('/real/PCBs/weather-pcb')

    expect(result).toEqual({ name: 'weather-pcb', directory: '/real/PCBs/weather-pcb' })
    expect(dispatchMock).toHaveBeenCalledWith('project.open_from_directory', {
      directory: '/real/PCBs/weather-pcb',
    })
  })

  it('openProjectFromDirectory throws the real ProjectNotLinkedError message, not a silent failure', async () => {
    dispatchMock.mockResolvedValueOnce(fail("'/real/empty' isn't linked to a Copperplane project yet"))

    await expect(openProjectFromDirectory('/real/empty')).rejects.toThrow(
      "isn't linked to a Copperplane project yet",
    )
  })
})

describe('pickProjectDirectory', () => {
  it('opens a real directory-mode dialog and returns the picked folder', async () => {
    openDialogMock.mockResolvedValueOnce('/real/PCBs/weather-pcb')

    await expect(pickProjectDirectory()).resolves.toBe('/real/PCBs/weather-pcb')
    expect(openDialogMock).toHaveBeenCalledWith({ directory: true })
  })

  it('returns null, not an error, when the dialog is cancelled', async () => {
    openDialogMock.mockResolvedValueOnce(null)

    await expect(pickProjectDirectory()).resolves.toBeNull()
  })
})

describe('listLibraryParts', () => {
  it('dispatches library.list_parts and returns real part ids, zero on a fresh install', async () => {
    dispatchMock.mockResolvedValueOnce(ok([]))
    await expect(listLibraryParts()).resolves.toEqual([])
    expect(dispatchMock).toHaveBeenCalledWith('library.list_parts', {})
  })
})

describe('loadConversation / appendConversationTurn', () => {
  it('loadConversation dispatches project.load_conversation scoped to the project', async () => {
    dispatchMock.mockResolvedValueOnce(ok([{ role: 'user', content: 'hello' }]))

    const turns = await loadConversation('weather-pcb')
    expect(turns).toEqual([{ role: 'user', content: 'hello' }])
    expect(dispatchMock).toHaveBeenCalledWith('project.load_conversation', {
      project_name: 'weather-pcb',
    })
  })

  it('appendConversationTurn dispatches project.append_conversation_turn with the turn', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ appended: true }))

    await appendConversationTurn('weather-pcb', { role: 'assistant', content: 'hi' })
    expect(dispatchMock).toHaveBeenCalledWith('project.append_conversation_turn', {
      project_name: 'weather-pcb',
      turn: { role: 'assistant', content: 'hi' },
    })
  })

  it('appendConversationTurn throws on a schema validation error rather than silently dropping the turn', async () => {
    dispatchMock.mockResolvedValueOnce(fail('Server error: some validation failure'))

    await expect(
      appendConversationTurn('weather-pcb', { role: 'user', content: 'x' }),
    ).rejects.toThrow('some validation failure')
  })
})

describe('setProjectFootprintOverride', () => {
  it('dispatches project.set_footprint_override with the real project/part/footprint ids', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ name: 'weather-pcb', footprint_overrides: { ATtiny85: 'SOIC-8' } }))

    const result = await setProjectFootprintOverride('weather-pcb', 'ATtiny85', 'SOIC-8')

    expect(result.footprint_overrides).toEqual({ ATtiny85: 'SOIC-8' })
    expect(dispatchMock).toHaveBeenCalledWith('project.set_footprint_override', {
      project_name: 'weather-pcb',
      part_id: 'ATtiny85',
      footprint_id: 'SOIC-8',
    })
  })

  it('passes footprint_id: null through to clear an existing override', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ name: 'weather-pcb', footprint_overrides: {} }))

    await setProjectFootprintOverride('weather-pcb', 'ATtiny85', null)

    expect(dispatchMock).toHaveBeenCalledWith('project.set_footprint_override', {
      project_name: 'weather-pcb',
      part_id: 'ATtiny85',
      footprint_id: null,
    })
  })
})
