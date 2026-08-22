import { beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()
const submitJobMock = vi.fn()

vi.mock('./ipc', () => ({ dispatch: dispatchMock, submitJob: submitJobMock }))

const {
  searchCommunityFootprints,
  importCommunityFootprint,
  attachCommunityFootprintToPart,
  attachFootprintToProjectOverride,
  attachCommunityFootprintToProjectOverride,
  generateFootprintForProjectOverride,
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

describe('attachFootprintToProjectOverride', () => {
  it('saves the real footprint record, then records it as this project\'s own override -- never re-saves the Part', async () => {
    dispatchMock.mockResolvedValueOnce({ result: {} }) // library.save_footprint
    dispatchMock.mockResolvedValueOnce({ result: { name: 'weather-pcb', footprint_overrides: { ATtiny85: 'MyPCBLibs__MP1584EN_5V_Module' } } }) // project.set_footprint_override (via setProjectFootprintOverride -> dispatch)
    const project = { name: 'weather-pcb' }
    const part = { part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', pins: [] }

    const footprintId = await attachFootprintToProjectOverride(project as never, part as never, 'MyPCBLibs', 'MP1584EN_5V_Module')

    expect(footprintId).toBe('MyPCBLibs__MP1584EN_5V_Module')
    expect(dispatchMock).toHaveBeenCalledWith('library.save_footprint', {
      footprint: { footprint_id: 'MyPCBLibs__MP1584EN_5V_Module', library: 'MyPCBLibs', footprint_name: 'MP1584EN_5V_Module' },
    })
    expect(dispatchMock).toHaveBeenCalledWith('project.set_footprint_override', {
      project_name: 'weather-pcb',
      part_id: 'ATtiny85',
      footprint_id: 'MyPCBLibs__MP1584EN_5V_Module',
    })
    // Real bug this guards against: the global Part must never be re-saved by this path.
    expect(dispatchMock).not.toHaveBeenCalledWith('library.save_part', expect.anything())
  })
})

describe('attachCommunityFootprintToProjectOverride', () => {
  it('records the already-imported footprint as this project\'s own override', async () => {
    dispatchMock.mockResolvedValueOnce({ result: { name: 'weather-pcb', footprint_overrides: { ATtiny85: 'sparkfun__SparkFun-KiCad-Libraries__y' } } })
    const project = { name: 'weather-pcb' }
    const part = { part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', pins: [] }
    const record = { footprint_id: 'sparkfun__SparkFun-KiCad-Libraries__y', pad_count: 4, provenance: {} as never }

    const footprintId = await attachCommunityFootprintToProjectOverride(project as never, part as never, record)

    expect(footprintId).toBe('sparkfun__SparkFun-KiCad-Libraries__y')
    expect(dispatchMock).toHaveBeenCalledWith('project.set_footprint_override', {
      project_name: 'weather-pcb',
      part_id: 'ATtiny85',
      footprint_id: 'sparkfun__SparkFun-KiCad-Libraries__y',
    })
    expect(dispatchMock).not.toHaveBeenCalledWith('library.save_part', expect.anything())
  })

  it('rejects a symbol record -- only a footprint can be attached this way', async () => {
    const project = { name: 'weather-pcb' }
    const part = { part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', pins: [] }
    const record = { symbol_id: 'x__y__C', pin_count: 2, provenance: {} as never }

    await expect(
      attachCommunityFootprintToProjectOverride(project as never, part as never, record),
    ).rejects.toThrow(/Only a footprint/)
  })
})

describe('generateFootprintForProjectOverride', () => {
  it('generates the real footprint, then records it as this project\'s own override -- never re-saves the Part', async () => {
    dispatchMock.mockResolvedValueOnce({
      result: {
        footprint_id: 'generated__ATtiny85',
        footprint_name: 'generated__ATtiny85',
        provenance: { source: 'generated_from_datasheet', generated_from_part_id: 'ATtiny85', verified: false },
      },
    }) // kicad.generate_footprint_from_part
    dispatchMock.mockResolvedValueOnce({ result: { name: 'weather-pcb', footprint_overrides: { ATtiny85: 'generated__ATtiny85' } } }) // project.set_footprint_override
    const project = { name: 'weather-pcb' }
    const part = { part_id: 'ATtiny85', manufacturer: 'Microchip', package: 'SOIC-8', pins: [] }

    const footprintId = await generateFootprintForProjectOverride(project as never, part as never)

    expect(footprintId).toBe('generated__ATtiny85')
    expect(dispatchMock).toHaveBeenCalledWith('kicad.generate_footprint_from_part', { part_id: 'ATtiny85' })
    expect(dispatchMock).toHaveBeenCalledWith('project.set_footprint_override', {
      project_name: 'weather-pcb',
      part_id: 'ATtiny85',
      footprint_id: 'generated__ATtiny85',
    })
    expect(dispatchMock).not.toHaveBeenCalledWith('library.save_part', expect.anything())
  })
})
