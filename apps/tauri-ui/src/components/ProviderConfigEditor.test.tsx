import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getProviderRecordsMock = vi.fn()
const saveProviderConfigMock = vi.fn()
const saveSecretMock = vi.fn()
const clearSecretMock = vi.fn()
const askMock = vi.fn()

vi.mock('../lib/settings', async () => {
  const actual = await vi.importActual<typeof import('../lib/settings')>('../lib/settings')
  return {
    ...actual,
    getProviderRecords: (...args: unknown[]) => getProviderRecordsMock(...args),
    saveProviderConfig: (...args: unknown[]) => saveProviderConfigMock(...args),
    saveSecret: (...args: unknown[]) => saveSecretMock(...args),
    clearSecret: (...args: unknown[]) => clearSecretMock(...args),
  }
})

// confirmRemoveRoleBoundProvider is real (from lib/settings) but delegates
// to @tauri-apps/plugin-dialog's ask() -- mocked here at its real source,
// same as every other lib/*.ts file in this repo that touches plugin-dialog.
vi.mock('@tauri-apps/plugin-dialog', () => ({
  ask: (...args: unknown[]) => askMock(...args),
  open: vi.fn(),
}))

const { ProviderConfigEditor } = await import('./ProviderConfigEditor')

const EMPTY_CONFIG = { llm_provider: null, llm_model: null }
const EMPTY_CAPABILITIES = {
  kicad_available: false,
  kicad_socket_path_checked: null,
  freecad_available: false,
  freecad_path_checked: null,
  freecad_error: null,
  llm_providers: [] as string[],
  log_path: null,
  python_version: '3.12.0',
  storage_root: null,
  github_token_configured: false,
  configured_secret_refs: [] as string[],
}

const ANTHROPIC_RECORD = {
  id: 'anthropic',
  kind: 'anthropic' as const,
  base_url: null,
  api_key_ref: 'anthropic_api_key',
  models: { reasoning: 'claude-sonnet-5', fast: 'claude-sonnet-5' },
  capabilities: { tool_use: true, strict_json: true },
}

const OLLAMA_RECORD = {
  id: 'ollama',
  kind: 'openai_compat' as const,
  base_url: 'http://localhost:11434/v1',
  api_key_ref: null,
  models: { reasoning: 'llama3.2:1b', fast: 'llama3.2:1b' },
  capabilities: { tool_use: false, strict_json: false },
}

function renderEditor(overrides?: { capabilities?: Partial<typeof EMPTY_CAPABILITIES> }) {
  const onSaved = vi.fn().mockResolvedValue(undefined)
  const onCapabilitiesChange = vi.fn().mockResolvedValue(undefined)
  render(
    <ProviderConfigEditor
      config={EMPTY_CONFIG}
      capabilities={{ ...EMPTY_CAPABILITIES, ...overrides?.capabilities }}
      onSaved={onSaved}
      onCapabilitiesChange={onCapabilitiesChange}
    />,
  )
  return { onSaved, onCapabilitiesChange }
}

beforeEach(() => {
  getProviderRecordsMock.mockReset().mockResolvedValue({
    records: [ANTHROPIC_RECORD],
    provider_roles: { reasoning: 'anthropic', fast: 'anthropic' },
    provider_roles_saved: true,
  })
  saveProviderConfigMock.mockReset().mockResolvedValue(undefined)
  saveSecretMock.mockReset().mockResolvedValue(undefined)
  clearSecretMock.mockReset().mockResolvedValue(undefined)
  askMock.mockReset().mockResolvedValue(true)
})

