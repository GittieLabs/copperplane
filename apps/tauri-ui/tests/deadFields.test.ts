import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/** A field the daemon sends, the UI declares, and nothing ever reads.
 *
 *  Written after `included_severities` reached the client and was neither typed
 *  nor rendered — so a commit message said an omission was closed while the
 *  data sat unused. `tsc` cannot catch it: an unread optional property is
 *  perfectly valid TypeScript. Nor can a component test, which only asserts
 *  what is rendered, never what was promised and is not.
 *
 *  Deliberately scoped to a named list rather than every exported interface.
 *  These are the shapes the daemon returns for the UI to render, where "we
 *  receive it and show nothing" is a defect. A type used only to post a payload
 *  has no such expectation, and sweeping all interfaces in would bury the
 *  signal. A new response type is added here on purpose. */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')

const RESPONSE_TYPES: { file: string; name: string }[] = [
  { file: 'lib/settings.ts', name: 'DaemonCapabilities' },
  { file: 'lib/boardAdvisor.ts', name: 'CheckResult' },
  { file: 'lib/kicadProject.ts', name: 'FootprintDetail' },
  { file: 'lib/kicadProject.ts', name: 'ProjectsInDirectory' },
  { file: 'lib/settings.ts', name: 'ProjectsInRoot' },
]

function sources(): Map<string, string> {
  const out = new Map<string, string>()
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (/\.tsx?$/.test(entry.name) && !entry.name.includes('.test.')) {
        out.set(full, fs.readFileSync(full, 'utf8'))
      }
    }
  }
  walk(ROOT)
  return out
}

function fieldsOf(text: string, name: string): string[] {
  const block = new RegExp(`export interface ${name} \\{(.*?)\\n\\}`, 's').exec(text)
  if (!block) throw new Error(`interface ${name} not found — has it been renamed?`)
  return [...block[1].matchAll(/^\s{2}(\w+)\??:/gm)].map((m) => m[1])
}

describe('fields the daemon sends and the UI never reads', () => {
  const all = sources()

  for (const { file, name } of RESPONSE_TYPES) {
    it(`${name}: every declared field is read somewhere`, () => {
      const declaring = fs.readFileSync(path.join(ROOT, file), 'utf8')
      const unread = fieldsOf(declaring, name).filter((field) => {
        const used = new RegExp(`\\.${field}\\b`)
        return ![...all.values()].some((text) => used.test(text))
      })

      expect(unread).toEqual([])
    })
  }

  it('would notice a field that nothing reads', () => {
    /** The guard on the guard: proves the detection reacts to an unread field
     *  rather than passing because the regex never matches anything. */
    // `description` is read all over the codebase; `neverRead` is read nowhere.
    // The first version of this used an invented name for BOTH and "passed"
    // by finding two unread fields where it meant to find one.
    const declaring = `export interface Invented {\n  description: string\n  neverRead: string\n}`
    const unread = fieldsOf(declaring, 'Invented').filter((field) => {
      const used = new RegExp(`\\.${field}\\b`)
      return ![...all.values()].some((text) => used.test(text))
    })

    expect(unread).toEqual(['neverRead'])
  })
})
