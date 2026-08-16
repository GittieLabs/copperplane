import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const getCapabilitiesMock = vi.fn()
const getConfigMock = vi.fn()
const saveConfigMock = vi.fn()
const saveSecretMock = vi.fn()
const clearSecretMock = vi.fn()
const setLlmProviderAndModelMock = vi.fn()
const copyDiagnosticsMock = vi.fn()
const chooseStorageFolderMock = vi.fn()
const confirmStorageLocationChangeMock = vi.fn()
const restartAppMock = vi.fn()
const checkForUpdatesMock = vi.fn()
const installUpdateAndRelaunchMock = vi.fn()

vi.mock('../lib/settings', async () => {
  const actual = await vi.importActual<typeof import('../lib/settings')>('../lib/settings')
  return {
    ...actual,
    getCapabilities: (...args: unknown[]) => getCapabilitiesMock(...args),
    getConfig: (...args: unknown[]) => getConfigMock(...args),
    saveConfig: (...args: unknown[]) => saveConfigMock(...args),
    saveSecret: (...args: unknown[]) => saveSecretMock(...args),
    clearSecret: (...args: unknown[]) => clearSecretMock(...args),
    setLlmProviderAndModel: (...args: unknown[]) => setLlmProviderAndModelMock(...args),
    copyDiagnostics: (...args: unknown[]) => copyDiagnosticsMock(...args),
    chooseStorageFolder: (...args: unknown[]) => chooseStorageFolderMock(...args),
    confirmStorageLocationChange: (...args: unknown[]) => confirmStorageLocationChangeMock(...args),
    restartApp: (...args: unknown[]) => restartAppMock(...args),
  }
})

vi.mock('../lib/updater', () => ({
  checkForUpdates: (...args: unknown[]) => checkForUpdatesMock(...args),
  installUpdateAndRelaunch: (...args: unknown[]) => installUpdateAndRelaunchMock(...args),
}))

const { Settings } = await import('./Settings')

const EMPTY_CAPABILITIES = {
  kicad_available: false,
  freecad_available: false,
  llm_providers: [],
  log_path: '/var/log/daemon.log',
  python_version: '3.12.0',
  storage_root: '/Users/test/Library/Application Support/has/storage',
}
const EMPTY_CONFIG = { llm_provider: null, llm_model: null }

beforeEach(() => {
  getCapabilitiesMock.mockReset().mockResolvedValue(EMPTY_CAPABILITIES)
  copyDiagnosticsMock.mockReset().mockResolvedValue(undefined)
  getConfigMock.mockReset().mockResolvedValue(EMPTY_CONFIG)
  saveConfigMock.mockReset().mockResolvedValue(undefined)
  saveSecretMock.mockReset().mockResolvedValue(undefined)
  clearSecretMock.mockReset().mockResolvedValue(undefined)
  setLlmProviderAndModelMock.mockReset().mockResolvedValue(undefined)
  chooseStorageFolderMock.mockReset()
  confirmStorageLocationChangeMock.mockReset().mockResolvedValue(false)
  restartAppMock.mockReset().mockResolvedValue(undefined)
  checkForUpdatesMock.mockReset()
  installUpdateAndRelaunchMock.mockReset().mockResolvedValue(undefined)
})

describe('Settings: Tier 1 (provider/model/keys)', () => {
  it('TEST-006: an unconfigured provider shows a key input and Save button', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    expect(screen.getByLabelText('anthropic API key')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Save' }).length).toBeGreaterThan(0)
  })

  it('TEST-006: saving a key calls saveSecret then refreshes capabilities, never showing the value again', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText('anthropic API key'), { target: { value: 'sk-real-secret' } })
    getCapabilitiesMock.mockResolvedValueOnce({ ...EMPTY_CAPABILITIES, llm_providers: ['anthropic'] })
    fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[0])

    await waitFor(() => expect(saveSecretMock).toHaveBeenCalledWith('anthropic_api_key', 'sk-real-secret'))
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByText('configured')).toBeTruthy())

    // The saved value must never appear anywhere in the rendered output.
    expect(screen.queryByText('sk-real-secret')).toBeNull()
    expect(screen.queryByDisplayValue('sk-real-secret')).toBeNull()
  })

  it('TEST-006: a configured provider shows Clear instead of a key input, and clearing refreshes capabilities', async () => {
    getCapabilitiesMock.mockResolvedValue({ ...EMPTY_CAPABILITIES, llm_providers: ['google'] })

    render(<Settings />)
    await waitFor(() => expect(screen.getAllByText('configured').length).toBeGreaterThan(0))

    expect(screen.queryByLabelText('google API key')).toBeNull()

    getCapabilitiesMock.mockResolvedValueOnce(EMPTY_CAPABILITIES)
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))

    await waitFor(() => expect(clearSecretMock).toHaveBeenCalledWith('google_api_key'))
    await waitFor(() => expect(screen.getByLabelText('google API key')).toBeTruthy())
  })

  it("TEST-006: changing the provider select calls setLlmProviderAndModel with the current config", async () => {
    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('LLM provider'), { target: { value: 'perplexity' } })

    await waitFor(() =>
      expect(setLlmProviderAndModelMock).toHaveBeenCalledWith('perplexity', null, EMPTY_CONFIG),
    )
  })

  it('surfaces an error message when getCapabilities fails, without crashing the screen', async () => {
    getCapabilitiesMock.mockReset().mockRejectedValueOnce(new Error('daemon unreachable'))

    render(<Settings />)

    await waitFor(() => expect(screen.getByText('daemon unreachable')).toBeTruthy())
  })
})

