import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ViolationsList } from './ViolationsList'

/** The real shape of a KiCad unconnected item, from a real DRC run on the
 *  maintainer's board. `items` used to be discarded as "internal uuids" --
 *  only `uuid` is; the rest is the answer to "where is it". */
const UNCONNECTED = {
  description: 'Missing connection between items',
  severity: 'error',
  type: 'unconnected_items',
  explanation: 'Two pads that should be joined are not.',
  suggested_fix: 'Route a track between them.',
  items: [
    {
      description: 'PTH pad 2 [Net-(U2-THRES)] of U2',
      pos: { x: 99.695, y: 68.23 },
      uuid: '316be86b',
    },
    {
      description: 'Track [Net-(U2-THRES)] on F.Cu, length 1.5556 mm',
      pos: { x: 107.315, y: 70.77 },
      uuid: '8568ccf9',
    },
  ],
}

function result(over: Record<string, unknown> = {}) {
  return {
    violations: [UNCONNECTED], summary: 's', truncated_count: 0,
    source_path: '/p/b.kicad_pcb', ...over,
  } as never
}

describe('ViolationsList: where the problem is', () => {
  it('names the pad, net and component KiCad flagged', async () => {
    render(<ViolationsList result={result()} kind="drc" />)

    expect(screen.getByText(/PTH pad 2 \[Net-\(U2-THRES\)\] of U2/)).toBeTruthy()
  })

  it('gives the position on the board, so it can be found', () => {
    render(<ViolationsList result={result()} kind="drc" />)

    expect(screen.getByText(/x 99\.695mm, y 68\.23mm/)).toBeTruthy()
  })

  it('offers plain-language expansions of the abbreviations', () => {
    render(<ViolationsList result={result()} kind="drc" />)

    expect(screen.getByText(/What these terms mean/)).toBeTruthy()
    expect(screen.getByText(/Plated through-hole/)).toBeTruthy()
    expect(screen.getByText(/pin THRES of U2/)).toBeTruthy()
  })

  it('shows no location block when KiCad gave no items', () => {
    render(<ViolationsList kind="drc" result={result({ violations: [{ ...UNCONNECTED, items: [] }] })} />)

    expect(screen.queryByText(/Where to find it/)).toBeNull()
  })
})

describe('ViolationsList: tests KiCad did not run', () => {
  const IGNORED = [
    { key: 'missing_courtyard', description: 'Footprint has no courtyard defined' },
    { key: 'track_not_centered_on_via', description: 'Track endpoint not centered on via' },
  ]

  it('says how many are switched off, and how many are worth turning back on', () => {
    render(<ViolationsList kind="drc" result={result({ ignored_checks: IGNORED })} />)

    expect(screen.getByText(/2 DRC tests switched off/)).toBeTruthy()
    expect(screen.getByText(/1 worth turning back on/)).toBeTruthy()
  })

  it('explains what each one would have caught', () => {
    render(<ViolationsList kind="drc" result={result({ ignored_checks: IGNORED })} />)

    expect(screen.getByText(/overlapping each other/)).toBeTruthy()
    expect(screen.getByText(/Cosmetic on a hobby board/)).toBeTruthy()
  })

  it('admits when it has no note for a check rather than inventing one', () => {
    render(<ViolationsList kind="drc" result={result({
      ignored_checks: [{ key: 'some_future_check', description: 'A check added by a later KiCad' }],
    })} />)

    expect(screen.getByText(/No plain-language note for this check yet/)).toBeTruthy()
  })

  it('says nothing at all when no checks are switched off', () => {
    render(<ViolationsList kind="drc" result={result({ ignored_checks: [] })} />)

    expect(screen.queryByText(/switched off/)).toBeNull()
  })
})

/** SPEC-332: the schematic check now reports what the board check does. The
 *  renderer was already shared -- SchematicAdvisor and BoardAdvisor both use
 *  ViolationsList -- so these render with no component change at all. */
