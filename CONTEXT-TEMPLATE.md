---

### Template 2: `CONTEXT-TEMPLATE.md`

```markdown
---
id: CTX-000.1
spec_ref: "../specs/SPEC-000.md"
title: "Implementation Context: Short Feature Name"
status: Planned | In-Progress | Review | Completed
author: "Name / AI Agent"
branch: "feat/CTX-000.1-short-name"
created: YYYY-MM-DD
last_touched: YYYY-MM-DD
version_included: "v0.1.0"
commit_hashes:
  - "a1b2c3d - Initial boilerplate"
  - "e4f5g6h - Added unit tests"
---

# CTX-000.1: Implementation Context: Short Feature Name

> **Spec Reference:** Links to [SPEC-000](../specs/SPEC-000.md)

## 1. Feature Definition & Execution Plan
Break down the implementation into discrete, reviewable phases.

### Phase 1: Foundation & Interfaces
*   [x] Define data types and interfaces.
*   [ ] Set up module scaffolding.

### Phase 2: Core Logic & Unit Testing
*   [ ] Implement main handler logic.
*   [ ] Write unit tests for happy and edge-case paths.

---

## 2. Testing Requirements Matrix

| Test ID | Test Description | Test File Location | Status |
| :--- | :--- | :--- | :--- |
| `TEST-001` | Validates valid JSON-RPC parsing | `tests/rpc_test.rs` | ✅ Passed |
| `TEST-002` | Handles broken pipe graceful crash | `tests/process_test.rs` | ⏳ Pending |

---

## 3. Implementation Log & Commit History

| Date | Phase | Description | Commit Hash |
| :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Phase 1 | Initial JSON parser interface | `a1b2c3d` |
| YYYY-MM-DD | Phase 2 | Unit tests for malformed JSON | `e4f5g6h` |

---

## 4. Plan Drift & Architectural Changes
*Document any deviations from the original SPEC definitions encountered during build time.*

*   **Deviation 1:** Swapped `std::sync::mpsc` for `tokio::sync::mpsc`.
    *   *Reasoning:* Required async support for Tauri event loop.
    *   *Impact:* Spec SPEC-000 updated on YYYY-MM-DD to reflect Tokio runtime usage.