describe('ProviderConfigEditor: list + migration display', () => {
  it('renders every record from getProviderRecords', async () => {
    render(<ProviderConfigEditor config={EMPTY_CONFIG} capabilities={EMPTY_CAPABILITIES} onSaved={vi.fn()} onCapabilitiesChange={vi.fn()} />)

    await waitFor(() => expect(getProviderRecordsMock).toHaveBeenCalled())
    expect(await screen.findByRole('button', { name: 'Edit anthropic' })).toBeTruthy()
  })

  it('shows the migration note when provider_roles_saved is false, not when true', async () => {
    getProviderRecordsMock.mockResolvedValue({
      records: [ANTHROPIC_RECORD],
      provider_roles: { reasoning: 'anthropic', fast: 'anthropic' },
      provider_roles_saved: false,
    })
    renderEditor()

    expect(await screen.findByText(/Not yet saved/)).toBeTruthy()
    expect(screen.getByText(/Not yet saved/).textContent).toContain('reasoning → anthropic')
  })

  it('hides the migration note once provider_roles_saved is true', async () => {
    renderEditor()

    await screen.findByRole('button', { name: 'Edit anthropic' })
    expect(screen.queryByText(/Not yet saved/)).toBeNull()
  })

  it('never renders "managed" as a kind option, even in the add-provider form', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })

    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    const kindSelect = screen.getByLabelText('Provider kind') as HTMLSelectElement
    const optionValues = Array.from(kindSelect.options).map((o) => o.value)
    expect(optionValues).toEqual(['anthropic', 'openai_compat', 'google'])
    expect(optionValues).not.toContain('managed')
  })
})

describe('ProviderConfigEditor: per-record key management', () => {
  it('a record with a configured key shows "configured" and a Clear button, no key input', async () => {
    renderEditor({ capabilities: { configured_secret_refs: ['anthropic_api_key'] } })

    await waitFor(() => expect(screen.getByText('configured')).toBeTruthy())
    expect(screen.queryByLabelText('anthropic API key')).toBeNull()
  })

  it('a record with no configured key shows an input + Save; saving calls saveSecret then onCapabilitiesChange', async () => {
    const { onCapabilitiesChange } = renderEditor()

    const keyInput = await screen.findByLabelText('anthropic API key')
    fireEvent.change(keyInput, { target: { value: 'sk-real-secret' } })
    fireEvent.click(within(keyInput.parentElement as HTMLElement).getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(saveSecretMock).toHaveBeenCalledWith('anthropic_api_key', 'sk-real-secret'),
    )
    await waitFor(() => expect(onCapabilitiesChange).toHaveBeenCalled())
    expect(screen.queryByDisplayValue('sk-real-secret')).toBeNull()
  })

  it('clearing a configured key calls clearSecret then onCapabilitiesChange', async () => {
    const { onCapabilitiesChange } = renderEditor({
      capabilities: { configured_secret_refs: ['anthropic_api_key'] },
    })

    await waitFor(() => expect(screen.getByText('configured')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))

    await waitFor(() => expect(clearSecretMock).toHaveBeenCalledWith('anthropic_api_key'))
    await waitFor(() => expect(onCapabilitiesChange).toHaveBeenCalled())
  })

  it('a record with a null api_key_ref (e.g. Ollama) shows no key row at all', async () => {
    getProviderRecordsMock.mockResolvedValue({
      records: [OLLAMA_RECORD],
      provider_roles: { reasoning: 'ollama', fast: 'ollama' },
      provider_roles_saved: true,
    })
    renderEditor()

    await screen.findByRole('button', { name: 'Edit ollama' })
    expect(screen.queryByText('API key')).toBeNull()
    expect(screen.queryByLabelText('ollama API key')).toBeNull()
  })
})

