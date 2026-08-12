import { useEffect, useState } from 'react'
import {
  ALL_PROVIDERS,
  KEY_BASED_PROVIDERS,
  clearSecret,
  getCapabilities,
  getConfig,
  saveConfig,
  saveSecret,
  secretKeyFor,
  setLlmProviderAndModel,
  type DaemonCapabilities,
  type DaemonConfig,
  type KeyBasedProvider,
} from '../lib/settings'

/** SPEC-303 Tier 1 (provider/model/keys) and Tier 2 (KiCad/FreeCAD
 * reachability + path overrides). Every secret save/clear re-fetches
 * `daemon.get_capabilities` afterward rather than trusting a value this
 * component holds itself -- a saved key never round-trips back to the
 * renderer (SPEC-106's existing security posture, which this screen must
 * not regress). Tier 2's three path fields are read once from an env var
 * at daemon *spawn* time (`CTX-106.1`) -- saving them writes `config.json`
 * for the next restart but does not take effect live, unlike Tier 1's
 * provider/model. The visible notice on those fields exists specifically
 * so that distinction is never silently implied away (SPEC-303 §3's own
 * named risk). */
export function Settings() {
  const [capabilities, setCapabilities] = useState<DaemonCapabilities | null>(null)
  const [config, setConfig] = useState<DaemonConfig | null>(null)
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({})
  const [busyProvider, setBusyProvider] = useState<string | null>(null)
  const [providerModel, setProviderModel] = useState('')
  const [pathFields, setPathFields] = useState({
    kicad_socket_path: '',
    kicad_timeout_ms: '',
    freecadcmd_path_override: '',
  })
  const [pathsSaved, setPathsSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void refreshCapabilities()
    void loadConfig()
  }, [])

  async function refreshCapabilities() {
    try {
      setCapabilities(await getCapabilities())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function loadConfig() {
    try {
      const cfg = await getConfig()
      setConfig(cfg)
      setProviderModel(cfg.llm_model ?? '')
      setPathFields({
        kicad_socket_path: cfg.kicad_socket_path ?? '',
        kicad_timeout_ms: cfg.kicad_timeout_ms != null ? String(cfg.kicad_timeout_ms) : '',
        freecadcmd_path_override: cfg.freecadcmd_path_override ?? '',
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleSaveKey(provider: KeyBasedProvider) {
    const value = keyInputs[provider]?.trim()
    if (!value) return
    setBusyProvider(provider)
    setError(null)
    try {
      await saveSecret(secretKeyFor(provider), value)
      setKeyInputs((prev) => ({ ...prev, [provider]: '' }))
      await refreshCapabilities()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyProvider(null)
    }
  }

  async function handleClearKey(provider: KeyBasedProvider) {
    setBusyProvider(provider)
    setError(null)
    try {
      await clearSecret(secretKeyFor(provider))
      await refreshCapabilities()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyProvider(null)
    }
  }

  async function handleSaveProvider(provider: string) {
    if (!config) return
    setError(null)
    try {
      await setLlmProviderAndModel(provider, providerModel.trim() || null, config)
      await loadConfig()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleSavePaths() {
    if (!config) return
    setError(null)
    setPathsSaved(false)
    try {
      const timeoutMs = pathFields.kicad_timeout_ms.trim()
      await saveConfig({
        ...config,
        kicad_socket_path: pathFields.kicad_socket_path.trim() || null,
        kicad_timeout_ms: timeoutMs ? Number(timeoutMs) : null,
        freecadcmd_path_override: pathFields.freecadcmd_path_override.trim() || null,
      })
      setPathsSaved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const configuredProviders = new Set(capabilities?.llm_providers ?? [])

  return (
    <div className="flex w-full max-w-md flex-col gap-4 text-neutral-100">
      <h2 className="text-lg font-medium">Settings</h2>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-neutral-400">LLM Provider</h3>
        <div className="flex gap-2">
          <select
            aria-label="LLM provider"
            className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
            value={config?.llm_provider ?? ''}
            onChange={(e) => void handleSaveProvider(e.target.value)}
          >
            <option value="" disabled>
              Select a provider
            </option>
            {ALL_PROVIDERS.map((provider) => (
              <option key={provider} value={provider}>
                {provider}
              </option>
            ))}
          </select>
          <input
            aria-label="Model"
            className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
            placeholder="model (optional)"
            value={providerModel}
            onChange={(e) => setProviderModel(e.target.value)}
            onBlur={() => config?.llm_provider && void handleSaveProvider(config.llm_provider)}
          />
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-neutral-400">API Keys</h3>
        {KEY_BASED_PROVIDERS.map((provider) => (
          <div key={provider} className="flex items-center gap-2">
            <span className="w-24 text-sm capitalize">{provider}</span>
            {configuredProviders.has(provider) ? (
              <>
                <span className="flex-1 text-sm text-emerald-400">configured</span>
                <button
                  type="button"
                  className="rounded border border-neutral-700 px-3 py-1 text-sm disabled:opacity-50"
                  onClick={() => void handleClearKey(provider)}
                  disabled={busyProvider === provider}
                >
                  Clear
                </button>
              </>
            ) : (
              <>
                <input
                  type="password"
                  aria-label={`${provider} API key`}
                  className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-1 text-sm"
                  placeholder="API key"
                  value={keyInputs[provider] ?? ''}
                  onChange={(e) => setKeyInputs((prev) => ({ ...prev, [provider]: e.target.value }))}
                />
                <button
                  type="button"
                  className="rounded bg-neutral-100 px-3 py-1 text-sm font-medium text-neutral-950 disabled:opacity-50"
                  onClick={() => void handleSaveKey(provider)}
                  disabled={busyProvider === provider || !keyInputs[provider]?.trim()}
                >
                  Save
                </button>
              </>
            )}
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-neutral-400">Connectivity</h3>
        <div className="flex gap-4 text-sm">
          <span className={capabilities?.kicad_available ? 'text-emerald-400' : 'text-neutral-500'}>
            KiCad: {capabilities?.kicad_available ? 'reachable' : 'not reachable'}
          </span>
          <span className={capabilities?.freecad_available ? 'text-emerald-400' : 'text-neutral-500'}>
            FreeCAD: {capabilities?.freecad_available ? 'reachable' : 'not reachable'}
          </span>
        </div>

        <label className="flex flex-col gap-1 text-sm text-neutral-400">
          KiCad IPC socket path
          <input
            aria-label="KiCad IPC socket path"
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1 text-sm text-neutral-100"
            placeholder="/tmp/kicad/api.sock"
            value={pathFields.kicad_socket_path}
            onChange={(e) => {
              setPathsSaved(false)
              setPathFields((prev) => ({ ...prev, kicad_socket_path: e.target.value }))
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-400">
          KiCad IPC timeout (ms)
          <input
            aria-label="KiCad IPC timeout (ms)"
            type="number"
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1 text-sm text-neutral-100"
            value={pathFields.kicad_timeout_ms}
            onChange={(e) => {
              setPathsSaved(false)
              setPathFields((prev) => ({ ...prev, kicad_timeout_ms: e.target.value }))
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-400">
          freecadcmd path override
          <input
            aria-label="freecadcmd path override"
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1 text-sm text-neutral-100"
            placeholder="/opt/freecad/bin/freecadcmd"
            value={pathFields.freecadcmd_path_override}
            onChange={(e) => {
              setPathsSaved(false)
              setPathFields((prev) => ({ ...prev, freecadcmd_path_override: e.target.value }))
            }}
          />
        </label>

        <p className="text-xs text-amber-400">
          These three fields are only read at daemon startup — restart the app to apply a change.
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded bg-neutral-100 px-3 py-1 text-sm font-medium text-neutral-950"
            onClick={() => void handleSavePaths()}
          >
            Save
          </button>
          {pathsSaved && <span className="text-sm text-emerald-400">Saved — restart to apply.</span>}
        </div>
      </section>
    </div>
  )
}
