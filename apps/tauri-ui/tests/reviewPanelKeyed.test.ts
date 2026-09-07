import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/** CTX-339.1: every ReviewPanel mount site must key it.
 *
 *  The panel used to reset its own state in an effect keyed on `scopeId`. That
 *  effect wrote state after the commit, which CTX-318.7 showed silently undoes
 *  a click landing in the same window -- and it now has a second job, loading a
 *  kept review, which must not be a reset at all.
 *
 *  So the guarantee moved to a `key` at the caller. That is the right shape and
 *  it is only as good as the callers honouring it: a mount site that forgets
 *  leaks one project's review into the next, silently, with nothing in the
 *  component able to notice. Nothing else in the suite reads a mount site, so
 *  this does. */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return walk(full)
    return entry.name.endsWith('.tsx') && !entry.name.endsWith('.test.tsx') ? [full] : []
  })
}

describe('ReviewPanel mount sites', () => {
  it('every one passes a key', () => {
    const offenders: string[] = []
    let sites = 0

    for (const file of walk(ROOT)) {
      const source = fs.readFileSync(file, 'utf8')
      for (const match of source.matchAll(/<ReviewPanel\b[\s\S]*?\/>/g)) {
        sites++
        if (!/\bkey=/.test(match[0])) {
          offenders.push(path.relative(ROOT, file))
        }
      }
    }

    // A regex that matched nothing would pass this test while proving nothing.
    expect(sites).toBeGreaterThan(0)
    expect(offenders).toEqual([])
  })
})
