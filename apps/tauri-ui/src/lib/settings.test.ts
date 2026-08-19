import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DaemonCapabilities } from './settings'

const invokeMock = vi.fn()
const dispatchMock = vi.fn()
const writeTextMock = vi.fn()

vi.mock('@tauri-apps/api/core', () => ({ invoke: invokeMock }))
vi.mock('@tauri-apps/plugin-clipboard-manager', () => ({ writeText: writeTextMock }))
vi.mock('./ipc', () => ({ dispatch: dispatchMock }))

const {
  saveSecret,
  clearSecret,
  getConfig,
  saveConfig,
  getCapabilities,
  setLlmProviderAndModel,
  secretKeyFor,
  getAppVersion,
  copyDiagnostics,
} = await import('./settings')

beforeEach(() => {
  invokeMock.mockReset()
  writeTextMock.mockReset()
  dispatchMock.mockReset()
})

describe('secretKeyFor', () => {
  it("matches daemon.py's f\"{provider}_api_key\" convention", () => {
    expect(secretKeyFor('anthropic')).toBe('anthropic_api_key')
    expect(secretKeyFor('perplexity')).toBe('perplexity_api_key')
  })
})

describe('saveSecret / clearSecret', () => {
  it('TEST-006: saveSecret invokes save_secret with the key and value', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    await saveSecret('anthropic_api_key', 'sk-test')
    expect(invokeMock).toHaveBeenCalledWith('save_secret', { key: 'anthropic_api_key', value: 'sk-test' })
  })

  it('clearSecret invokes clear_secret with the key', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    await clearSecret('anthropic_api_key')
    expect(invokeMock).toHaveBeenCalledWith('clear_secret', { key: 'anthropic_api_key' })
  })
})

describe('getConfig / saveConfig', () => {
  it('getConfig invokes get_config and returns its result', async () => {
    invokeMock.mockResolvedValueOnce({ llm_provider: 'anthropic' })
    const config = await getConfig()
    expect(invokeMock).toHaveBeenCalledWith('get_config')
    expect(config).toEqual({ llm_provider: 'anthropic' })
  })

  it('saveConfig invokes save_config_cmd with the config', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    await saveConfig({ llm_provider: 'google' })
    expect(invokeMock).toHaveBeenCalledWith('save_config_cmd', { config: { llm_provider: 'google' } })
  })
})

describe('getCapabilities', () => {
  it('TEST-004/006: dispatches daemon.get_capabilities and returns the result', async () => {
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0',
      id: 1,
      result: {
        kicad_available: true,
        freecad_available: false,
        llm_providers: ['anthropic'],
        log_path: '/var/log/daemon.log',
        python_version: '3.12.0',
      },
    })

    const caps = await getCapabilities()

    expect(dispatchMock).toHaveBeenCalledWith('daemon.get_capabilities', {})
    expect(caps).toEqual({
      kicad_available: true,
      freecad_available: false,
      llm_providers: ['anthropic'],
      log_path: '/var/log/daemon.log',
      python_version: '3.12.0',
    })
  })

  it('throws when the daemon returns an error response', async () => {
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0',
      id: 1,
      error: { code: -32601, message: 'Method not found' },
    })

    await expect(getCapabilities()).rejects.toThrow('Method not found')
  })
})

describe('setLlmProviderAndModel', () => {
  it('persists to config.json AND pushes live via daemon.configure', async () => {
    invokeMock.mockResolvedValueOnce(undefined) // saveConfig -> save_config_cmd
    dispatchMock.mockResolvedValueOnce({ jsonrpc: '2.0', id: 1, result: { configured: true } })

    await setLlmProviderAndModel('anthropic', 'claude-sonnet', { llm_provider: null, llm_model: null })

    expect(invokeMock).toHaveBeenCalledWith('save_config_cmd', {
      config: { llm_provider: 'anthropic', llm_model: 'claude-sonnet' },
    })
    expect(dispatchMock).toHaveBeenCalledWith('daemon.configure', {
      llm_provider: 'anthropic',
      llm_model: 'claude-sonnet',
    })
  })

  it('throws when the live daemon.configure push fails, even if the config.json write already succeeded', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0',
      id: 1,
      error: { code: -32602, message: 'Invalid params' },
    })

    await expect(
      setLlmProviderAndModel('anthropic', null, { llm_provider: null, llm_model: null }),
    ).rejects.toThrow('Invalid params')
  })
})

