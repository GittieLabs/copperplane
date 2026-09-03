import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const describeFootprintMock = vi.fn()

vi.mock('../lib/kicadProject', () => ({
  describeFootprint: (...a: unknown[]) => describeFootprintMock(...a),
}))

const { FootprintDetailView } = await import('./FootprintDetail')

const HEADER = {
  footprint_id: 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
  library: 'Connector_PinHeader_2.54mm',
  name: 'PinHeader_1x04_P2.54mm_Vertical',
  description: 'Through hole straight pin header, 1x04, 2.54mm pitch, single row',
  tags: ['Through hole', 'pin header'],
  datasheet_url: null,
  pad_count: 4,
  mounting: 'through-hole — the part’s legs go through the board',
  name_notes: [
    'P2.54mm is the pitch — the centre-to-centre distance between adjacent pads.',
    'Vertical means the part stands up off the board, so its height adds to what the enclosure needs.',
  ],
  footprint_found: true,
  courtyard: { x_mm: 10.4, y_mm: 3.4 },
  model_ref: 'x.step', model_path: '/x.step', has_model: true,
}

beforeEach(() => {
  describeFootprintMock.mockReset().mockResolvedValue(HEADER)
})

describe('FootprintDetailView', () => {
  it("shows the library author's own description and the name decoding", async () => {
    render(<FootprintDetailView footprintId={HEADER.footprint_id} onClose={() => {}} />)

    expect(await screen.findByText(/2.54mm pitch, single row/)).toBeTruthy()
    expect(screen.getByText(/centre-to-centre distance/)).toBeTruthy()
    expect(screen.getByText(/stands up off the board/)).toBeTruthy()
  })

  it('reports a footprint whose library carries no description, rather than showing nothing', async () => {
    /** A personal or community library is not obliged to fill `descr` in, and
     *  an empty panel would read as a broken feature. */
    describeFootprintMock.mockResolvedValue({
      ...HEADER, description: null, tags: [], courtyard: null,
    })
    render(<FootprintDetailView footprintId={HEADER.footprint_id} onClose={() => {}} />)

    expect(await screen.findByText(/gives no description/)).toBeTruthy()
    // The name decoding still carries the answer the user came for.
    expect(screen.getByText(/centre-to-centre distance/)).toBeTruthy()
  })

  it('says a footprint with a model is measured automatically', async () => {
    render(<FootprintDetailView footprintId={HEADER.footprint_id} onClose={() => {}} />)

    expect(await screen.findByText(/height is measured automatically/)).toBeTruthy()
  })

  it('invents nothing for a name it does not recognise', async () => {
    describeFootprintMock.mockResolvedValue({ ...HEADER, name_notes: [] })
    render(<FootprintDetailView footprintId={HEADER.footprint_id} onClose={() => {}} />)

    await screen.findByText(/2.54mm pitch/)
    expect(screen.queryByText('What the name is telling you')).toBeNull()
  })
})

/** SPEC-334, second pass: "THT, DIP and all of the other abbreviations are not
 *  intuitive. Adding links or help info could save time for the user to look
 *  up unfamiliar ones that Kicad uses in naming." */
describe('FootprintDetailView abbreviations', () => {
  it('expands the abbreviations in the name it was given', async () => {
    render(<FootprintDetailView footprintId={HEADER.footprint_id} onClose={() => {}} />)

    await screen.findByText(/2.54mm pitch/)
    expect(screen.getByText('What the abbreviations mean')).toBeTruthy()
  })

  it('expands a package abbreviation the user cannot be expected to know', async () => {
    describeFootprintMock.mockResolvedValue({
      ...HEADER,
      footprint_id: 'Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm',
      library: 'Package_DFN_QFN',
      name: 'VQFN-16-1EP_3x3mm_P0.5mm',
    })
    render(
      <FootprintDetailView
        footprintId="Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm"
        onClose={() => {}}
      />,
    )

    // VQFN from the name, and DFN and QFN from the library it lives in --
    // all three are terms the reader is looking at.
    expect((await screen.findAllByText(/no legs sticking out/)).length).toBeGreaterThan(1)
    // Composed from a height letter and a family, and says so.
    expect(screen.getByText(/read as V \+ QFN/)).toBeTruthy()
    expect(screen.getByText(/Very thin QFN/)).toBeTruthy()
  })

  it('offers the whole vocabulary to browse, closed by default', async () => {
    render(<FootprintDetailView footprintId={HEADER.footprint_id} onClose={() => {}} />)

    const open = await screen.findByText('All KiCad terms')
    expect(screen.queryByPlaceholderText('THT, QFN, 0805…')).toBeNull()

    fireEvent.click(open)
    expect(screen.getByPlaceholderText('THT, QFN, 0805…')).toBeTruthy()
  })

  it('still explains the abbreviations when the footprint file cannot be read', async () => {
    /** The vocabulary is fixed, so it does not depend on the library being
     *  installed -- which is exactly when a user is most stuck. */
    describeFootprintMock.mockRejectedValue(new Error('no such library'))
    render(
      <FootprintDetailView footprintId="Package_DIP:DIP-8_W7.62mm" onClose={() => {}} />,
    )

    expect(await screen.findByText(/Could not read this footprint/)).toBeTruthy()
    expect(screen.getByText('All KiCad terms')).toBeTruthy()
  })
})

