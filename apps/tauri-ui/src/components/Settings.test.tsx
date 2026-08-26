import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

/** jsdom doesn't implement `matchMedia` -- `useThemePreference` (SPEC-317)
 * calls it on every render, so every test in this file needs a stub, not
 * just the theme-specific ones below. */
function stubMatchMedia(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
}

const getCapabilitiesMock = vi.fn()
const getConfigMock = vi.fn()
const saveConfigMock = vi.fn()
const saveSecretMock = vi.fn()
const clearSecretMock = vi.fn()
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

// SPEC-321/CTX-321.2: ProviderConfigEditor has its own dedicated test file
// (ProviderConfigEditor.test.tsx) -- stubbed here, matching AgentChat's own
// precedent, so Settings' tests stay focused on its own wiring (does it
// pass the real loaded config/capabilities, does onSaved/onCapabilitiesChange
// reach loadConfig/refreshCapabilities) and never need to mock
// getProviderRecords/saveProviderConfig just to render Settings at all.
vi.mock('./ProviderConfigEditor', () => ({
  ProviderConfigEditor: ({
    config,
    capabilities,
    onSaved,
    onCapabilitiesChange,
  }: {
    config: { llm_provider?: string | null }
    capabilities: { storage_root?: string | null } | null
    onSaved: () => Promise<void>
    onCapabilitiesChange: () => Promise<void>
  }) => (
    <div>
      <p>
        ProviderConfigEditor stub: llm_provider={String(config.llm_provider)} storage_root=
        {String(capabilities?.storage_root)}
      </p>
      <button onClick={() => void onSaved()}>stub-trigger-onSaved</button>
      <button onClick={() => void onCapabilitiesChange()}>stub-trigger-onCapabilitiesChange</button>
    </div>
  ),
}))

const { Settings } = await import('./Settings')

const EMPTY_CAPABILITIES = {
  kicad_available: false,
  kicad_socket_path_checked: '/tmp/kicad/api.sock',
  freecad_available: false,
  freecad_path_checked: null,
  freecad_error: null,
  llm_providers: [],
  log_path: '/var/log/daemon.log',
  python_version: '3.12.0',
  storage_root: '/Users/test/Library/Application Support/has/storage',
  github_token_configured: false,
  configured_secret_refs: [] as string[],
}
const EMPTY_CONFIG = { llm_provider: null, llm_model: null }

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  stubMatchMedia(false)
  getCapabilitiesMock.mockReset().mockResolvedValue(EMPTY_CAPABILITIES)
  copyDiagnosticsMock.mockReset().mockResolvedValue(undefined)
  getConfigMock.mockReset().mockResolvedValue(EMPTY_CONFIG)
  saveConfigMock.mockReset().mockResolvedValue(undefined)
  saveSecretMock.mockReset().mockResolvedValue(undefined)
  clearSecretMock.mockReset().mockResolvedValue(undefined)
  chooseStorageFolderMock.mockReset()
  confirmStorageLocationChangeMock.mockReset().mockResolvedValue(false)
  restartAppMock.mockReset().mockResolvedValue(undefined)
  checkForUpdatesMock.mockReset()
  installUpdateAndRelaunchMock.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Settings: Appearance (SPEC-317)', () => {
  it('defaults to System, with no resolved-theme note when the OS reads light', () => {
    render(<Settings />)

    const systemButton = screen.getByRole('radio', { name: 'System' })
    expect(systemButton.getAttribute('aria-checked')).toBe('true')
    expect(screen.getByText(/Currently resolves to Light/)).toBeTruthy()
  })

  it('shows the resolved theme when the OS reads dark', () => {
    stubMatchMedia(true)
    render(<Settings />)

    expect(screen.getByText(/Currently resolves to Dark/)).toBeTruthy()
  })

  it('selecting Light persists the choice, applies data-theme, and hides the System note', () => {
    render(<Settings />)

    fireEvent.click(screen.getByRole('radio', { name: 'Light' }))

    expect(screen.getByRole('radio', { name: 'Light' }).getAttribute('aria-checked')).toBe('true')
    expect(localStorage.getItem('theme-preference')).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(screen.queryByText(/Currently resolves to/)).toBeNull()
  })

  it('a previously stored preference is reflected on mount', () => {
    localStorage.setItem('theme-preference', 'dark')
    render(<Settings />)

    expect(screen.getByRole('radio', { name: 'Dark' }).getAttribute('aria-checked')).toBe('true')
  })
})

