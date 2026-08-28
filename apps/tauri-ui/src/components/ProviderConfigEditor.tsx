import { useEffect, useState } from 'react'
import {
  ALL_PROVIDERS,
  clearSecret,
  confirmRemoveRoleBoundProvider,
  getProviderRecords,
  isNonLoopbackBaseUrl,
  listProviderModels,
  saveProviderConfig,
  saveSecret,
  type DaemonCapabilities,
  type DaemonConfig,
  type ModelRole,
  type ModelListing,
  type ProviderRecord,
  validateProviderModel,
} from '../lib/settings'

/** SPEC-321 §2.1-2.5: replaces the old flat provider `<select>` + free-text
 * model field + four hardcoded key rows with a real editor over `SPEC-208`'s
 * provider records -- add/edit/remove records (presets included), bind
 * `reasoning`/`fast` to them, and see a migrated install's real resolved
 * state. `managed` never appears here, structurally: `PROVIDER_KIND_OPTIONS`
 * below is the only picker a new record's `kind` can come from, and
 * `llm.get_provider_records` (CTX-321.1) already filters any `managed`
 * entry out of what this component ever receives. */
const PROVIDER_KIND_OPTIONS: ProviderRecord['kind'][] = ['anthropic', 'openai_compat', 'google']

/** The five preset ids `llm_providers._preset_records()` seeds every
 * install with -- reused here (not re-declared) so "you're editing a
 * built-in default" stays in sync with the one real list of presets. */
const PRESET_IDS: readonly string[] = ALL_PROVIDERS

const ROLES: ModelRole[] = ['reasoning', 'fast']

interface RecordDraft {
  id: string
  kind: ProviderRecord['kind']
  base_url: string
  reasoningModel: string
  fastModel: string
  tool_use: boolean
  strict_json: boolean
  needsApiKey: boolean
}

const BLANK_DRAFT: RecordDraft = {
  id: '',
  kind: 'openai_compat',
  base_url: '',
  reasoningModel: '',
  fastModel: '',
  tool_use: true,
  strict_json: true,
  needsApiKey: true,
}

function draftFromRecord(record: ProviderRecord): RecordDraft {
  return {
    id: record.id,
    kind: record.kind,
    base_url: record.base_url ?? '',
    reasoningModel: record.models.reasoning ?? '',
    fastModel: record.models.fast ?? '',
    tool_use: record.capabilities.tool_use,
    strict_json: record.capabilities.strict_json,
    needsApiKey: record.api_key_ref != null,
  }
}

function recordFromDraft(draft: RecordDraft): ProviderRecord {
  const id = draft.id.trim()
  const models: { reasoning?: string; fast?: string } = {}
  if (draft.reasoningModel.trim()) models.reasoning = draft.reasoningModel.trim()
  if (draft.fastModel.trim()) models.fast = draft.fastModel.trim()
  return {
    id,
    kind: draft.kind,
    base_url: draft.base_url.trim() || null,
    api_key_ref: draft.needsApiKey ? `${id}_api_key` : null,
    models,
    capabilities: { tool_use: draft.tool_use, strict_json: draft.strict_json },
  }
}

const NEW_RECORD_SENTINEL = '__new__'

interface ProviderConfigEditorProps {
  config: DaemonConfig
  capabilities: DaemonCapabilities | null
  /** Re-fetches `config.json` (Settings' own `loadConfig`) -- called after
   * any provider/role save so the rest of Settings never holds a stale
   * `providers`/`provider_roles` view. */
  onSaved: () => Promise<void>
  /** Re-fetches `daemon.get_capabilities` -- called after a key
   * save/clear, the same pattern every other key row in Settings uses. */
  onCapabilitiesChange: () => Promise<void>
}

