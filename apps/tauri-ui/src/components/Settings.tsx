import { useEffect, useState } from 'react'
import {
  ALL_PROVIDERS,
  KEY_BASED_PROVIDERS,
  clearSecret,
  getCapabilities,
  getConfig,
  saveSecret,
  secretKeyFor,
  setLlmProviderAndModel,
  type DaemonCapabilities,
  type DaemonConfig,
  type KeyBasedProvider,
} from '../lib/settings'

/** SPEC-303 Tier 1: LLM provider/model selection and per-provider API-key
 * management. Every save/clear re-fetches `daemon.get_capabilities`
 * afterward rather than trusting a value this component holds itself --
 * a saved key never round-trips back to the renderer (SPEC-106's existing
 * security posture, which this screen must not regress). */
export function Settings() {
  const [capabilities, setCapabilities] = useState<DaemonCapabilities | null>(null)
  const [config, setConfig] = useState<DaemonConfig | null>(null)
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({})
  const [busyProvider, setBusyProvider] = useState<string | null>(null)
  const [providerModel, setProviderModel] = useState('')
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
    </div>
  )
}
