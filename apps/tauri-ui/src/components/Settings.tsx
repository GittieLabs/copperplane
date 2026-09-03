import { useEffect, useState } from 'react'
import {
  chooseStorageFolder,
  clearSecret,
  confirmStorageLocationChange,
  listProjectsInRoot,
  type ProjectsInRoot,
  copyDiagnostics,
  getCapabilities,
  getConfig,
  restartApp,
  saveConfig,
  saveSecret,
  type DaemonCapabilities,
  type DaemonConfig,
} from '../lib/settings'
import { ProviderConfigEditor } from './ProviderConfigEditor'
import { checkForUpdates, installUpdateAndRelaunch, type Update } from '../lib/updater'
import { useThemePreference, type ThemePreference } from '../lib/theme'

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
const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]

export function Settings() {
  const { preference: themePreference, resolvedTheme, setPreference: setThemePreference } =
    useThemePreference()
  const [capabilities, setCapabilities] = useState<DaemonCapabilities | null>(null)
  const [config, setConfig] = useState<DaemonConfig | null>(null)
  const [githubTokenInput, setGithubTokenInput] = useState('')
  const [busyGithubToken, setBusyGithubToken] = useState(false)
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

  /** CTX-314.2: `github_token` is not an LLM provider key, so this is a
   * standalone field/handler pair -- no `SUPPLIERS`-style N-provider
   * list abstraction, which `CTX-203.2` already removed for exactly one
   * field being the wrong amount of code to build a list around. */
  async function handleSaveGithubToken() {
    const value = githubTokenInput.trim()
    if (!value) return
    setBusyGithubToken(true)
    setError(null)
    try {
      await saveSecret('github_token', value)
      setGithubTokenInput('')
      await refreshCapabilities()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyGithubToken(false)
    }
  }

  async function handleClearGithubToken() {
    setBusyGithubToken(true)
    setError(null)
    try {
      await clearSecret('github_token')
      await refreshCapabilities()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyGithubToken(false)
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
        // CTX-110.2: name the projects that will stop appearing. Both roots
        // are probed before the modal, and a failed probe falls back to the
        // original wording rather than a confident claim about projects we
        // could not look at.
        let leaving: ProjectsInRoot | undefined
        let arriving: ProjectsInRoot | undefined
        try {
          if (oldEffectiveRoot && newEffectiveRoot) {
            ;[leaving, arriving] = await Promise.all([
              listProjectsInRoot(oldEffectiveRoot),
              listProjectsInRoot(newEffectiveRoot),
            ])
          }
        } catch {
          leaving = undefined
          arriving = undefined
        }
        const shouldRestart = await confirmStorageLocationChange(leaving, arriving)
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

  return (
    <div className="flex w-full max-w-4xl flex-col gap-4 text-fg">
      <h2 className="text-lg font-medium">Settings</h2>
      {error && <p className="text-sm text-danger">{error}</p>}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-fg-tertiary">Appearance</h3>
        <div className="flex gap-2" role="radiogroup" aria-label="Theme">
          {THEME_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={themePreference === option.value}
              className={
                themePreference === option.value
                  ? 'rounded bg-accent px-3 py-1 text-sm font-medium text-accent-fg'
                  : 'rounded border border-line px-3 py-1 text-sm'
              }
              onClick={() => setThemePreference(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        {themePreference === 'system' && (
          <p className="text-xs text-fg-muted">
            Currently resolves to {resolvedTheme === 'dark' ? 'Dark' : 'Light'}, based on your OS
            setting.
          </p>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-fg-tertiary">Provider Configuration</h3>
        {config && (
          <ProviderConfigEditor
            config={config}
            capabilities={capabilities}
            onSaved={loadConfig}
            onCapabilitiesChange={refreshCapabilities}
          />
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-fg-tertiary">Community Library Search</h3>
        <p className="text-xs text-fg-muted">
          Optional. Searching community footprint/symbol libraries works without a token, limited
          to 60 requests/hour from GitHub. Adding a personal access token (no special scopes
          needed) raises that to 5,000/hour.
        </p>
        <div className="flex items-center gap-2">
          <span className="w-24 text-sm">GitHub token</span>
          {capabilities?.github_token_configured ? (
            <>
              <span className="flex-1 text-sm text-success">configured</span>
              <button
                type="button"
                className="rounded border border-line px-3 py-1 text-sm disabled:opacity-50"
                onClick={() => void handleClearGithubToken()}
                disabled={busyGithubToken}
              >
                Clear
              </button>
            </>
          ) : (
            <>
              <input
                type="password"
                aria-label="GitHub token"
                className="flex-1 rounded border border-line bg-surface px-3 py-1 text-sm"
                placeholder="personal access token"
                value={githubTokenInput}
                onChange={(e) => setGithubTokenInput(e.target.value)}
              />
              <button
                type="button"
                className="rounded bg-accent px-3 py-1 text-sm font-medium text-accent-fg disabled:opacity-50"
                onClick={() => void handleSaveGithubToken()}
                disabled={busyGithubToken || !githubTokenInput.trim()}
              >
                Save
              </button>
            </>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-fg-tertiary">Connectivity</h3>
        <div className="flex flex-col gap-1 text-sm">
          <span className={capabilities?.kicad_available ? 'text-success' : 'text-fg-muted'}>
            KiCad: {capabilities?.kicad_available ? 'reachable' : 'not reachable'}
          </span>
          {/* CTX-303.4: real user feedback -- "not reachable" alone gave no
           * way to tell why. The check itself is a cheap, non-blocking
           * file-existence probe (SPEC-107 §3), not a live connection
           * attempt, so this can only ever suggest the likely real causes,
           * not diagnose with certainty -- stated plainly, not overclaimed. */}
          {!capabilities?.kicad_available && capabilities?.kicad_socket_path_checked && (
            <p className="text-xs text-fg-muted">
              Checked: <code>{capabilities.kicad_socket_path_checked}</code> — no socket found there.
              Likely KiCad isn't running, or its IPC API isn't enabled (Preferences → Plugins).
            </p>
          )}
          <span className={capabilities?.freecad_available ? 'text-success' : 'text-fg-muted'}>
            FreeCAD: {capabilities?.freecad_available ? 'reachable' : 'not reachable'}
          </span>
          {capabilities?.freecad_available && capabilities.freecad_path_checked && (
            <p className="text-xs text-fg-muted">
              Found at: <code>{capabilities.freecad_path_checked}</code>
            </p>
          )}
          {!capabilities?.freecad_available && capabilities?.freecad_error && (
            <p className="text-xs text-fg-muted">{capabilities.freecad_error}</p>
          )}
        </div>

        <label className="flex flex-col gap-1 text-sm text-fg-tertiary">
          KiCad IPC socket path
          <input
            aria-label="KiCad IPC socket path"
            className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
            placeholder="/tmp/kicad/api.sock"
            value={pathFields.kicad_socket_path}
            onChange={(e) => {
              setPathsSaved(false)
              setPathFields((prev) => ({ ...prev, kicad_socket_path: e.target.value }))
            }}
          />
          <span className="text-xs text-fg-muted">
            Optional. Leave blank for a standard KiCad install — the app finds the real socket KiCad
            itself creates automatically. Only set this if KiCad's IPC socket lives somewhere
            non-standard.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm text-fg-tertiary">
          KiCad IPC timeout (ms)
          <input
            aria-label="KiCad IPC timeout (ms)"
            type="number"
            className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
            value={pathFields.kicad_timeout_ms}
            onChange={(e) => {
              setPathsSaved(false)
              setPathFields((prev) => ({ ...prev, kicad_timeout_ms: e.target.value }))
            }}
          />
          <span className="text-xs text-fg-muted">
            Optional. How long to wait for a KiCad IPC response before giving up. Leave blank to use
            the built-in default.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm text-fg-tertiary">
          freecadcmd path override
          <input
            aria-label="freecadcmd path override"
            className="rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
            placeholder="/opt/freecad/bin/freecadcmd"
            value={pathFields.freecadcmd_path_override}
            onChange={(e) => {
              setPathsSaved(false)
              setPathFields((prev) => ({ ...prev, freecadcmd_path_override: e.target.value }))
            }}
          />
          <span className="text-xs text-fg-muted">
            Optional. Leave blank for a standard FreeCAD install — the app searches PATH and the usual
            per-OS install locations automatically. Only set this if <code>freecadcmd</code> lives
            somewhere non-standard.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm text-fg-tertiary">
          Storage location
          <div className="flex gap-2">
            <input
              aria-label="Storage location"
              className="flex-1 rounded border border-line bg-surface px-3 py-1 text-sm text-fg"
              placeholder={capabilities?.storage_root ?? ''}
              value={pathFields.storage_root_override}
              onChange={(e) => {
                setPathsSaved(false)
                setPathFields((prev) => ({ ...prev, storage_root_override: e.target.value }))
              }}
            />
            <button
              type="button"
              className="shrink-0 rounded border border-line px-3 py-1 text-sm"
              onClick={() => void handleChooseStorageFolder()}
            >
              Choose folder…
            </button>
          </div>
          <span className="text-xs text-fg-muted">
            Where your projects and your parts library are kept. Your project list is whatever this
            folder contains, so changing it changes which projects Copperplane can see — nothing is
            deleted, and pointing back here brings them back.
          </span>
          {capabilities?.storage_root && (
            <span className="text-xs text-fg-muted">Currently: {capabilities.storage_root}</span>
          )}
        </label>

        <p className="text-xs text-warning">
          These four fields are only read at daemon startup — restart the app to apply a change.
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded bg-accent px-3 py-1 text-sm font-medium text-accent-fg"
            onClick={() => void handleSavePaths()}
          >
            Save
          </button>
          {pathsSaved && (
            <>
              <span className="text-sm text-success">Saved — restart to apply.</span>
              <button
                type="button"
                className="rounded border border-line px-2 py-0.5 text-xs"
                onClick={() => void handleRestartNow()}
              >
                Restart Now
              </button>
            </>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-fg-tertiary">Updates</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded border border-line px-3 py-1 text-sm disabled:opacity-50"
            onClick={() => void handleCheckForUpdates()}
            disabled={checkingUpdate || installingUpdate}
          >
            {checkingUpdate ? 'Checking…' : 'Check for Updates'}
          </button>
          {upToDate && !availableUpdate && (
            <span className="text-sm text-fg-tertiary">You're up to date.</span>
          )}
        </div>
        {updateError && <p className="text-sm text-danger">{updateError}</p>}
        {availableUpdate && (
          <div className="flex flex-col gap-2 rounded border border-line p-3">
            <p className="text-sm text-fg">
              Version {availableUpdate.version} is available (you have {availableUpdate.currentVersion}).
            </p>
            {availableUpdate.body && <p className="text-sm text-fg-tertiary">{availableUpdate.body}</p>}
            <button
              type="button"
              className="self-start rounded bg-accent px-3 py-1 text-sm font-medium text-accent-fg disabled:opacity-50"
              onClick={() => void handleInstallUpdate()}
              disabled={installingUpdate}
            >
              {installingUpdate ? 'Installing…' : 'Install & Restart'}
            </button>
          </div>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-fg-tertiary">Diagnostics</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="self-start rounded border border-line px-3 py-1 text-sm"
            onClick={() => void handleCopyDiagnostics()}
          >
            Copy Diagnostics
          </button>
          {diagnosticsCopied && <span className="text-sm text-success">Copied to clipboard.</span>}
        </div>
      </section>
    </div>
  )
}
