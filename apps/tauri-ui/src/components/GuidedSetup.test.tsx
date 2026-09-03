import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const saveSecretMock = vi.fn()
const bindBothRolesToMock = vi.fn()
const setToolPathMock = vi.fn()
const getCapabilitiesMock = vi.fn()
const chooseToolExecutableMock = vi.fn()
const openExternalMock = vi.fn()

vi.mock('../lib/settings', async () => {
  const actual = await vi.importActual<typeof import('../lib/settings')>('../lib/settings')
  return {
    KEY_BASED_PROVIDERS: actual.KEY_BASED_PROVIDERS,
    secretKeyFor: actual.secretKeyFor,
    saveSecret: (...a: unknown[]) => saveSecretMock(...a),
    bindBothRolesTo: (...a: unknown[]) => bindBothRolesToMock(...a),
    setToolPath: (...a: unknown[]) => setToolPathMock(...a),
    getCapabilities: (...a: unknown[]) => getCapabilitiesMock(...a),
    chooseToolExecutable: (...a: unknown[]) => chooseToolExecutableMock(...a),
  }
})
vi.mock('../lib/externalLinks', () => ({
  PROVIDER_KEY_DOCS: {
    anthropic: { label: 'Anthropic Console', url: 'https://console.anthropic.com/settings/keys' },
    openai: { label: 'OpenAI API keys', url: 'https://platform.openai.com/api-keys' },
    google: { label: 'Google AI Studio', url: 'https://aistudio.google.com/apikey' },
    perplexity: { label: 'Perplexity API settings', url: 'https://www.perplexity.ai/settings/api' },
  },
  TOOL_DOWNLOADS: {
    kicad: { label: 'KiCad downloads', url: 'https://www.kicad.org/download/' },
    freecad: { label: 'FreeCAD downloads', url: 'https://www.freecad.org/downloads.php' },
  },
  openExternal: (...a: unknown[]) => openExternalMock(...a),
}))

const { GuidedSetup } = await import('./GuidedSetup')

const EMPTY = {
  kicad_available: false,
  kicad_socket_path_checked: '/tmp/kicad/api.sock',
  freecad_available: false,
  freecad_path_checked: null,
  freecad_error: 'Could not find freecadcmd.',
  kicad_cli_available: false,
  kicad_cli_path_checked: null,
  kicad_cli_path_source: 'none' as const,
  kicad_cli_error: 'Could not find the kicad-cli executable.',
  llm_providers: [] as string[],
  log_path: '/tmp/daemon.log',
  python_version: '3.11.9',
  storage_root: '/data',
  github_token_configured: false,
  configured_secret_refs: [] as string[],
}
const READY = {
  ...EMPTY,
  kicad_cli_available: true,
  kicad_cli_path_checked: '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
  kicad_cli_path_source: 'install' as const,
  kicad_cli_error: null,
  freecad_available: true,
  freecad_path_checked: '/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd',
  freecad_error: null,
  llm_providers: ['anthropic'],
}

beforeEach(() => {
  saveSecretMock.mockReset().mockResolvedValue(undefined)
  bindBothRolesToMock.mockReset().mockResolvedValue(undefined)
  setToolPathMock.mockReset().mockResolvedValue(undefined)
  getCapabilitiesMock.mockReset().mockResolvedValue(EMPTY)
  chooseToolExecutableMock.mockReset()
  openExternalMock.mockReset()
})

function renderSetup(overrides: Partial<Parameters<typeof GuidedSetup>[0]> = {}) {
  return render(
    <GuidedSetup
      capabilities={EMPTY}
      onCapabilitiesChanged={() => {}}
      onFinish={() => {}}
      onOpenManualSettings={() => {}}
      {...overrides}
    />,
  )
}

