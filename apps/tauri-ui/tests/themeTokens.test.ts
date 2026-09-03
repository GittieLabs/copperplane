import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/** CTX-336.1: no component may use a colour class the theme does not define.
 *
 *  Written after the first click-through of SPEC-336's welcome screen found
 *  the primary button unreadable: `text-on-accent` is not a token, so the
 *  label fell back to the inherited `text-fg` — black on a black button in
 *  light mode, white on white in dark. Tailwind emits nothing for an unknown
 *  utility and reports no error, `tsc` cannot see inside a className string,
 *  and 728 passing tests never look at a colour. Nothing in the suite could
 *  have caught it, which is precisely why this exists.
 *
 *  It lives outside `src/` for the same reason as the glossary corpus test:
 *  it reads the filesystem, which browser-side code never does. */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')

/** Utilities whose colour comes from Tailwind's own palette or from a plain
 *  keyword, not from this app's theme. */
const BUILTIN = new Set([
  'transparent', 'current', 'inherit', 'white', 'black', 'none', 'auto',
  'solid', 'dashed', 'dotted', 'double', 'hidden', 'clip', 'ellipsis',
  'left', 'right', 'center', 'justify', 'start', 'end', 'top', 'bottom',
  'wrap', 'nowrap', 'balance', 'pretty', 'clear', 'both', 'cover', 'contain',
  'no', 'gradient', 'origin', 'x', 'y', 'r', 'l', 't', 'b', 'sm', 'md', 'lg',
  'xl', 'xs', 'base', 'full', 'medium', 'semibold', 'bold', 'normal', 'wide',
  'wider', 'tight', 'snug', 'relaxed', 'loose', 'uppercase', 'lowercase',
  'capitalize', 'opacity', 'offset', 'width', 'collapse', 'separate', 'fixed',
])

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return walk(full)
    return entry.name.endsWith('.tsx') && !entry.name.endsWith('.test.tsx') ? [full] : []
  })
}

describe('theme tokens', () => {
  it('every colour class a component uses is defined in index.css', () => {
    const css = fs.readFileSync(path.join(ROOT, 'index.css'), 'utf8')
    const defined = new Set([...css.matchAll(/--color-([a-z0-9-]+):/g)].map((m) => m[1]))
    expect(defined.size).toBeGreaterThan(10)

    const offenders: string[] = []
    for (const file of walk(ROOT)) {
      const source = fs.readFileSync(file, 'utf8')
      for (const match of source.matchAll(/\b(?:text|bg|border|decoration|ring)-([a-z][a-z0-9-]*)/g)) {
        const token = match[1]
        if (defined.has(token) || BUILTIN.has(token)) continue
        // A theme token with a numeric shade suffix, e.g. `bg-warning-500`,
        // still has to name a real base token.
        const base = token.replace(/-\d+$/, '')
        if (defined.has(base) || BUILTIN.has(base)) continue
        offenders.push(`${path.relative(ROOT, file)}: ${match[0]}`)
      }
    }

    expect(offenders).toEqual([])
  })

  it('a primary button states its own foreground colour', () => {
    /** The specific shape of the bug: `bg-accent` without a matching
     *  `text-accent-fg` inherits `text-fg`, which in both themes is the same
     *  colour as `bg-accent`. Invisible, in every theme, always. */
    const offenders: string[] = []
    for (const file of walk(ROOT)) {
      const source = fs.readFileSync(file, 'utf8')
      for (const match of source.matchAll(/className="([^"]*\bbg-accent\b[^"]*)"/g)) {
        const classes = match[1]
        // `bg-accent/10` and friends are tints behind ordinary body text.
        if (/bg-accent\/\d/.test(classes)) continue
        if (!/\btext-accent-fg\b/.test(classes)) {
          offenders.push(`${path.relative(ROOT, file)}: ${classes.trim().slice(0, 70)}`)
        }
      }
    }

    expect(offenders).toEqual([])
  })
})
