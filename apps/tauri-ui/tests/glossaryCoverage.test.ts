import fs from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import { explainFootprintTerms, explainPackageToken } from '../src/lib/packageGlossary'

/** SPEC-334: the glossary measured against every footprint KiCad ships,
 *  rather than against names invented here.
 *
 *  This test lives outside `src/` on purpose: it reads the filesystem, which
 *  browser-side code never does, and `tsconfig.app.json` deliberately gives
 *  `src` no node types. It is a check on the glossary's reach, not shipped
 *  code.
 *
 *  `ROADMAP.md` warns against this growing into "a general PCB dictionary".
 *  The floor below is therefore deliberately not 100%: the uncovered tail is
 *  vendor part codes (RV, MF, HDSP, WROOM) that have no standard meaning to
 *  give, and the right behaviour there is silence. */
const ROOT = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'

function everyFootprint(): { library: string; name: string }[] {
  const out: { library: string; name: string }[] = []
  for (const dir of fs.readdirSync(ROOT)) {
    if (!dir.endsWith('.pretty')) continue
    const library = dir.slice(0, -'.pretty'.length)
    for (const file of fs.readdirSync(path.join(ROOT, dir))) {
      if (file.endsWith('.kicad_mod')) {
        out.push({ library, name: file.slice(0, -'.kicad_mod'.length) })
      }
    }
  }
  return out
}

describe.skipIf(!fs.existsSync(ROOT))("KiCad's own footprint libraries", () => {
  it('explains at least one term for the large majority of real footprints', () => {
    const all = everyFootprint()
    const covered = all.filter(
      (f) => explainFootprintTerms(`${f.library}:${f.name}`, f.library).length > 0,
    )

    expect(all.length).toBeGreaterThan(10000)
    // Measured at 88.0% of 15,433 on KiCad 10 when this was written. The floor
    // is set below that so a library revision does not fail the build, but far
    // enough up that losing a whole family would.
    expect(covered.length / all.length).toBeGreaterThan(0.8)
  })

  it('decodes the variants of a family it has never seen individually', () => {
    /** The point of decoding a prefix plus a stem rather than enumerating:
     *  KiCad ships VQFN, TQFN, UQFN, WQFN, HVQFN and more, none of which are
     *  listed in the glossary by name. */
    const variants = new Set(
      everyFootprint()
        .map((f) => /^([A-Z]{2,6})-\d/.exec(f.name)?.[1])
        .filter((t): t is string => Boolean(t)),
    )
    const qfn = [...variants].filter((t) => t.endsWith('QFN') && t !== 'QFN')

    expect(qfn.length).toBeGreaterThan(3)
    for (const term of qfn) {
      const entry = explainPackageToken(term)
      expect(entry, `${term} was not decoded`).not.toBeNull()
      expect(entry?.builtFrom).toBeTruthy()
      expect(entry?.plain).toContain('no legs sticking out')
    }
  })

  it('names a vendor rather than inventing a meaning for its series codes', () => {
    /** `Connector_JST:JST_XH_...` — "XH" is JST's product line. There is no
     *  standard expansion, and claiming one would be the exact failure this
     *  repo keeps paying for. */
    const jst = everyFootprint().find((f) => f.library.startsWith('Connector_JST'))
    expect(jst).toBeTruthy()

    const terms = explainFootprintTerms(`${jst!.library}:${jst!.name}`, jst!.library)
    expect(terms.some((t) => t.term === 'JST' && t.plain.includes('manufacturer'))).toBe(true)
    expect(explainPackageToken('XH')).toBeNull()
  })
})