describe('Settings: Supplier APIs (SPEC-203, CTX-203.1)', () => {
  it('an unconfigured supplier shows one input per field, with Save disabled until all are filled', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    expect(screen.getByLabelText('DigiKey Client ID')).toBeTruthy()
    expect(screen.getByLabelText('DigiKey Client Secret')).toBeTruthy()
    expect(screen.getByLabelText('Mouser API Key')).toBeTruthy()
    expect(screen.getByLabelText('Octopart API Key')).toBeTruthy()

    const mouserSave = screen.getByLabelText('Mouser API Key').closest('div')!.parentElement!
    const saveButton = Array.from(mouserSave.querySelectorAll('button')).find(
      (b) => b.textContent === 'Save',
    ) as HTMLButtonElement
    expect(saveButton.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Mouser API Key'), { target: { value: 'm-real-key' } })
    expect(saveButton.disabled).toBe(false)
  })

  it("DigiKey's Save stays disabled until BOTH fields are filled, then saves both on click", async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    const digikeyRow = screen.getByLabelText('DigiKey Client ID').closest('div')!.parentElement!
    const saveButton = Array.from(digikeyRow.querySelectorAll('button')).find(
      (b) => b.textContent === 'Save',
    ) as HTMLButtonElement

    fireEvent.change(screen.getByLabelText('DigiKey Client ID'), { target: { value: 'id-123' } })
    expect(saveButton.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('DigiKey Client Secret'), { target: { value: 'secret-456' } })
    expect(saveButton.disabled).toBe(false)

    getCapabilitiesMock.mockResolvedValueOnce({ ...EMPTY_CAPABILITIES, digikey_available: true })
    fireEvent.click(saveButton)

    await waitFor(() => expect(saveSecretMock).toHaveBeenCalledWith('digikey_client_id', 'id-123'))
    expect(saveSecretMock).toHaveBeenCalledWith('digikey_client_secret', 'secret-456')
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(2))
  })

  it('a configured supplier shows Clear instead of inputs, and clearing clears every one of its fields', async () => {
    getCapabilitiesMock.mockResolvedValue({ ...EMPTY_CAPABILITIES, mouser_available: true })

    render(<Settings />)
    await waitFor(() => expect(screen.getAllByText('configured').length).toBeGreaterThan(0))

    expect(screen.queryByLabelText('Mouser API Key')).toBeNull()

    getCapabilitiesMock.mockResolvedValueOnce(EMPTY_CAPABILITIES)
    const mouserRow = screen.getByText('Mouser').closest('div')!
    fireEvent.click(mouserRow.querySelector('button')!)

    await waitFor(() => expect(clearSecretMock).toHaveBeenCalledWith('mouser_api_key'))
    await waitFor(() => expect(screen.getByLabelText('Mouser API Key')).toBeTruthy())
  })
})

