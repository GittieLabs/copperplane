import { useCallback, useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

/** Must match the key read by the FOUC-prevention script in apps/tauri-ui/index.html. */
const STORAGE_KEY = 'theme-preference'
const VALID_PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system']

export function getStoredTheme(): ThemePreference {
  const raw = localStorage.getItem(STORAGE_KEY)
  return (VALID_PREFERENCES as readonly string[]).includes(raw ?? '')
    ? (raw as ThemePreference)
    : 'system'
}

export function getSystemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Sets/clears the `data-theme` attribute index.css's `:root[data-theme=...]`
 * blocks key off of. `'system'` clears the attribute entirely so the CSS
 * `prefers-color-scheme` media query -- not JS -- drives the live result;
 * that media query updates automatically on an OS appearance change with no
 * listener needed here. */
export function applyTheme(preference: ThemePreference): void {
  const root = document.documentElement
  if (preference === 'system') {
    root.removeAttribute('data-theme')
  } else {
    root.setAttribute('data-theme', preference)
  }
}

/** Persists the choice and applies it to the DOM in one call, independent of
 * any component's React state -- so it stays correct regardless of how many
 * places call it. */
export function setThemePreference(preference: ThemePreference): void {
  localStorage.setItem(STORAGE_KEY, preference)
  applyTheme(preference)
}

/** Settings' own Appearance control: local UI state for the selected
 * preference, plus the live-resolved OS theme (only meaningful, and only
 * displayed, when `preference === 'system'`) so a user picking System can
 * see what it currently resolves to. */
export function useThemePreference(): {
  preference: ThemePreference
  resolvedTheme: ResolvedTheme
  setPreference: (preference: ThemePreference) => void
} {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => getStoredTheme())
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => getSystemTheme())

  useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => setSystemTheme(mql.matches ? 'dark' : 'light')
    mql.addEventListener('change', handleChange)
    return () => mql.removeEventListener('change', handleChange)
  }, [])

  const setPreference = useCallback((next: ThemePreference) => {
    setThemePreference(next)
    setPreferenceState(next)
  }, [])

  return {
    preference,
    resolvedTheme: preference === 'system' ? systemTheme : preference,
    setPreference,
  }
}
