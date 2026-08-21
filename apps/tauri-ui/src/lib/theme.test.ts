import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** jsdom doesn't implement `matchMedia` at all -- every test installs a
 * controllable fake so `getSystemTheme`/`useThemePreference` have something
 * real to query, and so a test can simulate an OS appearance change via
 * `emitChange`. */
function installMatchMediaMock(initialMatches: boolean) {
  let matches = initialMatches
  const listeners = new Set<() => void>()
  const mql = {
    get matches() {
      return matches
    },
    addEventListener: (_event: string, listener: () => void) => {
      listeners.add(listener)
    },
    removeEventListener: (_event: string, listener: () => void) => {
      listeners.delete(listener)
    },
  }
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => mql),
  )
  return {
    emitChange: (nextMatches: boolean) => {
      matches = nextMatches
      listeners.forEach((listener) => listener())
    },
  }
}

const { getStoredTheme, getSystemTheme, applyTheme, setThemePreference, useThemePreference } =
  await import('./theme')

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('getStoredTheme', () => {
  it('defaults to system when nothing is stored', () => {
    expect(getStoredTheme()).toBe('system')
  })

  it('returns a validly stored preference', () => {
    localStorage.setItem('theme-preference', 'light')
    expect(getStoredTheme()).toBe('light')
  })

  it('falls back to system for a garbage stored value', () => {
    localStorage.setItem('theme-preference', 'solarized')
    expect(getStoredTheme()).toBe('system')
  })
})

describe('getSystemTheme', () => {
  it('reads the OS preference via matchMedia', () => {
    installMatchMediaMock(true)
    expect(getSystemTheme()).toBe('dark')

    installMatchMediaMock(false)
    expect(getSystemTheme()).toBe('light')
  })
})

describe('applyTheme', () => {
  it('sets data-theme for an explicit light/dark choice', () => {
    applyTheme('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    applyTheme('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('clears data-theme for system, leaving the CSS media query in control', () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    applyTheme('system')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
})

describe('setThemePreference', () => {
  it('persists to localStorage and applies to the DOM in one call', () => {
    setThemePreference('light')
    expect(localStorage.getItem('theme-preference')).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
})

describe('useThemePreference', () => {
  it('initializes from the stored preference and the live system theme', () => {
    installMatchMediaMock(true)
    localStorage.setItem('theme-preference', 'system')

    const { result } = renderHook(() => useThemePreference())

    expect(result.current.preference).toBe('system')
    expect(result.current.resolvedTheme).toBe('dark')
  })

  it('setPreference persists, applies, and updates resolvedTheme immediately for an explicit choice', () => {
    installMatchMediaMock(true)
    const { result } = renderHook(() => useThemePreference())

    act(() => result.current.setPreference('light'))

    expect(result.current.preference).toBe('light')
    expect(result.current.resolvedTheme).toBe('light')
    expect(localStorage.getItem('theme-preference')).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('resolvedTheme tracks a live OS appearance change while on System', () => {
    const mock = installMatchMediaMock(false)
    const { result } = renderHook(() => useThemePreference())

    expect(result.current.resolvedTheme).toBe('light')

    act(() => mock.emitChange(true))

    expect(result.current.resolvedTheme).toBe('dark')
  })
})
