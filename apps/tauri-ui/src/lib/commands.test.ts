import { describe, expect, it } from 'vitest'
import { parseCommand } from './commands'

describe('parseCommand', () => {
  it('TEST-001: recognizes "generate <part number>"', () => {
    expect(parseCommand('generate ATtiny85')).toEqual({ type: 'generate', partNumber: 'ATtiny85' })
  })

  it('TEST-001: is case-insensitive and tolerant of surrounding/extra whitespace', () => {
    expect(parseCommand('  GENERATE   ATtiny85  ')).toEqual({
      type: 'generate',
      partNumber: 'ATtiny85',
    })
  })

  it('TEST-001: recognizes "inject" exactly, case-insensitive, whitespace-tolerant', () => {
    expect(parseCommand('inject')).toEqual({ type: 'inject' })
    expect(parseCommand('  INJECT  ')).toEqual({ type: 'inject' })
  })

  it('TEST-001: a near-miss (extra words) falls through to a plain chat turn, not a partial match', () => {
    expect(parseCommand('please generate a footprint for BME280')).toEqual({
      type: 'chat',
      message: 'please generate a footprint for BME280',
    })
    expect(parseCommand('inject it now')).toEqual({ type: 'chat', message: 'inject it now' })
  })

  it('TEST-001: "generate" with no part number falls through to a plain chat turn', () => {
    expect(parseCommand('generate')).toEqual({ type: 'chat', message: 'generate' })
    expect(parseCommand('generate   ')).toEqual({ type: 'chat', message: 'generate' })
  })

  it('TEST-001: an unrelated message is a plain chat turn', () => {
    expect(parseCommand('what does pin 3 do on that part?')).toEqual({
      type: 'chat',
      message: 'what does pin 3 do on that part?',
    })
  })
})
