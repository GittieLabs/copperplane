import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DaemonCapabilities } from './settings'

const invokeMock = vi.fn()
const dispatchMock = vi.fn()
const writeTextMock = vi.fn()
const submitJobMock = vi.fn()

vi.mock('@tauri-apps/api/core', () => ({ invoke: invokeMock }))
vi.mock('@tauri-apps/plugin-clipboard-manager', () => ({ writeText: writeTextMock }))
vi.mock('./ipc', () => ({ dispatch: dispatchMock, submitJob: submitJobMock }))

const {
  saveSecret,
  clearSecret,
  getConfig,
  saveConfig,
  getCapabilities,
  setLlmProviderAndModel,
  getProviderRecords,
  saveProviderConfig,
  isNonLoopbackBaseUrl,
  secretKeyFor,
  getAppVersion,
  copyDiagnostics,
} = await import('./settings')

beforeEach(() => {
  invokeMock.mockReset()
  writeTextMock.mockReset()
  dispatchMock.mockReset()
  submitJobMock.mockReset()
})

describe('isNonLoopbackBaseUrl', () => {
  it('a null base_url (a preset\'s own untouched default) is never a risk', () => {
    expect(isNonLoopbackBaseUrl(null)).toBe(false)
  })

  it('localhost and 127.0.0.1 are not flagged', () => {
    expect(isNonLoopbackBaseUrl('http://localhost:11434/v1')).toBe(false)
    expect(isNonLoopbackBaseUrl('http://127.0.0.1:11434/v1')).toBe(false)
  })

  it('a real remote host is flagged', () => {
    expect(isNonLoopbackBaseUrl('http://nuc.local:11434/v1')).toBe(true)
    expect(isNonLoopbackBaseUrl('https://api.example.com')).toBe(true)
  })

  it('an unparseable base_url fails toward "warn", not "trust it"', () => {
    expect(isNonLoopbackBaseUrl('not a url')).toBe(true)
  })
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
        kicad_cli_available: true,
        kicad_cli_path_checked: '/usr/local/bin/kicad-cli',
        kicad_cli_path_source: 'path' as const,
        kicad_cli_error: null,
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
      kicad_cli_available: true,
      kicad_cli_path_checked: '/usr/local/bin/kicad-cli',
      kicad_cli_path_source: 'path' as const,
      kicad_cli_error: null,
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

describe('getProviderRecords', () => {
  it('dispatches llm.get_provider_records and returns the result', async () => {
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0',
      id: 1,
      result: {
        records: [{
          id: 'anthropic', kind: 'anthropic', base_url: null, api_key_ref: 'anthropic_api_key',
          models: { reasoning: 'claude-sonnet-5', fast: 'claude-sonnet-5' },
          capabilities: { tool_use: true, strict_json: true },
        }],
        provider_roles: { reasoning: 'anthropic', fast: 'anthropic' },
        provider_roles_saved: false,
      },
    })

    const result = await getProviderRecords()

    expect(dispatchMock).toHaveBeenCalledWith('llm.get_provider_records', {})
    expect(result.records).toHaveLength(1)
    expect(result.records[0].id).toBe('anthropic')
    expect(result.provider_roles).toEqual({ reasoning: 'anthropic', fast: 'anthropic' })
    expect(result.provider_roles_saved).toBe(false)
  })

  it('never sees "managed" in a real response -- the daemon route filters it, not this function', async () => {
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0',
      id: 1,
      result: { records: [], provider_roles: {}, provider_roles_saved: false },
    })

    const result = await getProviderRecords()
    expect(result.records.some((r) => r.id === 'managed')).toBe(false)
  })

  it('throws when the daemon returns an error response', async () => {
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0',
      id: 1,
      error: { code: -32601, message: 'Method not found' },
    })

    await expect(getProviderRecords()).rejects.toThrow('Method not found')
  })
})

