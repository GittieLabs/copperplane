/** SPEC-334: what KiCad's package abbreviations mean.
 *
 *  Reported by the maintainer, using the footprint detail view: *"THT, DIP and
 *  all of the other abbreviations are not intuitive. Adding links or help info
 *  could save time for the user to look up unfamiliar ones that Kicad uses in
 *  naming."*
 *
 *  `ROADMAP.md` (SPEC-332, still-open items) warns against exactly the wrong
 *  shape for this: *"A glossary that is not a hard-coded list. Fine for the
 *  dozen terms KiCad's DRC actually emits; wrong if it grows into a general
 *  PCB dictionary."* So this is not a dictionary of everything a PCB has. It
 *  is bounded by measurement and decoded compositionally:
 *
 *  - The families come from KiCad's own `Package_*` libraries — BGA, CSP,
 *    DFN_QFN, DIP, LCC, LGA, QFP, SIP, SO, SON, SO_J-Lead, TO_SOT_SMD,
 *    TO_SOT_THT. That is KiCad's taxonomy, not one invented here.
 *  - The dozens of variants (VQFN, TQFN, UQFN, WQFN, HTSSOP, TFBGA, …) are
 *    *not* enumerated. They are a stem plus a height prefix, so the prefix is
 *    decoded once and applies to every combination, including ones this file
 *    has never seen.
 *  - A token belonging to a vendor's own product line — JST XH, Samtec HLE,
 *    Molex — is named as such rather than defined, because it has no standard
 *    meaning to give. Saying "this is a vendor series, check their datasheet"
 *    is a real answer; inventing an expansion would not be.
 *
 *  Nothing here is generated at runtime and nothing is guessed. A token this
 *  file does not know produces no entry at all (SPEC-326 §1's rule).
 */

export interface PackageTerm {
  /** As it appears in the name, e.g. `TQFP`. */
  term: string
  plain: string
  /** Set when the reading is assembled from a prefix and a stem rather than
   *  looked up whole, so the UI can show how it was arrived at. */
  builtFrom?: string
}

/** The package families, from KiCad's own `Package_*` libraries plus the
 *  discrete and connector families its other libraries use. */
const _FAMILIES: Record<string, string> = {
  LFCSP: 'Lead Frame Chip Scale Package — Analog Devices\' name for a package like a QFN: pads underneath, no legs. The LF is Lead Frame, not "low profile".',
  SC: 'A JEITA package code — SC-70 and the like are very small surface-mount packages for transistors and single-gate logic.',
  DIP: 'Dual In-line Package — two rows of legs 2.54mm apart, the classic chip shape that fits a socket or a breadboard.',
  SIP: 'Single In-line Package — one row of legs along a single edge.',
  SO: 'Small Outline — a surface-mount chip with gull-wing legs down two sides.',
  SOP: 'Small Outline Package — a surface-mount chip with legs down two sides.',
  SOIC: 'Small Outline Integrated Circuit — the common surface-mount chip with legs down two sides, usually 1.27mm apart.',
  SSOP: 'Shrink Small Outline Package — an SOP with its legs closer together.',
  TSSOP: 'Thin Shrink Small Outline Package — a low, narrow SOP with closely spaced legs.',
  MSOP: 'Mini Small Outline Package — a smaller SOP, typically 8 to 10 legs.',
  TSOP: 'Thin Small Outline Package — a low-profile SOP, common on memory chips.',
  SOJ: 'Small Outline J-lead — an SO package whose legs curl under the body in a J shape.',
  QFP: 'Quad Flat Package — a surface-mount chip with legs on all four sides.',
  QFN: 'Quad Flat No-lead — a square surface-mount chip with pads underneath and no legs sticking out. Hard to solder by hand and hard to inspect.',
  DFN: 'Dual Flat No-lead — like QFN but with pads on two sides only.',
  SON: 'Small Outline No-lead — a small package with pads underneath, no legs.',
  BGA: 'Ball Grid Array — a grid of solder balls underneath the chip. Not hand-solderable, and needs a multi-layer board to escape the pins.',
  CSP: 'Chip Scale Package — a package barely larger than the silicon inside it.',
  WLCSP: 'Wafer-Level Chip Scale Package — bare silicon with solder balls straight on it. Among the hardest to assemble.',
  LGA: 'Land Grid Array — a grid of flat pads underneath, no balls and no legs.',
  LCC: 'Leadless Chip Carrier — a square package with contacts around its edge, no legs.',
  PLCC: 'Plastic Leaded Chip Carrier — a square package with J-shaped legs, often used in a socket.',
  TO: 'Transistor Outline — the JEDEC family of power packages. TO-92 is the small plastic one with three wires, TO-220 the tab-and-screw-hole one that bolts to a heatsink.',
  SOT: 'Small Outline Transistor — a very small surface-mount package for transistors and regulators, usually three to eight pins.',
  DSUB: 'D-subminiature — the D-shaped shell connector, as on a classic serial or VGA port.',
  IDC: 'Insulation-Displacement Connector — the ribbon-cable header whose contacts cut through the wire insulation, so no stripping or soldering.',
  DIN: 'A connector to a DIN standard — the round multi-pin family, as on older keyboard and MIDI ports.',
  XLR: 'The three-pin locking audio connector used for microphones and balanced audio.',
}

