import { invoke } from '@tauri-apps/api/core'
import { writeText } from '@tauri-apps/plugin-clipboard-manager'
import { ask, open } from '@tauri-apps/plugin-dialog'
import { relaunch } from '@tauri-apps/plugin-process'
import { dispatch } from './ipc'

/** Must match `daemon.py`'s `_KEY_BASED_PROVIDERS` and
 * `core/tauri-rust/src/daemon.rs`'s `KNOWN_SECRET_KEYS` allowlist. Ollama
 * needs no key (a local server), so it's never included here. */
export const KEY_BASED_PROVIDERS = ['anthropic', 'google', 'openai', 'perplexity'] as const
export type KeyBasedProvider = (typeof KEY_BASED_PROVIDERS)[number]

/** Every provider the LLM picker offers -- key-based ones plus Ollama,
 * which needs no key, only a locally reachable server. */
export const ALL_PROVIDERS = [...KEY_BASED_PROVIDERS, 'ollama'] as const

/** Matches `llm_providers.py`'s own `f"{provider}_api_key"` lookup
 * convention -- the OS keychain key name for a given provider. */
export function secretKeyFor(provider: KeyBasedProvider): string {
  return `${provider}_api_key`
}

/** Mirrors `core/tauri-rust/src/config.rs`'s `DaemonConfig`. `output_dir`
 * and `storage_root` are deliberately omitted -- both are always
 * Rust-computed at spawn, never a real setting a human edits or reads
 * back from `config.json` (the real current `storage_root` is reported
 * via `DaemonCapabilities` instead). `storage_root_override` (SPEC-110)
 * is the one a human actually sets. */
export interface DaemonConfig {
  freecadcmd_path_override?: string | null
  kicad_socket_path?: string | null
  kicad_timeout_ms?: number | null
  llm_provider?: string | null
  llm_model?: string | null
  storage_root_override?: string | null
}

/** Mirrors `daemon.py`'s `_detect_capabilities()` shape. `log_path` is
 * `null` if only `stderr` logging is active (e.g. a read-only log dir) --
 * reported honestly by the daemon, not papered over here. */
export interface DaemonCapabilities {
  kicad_available: boolean
  /** CTX-303.4: the real path the daemon actually checked for KiCad's IPC
   * socket -- the configured override, or the real default
   * (`/tmp/kicad/api.sock`) -- reported whether or not it exists, so a
   * "not reachable" state can say exactly where it looked. */
  kicad_socket_path_checked: string | null
  freecad_available: boolean
  /** CTX-303.4: the real, resolved freecadcmd path on success -- never
   * set alongside a real freecad_error. */
  freecad_path_checked: string | null
  /** CTX-303.4: the real, specific reason freecadcmd couldn't be found,
   * straight from find_freecadcmd()'s own exception message -- never set
   * alongside a real freecad_path_checked. */
  freecad_error: string | null
  llm_providers: string[]
  log_path: string | null
  python_version: string
  /** SPEC-110: the real, currently-active storage root, whether the
   * app's default data directory or a user's real override -- reported
   * here (not config.json) since it's always Rust-computed at spawn. */
  storage_root: string | null
  /** CTX-314.1/CTX-314.2: whether a `github_token` secret is configured
   * -- real and dynamic since CTX-314.2 added the real KNOWN_SECRET_KEYS
   * entry; unauthenticated community-library search still works, just
   * at GitHub's lower unauthenticated rate limit. */
  github_token_configured: boolean
}

/** Saves a provider API key to the OS keychain and pushes the complete
 * current secret set to the already-running daemon -- no restart needed
 * (`core/tauri-rust/src/secrets.rs::save_secret`). The renderer never
 * receives the value back; call `getCapabilities()` afterward to confirm. */
export async function saveSecret(key: string, value: string): Promise<void> {
  await invoke('save_secret', { key, value })
}

/** Clears a provider API key and re-syncs the daemon so it stops
 * reporting that provider as configured, without a restart. */
export async function clearSecret(key: string): Promise<void> {
  await invoke('clear_secret', { key })
}

/** Reads the current non-secret config from `config.json`, to prefill
 * the Settings form. */
export async function getConfig(): Promise<DaemonConfig> {
  return invoke('get_config')
}

