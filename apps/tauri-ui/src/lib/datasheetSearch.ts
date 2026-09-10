/** A constructed search link for a datasheet the app could not resolve.
 *
 *  `SPEC-203` §3 names this pattern as what replaced supplier APIs for exactly
 *  this need: *"a constructed deep link. No API, no key, compliant
 *  everywhere."* `SPEC-212` measured why it is needed — a guessed datasheet URL
 *  resolves 3 of 3 for an IC and 0 of 3 for a generic passive, because a
 *  passive's datasheet is a family document and there is no per-part URL to
 *  guess. `SPEC-212` was then declined, so this is the whole fix rather than a
 *  stopgap before one.
 *
 *  **Deliberately a neutral web search, not a distributor's own.** Sending
 *  every failed lookup to one vendor's search page picks a commercial partner
 *  on the user's behalf, which is a business decision this app has not made and
 *  should not make silently. DuckDuckGo because this product's stated position
 *  is that nothing leaves the machine unasked — the user clicking a link is the
 *  asking, and the least-tracking default is the honest one to hand them. */
export function datasheetSearchUrl(partNumber: string, manufacturer?: string): string {
  const terms = [partNumber, manufacturer, 'datasheet'].filter(Boolean).join(' ')
  return `https://duckduckgo.com/?q=${encodeURIComponent(terms)}`
}
