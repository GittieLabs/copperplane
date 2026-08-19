import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OverviewDashboard } from './OverviewDashboard'
import type { Project } from '../lib/projects'

describe('OverviewDashboard', () => {
  it('TEST-005: renders "Not yet checked this session" for every area on a fresh project', () => {
    render(<OverviewDashboard project={null} chatHistory={[]} />)

    expect(screen.getByTestId('status-card-pcb').textContent).toContain('Not yet checked this session')
    expect(screen.getByTestId('status-card-schematic').textContent).toContain('Not yet checked this session')
    expect(screen.getByTestId('status-card-enclosure').textContent).toContain('Not yet checked this session')
    expect(screen.getByTestId('status-card-components').textContent).toContain('Not yet checked this session')
  })

  it('TEST-006: renders a real Enclosure summary from a populated last_results.enclosure', () => {
    const project: Project = {
      name: 'test-project',
      last_results: { enclosure: { wall_thickness_mm: 2, standoff_height_mm: 5 } },
    }

    render(<OverviewDashboard project={project} chatHistory={[]} />)

    expect(screen.getByTestId('status-card-enclosure').textContent).toContain('2mm walls, 5mm standoffs')
    expect(screen.getByTestId('status-card-pcb').textContent).toContain('Not yet checked this session')
  })

  it('renders the merged activity feed, most recent first', () => {
    const project: Project = {
      name: 'test-project',
      export_history: [{ area: 'enclosure', dest_path: '/out/x.step', exported_at: '2026-08-19T10:00:00.000Z' }],
    }

    render(
      <OverviewDashboard
        project={project}
        chatHistory={[{ role: 'user', content: 'hello', timestamp: '2026-08-19T09:00:00.000Z' }]}
      />,
    )

    const items = screen.getByTestId('activity-feed').querySelectorAll('li')
    expect(items).toHaveLength(2)
    expect(items[0].textContent).toBe('Exported enclosure to /out/x.step')
    expect(items[1].textContent).toBe('You: hello')
  })

  it('renders no activity section when there is nothing to show yet', () => {
    render(<OverviewDashboard project={null} chatHistory={[]} />)

    expect(screen.queryByTestId('activity-feed')).toBeNull()
  })
})
