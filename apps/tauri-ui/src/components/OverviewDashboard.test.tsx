import { describe, it } from 'vitest'

// CTX-313.1: real tests land alongside the implementation of
// `OverviewDashboard.tsx`. Stubbed now so `scripts/validate_spec_context.py`'s
// Testing Requirements Matrix path check has a real file to point at before
// that component exists.
describe('OverviewDashboard (CTX-313.1, pending implementation)', () => {
  it.todo('renders a real status card for Enclosure when Project.last_results.enclosure exists')
  it.todo('renders "Not yet checked this session" for PCB/Schematic/Components when absent')
  it.todo('renders the merged activity feed above/around the existing chat surface')
})