describe('ProviderConfigEditor: add/edit a record', () => {
  it('adding a new record with a blank id shows an error and does not save', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    expect(await screen.findByText('A provider needs an id.')).toBeTruthy()
    expect(saveProviderConfigMock).not.toHaveBeenCalled()
  })

  it('"managed" is rejected as an id with a clear error, never reaching saveProviderConfig', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    fireEvent.change(screen.getByLabelText('Provider id'), { target: { value: 'managed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    expect(await screen.findByText('"managed" is a reserved id and cannot be used here.')).toBeTruthy()
    expect(saveProviderConfigMock).not.toHaveBeenCalled()
  })

  it('adding a duplicate id is rejected before saving', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    fireEvent.change(screen.getByLabelText('Provider id'), { target: { value: 'anthropic' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    expect(await screen.findByText('A provider named "anthropic" already exists.')).toBeTruthy()
    expect(saveProviderConfigMock).not.toHaveBeenCalled()
  })

  it('adding a new custom record saves the complete records array, appended, with a derived api_key_ref', async () => {
    const { onSaved } = renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    fireEvent.change(screen.getByLabelText('Provider id'), { target: { value: 'my-server' } })
    fireEvent.change(screen.getByLabelText('Base URL'), { target: { value: 'http://nuc.local:11434/v1' } })
    fireEvent.change(screen.getByLabelText('Reasoning model'), { target: { value: 'llama3.3:70b' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    await waitFor(() => expect(saveProviderConfigMock).toHaveBeenCalled())
    const [records, roles] = saveProviderConfigMock.mock.calls[0]
    expect(records).toEqual([
      ANTHROPIC_RECORD,
      {
        id: 'my-server',
        kind: 'openai_compat',
        base_url: 'http://nuc.local:11434/v1',
        api_key_ref: 'my-server_api_key',
        models: { reasoning: 'llama3.3:70b' },
        capabilities: { tool_use: true, strict_json: true },
      },
    ])
    expect(roles).toEqual({ reasoning: 'anthropic', fast: 'anthropic' })
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    // The form closes and the new record now appears in the list.
    expect(screen.getByRole('button', { name: 'Edit my-server' })).toBeTruthy()
  })

  it('unchecking "Requires an API key" on a new record saves a null api_key_ref', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    fireEvent.change(screen.getByLabelText('Provider id'), { target: { value: 'local-box' } })
    fireEvent.click(screen.getByLabelText('Requires an API key'))
    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    await waitFor(() => expect(saveProviderConfigMock).toHaveBeenCalled())
    const [records] = saveProviderConfigMock.mock.calls[0]
    expect(records.find((r: { id: string }) => r.id === 'local-box').api_key_ref).toBeNull()
  })

  it('a not-yet-saved new record shows no key input, with a reason', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))

    const draftForm = screen.getByRole('button', { name: 'Save provider' }).closest('div') as HTMLElement
    expect(within(draftForm).queryByLabelText(/API key/)).toBeNull()
    expect(screen.getByText(/Save this provider first/)).toBeTruthy()
  })

  it('editing an existing record keeps its id immutable and saves the updated fields in place', async () => {
    const { onSaved } = renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })
    fireEvent.click(screen.getByRole('button', { name: 'Edit anthropic' }))

    const idInput = screen.getByLabelText('Provider id') as HTMLInputElement
    expect(idInput.disabled).toBe(true)
    expect(idInput.value).toBe('anthropic')

    fireEvent.change(screen.getByLabelText('Fast model'), { target: { value: 'claude-haiku-4-5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    await waitFor(() => expect(saveProviderConfigMock).toHaveBeenCalled())
    const [records] = saveProviderConfigMock.mock.calls[0]
    expect(records).toEqual([
      { ...ANTHROPIC_RECORD, models: { reasoning: 'claude-sonnet-5', fast: 'claude-haiku-4-5' } },
    ])
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('editing a preset shows a note that saving overrides its default', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })
    fireEvent.click(screen.getByRole('button', { name: 'Edit anthropic' }))

    expect(screen.getByText(/permanently overrides its default/)).toBeTruthy()
  })

  it('a non-loopback base URL paired with a required API key shows the exfiltration warning inline', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })
    fireEvent.click(screen.getByRole('button', { name: 'Edit anthropic' }))

    fireEvent.change(screen.getByLabelText('Base URL'), { target: { value: 'https://evil.example.com' } })

    expect(await screen.findByText(/Only point this at a host you trust/)).toBeTruthy()
  })

  it('cancelling the edit form discards changes without saving', async () => {
    renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })
    fireEvent.click(screen.getByRole('button', { name: 'Edit anthropic' }))
    fireEvent.change(screen.getByLabelText('Base URL'), { target: { value: 'https://should-not-save.example' } })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Base URL')).toBeNull()
    expect(saveProviderConfigMock).not.toHaveBeenCalled()
  })

  it('a save failure surfaces the real error message without closing the form', async () => {
    saveProviderConfigMock.mockRejectedValueOnce(new Error('daemon unreachable'))
    renderEditor()
    await screen.findByRole('button', { name: 'Add provider' })
    fireEvent.click(screen.getByRole('button', { name: 'Add provider' }))
    fireEvent.change(screen.getByLabelText('Provider id'), { target: { value: 'my-server' } })

    fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))

    expect(await screen.findByText('daemon unreachable')).toBeTruthy()
    expect(screen.getByLabelText('Provider id')).toBeTruthy()
  })
})