describe('getAppVersion', () => {
  it('invokes get_app_version and returns its result', async () => {
    invokeMock.mockResolvedValueOnce('0.1.0')
    await expect(getAppVersion()).resolves.toBe('0.1.0')
    expect(invokeMock).toHaveBeenCalledWith('get_app_version')
  })
})

describe('copyDiagnostics', () => {
  const BASE_CAPABILITIES: DaemonCapabilities = {
    kicad_available: false,
    kicad_socket_path_checked: '/tmp/kicad/api.sock',
    freecad_available: false,
    freecad_path_checked: null,
    freecad_error: 'Could not find the freecadcmd executable. Install FreeCAD 0.20+, or ensure it\'s on PATH.',
    llm_providers: [] as string[],
    log_path: '/var/log/daemon.log',
    python_version: '3.12.0',
    storage_root: '/Users/test/Library/Application Support/has/storage',
  }

  function mockCapabilitiesAndVersion(capabilities: typeof BASE_CAPABILITIES) {
    // getAppVersion -> invoke; getCapabilities -> dispatch. Order doesn't
    // matter since copyDiagnostics runs them concurrently.
    invokeMock.mockImplementation(async (cmd: string) => {
      if (cmd === 'get_app_version') return '0.1.0'
      throw new Error(`unexpected invoke: ${cmd}`)
    })
    dispatchMock.mockImplementation(async (method: string) => {
      if (method === 'daemon.get_capabilities') {
        return { jsonrpc: '2.0', id: 1, result: capabilities }
      }
      throw new Error(`unexpected dispatch: ${method}`)
    })
  }

  it('TEST: bundles version, python version, log path, and connectivity into clipboard text', async () => {
    mockCapabilitiesAndVersion(BASE_CAPABILITIES)

    await copyDiagnostics()

    expect(writeTextMock).toHaveBeenCalledTimes(1)
    const text = writeTextMock.mock.calls[0][0] as string
    expect(text).toContain('Hardware Agent Studio v0.1.0')
    expect(text).toContain('Python: 3.12.0')
    expect(text).toContain('Log file: /var/log/daemon.log')
    expect(text).toContain('KiCad: not reachable')
    expect(text).toContain('FreeCAD: not reachable')
    expect(text).toContain('LLM providers configured: (none)')
  })

  it('reports "(not available)" when the daemon has no log file active', async () => {
    mockCapabilitiesAndVersion({ ...BASE_CAPABILITIES, log_path: null })

    await copyDiagnostics()

    const text = writeTextMock.mock.calls[0][0] as string
    expect(text).toContain('Log file: (not available)')
  })

  it('looks up the real KiCad version only when kicad_available is true', async () => {
    mockCapabilitiesAndVersion({ ...BASE_CAPABILITIES, kicad_available: true })
    dispatchMock.mockImplementation(async (method: string) => {
      if (method === 'daemon.get_capabilities') {
        return { jsonrpc: '2.0', id: 1, result: { ...BASE_CAPABILITIES, kicad_available: true } }
      }
      if (method === 'kicad.get_version') {
        return { jsonrpc: '2.0', id: 2, result: { full_version: '10.0.3' } }
      }
      throw new Error(`unexpected dispatch: ${method}`)
    })

    await copyDiagnostics()

    expect(dispatchMock).toHaveBeenCalledWith('kicad.get_version', {})
    const text = writeTextMock.mock.calls[0][0] as string
    expect(text).toContain('KiCad: 10.0.3')
  })

  it('degrades to "unreachable" rather than failing the whole bundle when the KiCad lookup errors', async () => {
    dispatchMock.mockImplementation(async (method: string) => {
      if (method === 'daemon.get_capabilities') {
        return { jsonrpc: '2.0', id: 1, result: { ...BASE_CAPABILITIES, kicad_available: true } }
      }
      if (method === 'kicad.get_version') {
        return { jsonrpc: '2.0', id: 2, error: { code: -32000, message: 'not connected' } }
      }
      throw new Error(`unexpected dispatch: ${method}`)
    })
    invokeMock.mockResolvedValue('0.1.0')

    await copyDiagnostics()

    const text = writeTextMock.mock.calls[0][0] as string
    expect(text).toContain('KiCad: unreachable')
  })

  it('lists configured providers by name', async () => {
    mockCapabilitiesAndVersion({ ...BASE_CAPABILITIES, llm_providers: ['anthropic', 'google'] })

    await copyDiagnostics()

    const text = writeTextMock.mock.calls[0][0] as string
    expect(text).toContain('LLM providers configured: anthropic, google')
  })
})
