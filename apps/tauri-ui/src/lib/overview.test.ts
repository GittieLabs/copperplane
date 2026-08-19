import { describe, it, expect } from 'vitest'

// CTX-313.1: real tests land alongside the implementation of
// `mergeActivityFeed`/`buildAreaStatus` in `./overview.ts`. Stubbed now so
// `scripts/validate_spec_context.py`'s Testing Requirements Matrix path
// check has a real file to point at before that code exists.
describe('lib/overview (CTX-313.1, pending implementation)', () => {
  it.todo('merges conversation turns and export_history into one time-ordered feed')
  it.todo('sorts a turn with no timestamp (pre-CTX-313.1 legacy data) to the end, not first')
  it.todo('builds an area status summary from Project.last_results, honest about missing keys')
})