/** JEDEC height and variant prefixes. These are why `VQFN`, `TQFN`, `UQFN`,
 *  `WQFN` and `HVQFN` all exist and why enumerating them would be endless. */
const _PREFIXES: Record<string, { short: string; note?: string }> = {
  T: { short: 'Thin' },
  V: { short: 'Very thin' },
  U: { short: 'Ultra thin' },
  W: { short: 'Very very thin' },
  L: { short: 'Low profile' },
  F: { short: 'Fine pitch' },
  P: { short: 'Plastic' },
  S: { short: 'Shrink', note: 'Shrink means the legs sit closer together than the original.' },
  H: {
    short: 'Thermally enhanced',
    note: 'Thermally enhanced means a metal pad underneath carries heat into the board. It usually has to be soldered down, not left floating.',
  },
  CER: { short: 'Ceramic' },
  SM: { short: 'Surface-mount' },
}

/** Mounting and process vocabulary, which is what a maker actually has to act
 *  on: can I solder this with an iron, or not. */
const _MOUNTING: Record<string, string> = {
  THT: 'Through-hole technology — the part has legs that go through holes in the board. The easiest kind to solder by hand.',
  SMD: 'Surface-mount device — the part solders onto pads on the surface, with no holes. Smaller, and harder to place by hand.',
  SMT: 'Surface-mount technology — the same thing as SMD, describing the process rather than the part.',
  EP: 'Exposed pad — a bare metal pad under the chip that must be soldered to the board to carry heat away. Usually not optional.',
  NPTH: 'Non-plated through-hole — a plain drilled hole with no metal in it, usually for a screw.',
  PTH: 'Plated through-hole — a hole with metal through it, so a leg soldered in it connects to both sides.',
}

/** Switch and relay contact codes, which look like typos until you know them. */
const _CONTACTS: Record<string, string> = {
  SPST: 'Single Pole Single Throw — one circuit, simply on or off.',
  SPDT: 'Single Pole Double Throw — one circuit switched between two destinations.',
  DPST: 'Double Pole Single Throw — two circuits switched on and off together.',
  DPDT: 'Double Pole Double Throw — two circuits each switched between two destinations.',
  NO: 'Normally open — the contact is open until the switch is operated.',
  NC: 'Normally closed — the contact is closed until the switch is operated.',
}

/** Coaxial and RF connector standards, and the marks that get placed on a
 *  silkscreen. Both turn up in KiCad's own libraries often enough that a
 *  reader meets them, and both have fixed standard meanings — unlike a vendor
 *  series code, there is a real answer to give. */
