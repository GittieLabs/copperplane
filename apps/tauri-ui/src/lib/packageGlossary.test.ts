import { describe, expect, it } from 'vitest'

import {
  allPackageTerms,
  explainFootprintTerms,
  explainPackageToken,
  packagePrefixes,
} from './packageGlossary'

/** SPEC-334. The maintainer, using the footprint detail view: "THT, DIP and
 *  all of the other abbreviations are not intuitive." */
describe('explainPackageToken', () => {
  it('expands the mounting abbreviations a maker has to act on', () => {
    expect(explainPackageToken('THT')?.plain).toMatch(/through holes in the board/)
    expect(explainPackageToken('SMD')?.plain).toMatch(/no holes/)
  })

  it('expands a package family', () => {
    expect(explainPackageToken('DIP')?.plain).toMatch(/Dual In-line Package/)
    expect(explainPackageToken('QFN')?.plain).toMatch(/no legs sticking out/)
  })

  it('decodes a variant it does not list, from its ending', () => {
    /** KiCad ships VQFN, TQFN, UQFN, WQFN, HVQFN and DHVQFN. None are listed
     *  by name; all are a height prefix on a family. */
    const vqfn = explainPackageToken('VQFN')

    expect(vqfn?.plain).toMatch(/^Very thin QFN\./)
    expect(vqfn?.builtFrom).toBe('V + QFN')
  })

  it('names an unrecognised letter rather than expanding it', () => {
    /** DHVQFN's leading D is NXP's own and appears in no standard. The first
     *  version of this decoder matched a prefix at the START of the token and
     *  simply returned nothing for it. */
    const out = explainPackageToken('DHVQFN')

    expect(out?.plain).toMatch(/Thermally enhanced, very thin QFN/)
    expect(out?.plain).toMatch(/The D is the manufacturer's own variant letter/)
  })

  it('does not claim a mounting the prefix has already overridden', () => {
    /** "Surface-mount DIP ... a through-hole chip" is what the family text
     *  said before, in one sentence. */
    const out = explainPackageToken('SMDIP')

    expect(out?.plain).toMatch(/^Surface-mount DIP\./)
    expect(out?.plain).not.toMatch(/through-hole/)
  })

  it('prefers a whole-token meaning over a composed one', () => {
    /** LFCSP composes to "Low profile, fine pitch CSP", which is a confident
     *  wrong answer: Analog Devices means Lead Frame. Composition is a
     *  fallback, never the first move. */
    const out = explainPackageToken('LFCSP')

    expect(out?.plain).toMatch(/Lead Frame/)
    expect(out?.builtFrom).toBeUndefined()
  })

  it('says nothing about a token it does not know', () => {
    expect(explainPackageToken('XH')).toBeNull()
    expect(explainPackageToken('HLE')).toBeNull()
    expect(explainPackageToken('WROOM')).toBeNull()
  })

  it('does not read a longer word as a variant of a family it ends with', () => {
    expect(explainPackageToken('PROTO')).toBeNull()
  })
})

describe('explainFootprintTerms', () => {
  it('explains every term in a footprint name, without repeats', () => {
    const terms = explainFootprintTerms('Package_DIP:DIP-8_W7.62mm_Socket', 'Package_DIP')

    expect(terms.map((t) => t.term)).toContain('DIP')
    expect(terms.filter((t) => t.term === 'DIP')).toHaveLength(1)
  })

  it('explains that a chip size is one measurement written two ways', () => {
    /** `R_0805_2012Metric` looks like two different sizes on one part. */
    const terms = explainFootprintTerms('Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder')
    const size = terms.find((t) => t.term === '0805')

    expect(size?.plain).toMatch(/2.0 by 1.25mm/)
    expect(size?.plain).toMatch(/one size, not two/)
  })

  it("names the manufacturer instead of inventing a meaning for its series code", () => {
    const terms = explainFootprintTerms('Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical')

    expect(terms.find((t) => t.term === 'JST')?.plain).toMatch(/manufacturer/)
    expect(terms.some((t) => t.term === 'XH')).toBe(false)
  })

  it('does not call a KiCad library a manufacturer', () => {
    /** `Resistor_SMD` and `Capacitor_THT` are KiCad's own, not vendors. */
    const terms = explainFootprintTerms('Resistor_SMD:R_0805_2012Metric', 'Resistor_SMD')

    expect(terms.some((t) => t.plain.includes('manufacturer'))).toBe(false)
  })

  it('reads the library name too, since the family often lives there', () => {
    const terms = explainFootprintTerms('Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', 'Package_SO')

    expect(terms.map((t) => t.term)).toContain('SOIC')
  })
})

describe('the browsable list', () => {
  it('is sorted and free of duplicates', () => {
    const terms = allPackageTerms()
    const names = terms.map((t) => t.term)

    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)))
    expect(new Set(names).size).toBe(names.length)
    expect(terms.length).toBeGreaterThan(30)
  })

  it('lists the height letters once rather than multiplied across families', () => {
    /** The alternative is an entry for each of VQFN, TQFN, UQFN, WQFN, VSON,
     *  WSON, TSOP ... which is the "general PCB dictionary" ROADMAP.md warns
     *  this must not become. */
    expect(packagePrefixes().map((p) => p.term)).toContain('V')
    expect(packagePrefixes().length).toBeLessThan(15)
  })
})
