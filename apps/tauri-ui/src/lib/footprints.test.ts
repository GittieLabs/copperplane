import { beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()
const submitJobMock = vi.fn()

vi.mock('./ipc', () => ({ dispatch: dispatchMock, submitJob: submitJobMock }))

const {
  searchCommunityFootprints,
  importCommunityFootprint,
  attachCommunityFootprintToPart,
  renderSymbolPreview,
  renderFootprintPreview,
} = await import('./footprints')

beforeEach(() => {
  dispatchMock.mockReset()
  submitJobMock.mockReset()
})

function fakeHandle<T>(result: T) {
  return { jobId: 'job_1', result: Promise.resolve(result), onUpdate: vi.fn(), cancel: vi.fn() }
}

describe('searchCommunityFootprints', () => {
  it('submits library.search_community_footprints and resolves the real candidates', async () => {
    const candidates = [
      {
        owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: 'footprints/x.pretty/y.kicad_mod',
        kind: 'footprint' as const, license: 'CC-BY-4.0', blob_sha: 'abc', download_url: 'https://example.com/y.kicad_mod',
      },
    ]
    submitJobMock.mockResolvedValueOnce(fakeHandle(candidates))

    await expect(searchCommunityFootprints('C_0201')).resolves.toEqual(candidates)
    expect(submitJobMock).toHaveBeenCalledWith('library.search_community_footprints', { query: 'C_0201' })
  })
})

describe('importCommunityFootprint', () => {
  const footprintCandidate = {
    owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: 'footprints/x.pretty/y.kicad_mod',
    kind: 'footprint' as const, license: 'CC-BY-4.0', blob_sha: 'abc', download_url: 'https://example.com/y.kicad_mod',
  }

  it('submits library.import_community_footprint with the real candidate fields and no symbol_name', async () => {
    const record = {
      footprint_id: 'sparkfun__SparkFun-KiCad-Libraries__y', pad_count: 4,
      provenance: { source: 'community_library', owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: footprintCandidate.path, license: 'CC-BY-4.0', blob_sha: 'abc' },
    }
    submitJobMock.mockResolvedValueOnce(fakeHandle(record))

    await expect(importCommunityFootprint(footprintCandidate)).resolves.toEqual(record)
    expect(submitJobMock).toHaveBeenCalledWith('library.import_community_footprint', {
      owner: 'sparkfun', repo: 'SparkFun-KiCad-Libraries', path: footprintCandidate.path,
      kind: 'footprint', license: 'CC-BY-4.0', download_url: footprintCandidate.download_url,
      blob_sha: 'abc', symbol_name: null,
    })
  })

  it('passes a real, chosen symbolName through to the route', async () => {
    const symbolCandidate = { ...footprintCandidate, kind: 'symbol' as const, path: 'symbols/x.kicad_sym' }
    submitJobMock.mockResolvedValueOnce(fakeHandle({ symbol_id: 'x__y__C', pin_count: 2, provenance: {} }))

    await importCommunityFootprint(symbolCandidate, 'C_0402')

    expect(submitJobMock).toHaveBeenCalledWith(
      'library.import_community_footprint',
      expect.objectContaining({ kind: 'symbol', symbol_name: 'C_0402' }),
    )
  })

  it('returns a real browse list (not a persisted record) when the daemon has no symbol_name to import yet', async () => {
    const symbolCandidate = { ...footprintCandidate, kind: 'symbol' as const, path: 'symbols/x.kicad_sym' }
    const browse = { symbols: [{ name: 'C_0402', pin_count: 2 }, { name: 'C_0603', pin_count: 2 }] }
    submitJobMock.mockResolvedValueOnce(fakeHandle(browse))

    await expect(importCommunityFootprint(symbolCandidate)).resolves.toEqual(browse)
  })
})

describe('attachCommunityFootprintToPart', () => {
  it('saves the part with the already-final community footprint_id', async () => {
    dispatchMock.mockResolvedValueOnce({ result: {} })
    const part = { part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', pins: [] }
    const record = { footprint_id: 'sparkfun__SparkFun-KiCad-Libraries__y', pad_count: 4, provenance: {} as never }

    const updated = await attachCommunityFootprintToPart(part as never, record)

    expect(updated.footprint_id).toBe('sparkfun__SparkFun-KiCad-Libraries__y')
    expect(dispatchMock).toHaveBeenCalledWith('library.save_part', { part: updated })
  })

  it('rejects a symbol record -- only a footprint can be attached to a Part this way', async () => {
    const part = { part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', pins: [] }
    const record = { symbol_id: 'x__y__C', pin_count: 2, provenance: {} as never }

    await expect(attachCommunityFootprintToPart(part as never, record)).rejects.toThrow(/Only a footprint/)
  })
})

describe('renderSymbolPreview', () => {
  it('submits library.render_symbol_preview and resolves the real SVG text', async () => {
    submitJobMock.mockResolvedValueOnce(fakeHandle({ svg: '<svg>symbol</svg>' }))

    await expect(renderSymbolPreview('SOIC-8_0pin')).resolves.toBe('<svg>symbol</svg>')
    expect(submitJobMock).toHaveBeenCalledWith('library.render_symbol_preview', { symbol_id: 'SOIC-8_0pin' })
  })
})

describe('renderFootprintPreview', () => {
  it('submits library.render_footprint_preview and resolves the real SVG text', async () => {
    submitJobMock.mockResolvedValueOnce(fakeHandle({ svg: '<svg>footprint</svg>' }))

    await expect(renderFootprintPreview('MyPCBLibs__MP1584EN_5V_Module')).resolves.toBe('<svg>footprint</svg>')
    expect(submitJobMock).toHaveBeenCalledWith('library.render_footprint_preview', {
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
  })
})