const _STANDARDS: Record<string, string> = {
  BNC: 'A twist-lock coaxial connector, the round one on test equipment and video gear.',
  SMA: 'A small screw-on coaxial connector, common for antennas on radio boards.',
  MMCX: 'A very small snap-on coaxial connector, used where an SMA will not fit.',
  ESD: 'Electrostatic discharge — a static shock. An ESD part is there to protect the circuit from one.',
  CE: 'The CE mark — a European conformity marking printed on the silkscreen. It is artwork, not a part.',
  FCC: 'The FCC mark — a United States conformity marking printed on the silkscreen. Artwork, not a part.',
  UKCA: 'The UKCA mark — a United Kingdom conformity marking printed on the silkscreen. Artwork, not a part.',
  WEEE: 'The crossed-out bin mark for electrical waste disposal, printed on the silkscreen. Artwork, not a part.',
  OSHW: 'The Open Source Hardware mark, printed on the silkscreen. Artwork, not a part.',
  RoHS: 'The Restriction of Hazardous Substances mark, printed on the silkscreen. Artwork, not a part.',
}

/** The chip-size codes on every resistor and capacitor. The trap is that the
 *  same part carries two numbers that look like sizes and are not the same
 *  number system, which KiCad writes out in full: `R_0805_2012Metric`. */
const _CHIP_METRIC: Record<string, string> = {
  '0201': '0.6 by 0.3',
  '0402': '1.0 by 0.5',
  '0603': '1.6 by 0.8',
  '0805': '2.0 by 1.25',
  '1206': '3.2 by 1.6',
  '1210': '3.2 by 2.5',
  '1812': '4.5 by 3.2',
  '2010': '5.0 by 2.5',
  '2512': '6.3 by 3.2',
}

/** A library whose name is a manufacturer. Tokens inside such a footprint's
 *  name are that vendor's product-series codes, and have no standard meaning
 *  to expand — so this file says exactly that instead of inventing one. */
const _VENDOR_LIBRARY =
  /^(?:Connector|TerminalBlock|Inductor|Capacitor|Resistor|Diode|LED|Relay|Mounting|Converter|Transformer|Potentiometer|Button|Module|Sensor|RF|Display|Crystal|Oscillator|Fuse|Varistor|Buzzer|Motors|Battery|Transistor)_([A-Z][A-Za-z0-9-]+)(?:_.*)?$/

/** A tail that describes the part rather than naming a manufacturer. These
 *  libraries are KiCad's own, so there is no vendor to point at. */
const _GENERIC_LIBRARY_TAIL = new Set([
  'THT', 'SMD', 'SMT', 'Connector', 'TerminalBlock', 'Wire', 'Generic',
  'Tantalum', 'Module', 'Audio', 'Card', 'Coaxial', 'Display', 'Motors',
  'Power', 'Shielding', 'Antenna', 'Switch', 'Battery', 'Keyboard',
])

function _vendorOf(library: string | null): string | null {
  if (!library) return null
  const m = _VENDOR_LIBRARY.exec(library)
  if (!m || _GENERIC_LIBRARY_TAIL.has(m[1])) return null
  return m[1].replace(/-/g, ' ')
}

/** "Thermally enhanced, Very thin" reads as two labels; only the first word
 *  of the phrase is a sentence opening. */
function _asPhrase(parts: string[]): string {
  return parts
    .map((p, i) => (i === 0 ? p : p.charAt(0).toLowerCase() + p.slice(1)))
    .join(', ')
}

/** Decode one token, whole first, then as prefix plus family. Returns null
 *  rather than a guess. */