describe('Settings: Tier 2 (KiCad/FreeCAD status + paths)', () => {
  it('TEST-007: renders reachable/not-reachable status from capabilities', async () => {
    getCapabilitiesMock.mockResolvedValue({
      kicad_available: true,
      freecad_available: false,
      llm_providers: [],
    })

    render(<Settings />)

    await waitFor(() => expect(screen.getByText('KiCad: reachable')).toBeTruthy())
    screen.getByText('FreeCAD: not reachable')
  })

  it('TEST-007: the restart-to-apply notice is present once, scoped to the path fields section', async () => {
    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    expect(
      screen.getByText('These four fields are only read at daemon startup — restart the app to apply a change.'),
    ).toBeTruthy()
    // Tier 1's provider/model fields must not carry this notice -- they
    // apply live, no restart needed.
    expect(screen.getByLabelText('LLM provider').closest('section')?.textContent).not.toMatch(/restart/i)
  })

  it('TEST-007: saving path overrides calls saveConfig with the current config merged in, and confirms without claiming a live update', async () => {
    getConfigMock.mockResolvedValue({
      llm_provider: 'anthropic',
      llm_model: 'claude-sonnet',
      kicad_socket_path: null,
      kicad_timeout_ms: null,
      freecadcmd_path_override: null,
    })

    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('KiCad IPC socket path'), {
      target: { value: '/tmp/kicad/api.sock' },
    })
    fireEvent.change(screen.getByLabelText('freecadcmd path override'), {
      target: { value: '/opt/freecad/bin/freecadcmd' },
    })

    // There are multiple "Save" buttons (one per unconfigured provider,
    // plus this section's own) -- the connectivity section's Save is the
    // last one rendered, since Tier 1 renders above it.
    const saveButtons = screen.getAllByRole('button', { name: 'Save' })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() =>
      expect(saveConfigMock).toHaveBeenCalledWith({
        llm_provider: 'anthropic',
        llm_model: 'claude-sonnet',
        kicad_socket_path: '/tmp/kicad/api.sock',
        kicad_timeout_ms: null,
        freecadcmd_path_override: '/opt/freecad/bin/freecadcmd',
        storage_root_override: null,
      }),
    )
    await waitFor(() => expect(screen.getByText('Saved — restart to apply.')).toBeTruthy())
  })

  it('SPEC-110: shows the real current storage_root from capabilities, never config.json', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    screen.getByText(`Currently: ${EMPTY_CAPABILITIES.storage_root}`)
  })

  it('SPEC-110: "Choose folder…" calls chooseStorageFolder and fills the field with the real chosen path', async () => {
    chooseStorageFolderMock.mockResolvedValueOnce('/Volumes/External/has-storage')

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'Choose folder…' }))

    await waitFor(() =>
      expect((screen.getByLabelText('Storage location') as HTMLInputElement).value).toBe(
        '/Volumes/External/has-storage',
      ),
    )
  })

  it('SPEC-110: a cancelled folder picker (null) leaves the field unchanged', async () => {
    chooseStorageFolderMock.mockResolvedValueOnce(null)

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'Choose folder…' }))

    await waitFor(() => expect(chooseStorageFolderMock).toHaveBeenCalledTimes(1))
    expect((screen.getByLabelText('Storage location') as HTMLInputElement).value).toBe('')
  })

  it('SPEC-110: saving a chosen storage folder calls saveConfig with storage_root_override set, and shows the real restart-safety modal', async () => {
    getConfigMock.mockResolvedValue({
      llm_provider: 'anthropic',
      llm_model: 'claude-sonnet',
      kicad_socket_path: null,
      kicad_timeout_ms: null,
      freecadcmd_path_override: null,
      storage_root_override: null,
    })

    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Storage location'), {
      target: { value: '/Volumes/External/has-storage' },
    })

    const saveButtons = screen.getAllByRole('button', { name: 'Save' })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() =>
      expect(saveConfigMock).toHaveBeenCalledWith(
        expect.objectContaining({ storage_root_override: '/Volumes/External/has-storage' }),
      ),
    )
    // A real, changed storage location triggers the harder-to-ignore
    // native modal, not just the passive "restart to apply" text.
    await waitFor(() => expect(confirmStorageLocationChangeMock).toHaveBeenCalledTimes(1))
  })

  it('SPEC-110: confirming the restart-safety modal actually relaunches the app', async () => {
    confirmStorageLocationChangeMock.mockResolvedValueOnce(true)
    getConfigMock.mockResolvedValue({
      llm_provider: 'anthropic', llm_model: 'claude-sonnet',
      kicad_socket_path: null, kicad_timeout_ms: null, freecadcmd_path_override: null,
      storage_root_override: null,
    })

    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Storage location'), {
      target: { value: '/Volumes/External/has-storage' },
    })
    const saveButtons = screen.getAllByRole('button', { name: 'Save' })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() => expect(restartAppMock).toHaveBeenCalledTimes(1))
  })

  it('SPEC-110: saving an unchanged storage location never shows the modal -- only a real change does', async () => {
    getConfigMock.mockResolvedValue({
      llm_provider: 'anthropic', llm_model: 'claude-sonnet',
      kicad_socket_path: null, kicad_timeout_ms: null, freecadcmd_path_override: null,
      storage_root_override: '/Volumes/External/has-storage',
    })

    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    const saveButtons = screen.getAllByRole('button', { name: 'Save' })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() => expect(saveConfigMock).toHaveBeenCalled())
    expect(confirmStorageLocationChangeMock).not.toHaveBeenCalled()
  })

  it('SPEC-110 regression: re-selecting the currently-active folder via the picker must not trigger the modal', async () => {
    /** Real bug found by hand: "Choose folder…" opens at
     * capabilities.storage_root (the current real path) as its default
     * location. A user who opens it and picks that same folder -- a
     * completely natural action -- ends up with a non-null override
     * string identical to the current default; a raw field-vs-field
     * comparison wrongly called that "changed." */
    getConfigMock.mockResolvedValue({
      llm_provider: 'anthropic', llm_model: 'claude-sonnet',
      kicad_socket_path: null, kicad_timeout_ms: null, freecadcmd_path_override: null,
      storage_root_override: null,
    })
    chooseStorageFolderMock.mockResolvedValueOnce(EMPTY_CAPABILITIES.storage_root)

    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'Choose folder…' }))
    await waitFor(() =>
      expect((screen.getByLabelText('Storage location') as HTMLInputElement).value).toBe(
        EMPTY_CAPABILITIES.storage_root,
      ),
    )

    const saveButtons = screen.getAllByRole('button', { name: 'Save' })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() => expect(saveConfigMock).toHaveBeenCalled())
    expect(confirmStorageLocationChangeMock).not.toHaveBeenCalled()
  })

  it('SPEC-110: "Restart Now" next to the saved notice relaunches the app directly', async () => {
    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    const saveButtons = screen.getAllByRole('button', { name: 'Save' })
    fireEvent.click(saveButtons[saveButtons.length - 1])
    await waitFor(() => screen.getByRole('button', { name: 'Restart Now' }))

    fireEvent.click(screen.getByRole('button', { name: 'Restart Now' }))

    await waitFor(() => expect(restartAppMock).toHaveBeenCalledTimes(1))
  })
})