/** Persists non-secret config to `config.json`. Socket-path/timeout and
 * `freecadcmd`-path fields only take effect on the next daemon restart
 * (read once from an env var at spawn, per `CTX-106.1`) -- callers must
 * surface that distinction, not imply a live update that doesn't happen. */
export async function saveConfig(config: DaemonConfig): Promise<void> {
  await invoke('save_config_cmd', { config })
}

/** Calls the daemon's `daemon.get_capabilities` route on demand, so the
 * UI can refresh what's actually configured right after a save/clear. */
export async function getCapabilities(): Promise<DaemonCapabilities> {
  const response = await dispatch('daemon.get_capabilities', {})
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as DaemonCapabilities
}

/** Persists the provider/model choice to `config.json` (for the next
 * restart) and pushes it live to the running daemon via `daemon.configure`
 * (SPEC-303's extension) -- unlike the KiCad/FreeCAD path fields below,
 * this takes effect immediately, no restart required. */
export async function setLlmProviderAndModel(
  provider: string,
  model: string | null,
  currentConfig: DaemonConfig,
): Promise<void> {
  await saveConfig({ ...currentConfig, llm_provider: provider, llm_model: model })
  const response = await dispatch('daemon.configure', { llm_provider: provider, llm_model: model })
  if (response.error) {
    throw new Error(response.error.message)
  }
}

/** SPEC-110: a real native directory picker, not a raw text field --
 * appropriate for "pick a folder" in a way a plain input isn't. Returns
 * `null` if the user cancels. */
export async function chooseStorageFolder(currentPath?: string | null): Promise<string | null> {
  const selected = await open({ directory: true, defaultPath: currentPath ?? undefined })
  if (Array.isArray(selected)) {
    return selected[0] ?? null
  }
  return selected
}

/** Quits and relaunches the app for real (`@tauri-apps/plugin-process`'s
 * `relaunch()`) -- so a restart-required Tier 2 save can actually be
 * applied with one click, not just described in a passive text notice a
 * user can ignore. */
export async function restartApp(): Promise<void> {
  await relaunch()
}

/** SPEC-110: a real native, harder-to-ignore modal (not more inline text)
 * warning that a storage-location change needs a restart to take effect
 * safely -- files saved between now and a restart still go to the *old*
 * location, and nothing moves automatically once the new one is live.
 * Returns true if the user chose to restart now. */
export async function confirmStorageLocationChange(): Promise<boolean> {
  return ask(
    'New files will be saved to the new location once you restart. Anything already saved stays ' +
      'at the old location and will not move automatically. Restart now to apply this safely?',
    { title: 'Storage location changed', kind: 'warning', okLabel: 'Restart Now', cancelLabel: 'Later' },
  )
}

/** The app's own version -- a compile-time Rust constant
 * (`core/tauri-rust`'s `get_app_version`), not read from disk at runtime. */
export async function getAppVersion(): Promise<string> {
  return invoke('get_app_version')
}

/** SPEC-303 Tier 3: bundles capability flags, the daemon's real log file
 * location, and relevant versions into plain text and copies it to the
 * clipboard -- the exact surface `SPEC-107` was built anticipating and
 * that nothing has consumed until now. KiCad's version is looked up only
 * when `kicad_available` is true, and failure there degrades to
 * "unreachable" rather than failing the whole bundle. */
export async function copyDiagnostics(): Promise<void> {
  const [capabilities, appVersion] = await Promise.all([getCapabilities(), getAppVersion()])

  let kicadVersion = 'not reachable'
  if (capabilities.kicad_available) {
    try {
      const response = await dispatch('kicad.get_version', {})
      const result = response.result as { full_version?: string } | undefined
      kicadVersion = response.error ? 'unreachable' : result?.full_version ?? 'unknown'
    } catch {
      kicadVersion = 'unreachable'
    }
  }

  const lines = [
    `Copperplane v${appVersion}`,
    `Python: ${capabilities.python_version}`,
    `Log file: ${capabilities.log_path ?? '(not available)'}`,
    `KiCad: ${kicadVersion}`,
    `FreeCAD: ${capabilities.freecad_available ? 'reachable' : 'not reachable'}`,
    `LLM providers configured: ${capabilities.llm_providers.join(', ') || '(none)'}`,
  ]

  await writeText(lines.join('\n'))
}
