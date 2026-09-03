import { render, screen } from '@testing-library/react'
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
