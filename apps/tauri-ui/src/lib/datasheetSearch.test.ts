import { describe, expect, it } from 'vitest'
import { datasheetSearchUrl } from './datasheetSearch'

describe('datasheetSearchUrl', () => {
  it('builds a search that would actually find the document', () => {
    const url = datasheetSearchUrl('CFR-25JB-52-220R', 'Yageo')

    expect(url).toContain('CFR-25JB-52-220R')
    expect(url).toContain('Yageo')
    expect(url).toContain('datasheet')
  })

  it('works without a manufacturer, rather than putting "undefined" in the query', () => {
    const url = datasheetSearchUrl('NE555P')

    expect(url).not.toContain('undefined')
    expect(decodeURIComponent(url)).toContain('NE555P datasheet')
  })

  it('escapes a part number containing characters a URL cares about', () => {
    // Real part numbers carry +, /, # and spaces. An unescaped one silently
    // truncates the query and returns results for a different part.
    const url = datasheetSearchUrl('GRM188R71H104KA93D+/#', 'Murata')

    expect(url).not.toMatch(/[+#]/)
    expect(url.split('?q=')[1]).not.toContain('/')
  })

  it('sends nobody to a distributor of our choosing', () => {
    /* SPEC-203 §3's constructed deep link is "compliant everywhere" precisely
     * because it commits to nothing. Routing every failed lookup to one
     * vendor's search picks a commercial partner on the user's behalf, which
     * is a business decision this app has not made. */
    const url = datasheetSearchUrl('CFR-25JB-52-220R', 'Yageo')

    for (const vendor of ['digikey', 'mouser', 'lcsc', 'arrow', 'element14', 'tme']) {
      expect(url.toLowerCase()).not.toContain(vendor)
    }
  })
})
