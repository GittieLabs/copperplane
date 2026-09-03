/** Plain-language expansions for the abbreviations KiCad's DRC text is dense
 *  with. Static and instant: these are fixed facts about KiCad's own
 *  vocabulary, not judgements about a design, so spending an LLM call on them
 *  would be slower, costlier and less reliable than writing them down.
 *
 *  The agent still explains findings in context -- this is what the UI can
 *  show beside a location without asking anyone anything.
 *
 *  Reported by the maintainer, reading a real finding: "I don't know what
 *  [Net-(U2-THRES)] of U2 means or actually any of the abbreviations in order
 *  to find them." The target reader is a maker, not a PCB engineer. */
export interface GlossaryEntry {
  term: string
  plain: string
}

const _STATIC: GlossaryEntry[] = [
  { term: 'PTH', plain: 'Plated through-hole — a hole with metal through it, for a part with legs.' },
  { term: 'NPTH', plain: 'Non-plated through-hole — a plain hole with no metal, usually for a screw.' },
  { term: 'SMD', plain: 'Surface-mount — a flat pad soldered on top of the board, with no hole.' },
  { term: 'F.Cu', plain: 'Front copper — the top side of the board.' },
  { term: 'B.Cu', plain: 'Back copper — the underside of the board.' },
  { term: 'F.SilkS', plain: 'Front silkscreen — the printed white text and outlines on top.' },
  { term: 'F.Mask', plain: 'Front solder mask — the coloured coating with openings at each pad.' },
  { term: 'F.CrtYd', plain: 'Front courtyard — the keep-clear outline around a part.' },
  { term: 'Edge.Cuts', plain: 'The board outline — where the PCB gets cut out.' },
  { term: 'via', plain: 'A plated hole carrying a connection from one layer to another.' },
  { term: 'pad', plain: 'The metal spot a component leg is soldered to.' },
  { term: 'track', plain: 'A copper line — the wire connecting two pads.' },
]

/** `Net-(U2-THRES)` is KiCad's auto-name for a net with no name of its own.
 *  It reads as "the net attached to pin THRES of U2" -- so it names the wire,
 *  and is not itself a fault, which is not obvious from looking at it. */
const _AUTO_NET = /Net-\(([^-)]+)-([^)]+)\)/

export function explainAutoNet(text: string): GlossaryEntry | null {
  const m = _AUTO_NET.exec(text)
  if (!m) return null
  return {
    term: m[0],
    plain: `An unnamed connection — KiCad named it after pin ${m[2]} of ${m[1]}. It names the wire, not a problem.`,
  }
}

/** Every term worth expanding for one KiCad finding line, in the order they
 *  appear, without repeats. */
export function explainTerms(text: string): GlossaryEntry[] {
  const found: GlossaryEntry[] = []
  const autoNet = explainAutoNet(text)
  if (autoNet) found.push(autoNet)

  for (const entry of _STATIC) {
    // Word-boundary-ish: "pad" must not match inside "padding", and F.Cu's
    // dot must be matched literally rather than as "any character".
    // Case-insensitive: KiCad writes "Track [...] on F.Cu" with the noun
    // capitalised at the start of a line and lower-case mid-sentence. The
    // canonical spelling from the table is what gets displayed either way.
    const pattern = new RegExp(
      `(^|[^A-Za-z0-9.])${entry.term.replace(/\./g, '\\.')}([^A-Za-z0-9]|$)`,
      'i',
    )
    if (pattern.test(text)) found.push(entry)
  }
  return found
}

/** What a switched-off DRC test would have caught, and whether a maker
 *  should care before sending a board out. Keys are KiCad's own stable
 *  `ignored_checks[].key` values. */
export const IGNORED_CHECK_NOTES: Record<string, { plain: string; matters: boolean }> = {
  missing_courtyard: {
    plain: 'Parts with no keep-clear outline are not checked for overlapping each other. This app also measures courtyards to size your enclosure, so a missing one weakens that too.',
    matters: true,
  },
  footprint_type_mismatch: {
    plain: 'A part marked surface-mount whose pads are actually through-hole (or the reverse) is not flagged. That mismatch usually means the wrong footprint was chosen.',
    matters: true,
  },
  footprint_filters_mismatch: {
    plain: 'The footprint you picked is not checked against the list the symbol suggests. Worth having on if you choose footprints by hand.',
    matters: true,
  },
  track_not_centered_on_via: {
    plain: 'Tracks that stop slightly off-centre on a via are not flagged. Cosmetic on a hobby board; fabricators rarely care.',
    matters: false,
  },
  tuning_profile_track_geometries: {
    plain: 'Length-tuning patterns are not checked. Only relevant for high-speed designs with matched-length requirements.',
    matters: false,
  },
}
