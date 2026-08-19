import { describe, it, expect } from 'vitest'
import { buildAreaStatuses, mergeActivityFeed } from './overview'

describe('buildAreaStatuses', () => {
  it('TEST-004: reports a real Enclosure summary when last_results.enclosure exists', () => {
    const statuses = buildAreaStatuses({
      enclosure: { wall_thickness_mm: 2, standoff_height_mm: 5, glb_path: '/x/enclosure.glb' },
    })

    const enclosure = statuses.find((s) => s.area === 'enclosure')
    expect(enclosure).toEqual({ area: 'enclosure', checked: true, summary: '2mm walls, 5mm standoffs' })
  })

  it('reports checked: false for every area with no last_results entry, honest not omitted', () => {
    const statuses = buildAreaStatuses(undefined)

    expect(statuses).toEqual([
      { area: 'pcb', checked: false },
      { area: 'schematic', checked: false },
      { area: 'enclosure', checked: false },
      { area: 'components', checked: false },
    ])
  })

  it('reports checked: false for PCB/Schematic/Components even when Enclosure has real data', () => {
    const statuses = buildAreaStatuses({ enclosure: { wall_thickness_mm: 3 } })

    expect(statuses.find((s) => s.area === 'pcb')).toEqual({ area: 'pcb', checked: false })
    expect(statuses.find((s) => s.area === 'schematic')).toEqual({ area: 'schematic', checked: false })
    expect(statuses.find((s) => s.area === 'components')).toEqual({ area: 'components', checked: false })
  })
})

describe('mergeActivityFeed', () => {
  it('TEST-002: merges conversation turns and export_history into one descending time-ordered list', () => {
    const feed = mergeActivityFeed(
      [
        { role: 'user', content: 'hello', timestamp: '2026-08-19T10:00:00.000Z' },
        { role: 'assistant', content: 'hi', timestamp: '2026-08-19T10:00:01.000Z' },
      ],
      [{ area: 'enclosure', dest_path: '/out/enclosure.step', exported_at: '2026-08-19T10:30:00.000Z' }],
    )

    expect(feed.map((item) => item.kind)).toEqual(['export', 'chat', 'chat'])
    expect(feed[0]).toEqual({
      kind: 'export',
      timestamp: '2026-08-19T10:30:00.000Z',
      summary: 'Exported enclosure to /out/enclosure.step',
    })
    expect(feed[1].summary).toBe('Assistant: hi')
    expect(feed[2].summary).toBe('You: hello')
  })

  it('TEST-003: a turn with no timestamp sorts to the end, not first, and does not throw', () => {
    const feed = mergeActivityFeed(
      [
        { role: 'user', content: 'legacy turn, no timestamp' },
        { role: 'user', content: 'new turn', timestamp: '2026-08-19T10:00:00.000Z' },
      ],
      [],
    )

    expect(feed.map((item) => item.summary)).toEqual(['You: new turn', 'You: legacy turn, no timestamp'])
    expect(feed[1].timestamp).toBeNull()
  })

  it('returns an empty feed for a project with no chat and no exports yet', () => {
    expect(mergeActivityFeed([], [])).toEqual([])
  })
})
