import { describe, expect, it } from 'vitest'
import { explainAutoNet, explainTerms, IGNORED_CHECK_NOTES } from './kicadGlossary'

/** Reported while reading a real DRC finding: "I don't know what
 *  [Net-(U2-THRES)] of U2 means or actually any of the abbreviations in order
 *  to find them." */
describe('explainAutoNet', () => {
  it('reads a KiCad auto-net name back as the pin it came from', () => {
    const entry = explainAutoNet('PTH pad 2 [Net-(U2-THRES)] of U2')
    expect(entry?.term).toBe('Net-(U2-THRES)')
    expect(entry?.plain).toContain('pin THRES of U2')
  })

  it('says an auto-net name is not itself a fault', () => {
    // The name looks like an error code to someone who has not seen one before.
    expect(explainAutoNet('[Net-(D1-K)]')?.plain).toContain('not a problem')
  })

  it('returns nothing for a named net, which needs no expansion', () => {
    expect(explainAutoNet('Track [GND] on F.Cu')).toBeNull()
  })
})

describe('explainTerms', () => {
  it('expands the abbreviations in a real unconnected-item line', () => {
    const terms = explainTerms('PTH pad 2 [Net-(U2-THRES)] of U2').map((t) => t.term)
    expect(terms).toContain('PTH')
    expect(terms).toContain('pad')
    expect(terms).toContain('Net-(U2-THRES)')
  })

  it('expands layer names in a track line', () => {
    const terms = explainTerms('Track [Net-(D1-K)] on F.Cu, length 1.5556 mm').map((t) => t.term)
    expect(terms).toContain('F.Cu')
    expect(terms).toContain('track')
  })

  it('does not match a term inside a longer word', () => {
    expect(explainTerms('padding around the keepout').map((t) => t.term)).not.toContain('pad')
  })

  it("does not treat F.Cu's dot as a wildcard", () => {
    expect(explainTerms('FxCu is not a layer').map((t) => t.term)).not.toContain('F.Cu')
  })

  it('lists each term once even when it appears twice', () => {
    const terms = explainTerms('PTH pad 1 and PTH pad 2').map((t) => t.term)
    expect(terms.filter((t) => t === 'PTH')).toHaveLength(1)
  })
})

describe('IGNORED_CHECK_NOTES', () => {
  it('flags the ignored checks a maker should care about before manufacturing', () => {
    expect(IGNORED_CHECK_NOTES.missing_courtyard.matters).toBe(true)
    expect(IGNORED_CHECK_NOTES.footprint_type_mismatch.matters).toBe(true)
  })

  it('does not cry wolf about checks that do not matter on a hobby board', () => {
    expect(IGNORED_CHECK_NOTES.track_not_centered_on_via.matters).toBe(false)
    expect(IGNORED_CHECK_NOTES.tuning_profile_track_geometries.matters).toBe(false)
  })

  it('says why missing_courtyard matters to this app specifically', () => {
    // SPEC-326 measures courtyards to size the enclosure.
    expect(IGNORED_CHECK_NOTES.missing_courtyard.plain).toContain('enclosure')
  })

  it('covers every key this KiCad install actually reported', () => {
    // The five from the maintainer's own board, read from a real DRC run.
    for (const key of [
      'missing_courtyard', 'track_not_centered_on_via', 'tuning_profile_track_geometries',
      'footprint_filters_mismatch', 'footprint_type_mismatch',
    ]) {
      expect(IGNORED_CHECK_NOTES[key], key).toBeDefined()
    }
  })
})