export function ProviderConfigEditor({
  config,
  capabilities,
  onSaved,
  onCapabilitiesChange,
}: ProviderConfigEditorProps) {
  const [records, setRecords] = useState<ProviderRecord[]>([])
  const [providerRoles, setProviderRoles] = useState<Record<ModelRole, string>>({
    reasoning: '',
    fast: '',
  })
  const [providerRolesSaved, setProviderRolesSaved] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<RecordDraft>(BLANK_DRAFT)
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({})
  const [busyKeyFor, setBusyKeyFor] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    try {
      const result = await getProviderRecords()
      setRecords(result.records)
      setProviderRoles(result.provider_roles)
      setProviderRolesSaved(result.provider_roles_saved)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  function startAdd() {
    setError(null)
    setDraft(BLANK_DRAFT)
    setEditingId(NEW_RECORD_SENTINEL)
  }

  function startEdit(record: ProviderRecord) {
    setError(null)
    setDraft(draftFromRecord(record))
    setEditingId(record.id)
  }

  function cancelEdit() {
    setEditingId(null)
    setError(null)
  }

  async function handleSaveRecord() {
    setError(null)
    const id = draft.id.trim()
    if (!id) {
      setError('A provider needs an id.')
      return
    }
    if (id === 'managed') {
      setError('"managed" is a reserved id and cannot be used here.')
      return
    }
    if (editingId === NEW_RECORD_SENTINEL && records.some((r) => r.id === id)) {
      setError(`A provider named "${id}" already exists.`)
      return
    }

    const nextRecord = recordFromDraft(draft)
    const nextRecords =
      editingId === NEW_RECORD_SENTINEL
        ? [...records, nextRecord]
        : records.map((r) => (r.id === editingId ? nextRecord : r))

    setBusy(true)
    try {
      await saveProviderConfig(nextRecords, providerRoles, config)
      setRecords(nextRecords)
      setEditingId(null)
      await onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleDeleteRecord(record: ProviderRecord) {
    setError(null)
    const boundRoles = ROLES.filter((role) => providerRoles[role] === record.id)
    if (boundRoles.length > 0) {
      const confirmed = await confirmRemoveRoleBoundProvider(record.id, boundRoles)
      if (!confirmed) return
    }

    const nextRecords = records.filter((r) => r.id !== record.id)
    setBusy(true)
    try {
      await saveProviderConfig(nextRecords, providerRoles, config)
      setRecords(nextRecords)
      if (editingId === record.id) setEditingId(null)
      await onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRoleChange(role: ModelRole, id: string) {
    setError(null)
    const nextRoles = { ...providerRoles, [role]: id }
    setBusy(true)
    try {
      await saveProviderConfig(records, nextRoles, config)
      setProviderRoles(nextRoles)
      setProviderRolesSaved(true)
      await onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveKey(apiKeyRef: string) {
    const value = keyInputs[apiKeyRef]?.trim()
    if (!value) return
    setBusyKeyFor(apiKeyRef)
    setError(null)
    try {
      await saveSecret(apiKeyRef, value)
      setKeyInputs((prev) => ({ ...prev, [apiKeyRef]: '' }))
      await onCapabilitiesChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyKeyFor(null)
    }
  }

  async function handleClearKey(apiKeyRef: string) {
    setBusyKeyFor(apiKeyRef)
    setError(null)
    try {
      await clearSecret(apiKeyRef)
      await onCapabilitiesChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyKeyFor(null)
    }
  }

  const configuredSecretRefs = new Set(capabilities?.configured_secret_refs ?? [])

  function renderKeyRow(record: ProviderRecord) {
    if (!record.api_key_ref) return null
    const ref = record.api_key_ref
    const configured = configuredSecretRefs.has(ref)
    return (
      <div className="flex items-center gap-2">
        <span className="w-16 text-xs text-fg-muted">API key</span>
        {configured ? (
          <>
            <span className="flex-1 text-sm text-success">configured</span>
            <button
              type="button"
              className="rounded border border-line px-3 py-1 text-sm disabled:opacity-50"
              onClick={() => void handleClearKey(ref)}
              disabled={busyKeyFor === ref}
            >
              Clear
            </button>
          </>
        ) : (
          <>
            <input
              type="password"
              aria-label={`${record.id} API key`}
              className="flex-1 rounded border border-line bg-surface px-3 py-1 text-sm"
              placeholder="API key"
              value={keyInputs[ref] ?? ''}
              onChange={(e) => setKeyInputs((prev) => ({ ...prev, [ref]: e.target.value }))}
            />
            <button
              type="button"
              className="rounded bg-accent px-3 py-1 text-sm font-medium text-accent-fg disabled:opacity-50"
              onClick={() => void handleSaveKey(ref)}
              disabled={busyKeyFor === ref || !keyInputs[ref]?.trim()}
            >
              Save
            </button>
          </>
        )}
      </div>
    )
  }

  /* SPEC-324: the models a provider reports, fetched only when asked
     (§2.3 -- no startup fetch, none on save, so nothing spends a user's
     quota without them acting). `supported: false` is surfaced as a reason
     rather than swallowed: an openai_compat record may point at a server
     with no /v1/models, which is ordinary rather than broken. */
  const [listing, setListing] = useState<ModelListing | null>(null)
  const [listingBusy, setListingBusy] = useState(false)
  const [modelCheck, setModelCheck] = useState<Record<string, string>>({})

  const loadModelList = async () => {
    if (!draft.id.trim()) return
    setListingBusy(true)
    try {
      setListing(await listProviderModels(draft.id.trim()))
    } catch (e) {
      setListing({ supported: false, models: [], reason: e instanceof Error ? e.message : String(e) })
    } finally {
      setListingBusy(false)
    }
  }

  const checkModel = async (role: ModelRole, model: string) => {
    setModelCheck((prev) => ({ ...prev, [role]: 'checking...' }))
    try {
      const result = await validateProviderModel(draft.id.trim(), model)
      setModelCheck((prev) => ({ ...prev, [role]: result.reason }))
    } catch (e) {
      setModelCheck((prev) => ({ ...prev, [role]: e instanceof Error ? e.message : String(e) }))
    }
  }

  /* SPEC-324 §2.2: a combobox, not a dropdown. The list is a suggestion and
     the field stays typeable, so a private deployment, a model newer than the
     provider's own list, or a compat server with its own naming all still
     work. With no list available this degrades to exactly the plain text
     field that shipped before -- never worse than today. */
  const renderModelField = (role: ModelRole, value: string, onChange: (v: string) => void) => {
    const label = role === 'reasoning' ? 'Reasoning model' : 'Fast model'
    return (
      <>
        <div className="flex gap-1">
          <input
            aria-label={label}
            list={`models-${role}`}
            className="flex-1 rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
            placeholder="(blank = can't serve this role)"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onFocus={() => {
              if (!listing && !listingBusy) void loadModelList()
            }}
          />
          <button
            type="button"
            aria-label={`Validate ${label}`}
            className="rounded border border-line px-2 py-0.5 text-xs"
            onClick={() => void checkModel(role, value)}
            disabled={!value.trim()}
          >
            Validate
          </button>
        </div>
        <datalist id={`models-${role}`}>
          {(listing?.models ?? []).map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
        {modelCheck[role] && <span className="text-fg-muted">{modelCheck[role]}</span>}
      </>
    )
  }

  function renderDraftForm() {
    const isNew = editingId === NEW_RECORD_SENTINEL
    return (
      <div className="flex flex-col gap-2 rounded border border-line p-3">
        <label className="flex flex-col gap-1 text-xs text-fg-tertiary">
          Id
          <input
            aria-label="Provider id"
            className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg disabled:opacity-50"
            value={draft.id}
            disabled={!isNew}
            onChange={(e) => setDraft((prev) => ({ ...prev, id: e.target.value }))}
          />
        </label>
        {!isNew && PRESET_IDS.includes(draft.id) && (
          <p className="text-xs text-warning">
            This is a built-in preset. Saving changes here permanently overrides its default for this
            install, until you delete your override.
          </p>
        )}
        <label className="flex flex-col gap-1 text-xs text-fg-tertiary">
          Kind
          <select
            aria-label="Provider kind"
            className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
            value={draft.kind}
            onChange={(e) =>
              setDraft((prev) => ({ ...prev, kind: e.target.value as ProviderRecord['kind'] }))
            }
          >
            {PROVIDER_KIND_OPTIONS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-tertiary">
          Base URL
          <input
            aria-label="Base URL"
            className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
            placeholder="(leave blank for the vendor's default)"
            value={draft.base_url}
            onChange={(e) => setDraft((prev) => ({ ...prev, base_url: e.target.value }))}
          />
        </label>
        {draft.needsApiKey && isNonLoopbackBaseUrl(draft.base_url.trim() || null) && (
          <p className="text-xs text-warning">
            This sends this provider's API key to {draft.base_url.trim()}. Only point this at a host
            you trust with that key.
          </p>
        )}
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-xs text-fg-tertiary">
            Reasoning model
            {renderModelField('reasoning', draft.reasoningModel, (v) =>
              setDraft((prev) => ({ ...prev, reasoningModel: v })))}
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs text-fg-tertiary">
            Fast model
            {renderModelField('fast', draft.fastModel, (v) =>
              setDraft((prev) => ({ ...prev, fastModel: v })))}
          </label>
        </div>
        {/* SPEC-324: listing is per PROVIDER, not per field, so its status
            belongs here once rather than duplicated under both models. */}
        {listingBusy && <p className="text-xs text-fg-muted">Loading models…</p>}
        {listing && !listing.supported && (
          <p className="text-xs text-fg-muted">
            Could not list models ({listing.reason}). Type the id yourself — it will still be saved.
          </p>
        )}
        <label className="flex items-center gap-2 text-xs text-fg-tertiary">
          <input
            type="checkbox"
            aria-label="Requires an API key"
            checked={draft.needsApiKey}
            onChange={(e) => setDraft((prev) => ({ ...prev, needsApiKey: e.target.checked }))}
          />
          Requires an API key
        </label>
        {isNew && draft.needsApiKey && (
          <p className="text-xs text-fg-muted">
            Save this provider first — its API key field appears once it exists.
          </p>
        )}
        <label className="flex items-center gap-2 text-xs text-fg-tertiary">
          <input
            type="checkbox"
            aria-label="Supports tool use"
            checked={draft.tool_use}
            onChange={(e) => setDraft((prev) => ({ ...prev, tool_use: e.target.checked }))}
          />
          Supports tool use
        </label>
        <label className="flex items-center gap-2 text-xs text-fg-tertiary">
          <input
            type="checkbox"
            aria-label="Supports strict JSON"
            checked={draft.strict_json}
            onChange={(e) => setDraft((prev) => ({ ...prev, strict_json: e.target.checked }))}
          />
          Supports strict JSON
        </label>
        <p className="text-xs text-fg-muted">
          Both capability boxes are a claim you're making about this model, not a measurement this app
          runs.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded bg-accent px-3 py-1 text-sm font-medium text-accent-fg disabled:opacity-50"
            onClick={() => void handleSaveRecord()}
            disabled={busy}
          >
            Save provider
          </button>
          <button
            type="button"
            className="rounded border border-line px-3 py-1 text-sm"
            onClick={cancelEdit}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  /* SPEC-322 §2.1: the missing link between the two levels of this screen.
     The dropdown names a provider record; what a user needs to know is the
     model that record will actually serve for this role -- and, when that
     field is blank on the record, that the role currently resolves to
     nothing at all. Reported as "this isn't self explanatory". */
  const describeRole = (role: ModelRole): string => {
    const bound = records.find((record) => record.id === providerRoles[role])
    if (!bound) return 'No provider selected.'
    const model = bound.models[role]
    if (!model) return `${bound.id} has no ${role} model set — this role cannot run.`
    return `Uses ${model}`
  }

  /* SPEC-322 §2.5: which roles, if any, this record actually serves. Empty
     string means nothing calls it -- reported as "not in use" rather than
     left blank, so an inert provider reads as a deliberate state and not as
     a rendering gap. */
  const rolesServedBy = (recordId: string): string =>
    (['reasoning', 'fast'] as ModelRole[])
      .filter((role) => providerRoles[role] === recordId)
      .join(' + ')

  return (
    <div className="flex flex-col gap-2">
      {error && <p className="text-sm text-danger">{error}</p>}

      {!providerRolesSaved && (
        <p className="text-xs text-fg-muted">
          Not yet saved — currently resolves to reasoning → {providerRoles.reasoning || '(none)'}, fast
          → {providerRoles.fast || '(none)'}, based on your existing provider/model setting.
        </p>
      )}

      <div className="flex flex-col gap-2">
        {records.map((record) => (
          <div key={record.id} className="flex flex-col gap-1 rounded border border-line p-2">
            <div className="flex items-center gap-2">
              <span className="flex-1 text-sm font-medium">{record.id}</span>
              {/* SPEC-322 §2.5: adding a provider does nothing on its own -- only the
                  records bound to a role are ever called. Without this, a user who
                  configures three providers and three API keys has no way to tell that
                  two of them are inert, or which one is answering. */}
              <span
                className={rolesServedBy(record.id) ? 'text-xs text-accent' : 'text-xs text-fg-muted'}
              >
                {rolesServedBy(record.id) || 'not in use'}
              </span>
              <span className="text-xs text-fg-muted">{record.kind}</span>
              <button
                type="button"
                aria-label={`Edit provider ${record.id}`}
                className="rounded border border-line px-2 py-0.5 text-xs"
                onClick={() => startEdit(record)}
              >
                Edit provider
              </button>
              <button
                type="button"
                aria-label={`Delete ${record.id}`}
                className="rounded border border-line px-2 py-0.5 text-xs"
                onClick={() => void handleDeleteRecord(record)}
                disabled={busy}
              >
                Delete
              </button>
            </div>
            {record.api_key_ref && isNonLoopbackBaseUrl(record.base_url) && (
              <p className="text-xs text-warning">
                This provider's API key is sent to {record.base_url}. Only use this for a host you
                trust with that key.
              </p>
            )}
            {renderKeyRow(record)}
            {editingId === record.id && renderDraftForm()}
          </div>
        ))}
      </div>

      {editingId === NEW_RECORD_SENTINEL ? (
        renderDraftForm()
      ) : (
        <button
          type="button"
          className="self-start rounded border border-line px-3 py-1 text-sm"
          onClick={startAdd}
        >
          Add provider
        </button>
      )}

      {/* SPEC-322 §2.1: this block used to be two bare dropdowns labelled
          "Reasoning" and "Fast" with no copy at all. A user who had not read
          SPEC-208 could not tell what a role was, which agents used it, or
          that the model itself is set per provider record above -- reported
          directly by the maintainer on first real use of the shipped screen. */}
      <section className="flex flex-col gap-2 border-t border-line pt-3">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium text-fg">Model roles</h3>
          <p className="text-xs text-fg-muted">
            Every AI feature in the app asks for one of two roles rather than naming a model
            directly. Choose which provider answers each role here; the model it actually uses is
            the one you set on that provider above.
          </p>
        </div>

        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-xs text-fg-tertiary">
            Reasoning
            <select
              aria-label="Reasoning role provider"
              className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
              value={providerRoles.reasoning}
              onChange={(e) => void handleRoleChange('reasoning', e.target.value)}
            >
              {records.map((record) => (
                <option key={record.id} value={record.id}>
                  {record.id}
                </option>
              ))}
            </select>
            <span className="text-fg-muted">{describeRole('reasoning')}</span>
            <span className="text-fg-muted">
              Part lookup, datasheet extraction, board review, connection guidance.
            </span>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs text-fg-tertiary">
            Fast
            <select
              aria-label="Fast role provider"
              className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
              value={providerRoles.fast}
              onChange={(e) => void handleRoleChange('fast', e.target.value)}
            >
              {records.map((record) => (
                <option key={record.id} value={record.id}>
                  {record.id}
                </option>
              ))}
            </select>
            <span className="text-fg-muted">{describeRole('fast')}</span>
            <span className="text-fg-muted">
              In-app chat in each area, and shorter summarising passes.
            </span>
          </label>
        </div>

        <p className="text-xs text-fg-muted">
          Which role a given feature asks for is fixed by the app, not configurable here.
        </p>
      </section>
    </div>
  )
}
