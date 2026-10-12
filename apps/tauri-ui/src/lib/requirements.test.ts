import { describe, expect, it } from 'vitest'

import { missingRequirements } from './requirements'
import type { DaemonCapabilities } from './settings'

const BASE = {
  kicad_available: true,
  kicad_socket_path_checked: null,
  freecad_available: true,
  freecad_path_checked: '/usr/bin/freecadcmd',
  freecad_error: null,
  kicad_cli_available: true,
  kicad_cli_path_checked: '/usr/bin/kicad-cli',
  kicad_cli_path_source: 'path',
  kicad_cli_error: null,
  llm_providers: [],
  log_path: null,
  python_version: '3.11.9',
  storage_root: '/data',
  github_token_configured: false,
  configured_secret_refs: [],
} as unknown as DaemonCapabilities

const providerMissing = (caps: DaemonCapabilities) =>
  missingRequirements(caps).some((m) => m.id === 'provider')

/** SPEC-213 §2.4: an install on Ollama has no keys, and was told it had no
 *  AI provider. */
describe('missingRequirements: the AI provider', () => {
  it('counts a local model the daemon reports ready', () => {
    expect(providerMissing({ ...BASE, llm_ready: true })).toBe(false)
  })

  it('believes llm_ready over a saved key it does not use', () => {
    expect(providerMissing({ ...BASE, llm_providers: ['openai'], llm_ready: false })).toBe(true)
  })

  it('falls back to counting keys for a daemon without llm_ready', () => {
    expect(providerMissing(BASE)).toBe(true)
    expect(providerMissing({ ...BASE, llm_providers: ['anthropic'] })).toBe(false)
  })
})
