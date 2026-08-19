import { useEffect, useState } from 'react'
import {
  ALL_PROVIDERS,
  KEY_BASED_PROVIDERS,
  chooseStorageFolder,
  clearSecret,
  confirmStorageLocationChange,
  copyDiagnostics,
  getCapabilities,
  getConfig,
  restartApp,
  saveConfig,
  saveSecret,
  secretKeyFor,
  setLlmProviderAndModel,
  type DaemonCapabilities,
  type DaemonConfig,
  type KeyBasedProvider,
} from '../lib/settings'
import { checkForUpdates, installUpdateAndRelaunch, type Update } from '../lib/updater'

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
    storage_root_override: '',
  })
  const [pathsSaved, setPathsSaved] = useState(false)
  const [diagnosticsCopied, setDiagnosticsCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checkingUpdate, setCheckingUpdate] = useState(false)
  const [installingUpdate, setInstallingUpdate] = useState(false)
  const [availableUpdate, setAvailableUpdate] = useState<Update | null>(null)
  const [upToDate, setUpToDate] = useState(false)
  const [updateError, setUpdateError] = useState<string | null>(null)

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
        storage_root_override: cfg.storage_root_override ?? '',
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
    const newStorageOverride = pathFields.storage_root_override.trim() || null
    // Compares the real *effective* root, not just the raw override
    // field -- a real bug found by hand: the folder picker opens at
    // capabilities.storage_root (the current real path) as its default
    // location, so a user who opens it and re-selects that same folder
    // (a completely natural action) ends up with a non-null override
    // string that's identical to the current default, which a raw
    // field-vs-field comparison would wrongly call "changed."
    const oldEffectiveRoot = config.storage_root_override || capabilities?.storage_root || null
    const newEffectiveRoot = newStorageOverride || capabilities?.storage_root || null
    const storageOverrideChanged = newEffectiveRoot !== oldEffectiveRoot
    try {
      const timeoutMs = pathFields.kicad_timeout_ms.trim()
      await saveConfig({
        ...config,
        kicad_socket_path: pathFields.kicad_socket_path.trim() || null,
        kicad_timeout_ms: timeoutMs ? Number(timeoutMs) : null,
        freecadcmd_path_override: pathFields.freecadcmd_path_override.trim() || null,
        storage_root_override: newStorageOverride,
      })
      setPathsSaved(true)
      await loadConfig()
      // SPEC-110: a real, harder-to-ignore native modal specifically for
      // the storage location -- unlike KiCad/FreeCAD path changes, an
      // un-applied storage change risks real files landing in two
      // different places depending on whether a restart happened yet.
      if (storageOverrideChanged) {
        const shouldRestart = await confirmStorageLocationChange()
        if (shouldRestart) {
          await restartApp()
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleRestartNow() {
    setError(null)
    try {
      await restartApp()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleChooseStorageFolder() {
    setError(null)
    try {
      const chosen = await chooseStorageFolder(pathFields.storage_root_override || capabilities?.storage_root)
      if (chosen) {
        setPathsSaved(false)
        setPathFields((prev) => ({ ...prev, storage_root_override: chosen }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleCheckForUpdates() {
    setCheckingUpdate(true)
    setUpdateError(null)
    setUpToDate(false)
    try {
      const update = await checkForUpdates()
      setAvailableUpdate(update)
      setUpToDate(update === null)
    } catch (err) {
      setUpdateError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingUpdate(false)
    }
  }

  async function handleInstallUpdate() {
    if (!availableUpdate) return
    setInstallingUpdate(true)
    setUpdateError(null)
    try {
      await installUpdateAndRelaunch(availableUpdate)
    } catch (err) {
      setUpdateError(err instanceof Error ? err.message : String(err))
      setInstallingUpdate(false)
    }
  }

  async function handleCopyDiagnostics() {
    setError(null)
    setDiagnosticsCopied(false)
    try {
      await copyDiagnostics()
      setDiagnosticsCopied(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const configuredProviders = new Set(capabilities?.llm_providers ?? [])

  return (
    <div className="flex w-full max-w-4xl flex-col gap-4 text-neutral-100">
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
        <div className="flex flex-col gap-1 text-sm">
          <span className={capabilities?.kicad_available ? 'text-emerald-400' : 'text-neutral-500'}>
            KiCad: {capabilities?.kicad_available ? 'reachable' : 'not reachable'}
          </span>
          {/* CTX-303.4: real user feedback -- "not reachable" alone gave no
           * way to tell why. The check itself is a cheap, non-blocking
           * file-existence probe (SPEC-107 §3), not a live connection
           * attempt, so this can only ever suggest the likely real causes,
           * not diagnose with certainty -- stated plainly, not overclaimed. */}
          {!capabilities?.kicad_available && capabilities?.kicad_socket_path_checked && (
            <p className="text-xs text-neutral-500">
              Checked: <code>{capabilities.kicad_socket_path_checked}</code> — no socket found there.
              Likely KiCad isn't running, or its IPC API isn't enabled (Preferences → Plugins).
            </p>
          )}
          <span className={capabilities?.freecad_available ? 'text-emerald-400' : 'text-neutral-500'}>
            FreeCAD: {capabilities?.freecad_available ? 'reachable' : 'not reachable'}
          </span>
          {capabilities?.freecad_available && capabilities.freecad_path_checked && (
            <p className="text-xs text-neutral-500">
              Found at: <code>{capabilities.freecad_path_checked}</code>
            </p>
          )}
          {!capabilities?.freecad_available && capabilities?.freecad_error && (
            <p className="text-xs text-neutral-500">{capabilities.freecad_error}</p>
          )}
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
          <span className="text-xs text-neutral-500">
            Optional. Leave blank for a standard KiCad install — the app finds the real socket KiCad
            itself creates automatically. Only set this if KiCad's IPC socket lives somewhere
            non-standard.
          </span>
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
          <span className="text-xs text-neutral-500">
            Optional. How long to wait for a KiCad IPC response before giving up. Leave blank to use
            the built-in default.
          </span>
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
          <span className="text-xs text-neutral-500">
            Optional. Leave blank for a standard FreeCAD install — the app searches PATH and the usual
            per-OS install locations automatically. Only set this if <code>freecadcmd</code> lives
            somewhere non-standard.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-400">
          Storage location
          <div className="flex gap-2">
            <input
              aria-label="Storage location"
              className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-1 text-sm text-neutral-100"
              placeholder={capabilities?.storage_root ?? ''}
              value={pathFields.storage_root_override}
              onChange={(e) => {
                setPathsSaved(false)
                setPathFields((prev) => ({ ...prev, storage_root_override: e.target.value }))
              }}
            />
            <button
              type="button"
              className="shrink-0 rounded border border-neutral-700 px-3 py-1 text-sm"
              onClick={() => void handleChooseStorageFolder()}
            >
              Choose folder…
            </button>
          </div>
          {capabilities?.storage_root && (
            <span className="text-xs text-neutral-500">Currently: {capabilities.storage_root}</span>
          )}
        </label>

        <p className="text-xs text-amber-400">
          These four fields are only read at daemon startup — restart the app to apply a change.
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded bg-neutral-100 px-3 py-1 text-sm font-medium text-neutral-950"
            onClick={() => void handleSavePaths()}
          >
            Save
          </button>
          {pathsSaved && (
            <>
              <span className="text-sm text-emerald-400">Saved — restart to apply.</span>
              <button
                type="button"
                className="rounded border border-neutral-700 px-2 py-0.5 text-xs"
                onClick={() => void handleRestartNow()}
              >
                Restart Now
              </button>
            </>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-neutral-400">Updates</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded border border-neutral-700 px-3 py-1 text-sm disabled:opacity-50"
            onClick={() => void handleCheckForUpdates()}
            disabled={checkingUpdate || installingUpdate}
          >
            {checkingUpdate ? 'Checking…' : 'Check for Updates'}
          </button>
          {upToDate && !availableUpdate && (
            <span className="text-sm text-neutral-400">You're up to date.</span>
          )}
        </div>
        {updateError && <p className="text-sm text-red-400">{updateError}</p>}
        {availableUpdate && (
          <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
            <p className="text-sm text-neutral-100">
              Version {availableUpdate.version} is available (you have {availableUpdate.currentVersion}).
            </p>
            {availableUpdate.body && <p className="text-sm text-neutral-400">{availableUpdate.body}</p>}
            <button
              type="button"
              className="self-start rounded bg-neutral-100 px-3 py-1 text-sm font-medium text-neutral-950 disabled:opacity-50"
              onClick={() => void handleInstallUpdate()}
              disabled={installingUpdate}
            >
              {installingUpdate ? 'Installing…' : 'Install & Restart'}
            </button>
          </div>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-neutral-400">Diagnostics</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded border border-neutral-700 px-3 py-1 text-sm"
            onClick={() => void handleCopyDiagnostics()}
          >
            Copy Diagnostics
          </button>
          {diagnosticsCopied && <span className="text-sm text-emerald-400">Copied to clipboard.</span>}
        </div>
      </section>
    </div>
  )
}
