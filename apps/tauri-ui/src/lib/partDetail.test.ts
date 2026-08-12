import { beforeEach, describe, expect, it, vi } from 'vitest'

const submitJobMock = vi.fn()
const dispatchMock = vi.fn()

vi.mock('./ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
  dispatch: (...args: unknown[]) => dispatchMock(...args),
}))

const { extractPartDetail, saveConfirmedPart, exportSymbol } = await import('./partDetail')

function fakeJobHandle<T>(result: Promise<T>) {
  result.catch(() => {})
  return { jobId: 'job_1', result, onUpdate: () => () => {}, cancel: vi.fn() }
}

function ok(result: unknown) {
  return { jsonrpc: '2.0' as const, id: 1, result }
}

function fail(message: string) {
  return { jsonrpc: '2.0' as const, id: 1, error: { code: -32000, message } }
}

beforeEach(() => {
  submitJobMock.mockReset()
  dispatchMock.mockReset()
})

describe('extractPartDetail', () => {
  it('submits kicad.generate_component and returns the real extracted schema', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))

    await expect(extractPartDetail('ATtiny85')).resolves.toEqual(schema)
    expect(submitJobMock).toHaveBeenCalledWith('kicad.generate_component', { part_number: 'ATtiny85' })
  })
})

describe('saveConfirmedPart', () => {
  it('dispatches library.save_confirmed_part with the candidate and extraction', async () => {
    const candidate = {
      part_number: 'ATtiny85', manufacturer: 'Microchip', package: 'DIP-8',
      datasheet_url: 'https://example.com/x.pdf', confidence: 'high' as const, rationale: 'r',
    }
    const extraction = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    const saved = { part: { part_id: 'ATtiny85' }, symbol: { symbol_id: 'SOIC-8_0pin' } }
    dispatchMock.mockResolvedValueOnce(ok(saved))

    await expect(saveConfirmedPart(candidate, extraction)).resolves.toEqual(saved)
    expect(dispatchMock).toHaveBeenCalledWith('library.save_confirmed_part', { candidate, extraction })
  })

  it('throws on a daemon error rather than silently dropping the save', async () => {
    dispatchMock.mockResolvedValueOnce(fail('Part is missing provenance for required field(s): package.'))

    await expect(
      saveConfirmedPart(
        { part_number: 'X', manufacturer: 'X', package: 'X', datasheet_url: 'https://x', confidence: 'low', rationale: 'r' },
        { part_number: 'X', package: 'X', pins: [] },
      ),
    ).rejects.toThrow('missing provenance')
  })
})

describe('exportSymbol', () => {
  it('dispatches library.export_symbol and returns the real path', async () => {
    dispatchMock.mockResolvedValueOnce(ok({ path: '/storage/library/symbols/SOIC-8_8pin.kicad_sym' }))

    await expect(exportSymbol('SOIC-8_8pin')).resolves.toBe('/storage/library/symbols/SOIC-8_8pin.kicad_sym')
    expect(dispatchMock).toHaveBeenCalledWith('library.export_symbol', { symbol_id: 'SOIC-8_8pin' })
  })
})