describe('Settings: Updates (SPEC-402, CTX-402.2)', () => {
  it('checking for updates with none available shows "up to date", no install button', async () => {
    checkForUpdatesMock.mockResolvedValueOnce(null)

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Check for Updates' }))

    await waitFor(() => screen.getByText("You're up to date."))
    expect(screen.queryByRole('button', { name: 'Install & Restart' })).toBeNull()
  })

  it('a real available update shows its version, notes, and an Install & Restart button', async () => {
    checkForUpdatesMock.mockResolvedValueOnce({
      version: '0.2.0',
      currentVersion: '0.1.0',
      body: 'Real release notes.',
    })

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Check for Updates' }))

    await waitFor(() => screen.getByText(/Version 0.2.0 is available/))
    screen.getByText(/you have 0.1.0/)
    screen.getByText('Real release notes.')
    screen.getByRole('button', { name: 'Install & Restart' })
  })

  it('clicking Install & Restart calls installUpdateAndRelaunch with the real checked update', async () => {
    const fakeUpdate = { version: '0.2.0', currentVersion: '0.1.0', body: null }
    checkForUpdatesMock.mockResolvedValueOnce(fakeUpdate)

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Check for Updates' }))
    await waitFor(() => screen.getByRole('button', { name: 'Install & Restart' }))
    fireEvent.click(screen.getByRole('button', { name: 'Install & Restart' }))

    await waitFor(() => expect(installUpdateAndRelaunchMock).toHaveBeenCalledWith(fakeUpdate))
  })

  it('a failed check surfaces the real error, not a crash', async () => {
    checkForUpdatesMock.mockRejectedValueOnce(new Error('update server unreachable'))

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Check for Updates' }))

    await waitFor(() => screen.getByText('update server unreachable'))
  })

  it('a failed install surfaces the real error and does not relaunch', async () => {
    checkForUpdatesMock.mockResolvedValueOnce({ version: '0.2.0', currentVersion: '0.1.0', body: null })
    installUpdateAndRelaunchMock.mockReset().mockRejectedValueOnce(new Error('download failed'))

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Check for Updates' }))
    await waitFor(() => screen.getByRole('button', { name: 'Install & Restart' }))
    fireEvent.click(screen.getByRole('button', { name: 'Install & Restart' }))

    await waitFor(() => screen.getByText('download failed'))
  })
})

describe('Settings: Tier 3 (Copy Diagnostics)', () => {
  it('clicking Copy Diagnostics calls copyDiagnostics and confirms success', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'Copy Diagnostics' }))

    await waitFor(() => expect(copyDiagnosticsMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.getByText('Copied to clipboard.')).toBeTruthy())
  })

  it('surfaces an error instead of a false success message when copyDiagnostics fails', async () => {
    copyDiagnosticsMock.mockRejectedValueOnce(new Error('clipboard unavailable'))

    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    fireEvent.click(screen.getByRole('button', { name: 'Copy Diagnostics' }))

    await waitFor(() => expect(screen.getByText('clipboard unavailable')).toBeTruthy())
    expect(screen.queryByText('Copied to clipboard.')).toBeNull()
  })
})
