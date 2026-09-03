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
    render(<ViolationsList result={result()} />)

    expect(screen.getByText(/PTH pad 2 \[Net-\(U2-THRES\)\] of U2/)).toBeTruthy()
  })

  it('gives the position on the board, so it can be found', () => {
    render(<ViolationsList result={result()} />)

    expect(screen.getByText(/x 99\.695mm, y 68\.23mm/)).toBeTruthy()
  })

  it('offers plain-language expansions of the abbreviations', () => {
    render(<ViolationsList result={result()} />)

    expect(screen.getByText(/What these terms mean/)).toBeTruthy()
    expect(screen.getByText(/Plated through-hole/)).toBeTruthy()
    expect(screen.getByText(/pin THRES of U2/)).toBeTruthy()
  })

  it('shows no location block when KiCad gave no items', () => {
    render(<ViolationsList result={result({ violations: [{ ...UNCONNECTED, items: [] }] })} />)

    expect(screen.queryByText(/Where to find it/)).toBeNull()
  })
})

describe('ViolationsList: tests KiCad did not run', () => {
  const IGNORED = [
    { key: 'missing_courtyard', description: 'Footprint has no courtyard defined' },
    { key: 'track_not_centered_on_via', description: 'Track endpoint not centered on via' },
  ]

  it('says how many are switched off, and how many are worth turning back on', () => {
    render(<ViolationsList result={result({ ignored_checks: IGNORED })} />)

    expect(screen.getByText(/2 DRC tests switched off/)).toBeTruthy()
    expect(screen.getByText(/1 worth turning back on/)).toBeTruthy()
  })

  it('explains what each one would have caught', () => {
    render(<ViolationsList result={result({ ignored_checks: IGNORED })} />)

    expect(screen.getByText(/overlapping each other/)).toBeTruthy()
    expect(screen.getByText(/Cosmetic on a hobby board/)).toBeTruthy()
  })

  it('admits when it has no note for a check rather than inventing one', () => {
    render(<ViolationsList result={result({
      ignored_checks: [{ key: 'some_future_check', description: 'A check added by a later KiCad' }],
    })} />)

    expect(screen.getByText(/No plain-language note for this check yet/)).toBeTruthy()
  })

  it('says nothing at all when no checks are switched off', () => {
    render(<ViolationsList result={result({ ignored_checks: [] })} />)

    expect(screen.queryByText(/switched off/)).toBeNull()
  })
})

/** SPEC-332: the schematic check now reports what the board check does. The
 *  renderer was already shared -- SchematicAdvisor and BoardAdvisor both use
 *  ViolationsList -- so these render with no component change at all. */
describe('ViolationsList: an ERC result', () => {
  const ercResult = {
    summary: 'One pin is not connected.',
    violations: [
      {
        severity: 'error',
        description: 'Pin not connected',
        sheet_path: '/',
        items: [{ description: 'Symbol #PWR03 Pin 1 [Power input, Line]' }],
      },
    ],
    truncated_count: 0,
    ignored_checks: [
      { key: 'single_global_label', description: 'Global label only appears once in the schematic' },
      { key: 'simulation_model_issue', description: 'SPICE model issue' },
    ],
  }

  it('shows which schematic checks were switched off', () => {
    render(<ViolationsList result={ercResult} />)

    expect(screen.getByText(/A global label used in only one place/)).toBeTruthy()
    expect(screen.getByText(/Irrelevant unless you actually simulate/)).toBeTruthy()
  })

  it('explains ERC vocabulary in the finding itself', () => {
    /** "Power input" is the term a maker cannot act on: the schematic is
     *  usually right and a PWR_FLAG is missing. */
    render(<ViolationsList result={ercResult} />)

    expect(screen.getByText(/expects to be fed power/)).toBeTruthy()
  })

  it('still says where the problem is', () => {
    render(<ViolationsList result={ercResult} />)

    expect(screen.getByText(/Symbol #PWR03 Pin 1/)).toBeTruthy()
  })
})
