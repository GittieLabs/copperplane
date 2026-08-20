import { beforeEach, describe, expect, it, vi } from 'vitest'

const invokeMock = vi.fn()

vi.mock('@tauri-apps/api/core', () => ({ invoke: (...args: unknown[]) => invokeMock(...args) }))

const { syncLibraryMenu, setDesignMenuEnabled } = await import('./menu')

beforeEach(() => {
  invokeMock.mockReset()
})

describe('syncLibraryMenu', () => {
  it('TEST-004: invokes update_library_menu with the real id/name pairs', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    const libraries = [
      { id: 'default', name: 'Default', part_count: 3, symbol_count: 1, footprint_count: 2 },
      { id: 'esp32-boards', name: 'ESP32 Boards', part_count: 1, symbol_count: 0, footprint_count: 1 },
    ]

    await syncLibraryMenu(libraries)

    expect(invokeMock).toHaveBeenCalledWith('update_library_menu', {
      libraries: [
        { id: 'default', name: 'Default' },
        { id: 'esp32-boards', name: 'ESP32 Boards' },
      ],
    })
  })

  it('TEST-005: swallows a rejected invoke rather than throwing', async () => {
    invokeMock.mockRejectedValueOnce(new Error('native menu not ready'))

    await expect(syncLibraryMenu([])).resolves.toBeUndefined()
  })
})

describe('setDesignMenuEnabled', () => {
  it('TEST-006: invokes set_design_menu_enabled with the real boolean', async () => {
    invokeMock.mockResolvedValueOnce(undefined)

    await setDesignMenuEnabled(true)

    expect(invokeMock).toHaveBeenCalledWith('set_design_menu_enabled', { enabled: true })
  })

  it('TEST-007: swallows a rejected invoke rather than throwing', async () => {
    invokeMock.mockRejectedValueOnce(new Error('menu_design not found'))

    await expect(setDesignMenuEnabled(false)).resolves.toBeUndefined()
  })
})
