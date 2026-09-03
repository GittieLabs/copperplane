import { open } from '@tauri-apps/plugin-shell'

/** SPEC-336: the links onboarding needs, and nothing invented.
 *
 *  §3 is blunt about the constraint: *"The docs site does not exist ... a link
 *  that 404s on first run is worse than no link."* Settled with the
 *  maintainer on 2026-09-03: **link to each provider's own documentation.**
 *  No Copperplane docs site is assumed or referenced.
 *
 *  Each URL below is a provider's own published console or documentation entry
 *  point — the page a user lands on to create a key. They are listed here, in
 *  one place, rather than inline in a component, so there is exactly one thing
 *  to correct if a vendor moves a page. */
export const GITHUB_REPO_URL = 'https://github.com/GittieLabs/copperplane'

/** Where a user gets an API key, per provider. Keys match
 *  `KEY_BASED_PROVIDERS` in `settings.ts`. */
export const PROVIDER_KEY_DOCS: Record<string, { label: string; url: string }> = {
  anthropic: { label: "Anthropic Console", url: 'https://console.anthropic.com/settings/keys' },
  openai: { label: 'OpenAI API keys', url: 'https://platform.openai.com/api-keys' },
  google: { label: 'Google AI Studio', url: 'https://aistudio.google.com/apikey' },
  perplexity: { label: 'Perplexity API settings', url: 'https://www.perplexity.ai/settings/api' },
}

/** Where a user gets the tools. Both are hard requirements. */
export const TOOL_DOWNLOADS: Record<'kicad' | 'freecad', { label: string; url: string }> = {
  kicad: { label: 'KiCad downloads', url: 'https://www.kicad.org/download/' },
  freecad: { label: 'FreeCAD downloads', url: 'https://www.freecad.org/downloads.php' },
}

/** Opens a URL in the user's own browser. Never in an app window: a login or
 *  a key-creation page belongs in the browser the user already trusts, with
 *  their own password manager and their own session. */
export async function openExternal(url: string): Promise<void> {
  await open(url)
}
