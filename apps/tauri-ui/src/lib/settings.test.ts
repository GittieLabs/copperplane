import { beforeEach, describe, expect, it, vi } from 'vitest'

const invokeMock = vi.fn()
const dispatchMock = vi.fn()

vi.mock('@tauri-apps/api/core', () => ({ invoke: invokeMock }))
vi.mock('./ipc', () => ({ dispatch: dispatchMock }))

const {
  saveSecret,
  clearSecret,
  getConfig,
  saveConfig,
  getCapabilities,
  setLlmProviderAndModel,
  secretKeyFor,
} = await import('./settings')

beforeEach(() => {
  invokeMock.mockReset()
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
      result: { kicad_available: true, freecad_available: false, llm_providers: ['anthropic'] },
    })

    const caps = await getCapabilities()

    expect(dispatchMock).toHaveBeenCalledWith('daemon.get_capabilities', {})
    expect(caps).toEqual({ kicad_available: true, freecad_available: false, llm_providers: ['anthropic'] })
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