export function explainPackageToken(token: string): PackageTerm | null {
  const upper = token.toUpperCase()

  if (_MOUNTING[upper]) return { term: upper, plain: _MOUNTING[upper] }
  if (_STANDARDS[upper]) return { term: upper, plain: _STANDARDS[upper] }
  if (_CONTACTS[upper]) return { term: upper, plain: _CONTACTS[upper] }
  if (_FAMILIES[upper]) return { term: upper, plain: _FAMILIES[upper] }

  // Not a lookup: find the family this token ENDS with, then read the letters
  // in front of it. KiCad ships VQFN, TQFN, UQFN, WQFN, HVQFN and DHVQFN;
  // enumerating them is endless, and the first attempt here -- matching a
  // known prefix at the START -- failed on DHVQFN, whose leading D is NXP's
  // own and appears in no standard.
  const families = Object.keys(_FAMILIES).sort((a, b) => b.length - a.length)
  for (const stem of families) {
    if (!upper.endsWith(stem) || upper === stem) continue
    const head = upper.slice(0, -stem.length)
    // A long head is a different word that happens to end in a family name,
    // not a variant of it.
    if (head.length > 3) continue

    const read: string[] = []
    const notes: string[] = []
    const unknown: string[] = []
    let rest = head
    while (rest) {
      const prefix = Object.keys(_PREFIXES)
        .sort((a, b) => b.length - a.length)
        .find((p) => rest.startsWith(p))
      if (prefix) {
        read.push(_PREFIXES[prefix].short)
        const note = _PREFIXES[prefix].note
        if (note) notes.push(note)
        rest = rest.slice(prefix.length)
      } else {
        unknown.push(rest[0])
        rest = rest.slice(1)
      }
    }
    // One unrecognised letter is a manufacturer's variant (DHVQFN's D). Two
    // means this is a different word that happens to end in a family name --
    // PROTO read as "Plastic TO" with R and O left over.
    if (!read.length || unknown.length > 1) continue

    // An unrecognised letter is reported as unrecognised. Expanding it would
    // be a guess, and the whole point of this file is that it does not guess.
    const note = unknown.length
      ? ` The ${unknown.join(' and ')} is the manufacturer's own variant letter, not a standard one.`
      : ''
    return {
      term: upper,
      plain: `${_asPhrase(read)} ${stem}. ${_FAMILIES[stem]}${notes.map((n) => ` ${n}`).join('')}${note}`,
      builtFrom: `${head} + ${stem}`,
    }
  }
  return null
}

/** Every term worth expanding for one footprint, in the order a reader meets
 *  them, without repeats. Silent about anything it does not know. */
export function explainFootprintTerms(
  footprintId: string,
  library?: string | null,
): PackageTerm[] {
  const found: PackageTerm[] = []
  const seen = new Set<string>()
  const add = (entry: PackageTerm | null) => {
    if (!entry || seen.has(entry.term)) return
    seen.add(entry.term)
    found.push(entry)
  }

  const name = footprintId.includes(':') ? footprintId.split(':').pop() ?? '' : footprintId
  const lib = library ?? (footprintId.includes(':') ? footprintId.split(':')[0] : null)

  for (const token of name.split(/[_\-.]/)) {
    if (token) add(explainPackageToken(token))
  }
  // The library name carries the family too: `Package_SO`, `Package_DIP`.
  for (const token of (lib ?? '').split(/[_\-.]/)) {
    if (token) add(explainPackageToken(token))
  }

  // Matched against whole tokens, not with a word boundary: `\b` does not
  // match between "_" and "0", so /\b0805\b/ never fired on `R_0805_2012Metric`.
  const size = name.split(/[_\-.]/).find((t) => t in _CHIP_METRIC)
  if (size) {
    add({
      term: size,
      plain: `${size} is the body size in hundredths of an inch — ${size.slice(0, 2)} by ${size.slice(2)} — which is ${_CHIP_METRIC[size]}mm. KiCad writes the metric code beside it, so 0805 and 2012Metric on the same name are one size, not two.`,
    })
  }

  const vendor = _vendorOf(lib)
  if (vendor) {
    add({
      term: vendor,
      plain: `${vendor} is the manufacturer. The letters and numbers in this footprint's name are ${vendor}'s own series codes, not standard abbreviations, so their datasheet is the place to decode them.`,
    })
  }

  return found
}

/** The whole vocabulary, for a reader who wants to browse rather than look up
 *  the part in front of them. */
export function allPackageTerms(): PackageTerm[] {
  const terms: PackageTerm[] = []
  for (const [term, plain] of Object.entries(_MOUNTING)) terms.push({ term, plain })
  for (const [term, plain] of Object.entries(_FAMILIES)) terms.push({ term, plain })
  for (const [term, plain] of Object.entries(_CONTACTS)) terms.push({ term, plain })
  for (const [term, plain] of Object.entries(_STANDARDS)) terms.push({ term, plain })
  return terms.sort((a, b) => a.term.localeCompare(b.term))
}

/** The height and variant letters, listed once rather than multiplied out
 *  across every family they can be attached to. */
export function packagePrefixes(): PackageTerm[] {
  return Object.entries(_PREFIXES).map(([term, { short, note }]) => ({
    term,
    plain: note ? `${short}. ${note}` : `${short}.`,
  }))
}
