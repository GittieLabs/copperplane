import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const getCapabilitiesMock = vi.fn()
const getConfigMock = vi.fn()
const saveConfigMock = vi.fn()
const saveSecretMock = vi.fn()
const clearSecretMock = vi.fn()
const setLlmProviderAndModelMock = vi.fn()

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
  }
})

const { Settings } = await import('./Settings')

const EMPTY_CAPABILITIES = { kicad_available: false, freecad_available: false, llm_providers: [] }
const EMPTY_CONFIG = { llm_provider: null, llm_model: null }

beforeEach(() => {
  getCapabilitiesMock.mockReset().mockResolvedValue(EMPTY_CAPABILITIES)
  getConfigMock.mockReset().mockResolvedValue(EMPTY_CONFIG)
  saveConfigMock.mockReset().mockResolvedValue(undefined)
  saveSecretMock.mockReset().mockResolvedValue(undefined)
  clearSecretMock.mockReset().mockResolvedValue(undefined)
  setLlmProviderAndModelMock.mockReset().mockResolvedValue(undefined)
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
      screen.getByText('These three fields are only read at daemon startup — restart the app to apply a change.'),
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
      }),
    )
    await waitFor(() => expect(screen.getByText('Saved — restart to apply.')).toBeTruthy())
  })
})
