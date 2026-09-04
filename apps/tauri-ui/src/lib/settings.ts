import { invoke } from '@tauri-apps/api/core'
import { writeText } from '@tauri-apps/plugin-clipboard-manager'
import { ask, open } from '@tauri-apps/plugin-dialog'
import { relaunch } from '@tauri-apps/plugin-process'
import { dispatch, submitJob } from './ipc'

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

/** Mirrors `services/python-daemon/llm_providers.py`'s `ProviderRecord`
 * (SPEC-208 §2.2.1) -- `kind` selects the SDK, never `id`. `"managed"` is
 * never a real `kind` value a client constructs; it never appears in
 * `getProviderRecords()`'s own response at all (SPEC-321 §2.4). */
export interface ProviderRecord {
  id: string
  kind: 'anthropic' | 'openai_compat' | 'google'
  base_url: string | null
  api_key_ref: string | null
  models: { reasoning?: string; fast?: string }
  capabilities: { tool_use: boolean; strict_json: boolean }
}

export type ModelRole = 'reasoning' | 'fast'

/** Mirrors `core/tauri-rust/src/config.rs`'s `DaemonConfig`. `output_dir`
 * and `storage_root` are deliberately omitted -- both are always
 * Rust-computed at spawn, never a real setting a human edits or reads
 * back from `config.json` (the real current `storage_root` is reported
 * via `DaemonCapabilities` instead). `storage_root_override` (SPEC-110)
 * is the one a human actually sets.
 *
 * `providers`/`provider_roles` (SPEC-321 §2.3): present on the struct
 * since `CTX-208.1`, but never round-tripped by this interface until now
 * -- a pure TypeScript typing gap, not a missing IPC command. */
