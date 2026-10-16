import { useState } from 'react'

import { OLLAMA_DOWNLOAD, PROVIDER_KEY_DOCS, TOOL_DOWNLOADS, openExternal } from '../lib/externalLinks'
import { missingRequirements } from '../lib/requirements'
import {
  KEY_BASED_PROVIDERS,
  LOCAL_OLLAMA_BASE_URL,
  chooseToolExecutable,
  copyText,
  getCapabilities,
  getProviderRecords,
  probeEndpoint,
  saveSecret,
  secretKeyFor,
  bindBothRolesTo,
  setToolPath,
  type DaemonCapabilities,
  type KeyBasedProvider,
} from '../lib/settings'

/** SPEC-336 steps 4-5: pick a provider, paste a key, confirm the tools.
 *
 *  Two rules from the spec shape every control here.
 *
 *  **Nothing blocks.** *"Every step is skippable, and the wizard never blocks
 *  entry."* The maintainer's reasoning is decisive on consistency alone: the
 *  manual path never gated anyone, so gating the guided path "would punish
 *  precisely the user who asked for help, and would make 'guided' the more
 *  restrictive choice — the opposite of what it is for."
 *
 *  **Guided means fewer decisions, not fewer capabilities.** Settled with the
 *  maintainer: the pre-selected provider is `anthropic`, which is also
 *  `llm_providers.py`'s own `_DEFAULT_PROVIDER`, so this introduces no second
 *  opinion. Both model roles bind to the chosen provider, exactly as an
 *  unconfigured install already resolves them. */
type Step = 'provider' | 'tools' | 'done'

/** SPEC-213 §2.4: Ollama sits beside the key-based providers. It needs no
 *  key, so choosing it swaps the key field for a check of the local server. */
type SetupProvider = KeyBasedProvider | 'ollama'

const PROVIDER_LABELS: Record<SetupProvider, string> = {
  anthropic: 'Anthropic (Claude)',
  openai: 'OpenAI',
  google: 'Google (Gemini)',
  perplexity: 'Perplexity',
  ollama: 'Ollama — a model on this computer, no key',
}

/** What the local check found. `model` is the Ollama record's own reasoning
 *  model, read from the daemon rather than repeated here, so a release that
 *  moves the default cannot leave this screen asking for the old one. */
type LocalCheck =
  | { state: 'checking' }
  | { state: 'not-running'; reason: string | null }
  | { state: 'no-model'; model: string }
  | { state: 'ready'; model: string }

/** Ollama lists a model by the tag it was pulled with; an untagged name is
 *  stored as `:latest`. */
function hasModel(models: string[], wanted: string): boolean {
  const full = wanted.includes(':') ? wanted : `${wanted}:latest`
  return models.some((m) => m === wanted || m === full)
}