describe('ProviderConfigEditor: deleting a record', () => {
  it('deleting a record not bound to any role never prompts for confirmation', async () => {
    getProviderRecordsMock.mockResolvedValue({
      records: [ANTHROPIC_RECORD, OLLAMA_RECORD],
      provider_roles: { reasoning: 'anthropic', fast: 'anthropic' },
      provider_roles_saved: true,
    })
    const { onSaved } = renderEditor()
    await screen.findByRole('button', { name: 'Edit ollama' })

    fireEvent.click(screen.getByRole('button', { name: 'Delete ollama' }))

    expect(askMock).not.toHaveBeenCalled()
    await waitFor(() =>
      expect(saveProviderConfigMock).toHaveBeenCalledWith(
        [ANTHROPIC_RECORD],
        { reasoning: 'anthropic', fast: 'anthropic' },
        EMPTY_CONFIG,
      ),
    )
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('deleting a role-bound record prompts for confirmation first', async () => {
    askMock.mockResolvedValueOnce(false)
    renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })

    fireEvent.click(screen.getByRole('button', { name: 'Delete anthropic' }))

    await waitFor(() => expect(askMock).toHaveBeenCalled())
    expect(saveProviderConfigMock).not.toHaveBeenCalled()
  })

  it('confirming the role-bound deletion proceeds, leaving the dangling role binding as-is', async () => {
    askMock.mockResolvedValueOnce(true)
    const { onSaved } = renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })

    fireEvent.click(screen.getByRole('button', { name: 'Delete anthropic' }))

    await waitFor(() =>
      expect(saveProviderConfigMock).toHaveBeenCalledWith(
        [],
        { reasoning: 'anthropic', fast: 'anthropic' },
        EMPTY_CONFIG,
      ),
    )
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })
})

describe('ProviderConfigEditor: role binding', () => {
  it('role dropdowns list only currently-saved record ids', async () => {
    getProviderRecordsMock.mockResolvedValue({
      records: [ANTHROPIC_RECORD, OLLAMA_RECORD],
      provider_roles: { reasoning: 'anthropic', fast: 'anthropic' },
      provider_roles_saved: true,
    })
    renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })

    const reasoningSelect = screen.getByLabelText('Reasoning role provider') as HTMLSelectElement
    expect(Array.from(reasoningSelect.options).map((o) => o.value)).toEqual(['anthropic', 'ollama'])
  })

  it('changing a role dropdown saves the complete records + updated roles pair immediately', async () => {
    getProviderRecordsMock.mockResolvedValue({
      records: [ANTHROPIC_RECORD, OLLAMA_RECORD],
      provider_roles: { reasoning: 'anthropic', fast: 'anthropic' },
      provider_roles_saved: true,
    })
    const { onSaved } = renderEditor()
    await screen.findByRole('button', { name: 'Edit anthropic' })

    fireEvent.change(screen.getByLabelText('Fast role provider'), { target: { value: 'ollama' } })

    await waitFor(() =>
      expect(saveProviderConfigMock).toHaveBeenCalledWith(
        [ANTHROPIC_RECORD, OLLAMA_RECORD],
        { reasoning: 'anthropic', fast: 'ollama' },
        EMPTY_CONFIG,
      ),
    )
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })
})
