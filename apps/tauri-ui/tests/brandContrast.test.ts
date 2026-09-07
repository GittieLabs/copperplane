import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/** SPEC-338: the brand green has to be the brand's green, and it has to be
 *  legible in every theme.
 *
 *  `themeTokens.test.ts` guards that a colour class a component uses is
 *  *defined*. It cannot tell whether the definition is readable: an accent
 *  and a foreground can both exist and still be the same colour, which is
 *  exactly the shipped defect it was written after (CTX-336.1, Deviation 9 --
 *  a button that rendered black on black in light and white on white in
 *  dark). Nobody writes a test that says "4.5:1", so nobody catches the pair
 *  that fails it.
 *
 *  This computes the real WCAG 2.1 ratio from the values in index.css, for
 *  every theme block, and separately checks the greens are the ones
 *  brand/README.md actually specifies rather than something close to them. */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const CSS = fs.readFileSync(path.join(HERE, '..', 'src', 'index.css'), 'utf8')
const BRAND_README = path.join(HERE, '..', '..', '..', 'brand', 'README.md')

/** Relative luminance, WCAG 2.1 §relative-luminance. */
function luminance(hex: string): number {
  const channel = (v: number) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
  const [r, g, b] = [1, 3, 5].map((i) => channel(parseInt(hex.slice(i, i + 2), 16) / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** The text of one declaration block, found by its selector and matched on
 *  braces so a nested block does not truncate it. */
function block(selector: string): string {
  // Anchored on the selector followed by its opening brace, not a bare
  // substring search: this file's own header comment names
  // `:root[data-theme="light"]` in prose, and matching that instead sent
  // every lookup to the first block in the file. Caught by the one test
  // here that compares two blocks against each other.
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const start = CSS.search(new RegExp(`^[ \\t]*${escaped}\\s*\\{`, 'm'))
  if (start === -1) throw new Error(`index.css has no ${selector} block`)
  let depth = 0
  for (let i = CSS.indexOf('{', start); i < CSS.length; i++) {
    if (CSS[i] === '{') depth++
    else if (CSS[i] === '}' && --depth === 0) return CSS.slice(start, i)
  }
  throw new Error(`${selector} block never closes`)
}

function token(text: string, name: string): string {
  const match = text.match(new RegExp(`--color-${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!match) throw new Error(`no --color-${name} in that block`)
  return match[1].toLowerCase()
}

/** Every theme the app can actually be in. The middle one is System mode
 *  with a light OS setting, which is the default a new user arrives in. */
const THEMES = [
  { name: 'dark (default)', selector: '@theme' },
  { name: 'light (system)', selector: ':root:not([data-theme="dark"])' },
  { name: 'light (chosen)', selector: ':root[data-theme="light"]' },
]

describe('brand colour', () => {
  it.each(THEMES)('$name: accent text is legible on the accent fill', ({ selector }) => {
    const text = block(selector)
    const ratio = contrast(token(text, 'accent'), token(text, 'accent-fg'))

    // 4.5:1 is WCAG AA for normal text. Button labels are normal text.
    expect(ratio).toBeGreaterThanOrEqual(4.5)
  })

  it.each(THEMES)('$name: the brand colour is legible on the base surface', ({ selector }) => {
    const text = block(selector)
    const ratio = contrast(token(text, 'brand'), token(text, 'base'))

    expect(ratio).toBeGreaterThanOrEqual(4.5)
  })

  it.each(THEMES)('$name: every theme defines all three brand tokens', ({ selector }) => {
    const text = block(selector)

    // A token missing from one block is the CTX-336.1 failure exactly: it
    // falls back to whatever it inherits, in one theme only.
    expect(() => [token(text, 'accent'), token(text, 'accent-fg'), token(text, 'brand')]).not.toThrow()
  })

  it('the greens are the ones the brand kit specifies, not merely similar', () => {
    // Read from brand/README.md rather than restated here, so regenerating
    // the kit with a different palette fails this instead of drifting.
    const palette = new Set(
      [...fs.readFileSync(BRAND_README, 'utf8').matchAll(/`(#[0-9A-Fa-f]{6})`/g)].map((m) =>
        m[1].toLowerCase(),
      ),
    )
    expect(palette.size).toBeGreaterThan(3)

    for (const { name, selector } of THEMES) {
      const text = block(selector)
      expect(palette, `${name}: --color-brand is not a brand palette colour`).toContain(
        token(text, 'brand'),
      )
      expect(palette, `${name}: --color-accent is not a brand palette colour`).toContain(
        token(text, 'accent'),
      )
    }
  })

  it('dark and light do not use the same green', () => {
    // The whole reason there are two: Copperplane green scores 3.39:1 on the
    // app's dark ground and Bright scores 2.27:1 on white. A single token
    // would have to fail one of them.
    expect(token(block('@theme'), 'brand')).not.toEqual(
      token(block(':root[data-theme="light"]'), 'brand'),
    )
  })
})