export interface DaemonConfig {
  freecadcmd_path_override?: string | null
  /** CTX-336.1: where `kicad-cli` lives when it is not on PATH or in a
   *  standard install. The FreeCAD field above has existed since SPEC-303;
   *  this one did not, so SPEC-336's path picker had nothing to write to. */
  kicad_cli_path_override?: string | null
  /** CTX-336.1: first-run setup has been offered and dismissed. Not "the app
   *  is configured" -- that is `isFullyConfigured(capabilities)`, computed
   *  live. A user who finished the wizard and later uninstalled KiCad is not
   *  configured; one who skipped every step and already had both tools is. */
  onboarding_completed?: boolean | null
  kicad_socket_path?: string | null
  kicad_timeout_ms?: number | null
  llm_provider?: string | null
  llm_model?: string | null
  storage_root_override?: string | null
  providers?: ProviderRecord[] | null
  provider_roles?: Record<ModelRole, string> | null
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
  /** SPEC-309: whether `kicad-cli` was located. Returned by the daemon since
   *  SPEC-309 and never declared on this type until CTX-336.1 needed it --
   *  every board check, ERC/DRC run and schematic read goes through it. */
  kicad_cli_available: boolean
  /** CTX-336.1: the binary that was actually resolved, and how. "Found"
   *  cannot tell a user whether the KiCad they pointed at is the one in use,
   *  which is the only question a path picker leaves them with. */
  kicad_cli_path_checked: string | null
  kicad_cli_path_source: 'override' | 'path' | 'install' | 'none' | null
  kicad_cli_error: string | null
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
  /** SPEC-321 §2.5: every secret ref the real keychain currently has a
   * value for -- vendor presets and custom `providers[].api_key_ref`
   * names alike (`daemon.py`'s `_detect_capabilities`, sourced from the
   * same `CONFIG["secrets"]` `collect_known_secrets` already populates).
   * Lets the editor ask "is a key saved for this record" for any record,
   * not just the four fixed vendor names `llm_providers` above covers. */
  configured_secret_refs: string[]
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

/** SPEC-321 §2.4/§2.5: the resolved provider set (presets + whatever
 * `config.json` currently authors) for the editor to render --
 * `records` never includes `"managed"`, and `provider_roles` is always
 * the real, resolved binding (already run through the daemon's own
 * `migrate_legacy_config`, never an empty map on a pre-SPEC-208 install).
 * `provider_roles_saved` is false when that binding is only a migrated
 * projection, not yet a real, explicit save. */
export async function getProviderRecords(): Promise<{
  records: ProviderRecord[]
  provider_roles: Record<ModelRole, string>
  provider_roles_saved: boolean
}> {
  const response = await dispatch('llm.get_provider_records', {})
  if (response.error) {
    throw new Error(response.error.message)
  }
  return response.result as {
    records: ProviderRecord[]
    provider_roles: Record<ModelRole, string>
    provider_roles_saved: boolean
  }
}

/** SPEC-324 §2.1: the models a provider actually reports.
 *
 * `submitJob`, not `dispatch` -- this is a real network call to the vendor
 * and is ASYNC_ROUTES-registered for it. CTX-314.2 records the real bug
 * from getting that wrong: a sync route runs inline in the daemon's
 * request path, so a slow provider would block every other request.
 *
 * `supported: false` is a real answer, not an error -- an openai_compat
 * record may point at a server with no /v1/models at all. Callers show the
 * reason and keep the field typeable (SPEC-324 §2.2). */
export interface ModelListing {
  supported: boolean
  models: string[]
  reason: string | null
}

export async function listProviderModels(providerId: string): Promise<ModelListing> {
  const handle = await submitJob<ModelListing>('llm.list_models', { provider_id: providerId })
  return handle.result
}

/** SPEC-324 §2.3: an on-demand existence check. Never called on save or at
 * startup -- quota is a real cost even for a cheap check, and SPEC-107 §3
 * already holds that line for capability probes. */
export interface ModelValidation {
  valid: boolean
  reason: string
}

export async function validateProviderModel(
  providerId: string,
  model: string,
): Promise<ModelValidation> {
  const handle = await submitJob<ModelValidation>('llm.validate_model', {
    provider_id: providerId,
    model,
  })
  return handle.result
}

/** CTX-321.3: is an OpenAI-compatible server answering at a URL the user
 * has not saved yet? Takes a URL rather than a provider id because the
 * record being configured does not exist yet -- `llm.list_models` needs a
 * resolvable record and a new draft has none.
 *
 * `reachable: false` is the ordinary answer, not an error: most of the
 * time nothing is listening and the editor says nothing at all. */
export interface EndpointProbe {
  reachable: boolean
  models: string[]
  reason: string | null
}

/** The local endpoint the editor offers. Mirrors the daemon's own
 * `LOCAL_OLLAMA_BASE_URL`, which is the ollama preset's `base_url`. */
export const LOCAL_OLLAMA_BASE_URL = 'http://localhost:11434/v1'

export async function probeEndpoint(baseUrl: string): Promise<EndpointProbe> {
  const handle = await submitJob<EndpointProbe>('llm.probe_endpoint', { base_url: baseUrl })
  return handle.result
}

/** SPEC-321 §2.3: persists the complete current provider records and
 * role bindings to `config.json` (for the next restart) and pushes them
 * live to the running daemon via `daemon.configure`, same pattern as
 * `setLlmProviderAndModel` -- both `providers` and `provider_roles` are
 * always sent as a whole, never a partial delta (SPEC-208 §2.5's own
 * contract, applied here). */
export async function saveProviderConfig(
  providers: ProviderRecord[],
  providerRoles: Record<ModelRole, string>,
  currentConfig: DaemonConfig,
): Promise<void> {
  /* SPEC-209 §2.3: the daemon reduces each record to only what differs
     from its shipped preset and returns that; what gets written to
     config.json is the daemon's answer, not what was sent.
     
     The order matters and is the reverse of what it was. `daemon.configure`
     runs FIRST so its normalized result is what `saveConfig` persists.
     Computing the delta here instead would mean a second implementation of
     a rule whose whole job is to be the exact inverse of the daemon's
     merge -- two copies that can disagree about what "differs from the
     preset" means, which is the class of drift this repo keeps paying for.
     
     A daemon that returns no `providers` (an older build, mid-upgrade)
     falls back to persisting what was sent: the previous whole-record
     behaviour, which merge-on-read still resolves correctly. */
  const response = await dispatch('daemon.configure', { providers, provider_roles: providerRoles })
  if (response.error) {
    throw new Error(response.error.message)
  }
  const normalized = (response.result as { providers?: ProviderRecord[] } | undefined)?.providers
  await saveConfig({
    ...currentConfig,
    providers: normalized ?? providers,
    provider_roles: providerRoles,
  })
}

/** SPEC-208 §3 / SPEC-321 §2.5: the exact exfiltration risk both specs
 * name -- a record pairing a real `api_key_ref` with a `base_url` on some
 * other host sends that key wherever the host names. `null` (a preset's
 * own untouched default endpoint) is never a risk by construction. An
 * unparseable `base_url` fails toward "warn" rather than "trust it" --
 * the whole point of this check is not to silently miss a real risk. */
export function isNonLoopbackBaseUrl(base_url: string | null): boolean {
  if (!base_url) return false
  try {
    const hostname = new URL(base_url).hostname
    return hostname !== 'localhost' && hostname !== '127.0.0.1' && hostname !== '::1'
  } catch {
    return true
  }
}

/** SPEC-321 §3: removing a record a role is still bound to is a real,
 * reachable misconfiguration (`resolve()` raises a real `LLMProviderError`
 * at the next chat/extraction call, not a friendly message) -- this is
 * the "warn before letting a save proceed" the spec calls for, the same
 * harder-to-ignore native-modal treatment `confirmStorageLocationChange`
 * already established for a different real risk. Returns true if the
 * user chose to remove it anyway. */
export async function confirmRemoveRoleBoundProvider(
  recordId: string,
  boundRoles: ModelRole[],
): Promise<boolean> {
  return ask(
    `"${recordId}" is currently bound to the ${boundRoles.join(' and ')} role${
      boundRoles.length > 1 ? 's' : ''
    }. Removing it will leave that binding pointing at a provider that no longer exists, which fails ` +
      'the next chat or extraction that uses it. Remove it anyway?',
    { title: 'Provider still in use', kind: 'warning', okLabel: 'Remove Anyway', cancelLabel: 'Cancel' },
  )
}

/** CTX-336.1: read-modify-write against what is actually on disk.
 *
 *  Every other config writer takes a `currentConfig` snapshot and saves the
 *  whole object over it. That is a last-write-wins clobber whenever two
 *  surfaces hold snapshots taken at different moments, and it cost a real
 *  defect: guided setup bound both model roles to the provider the user
 *  chose, and then finishing the wizard wrote `App`'s launch-time snapshot
 *  back with `onboarding_completed` added -- silently restoring the provider
 *  that was bound before. The user picked Anthropic, entered an Anthropic
 *  key, and ended with Google still answering. Nothing failed, and nothing
 *  said so.
 *
 *  A patch applied to a freshly-read config cannot do that: it can only
 *  overwrite the keys it actually names. */
export async function updateConfig(patch: Partial<DaemonConfig>): Promise<DaemonConfig> {
  const latest = await getConfig()
  const next = { ...latest, ...patch }
  await saveConfig(next)
  return next
}

/** CTX-336.1: binds BOTH model roles to one provider, for guided setup.
 *
 *  `setLlmProviderAndModel` above writes the legacy `llm_provider`/`llm_model`
 *  pair, and `llm_providers.py`'s `_migrate_provider_roles` only consults
 *  those when `provider_roles` is *unset*: an existing map wins and the legacy
 *  field is ignored. So on a fresh install the legacy write happens to work,
 *  and after any Settings save that persisted `provider_roles` it silently
 *  would not -- guided setup would report success and change nothing about
 *  which provider actually answers.
 *
 *  Binding both roles is also exactly what an unconfigured install already
 *  resolves to (`llm_providers.py:473`), so this makes the existing default
 *  explicit rather than inventing a policy. */
export async function bindBothRolesTo(providerId: string): Promise<void> {
  const provider_roles = { reasoning: providerId, fast: providerId } as Record<ModelRole, string>
  const response = await dispatch('daemon.configure', {
    provider_roles,
    llm_provider: providerId,
  })
  if (response.error) {
    throw new Error(response.error.message)
  }
  await updateConfig({ provider_roles, llm_provider: providerId })
}

/** CTX-336.1: applies a tool path to the RUNNING daemon and persists it.
 *
 *  `saveConfig` alone would only take effect at the next spawn -- see its own
 *  docstring. SPEC-336's guided setup fixes a missing tool and then shows the
 *  user the result, so `daemon.configure` goes first and the write follows.
 *
 *  Pass `null` to clear an override. The route distinguishes "leave unchanged"
 *  (field absent) from "clear" (empty string), so this sends the empty string
 *  deliberately rather than omitting the field. */
export async function setToolPath(
  tool: 'kicad' | 'freecad',
  path: string | null,
): Promise<void> {
  const field = tool === 'kicad' ? 'kicad_cli_path_override' : 'freecadcmd_path_override'
  const response = await dispatch('daemon.configure', { [field]: path ?? '' })
  if (response.error) {
    throw new Error(response.error.message)
  }
  await updateConfig({ [field]: path })
}

/** CTX-336.1: a native picker for an executable, not a folder. SPEC-336's
 *  step 5 asks the user to point at `kicad-cli` or `freecadcmd` themselves,
 *  and a text field for an absolute path to a binary inside a .app bundle is
 *  not a reasonable thing to ask anyone to type. */
export async function chooseToolExecutable(currentPath?: string | null): Promise<string | null> {
  const selected = await open({ directory: false, multiple: false, defaultPath: currentPath ?? undefined })
  if (Array.isArray(selected)) {
    return selected[0] ?? null
  }
  return selected
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
export interface ProjectsInRoot {
  root: string
  projects: string[]
  count: number
}

/** CTX-110.2: what projects a storage root holds, without switching to it. */
export async function listProjectsInRoot(root: string): Promise<ProjectsInRoot> {
  const handle = await submitJob<ProjectsInRoot>('project.list_in_root', { root })
  return handle.result
}

/** The sentence the old warning could not say.
 *
 *  It used to read: "New files will be saved to the new location once you
 *  restart. Anything already saved stays at the old location and will not move
 *  automatically." Every clause is true, and it still failed — because it
 *  describes FILES, and a user's model is a LIST OF PROJECTS. The maintainer
 *  changed his storage location, lost sight of two projects, and asked how
 *  projects are found at all.
 *
 *  There is no project registry: a project is listed if and only if a folder
 *  holding `project.json` sits in `<storage_root>/projects/`. So changing the
 *  root replaces the entire list, and the only warning that could have stopped
 *  him is one that names the projects about to disappear. */
export function storageChangeMessage(leaving: ProjectsInRoot, arriving: ProjectsInRoot): string {
  const name = (list: string[]) =>
    list.length <= 3 ? list.join(', ') : `${list.slice(0, 3).join(', ')} and ${list.length - 3} more`

  const lines: string[] = []

  if (leaving.count > 0) {
    lines.push(
      `${leaving.count === 1 ? 'This project is' : `These ${leaving.count} projects are`} ` +
        `stored in ${leaving.root} and will no longer appear in Copperplane: ` +
        `${name(leaving.projects)}.`,
    )
  }

  lines.push(
    arriving.count > 0
      ? `${arriving.root} already holds ${arriving.count} ` +
        `${arriving.count === 1 ? 'project' : 'projects'}: ${name(arriving.projects)}. ` +
        `Those are what you will see instead.`
      : 'The new location holds no projects yet, so your project list will start empty.',
  )

  // Said last and said plainly: the word a user brings to this is "lost".
  lines.push(
    'Nothing is deleted. Every file stays exactly where it is, and pointing Copperplane back at ' +
      'the old folder brings those projects back.',
  )

  return lines.join('\n\n')
}

export async function confirmStorageLocationChange(
  leaving?: ProjectsInRoot,
  arriving?: ProjectsInRoot,
): Promise<boolean> {
  const detail =
    leaving && arriving
      ? `${storageChangeMessage(leaving, arriving)}\n\nRestart now to apply this?`
      : // No counts available (the probe failed): the original wording, which
        // is honest, rather than a confident claim about projects we could not
        // actually look at.
        'New files will be saved to the new location once you restart. Anything already saved ' +
        'stays at the old location and will not move automatically. Restart now to apply this ' +
        'safely?'
  return ask(detail, {
    title: 'Storage location changed',
    kind: 'warning',
    okLabel: 'Restart Now',
    cancelLabel: 'Later',
  })
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

  /* CTX-107.2 (issue #249): FreeCAD's real version, fetched the same way
     and in the same place as KiCad's just above -- on demand, only when a
     human asks for diagnostics. Deliberately not part of the capability
     probe: SPEC-107 §3 requires that to stay cheap and non-blocking, and
     names a long `freecadcmd` call as the thing that would starve the
     heartbeat. `freecad.get_version` is async-registered, so it goes
     through submitJob rather than dispatch -- the one shape difference
     from the KiCad path above. */
  let freecadVersion = 'not reachable'
  if (capabilities.freecad_available) {
    try {
      const handle = await submitJob<{ version: string | null; reason: string | null }>(
        'freecad.get_version',
        {},
      )
      freecadVersion = (await handle.result).version ?? 'unknown'
    } catch {
      freecadVersion = 'unknown'
    }
  }

  const lines = [
    `Copperplane v${appVersion}`,
    `Python: ${capabilities.python_version}`,
    `Log file: ${capabilities.log_path ?? '(not available)'}`,
    `KiCad: ${kicadVersion}`,
    `FreeCAD: ${freecadVersion}`,
    `LLM providers configured: ${capabilities.llm_providers.join(', ') || '(none)'}`,
  ]

  await writeText(lines.join('\n'))
}

/** SPEC-333: the confirmation for removing a project from the list.
 *
 *  Says plainly that nothing is deleted. The word a user brings to this is
 *  "delete", and being wrong in either direction costs something: believing
 *  files are gone costs trust, believing they are safe when they are not costs
 *  work. */
export async function confirmRemoveProject(name: string): Promise<boolean> {
  return ask(
    `Remove "${name}" from your project list?\n\nNothing is deleted. Its files, its board and ` +
      'anything you exported stay exactly where they are, and you can put it back from the ' +
      'projects screen.',
    { title: 'Remove from list', kind: 'warning', okLabel: 'Remove', cancelLabel: 'Cancel' },
  )
}