describe('Settings: Provider Configuration (SPEC-321)', () => {
  it('renders ProviderConfigEditor once config has loaded, passing the real loaded config/capabilities', async () => {
    getConfigMock.mockResolvedValue({ llm_provider: 'anthropic', llm_model: null })
    getCapabilitiesMock.mockResolvedValue({ ...EMPTY_CAPABILITIES, storage_root: '/real/storage/root' })

    render(<Settings />)

    await waitFor(() =>
      expect(screen.getByText(/ProviderConfigEditor stub/).textContent).toContain(
        'llm_provider=anthropic',
      ),
    )
    expect(screen.getByText(/ProviderConfigEditor stub/).textContent).toContain(
      'storage_root=/real/storage/root',
    )
    // The old flat picker/four hardcoded key rows are gone -- ProviderConfigEditor
    // is the one and only place provider configuration now lives.
    expect(screen.queryByLabelText('LLM provider')).toBeNull()
  })

  it('does not render the editor before config has loaded (avoids passing a null config)', () => {
    getConfigMock.mockReturnValue(new Promise(() => {})) // never resolves
    render(<Settings />)

    expect(screen.queryByText(/ProviderConfigEditor stub/)).toBeNull()
  })

  it('onSaved (from the editor) reloads config via getConfig', async () => {
    render(<Settings />)
    await screen.findByText(/ProviderConfigEditor stub/)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'stub-trigger-onSaved' }))

    await waitFor(() => expect(getConfigMock).toHaveBeenCalledTimes(2))
  })

  it('onCapabilitiesChange (from the editor) refreshes capabilities via getCapabilities', async () => {
    render(<Settings />)
    await screen.findByText(/ProviderConfigEditor stub/)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'stub-trigger-onCapabilitiesChange' }))

    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(2))
  })

  it('surfaces an error message when getCapabilities fails, without crashing the screen', async () => {
    getCapabilitiesMock.mockReset().mockRejectedValueOnce(new Error('daemon unreachable'))

    render(<Settings />)

    await waitFor(() => expect(screen.getByText('daemon unreachable')).toBeTruthy())
  })
})


describe('Settings: Community Library Search (SPEC-314, CTX-314.2)', () => {
  it('an unconfigured GitHub token shows an input and Save button', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalled())

    expect(screen.getByLabelText('GitHub token')).toBeTruthy()
  })

  it('saving the token calls saveSecret with github_token then refreshes capabilities', async () => {
    render(<Settings />)
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(1))

    const tokenInput = screen.getByLabelText('GitHub token')
    fireEvent.change(tokenInput, { target: { value: 'ghp_real_token' } })
    getCapabilitiesMock.mockResolvedValueOnce({ ...EMPTY_CAPABILITIES, github_token_configured: true })
    fireEvent.click(within(tokenInput.parentElement as HTMLElement).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(saveSecretMock).toHaveBeenCalledWith('github_token', 'ghp_real_token'))
    await waitFor(() => expect(getCapabilitiesMock).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByLabelText('GitHub token')).toBeNull())

    expect(screen.queryByText('ghp_real_token')).toBeNull()
    expect(screen.queryByDisplayValue('ghp_real_token')).toBeNull()
  })

  it('a configured token shows Clear instead of an input, and clearing refreshes capabilities', async () => {
    getCapabilitiesMock.mockResolvedValue({ ...EMPTY_CAPABILITIES, github_token_configured: true })

    render(<Settings />)
    await waitFor(() => expect(screen.queryByLabelText('GitHub token')).toBeNull())

    const configuredRow = screen.getByText('GitHub token').parentElement as HTMLElement
    getCapabilitiesMock.mockResolvedValueOnce(EMPTY_CAPABILITIES)
    fireEvent.click(within(configuredRow).getByRole('button', { name: 'Clear' }))

    await waitFor(() => expect(clearSecretMock).toHaveBeenCalledWith('github_token'))
    await waitFor(() => expect(screen.getByLabelText('GitHub token')).toBeTruthy())
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

  it('CTX-303.4: KiCad not reachable shows the real checked socket path and a concrete explanation', async () => {
    getCapabilitiesMock.mockResolvedValue({
      ...EMPTY_CAPABILITIES,
      kicad_available: false,
      kicad_socket_path_checked: '/tmp/kicad/api.sock',
    })

    render(<Settings />)

    await waitFor(() => screen.getByText('KiCad: not reachable'))
    screen.getByText('/tmp/kicad/api.sock', { exact: false })
    screen.getByText(/Preferences → Plugins/)
  })

  it('CTX-303.4: FreeCAD not reachable shows the real, specific error message', async () => {
    getCapabilitiesMock.mockResolvedValue({
      ...EMPTY_CAPABILITIES,
      freecad_available: false,
      freecad_error: 'Could not find the freecadcmd executable. Install FreeCAD 0.20+, or ensure it\'s on PATH.',
    })

    render(<Settings />)

    await waitFor(() => screen.getByText(/Could not find the freecadcmd executable/))
  })

  it('CTX-303.4: FreeCAD reachable shows the real path it was found at', async () => {
    getCapabilitiesMock.mockResolvedValue({
      ...EMPTY_CAPABILITIES,
      freecad_available: true,
      freecad_path_checked: '/opt/freecad/bin/freecadcmd',
    })

    render(<Settings />)

    await waitFor(() => screen.getByText('/opt/freecad/bin/freecadcmd', { exact: false }))
  })

  it('TEST-007: the restart-to-apply notice is present once, scoped to the path fields section', async () => {
    render(<Settings />)
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled())

    expect(
      screen.getByText('These four fields are only read at daemon startup — restart the app to apply a change.'),
    ).toBeTruthy()
    // Provider configuration applies live via daemon.configure -- it must
    // not carry this restart-required notice, unlike the path fields above.
    expect(screen.getByText('Provider Configuration').closest('section')?.textContent).not.toMatch(
      /restart/i,
    )
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
