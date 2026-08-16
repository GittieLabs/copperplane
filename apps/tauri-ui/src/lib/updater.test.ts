import { beforeEach, describe, expect, it, vi } from 'vitest'

const checkMock = vi.fn()
const relaunchMock = vi.fn()

vi.mock('@tauri-apps/plugin-updater', () => ({ check: checkMock }))
vi.mock('@tauri-apps/plugin-process', () => ({ relaunch: relaunchMock }))

const { checkForUpdates, installUpdateAndRelaunch } = await import('./updater')

beforeEach(() => {
  checkMock.mockReset()
  relaunchMock.mockReset()
})

describe('checkForUpdates', () => {
  it('returns the real Update object when one is available', async () => {
    const fakeUpdate = { available: true, version: '0.2.0', currentVersion: '0.1.0' }
    checkMock.mockResolvedValueOnce(fakeUpdate)

    await expect(checkForUpdates()).resolves.toBe(fakeUpdate)
  })

  it('returns null, not the raw object, when no update is available', async () => {
    checkMock.mockResolvedValueOnce({ available: false })

    await expect(checkForUpdates()).resolves.toBeNull()
  })

  it('returns null when check() itself returns null (no endpoint reachable)', async () => {
    checkMock.mockResolvedValueOnce(null)

    await expect(checkForUpdates()).resolves.toBeNull()
  })
})

describe('installUpdateAndRelaunch', () => {
  it('downloads and installs the given update, then relaunches', async () => {
    const downloadAndInstall = vi.fn().mockResolvedValueOnce(undefined)
    const fakeUpdate = { downloadAndInstall } as unknown as Parameters<typeof installUpdateAndRelaunch>[0]

    await installUpdateAndRelaunch(fakeUpdate)

    expect(downloadAndInstall).toHaveBeenCalledTimes(1)
    expect(relaunchMock).toHaveBeenCalledTimes(1)
  })

  it('does not relaunch if the install itself fails', async () => {
    const downloadAndInstall = vi.fn().mockRejectedValueOnce(new Error('download failed'))
    const fakeUpdate = { downloadAndInstall } as unknown as Parameters<typeof installUpdateAndRelaunch>[0]

    await expect(installUpdateAndRelaunch(fakeUpdate)).rejects.toThrow('download failed')
    expect(relaunchMock).not.toHaveBeenCalled()
  })
})