/** CTX-336.1 Phase 4, SPEC-336 steps 4-5. */
describe('GuidedSetup', () => {
  it('pre-selects anthropic', () => {
    /** Settled with the maintainer on 2026-09-03, and the same default
     *  `llm_providers.py:67` already has, so no second opinion is introduced. */
    renderSetup()

    expect((screen.getByLabelText('Provider') as HTMLSelectElement).value).toBe('anthropic')
  })

  it('saves the key and binds both model roles to that provider', async () => {
    renderSetup()

    fireEvent.change(screen.getByPlaceholderText('Paste the key here'), {
      target: { value: 'sk-test-123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save key and continue' }))

    await waitFor(() => expect(saveSecretMock).toHaveBeenCalledWith('anthropic_api_key', 'sk-test-123'))
    expect(bindBothRolesToMock).toHaveBeenCalledWith('anthropic')
  })

  it('links to the chosen provider’s own docs, not to a Copperplane page', async () => {
    /** SPEC-336 §3: the docs site does not exist, and "a link that 404s on
     *  first run is worse than no link". */
    renderSetup()

    fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'google' } })
    fireEvent.click(screen.getByRole('button', { name: /Where do I get a key/ }))

    expect(openExternalMock).toHaveBeenCalledWith('https://aistudio.google.com/apikey')
  })

  it('will not save an empty key', () => {
    renderSetup()

    expect((screen.getByRole('button', { name: 'Save key and continue' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('surfaces a failed key save instead of moving on as if it worked', async () => {
    saveSecretMock.mockRejectedValue(new Error('keychain refused'))
    renderSetup()

    fireEvent.change(screen.getByPlaceholderText('Paste the key here'), { target: { value: 'k' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save key and continue' }))

    expect(await screen.findByText('keychain refused')).toBeTruthy()
    // Still on the provider step, not advanced past a failure.
    expect(screen.getByLabelText('Provider')).toBeTruthy()
  })

  it('lets the provider step be skipped', async () => {
    renderSetup()

    fireEvent.click(screen.getByRole('button', { name: 'Skip this step' }))

    expect(await screen.findByText(/Step 2 of 2/)).toBeTruthy()
    expect(saveSecretMock).not.toHaveBeenCalled()
  })

  it('opens straight at the tool step when the banner sent the user there', () => {
    renderSetup({ startAt: 'tools' })

    expect(screen.getByText(/Step 2 of 2/)).toBeTruthy()
  })

  it('names each missing tool and what it costs', () => {
    renderSetup({ startAt: 'tools' })

    expect(screen.getByText(/checks and component lists cannot run/)).toBeTruthy()
    expect(screen.getByText(/enclosures cannot be generated/)).toBeTruthy()
  })

  it('applies a picked path and re-checks, so the effect is visible at once', async () => {
    /** Phase 1 exists for this: `setToolPath` reaches the running daemon, so
     *  the "found" line updates without a restart. */
    chooseToolExecutableMock.mockResolvedValue('/opt/kicad/bin/kicad-cli')
    getCapabilitiesMock.mockResolvedValue(READY)
    const onCapabilitiesChanged = vi.fn()
    renderSetup({ startAt: 'tools', onCapabilitiesChanged })

    fireEvent.click(screen.getAllByRole('button', { name: /point to it/ })[0])

    await waitFor(() =>
      expect(setToolPathMock).toHaveBeenCalledWith('kicad', '/opt/kicad/bin/kicad-cli'),
    )
    expect(onCapabilitiesChanged).toHaveBeenCalledWith(READY)
  })

  it('does nothing when the file picker is cancelled', async () => {
    chooseToolExecutableMock.mockResolvedValue(null)
    renderSetup({ startAt: 'tools' })

    fireEvent.click(screen.getAllByRole('button', { name: /point to it/ })[0])

    await waitFor(() => expect(chooseToolExecutableMock).toHaveBeenCalled())
    expect(setToolPathMock).not.toHaveBeenCalled()
  })

  it('shows where a found tool was found', () => {
    renderSetup({ startAt: 'tools', capabilities: READY })

    expect(screen.getByText('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /point to it/ })).toBeNull()
  })

  it('lets the user continue with things still missing', async () => {
    /** The rule the whole spec turns on: "Every step is skippable, and the
     *  wizard never blocks entry." */
    const onFinish = vi.fn()
    renderSetup({ startAt: 'tools', onFinish })

    const button = screen.getByRole('button', { name: 'Continue anyway' })
    expect((button as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(button)

    expect(onFinish).toHaveBeenCalled()
  })

  it('says Done rather than Continue anyway when nothing is missing', () => {
    renderSetup({ startAt: 'tools', capabilities: READY })

    expect(screen.getByRole('button', { name: 'Done' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Continue anyway' })).toBeNull()
  })

  it('offers the full settings screen as an escape hatch', () => {
    const onOpenManualSettings = vi.fn()
    renderSetup({ onOpenManualSettings })

    fireEvent.click(screen.getByRole('button', { name: /Open full settings instead/ }))
    expect(onOpenManualSettings).toHaveBeenCalled()
  })

  it('re-checks the tools on demand, for a tool installed while the app was open', async () => {
    getCapabilitiesMock.mockResolvedValue(READY)
    const onCapabilitiesChanged = vi.fn()
    renderSetup({ startAt: 'tools', onCapabilitiesChanged })

    fireEvent.click(screen.getByRole('button', { name: 'Check again' }))

    await waitFor(() => expect(onCapabilitiesChanged).toHaveBeenCalledWith(READY))
  })
})
