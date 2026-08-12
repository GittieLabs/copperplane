import { invoke } from '@tauri-apps/api/core'
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
 * is deliberately omitted -- it's always Rust-computed at spawn, never a
 * real setting a human edits. */
export interface DaemonConfig {
  freecadcmd_path_override?: string | null
  kicad_socket_path?: string | null
  kicad_timeout_ms?: number | null
  llm_provider?: string | null
  llm_model?: string | null
}

/** Mirrors `daemon.py`'s `_detect_capabilities()` shape. */
export interface DaemonCapabilities {
  kicad_available: boolean
  freecad_available: boolean
  llm_providers: string[]
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