describe('saveProviderConfig', () => {
  const record = {
    id: 'workshop', kind: 'openai_compat' as const, base_url: 'http://localhost:11434/v1',
    api_key_ref: null, models: { reasoning: 'big-model', fast: 'small-model' },
    capabilities: { tool_use: true, strict_json: true },
  }
  const roles = { reasoning: 'workshop', fast: 'workshop' }

  it('persists to config.json AND pushes live via daemon.configure, both as a complete set', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    dispatchMock.mockResolvedValueOnce({ jsonrpc: '2.0', id: 1, result: { configured: true } })

    await saveProviderConfig([record], roles, { llm_provider: null, llm_model: null })

    expect(invokeMock).toHaveBeenCalledWith('save_config_cmd', {
      config: { llm_provider: null, llm_model: null, providers: [record], provider_roles: roles },
    })
    expect(dispatchMock).toHaveBeenCalledWith('daemon.configure', { providers: [record], provider_roles: roles })
  })

  /* CTX-209.2: the daemon reduces each record to what differs from its
     shipped preset and returns that; THAT is what gets persisted. So
     daemon.configure runs first and config.json is written from its
     answer -- the delta rule has one implementation, in the daemon,
     rather than a second copy here that could disagree with the merge it
     is supposed to invert. */
  it('persists the daemon\'s normalized records rather than what was sent', async () => {
    invokeMock.mockResolvedValueOnce(undefined)
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0', id: 1,
      result: { configured: true, providers: [{ id: 'workshop', models: { reasoning: 'big-model' } }] },
    })

    await saveProviderConfig([record], roles, { llm_provider: null, llm_model: null })

    expect(invokeMock).toHaveBeenCalledWith('save_config_cmd', {
      config: {
        llm_provider: null, llm_model: null,
        providers: [{ id: 'workshop', models: { reasoning: 'big-model' } }],
        provider_roles: roles,
      },
    })
  })

  it('falls back to what was sent when the daemon returns no normalized set', async () => {
    // An older daemon mid-upgrade. Whole records still resolve correctly,
    // because merge-on-read treats one as a delta covering every field.
    invokeMock.mockResolvedValueOnce(undefined)
    dispatchMock.mockResolvedValueOnce({ jsonrpc: '2.0', id: 1, result: { configured: true } })

    await saveProviderConfig([record], roles, { llm_provider: null, llm_model: null })

    expect(invokeMock).toHaveBeenCalledWith('save_config_cmd', {
      config: { llm_provider: null, llm_model: null, providers: [record], provider_roles: roles },
    })
  })

  it('writes nothing to config.json when the daemon rejects the push', async () => {
    // Reversing the order removed a real failure mode: config.json used to
    // be written before the daemon had accepted the change, so a rejected
    // push left the file holding configuration the daemon had refused.
    dispatchMock.mockResolvedValueOnce({
      jsonrpc: '2.0', id: 1, error: { code: -32602, message: 'Invalid params' },
    })

    await expect(
      saveProviderConfig([record], roles, { llm_provider: null, llm_model: null }),
    ).rejects.toThrow('Invalid params')
    expect(invokeMock).not.toHaveBeenCalled()
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
    kicad_cli_available: true,
    kicad_cli_path_checked: '/usr/local/bin/kicad-cli',
    kicad_cli_path_source: 'path' as const,
    kicad_cli_error: null,
    log_path: '/var/log/daemon.log',
    python_version: '3.12.0',
    storage_root: '/Users/test/Library/Application Support/has/storage',
    github_token_configured: false,
    configured_secret_refs: [] as string[],
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
    expect(text).toContain('Copperplane v0.1.0')
    expect(text).toContain('Python: 3.12.0')
    expect(text).toContain('Log file: /var/log/daemon.log')
    expect(text).toContain('KiCad: not reachable')
    expect(text).toContain('FreeCAD: not reachable')
    expect(text).toContain('LLM providers configured: (none)')
  })

  /* CTX-107.2 (issue #249). The version is fetched here, on demand, the
     same way and in the same place as KiCad's -- never from the capability
     probe, which SPEC-107 §3 requires to stay cheap and non-blocking. */
  it('looks up the real FreeCAD version only when freecad_available is true', async () => {
    mockCapabilitiesAndVersion({ ...BASE_CAPABILITIES, freecad_available: true })
    submitJobMock.mockResolvedValue({
      result: Promise.resolve({ version: 'FreeCAD 1.0.0, Libs: 1.0.0R', reason: null }),
    })

    await copyDiagnostics()

    expect(submitJobMock).toHaveBeenCalledWith('freecad.get_version', {})
    expect(writeTextMock.mock.calls[0][0] as string).toContain('FreeCAD: FreeCAD 1.0.0, Libs: 1.0.0R')
  })

  it('never asks for a FreeCAD version when FreeCAD is not reachable', async () => {
    mockCapabilitiesAndVersion(BASE_CAPABILITIES)

    await copyDiagnostics()

    expect(submitJobMock).not.toHaveBeenCalledWith('freecad.get_version', {})
    expect(writeTextMock.mock.calls[0][0] as string).toContain('FreeCAD: not reachable')
  })

  it('reports an unknown FreeCAD version rather than failing the whole diagnostic', async () => {
    // A version that cannot be read must never cost the user the rest of
    // their diagnostics -- the same rule the daemon route follows.
    mockCapabilitiesAndVersion({ ...BASE_CAPABILITIES, freecad_available: true })
    submitJobMock.mockRejectedValue(new Error('job failed'))

    await copyDiagnostics()

    expect(writeTextMock.mock.calls[0][0] as string).toContain('FreeCAD: unknown')
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