describe('ViolationsList: an ERC result', () => {
  const ercResult = {
    source_path: '/p/Blinky.kicad_sch',
    summary: 'One pin is not connected.',
    violations: [
      {
        severity: 'error',
        description: 'Pin not connected',
        type: 'pin_not_connected',
        sheet_path: '/',
        items: [{ description: 'Symbol #PWR03 Pin 1 [Power input, Line]' }],
        explanation: '',
        suggested_fix: '',
      },
    ],
    truncated_count: 0,
    ignored_checks: [
      { key: 'single_global_label', description: 'Global label only appears once in the schematic' },
      { key: 'simulation_model_issue', description: 'SPICE model issue' },
    ],
  }

  it('shows which schematic checks were switched off', () => {
    render(<ViolationsList result={ercResult} kind="erc" />)

    expect(screen.getByText(/A global label used in only one place/)).toBeTruthy()
    expect(screen.getByText(/Irrelevant unless you actually simulate/)).toBeTruthy()
  })

  it('explains ERC vocabulary in the finding itself', () => {
    /** "Power input" is the term a maker cannot act on: the schematic is
     *  usually right and a PWR_FLAG is missing. */
    render(<ViolationsList result={ercResult} kind="erc" />)

    expect(screen.getByText(/expects to be fed power/)).toBeTruthy()
  })

  it('still says where the problem is', () => {
    render(<ViolationsList result={ercResult} kind="erc" />)

    expect(screen.getByText(/Symbol #PWR03 Pin 1/)).toBeTruthy()
  })
})

/** SPEC-332: a check filtered to one severity, presented as clean, is the same
 *  lie as a clean result from a test that was switched off. */
describe('ViolationsList: which severities were included', () => {
  const base = {
    source_path: '/p/Blinky.kicad_sch',
    summary: 'Nothing found.',
    violations: [],
    truncated_count: 0,
  }

  it('says so when warnings were not looked for', () => {
    render(<ViolationsList kind="drc" result={{ ...base, included_severities: ['error'] }} />)

    expect(screen.getByText(/only looked for error/)).toBeTruthy()
    expect(screen.getByText(/does not mean there is nothing to see/)).toBeTruthy()
  })

  it('stays silent on an ordinary full run', () => {
    /** Saying "errors and warnings were included" on every clean run is noise,
     *  and noise is how a real warning gets ignored. */
    render(
      <ViolationsList kind="drc" result={{ ...base, included_severities: ['error', 'warning', 'exclusion'] }} />,
    )

    expect(screen.queryByText(/only looked for/)).toBeNull()
  })

  it('stays silent when the report does not say', () => {
    render(<ViolationsList result={base} kind="drc" />)

    expect(screen.queryByText(/only looked for/)).toBeNull()
  })
})

/** SPEC-332: the ignored-checks block names the tool and the menu path to fix
 *  it. Sharing the component put DRC's wording on the Schematic tab until
 *  `kind` existed. Both paths are read from KiCad's own binaries: eeschema and
 *  pcbnew each carry "Edit ignored tests", under their own checker. */
describe('ViolationsList: ignored checks name the right checker', () => {
  const withIgnored = (extra: object) => ({
    source_path: '/p/x',
    summary: '',
    violations: [],
    truncated_count: 0,
    ignored_checks: [{ key: 'footprint_filter', description: "Assigned footprint doesn't match filters" }],
    ...extra,
  })

  it('sends a schematic user to the Electrical Rules Checker', () => {
    render(<ViolationsList result={withIgnored({})} kind="erc" />)

    expect(screen.getByText(/1 ERC test switched off/)).toBeTruthy()
    expect(screen.getByText(/Electrical Rules Checker/)).toBeTruthy()
    expect(screen.getByText(/your schematic can look clean/)).toBeTruthy()
  })

  it('sends a board user to the Design Rules Checker', () => {
    render(<ViolationsList result={withIgnored({})} kind="drc" />)

    expect(screen.getByText(/1 DRC test switched off/)).toBeTruthy()
    expect(screen.getByText(/Design Rules Checker/)).toBeTruthy()
    expect(screen.getByText(/your board can look clean/)).toBeTruthy()
  })

  it('flags the switched-off checks that are worth turning back on, on both', () => {
    /** The board review already did this; the schematic review now does too --
     *  same IGNORED_CHECK_NOTES table, with the ERC keys added. */
    for (const kind of ['erc', 'drc'] as const) {
      const { unmount } = render(<ViolationsList result={withIgnored({})} kind={kind} />)
      expect(screen.getByText(/1 worth turning back on/)).toBeTruthy()
      unmount()
    }
  })

  it('says nothing about turning tests back on when none of them matter', () => {
    const result = withIgnored({
      ignored_checks: [{ key: 'simulation_model_issue', description: 'SPICE model issue' }],
    })
    render(<ViolationsList result={result} kind="erc" />)

    expect(screen.queryByText(/worth turning back on/)).toBeNull()
    expect(screen.getByText(/Irrelevant unless you actually simulate/)).toBeTruthy()
  })
})
