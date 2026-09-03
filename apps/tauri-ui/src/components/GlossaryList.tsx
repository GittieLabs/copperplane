import { useMemo, useState } from 'react'

import { allPackageTerms, packagePrefixes } from '../lib/packageGlossary'

/** SPEC-334: the whole KiCad naming vocabulary, for a reader who wants to
 *  browse rather than look up the part in front of them.
 *
 *  "THT, DIP and all of the other abbreviations are not intuitive. Adding
 *  links or help info could save time for the user to look up unfamiliar
 *  ones."
 *
 *  Deliberately not a link out: a definition read here costs no round trip and
 *  no reading of a datasheet written for someone else. */
export function GlossaryList() {
  const [filter, setFilter] = useState('')

  const terms = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!needle) return allPackageTerms()
    return allPackageTerms().filter(
      (t) => t.term.toLowerCase().includes(needle) || t.plain.toLowerCase().includes(needle),
    )
  }, [filter])

  return (
    <div className="flex flex-col gap-3 text-xs">
      <label className="flex flex-col gap-1">
        <span className="text-fg-muted">Find a term</span>
        <input
          className="w-full rounded border border-line bg-surface px-2 py-1 text-fg"
          placeholder="THT, QFN, 0805…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </label>

      {terms.length === 0 ? (
        /* Silence about an unknown term is the rule everywhere else in this
           surface; saying so plainly beats an empty list that reads as broken. */
        <p className="text-fg-muted">
          Nothing here matches “{filter.trim()}”. This list covers the abbreviations KiCad's own
          libraries use — a manufacturer's series code, like JST&rsquo;s XH, is not one of them and
          lives in their datasheet instead.
        </p>
      ) : (
        <dl className="flex flex-col gap-2">
          {terms.map((t) => (
            <div key={t.term}>
              <dt className="font-medium text-fg-bright">{t.term}</dt>
              <dd className="text-fg-secondary">{t.plain}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="flex flex-col gap-2 rounded bg-surface-alt/60 p-2">
        <p className="font-medium text-fg-secondary">The letters in front of a package name</p>
        <p className="text-fg-muted">
          These attach to any family, which is why QFN also appears as VQFN, TQFN, UQFN, WQFN and
          HVQFN. Reading the letters is quicker than learning each combination.
        </p>
        <dl className="flex flex-col gap-1">
          {packagePrefixes().map((p) => (
            <div key={p.term}>
              <dt className="inline font-medium text-fg-bright">{p.term} </dt>
              <dd className="inline text-fg-secondary">{p.plain}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