export function GuidedSetup({
  capabilities,
  startAt = 'provider',
  onCapabilitiesChanged,
  onFinish,
  onOpenManualSettings,
}: {
  capabilities: DaemonCapabilities | null
  /** Which step to open on. The banner routes a specific missing thing
   *  straight to the step that fixes it rather than restarting the wizard. */
  startAt?: 'provider' | 'tools'
  onCapabilitiesChanged: (caps: DaemonCapabilities) => void
  onFinish: () => void
  onOpenManualSettings: () => void
}) {
  const [step, setStep] = useState<Step>(startAt)
  const [provider, setProvider] = useState<SetupProvider>('anthropic')
  const [local, setLocal] = useState<LocalCheck>({ state: 'checking' })
  const [savedLocal, setSavedLocal] = useState(false)
  const [copied, setCopied] = useState(false)
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function refreshCapabilities() {
    const caps = await getCapabilities()
    onCapabilitiesChanged(caps)
    return caps
  }

  async function checkLocal() {
    setLocal({ state: 'checking' })
    setCopied(false)
    try {
      const [probe, { records }] = await Promise.all([
        probeEndpoint(LOCAL_OLLAMA_BASE_URL),
        getProviderRecords(),
      ])
      const model = records.find((r) => r.id === 'ollama')?.models.reasoning ?? 'qwen2.5:7b'
      if (!probe.reachable) {
        setLocal({ state: 'not-running', reason: probe.reason })
      } else {
        setLocal({ state: hasModel(probe.models, model) ? 'ready' : 'no-model', model })
      }
    } catch (err) {
      setLocal({ state: 'not-running', reason: err instanceof Error ? err.message : String(err) })
    }
  }

  async function handleUseOllama() {
    setBusy(true)
    setError(null)
    try {
      await bindBothRolesTo('ollama')
      setSavedLocal(true)
      await refreshCapabilities()
      setStep('tools')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveKey() {
    if (provider === 'ollama') return
    const trimmed = key.trim()
    if (!trimmed) return
    setBusy(true)
    setError(null)
    try {
      await saveSecret(secretKeyFor(provider), trimmed)
      // Both roles, explicitly. `setLlmProviderAndModel` writes only the
      // legacy `llm_provider`, which `_migrate_provider_roles` ignores once a
      // `provider_roles` map exists -- so after any Settings save, guided
      // setup would have reported success and changed nothing.
      await bindBothRolesTo(provider)
      setKey('')
      setSaved(true)
      await refreshCapabilities()
      setStep('tools')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handlePickToolPath(tool: 'kicad' | 'freecad') {
    setBusy(true)
    setError(null)
    try {
      const picked = await chooseToolExecutable()
      if (picked === null) return
      // Applied to the running daemon, not only written to config.json --
      // CTX-336.1 Phase 1's whole point. Without that, this button would
      // appear to do nothing until the next launch.
      await setToolPath(tool, picked)
      await refreshCapabilities()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const missing = missingRequirements(capabilities)
  const providerMissing = missing.some((m) => m.id === 'provider')

  return (
    <div className="flex h-full flex-col items-start gap-5 overflow-y-auto p-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-medium text-fg-bright">Setting up Copperplane</h1>
        <p className="text-xs text-fg-muted">
          {step === 'provider' ? 'Step 1 of 2 — an AI provider' : 'Step 2 of 2 — KiCad and FreeCAD'}
        </p>
      </div>

      {error && <p className="text-xs text-danger">{error}</p>}

      {step === 'provider' && (
        <div className="flex w-full max-w-xl flex-col gap-3 text-xs">
          {!providerMissing && capabilities && (
            <p className="text-fg-secondary">
              A provider is already configured ({capabilities.llm_providers.join(', ')}). You can
              add another, or move on.
            </p>
          )}
          <p className="text-fg-secondary">
            Copperplane needs an AI model to explain checks, look up parts and answer questions
            about your project. Either add an API key &mdash; you pay the provider directly, and the
            key is stored in your machine&rsquo;s keychain and never sent anywhere else &mdash; or run
            a model on this computer with Ollama, for free.
          </p>

          <label className="flex flex-col gap-1">
            <span className="text-fg-muted">Provider</span>
            <select
              className="w-full rounded border border-line bg-surface px-2 py-1 text-fg"
              value={provider}
              onChange={(e) => {
                const next = e.target.value as SetupProvider
                setProvider(next)
                if (next === 'ollama') void checkLocal()
              }}
            >
              {[...KEY_BASED_PROVIDERS, 'ollama' as const].map((p) => (
                <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>
              ))}
            </select>
          </label>

          {provider === 'ollama' && (
            <div className="flex flex-col gap-2 rounded border border-line p-3" data-testid="local-model">
              <p className="text-fg-secondary">
                A local model explains checks, reviews your board and answers chat. Looking up a new
                part still needs an API key: local models get part packages wrong often enough to
                put the wrong footprint on a board.
              </p>
              {local.state === 'checking' && <p className="text-fg-muted">Checking for Ollama…</p>}
              {local.state === 'not-running' && (
                <>
                  <p className="text-warning">Ollama is not running on this computer.</p>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      className="text-fg-secondary underline decoration-dotted underline-offset-2 hover:text-fg-bright"
                      onClick={() => void openExternal(OLLAMA_DOWNLOAD.url)}
                    >
                      Download Ollama
                    </button>
                    <button
                      type="button"
                      className="text-fg-muted hover:text-fg-secondary"
                      onClick={() => void checkLocal()}
                    >
                      Check again
                    </button>
                  </div>
                </>
              )}
              {local.state === 'no-model' && (
                <>
                  <p className="text-fg-secondary">
                    Ollama is running, but <code>{local.model}</code> is not on this computer yet.
                    Run this in a terminal. It downloads about 5 GB, and the model needs about 5 GB
                    of free memory while it answers.
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <code className="rounded bg-surface-alt px-2 py-1 text-fg">ollama pull {local.model}</code>
                    <button
                      type="button"
                      className="text-fg-secondary underline decoration-dotted underline-offset-2 hover:text-fg-bright"
                      onClick={() => void copyText(`ollama pull ${local.model}`).then(() => setCopied(true))}
                    >
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                    <button
                      type="button"
                      className="text-fg-muted hover:text-fg-secondary"
                      onClick={() => void checkLocal()}
                    >
                      Check again
                    </button>
                  </div>
                </>
              )}
              {local.state === 'ready' && (
                <p className="text-success">
                  Ollama is running and <code>{local.model}</code> is ready.
                </p>
              )}
            </div>
          )}

          {provider !== 'ollama' && (<>
          <label className="flex flex-col gap-1">
            <span className="text-fg-muted">API key</span>
            <input
              type="password"
              className="w-full rounded border border-line bg-surface px-2 py-1 text-fg"
              placeholder="Paste the key here"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
          </label>

          <button
            type="button"
            className="self-start text-fg-secondary underline decoration-dotted underline-offset-2 hover:text-fg-bright"
            onClick={() => void openExternal(PROVIDER_KEY_DOCS[provider].url)}
          >
            Where do I get a key? — {PROVIDER_KEY_DOCS[provider].label}
          </button>
          </>)}

          <div className="mt-1 flex flex-wrap items-center gap-3">
            {provider === 'ollama' ? (
              <button
                type="button"
                className="rounded bg-accent px-3 py-1.5 font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
                disabled={busy || local.state !== 'ready'}
                onClick={() => void handleUseOllama()}
              >
                {busy ? 'Saving…' : 'Use Ollama and continue'}
              </button>
            ) : (
              <button
                type="button"
                className="rounded bg-accent px-3 py-1.5 font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
                disabled={busy || !key.trim()}
                onClick={() => void handleSaveKey()}
              >
                {busy ? 'Saving…' : 'Save key and continue'}
              </button>
            )}
            {/* Skipping forward, not out. A user unsure about a key can still
                see the tool check, which costs them nothing. */}
            <button
              type="button"
              className="text-fg-muted underline decoration-dotted underline-offset-2 hover:text-fg-secondary"
              onClick={() => setStep('tools')}
            >
              Skip this step
            </button>
            <button
              type="button"
              className="text-fg-muted hover:text-fg-secondary"
              onClick={onOpenManualSettings}
            >
              Open full settings instead
            </button>
          </div>
        </div>
      )}

      {step === 'tools' && (
        <div className="flex w-full max-w-xl flex-col gap-4 text-xs">
          {(saved || savedLocal) && (
            <p className="text-fg-secondary">
              {savedLocal ? 'Ollama is set up.' : 'Key saved.'} Now the two tools Copperplane drives.
            </p>
          )}

          {(['kicad', 'freecad'] as const).map((tool) => {
            const found = tool === 'kicad'
              ? capabilities?.kicad_cli_available
              : capabilities?.freecad_available
            const where = tool === 'kicad'
              ? capabilities?.kicad_cli_path_checked
              : capabilities?.freecad_path_checked
            const label = tool === 'kicad' ? 'KiCad' : 'FreeCAD'

            return (
              <div key={tool} className="flex flex-col gap-1 rounded border border-line p-3">
                <p className="text-sm font-medium text-fg-bright">
                  {label}{' '}
                  <span className={found ? 'text-success' : 'text-warning'}>
                    {found ? '— found' : '— not found'}
                  </span>
                </p>
                {found && where && (
                  <p className="break-all text-fg-muted">{where}</p>
                )}
                {!found && (
                  <>
                    <p className="text-fg-secondary">
                      {tool === 'kicad'
                        ? 'Without it, checks and component lists cannot run.'
                        : 'Without it, enclosures cannot be generated.'}
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        className="rounded border border-line px-2 py-1 text-fg-secondary hover:bg-surface-alt disabled:opacity-50"
                        disabled={busy}
                        onClick={() => void handlePickToolPath(tool)}
                      >
                        I have it — point to it
                      </button>
                      <button
                        type="button"
                        className="text-fg-secondary underline decoration-dotted underline-offset-2 hover:text-fg-bright"
                        onClick={() => void openExternal(TOOL_DOWNLOADS[tool].url)}
                      >
                        Download {label}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })}

          <button
            type="button"
            className="self-start text-fg-muted hover:text-fg-secondary"
            disabled={busy}
            onClick={() => void refreshCapabilities()}
          >
            Check again
          </button>

          <div className="mt-1 flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="rounded bg-accent px-3 py-1.5 font-medium text-accent-fg hover:opacity-90"
              onClick={onFinish}
            >
              {missing.length === 0 ? 'Done' : 'Continue anyway'}
            </button>
            <button
              type="button"
              className="text-fg-muted hover:text-fg-secondary"
              onClick={() => setStep('provider')}
            >
              Back
            </button>
          </div>
          {missing.length > 0 && (
            <p className="text-fg-muted">
              You can carry on without these. Copperplane will keep a note of what is missing and
              how to fix it, and you can come back here at any time.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
