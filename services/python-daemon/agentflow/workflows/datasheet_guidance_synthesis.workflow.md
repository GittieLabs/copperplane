---
name: datasheet_guidance_synthesis
description: Writes a plain-language summary of one category's already-validated cited items
trigger: manual
nodes:
  - id: synthesize
    agent: datasheet_guidance_synthesis
---
A single-node workflow: given one category's already-validated cited items (produced by the real
`datasheet_guidance` workflow), writes a short plain-language paragraph explaining what they mean
for a maker/hobbyist building a project with this chip (SPEC-205 §2.1.1). No new citable facts are
introduced -- this is a grounded translation of already-cited evidence, not independent extraction.

Run once per real category with at least one validated item (`datasheet_guidance.py`'s own
orchestration, not this file) -- a category with zero validated items never reaches this workflow
at all, matching the main `datasheet_guidance` workflow's own "empty input, no LLM call" pattern.
