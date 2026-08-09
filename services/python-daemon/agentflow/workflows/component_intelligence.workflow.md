---
name: component_intelligence
description: Extracts and validates a structured component schema from a part number
trigger: manual
nodes:
  - id: extract
    agent: component_extraction
  - id: validate
    handler: validate_component_schema
    inputs:
      message: "extract.text"
---
Extracts a component schema via the configured LLM (the `extract` node), then validates it
deterministically -- pin count matches the package, pitch is sane, courtyard encloses the pads
(the `validate` node, plain Python, no LLM call) -- before it can reach a real board. See
SPEC-202 for the full rationale.
