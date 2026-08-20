---
name: datasheet_guidance
description: Extracts and validates cited design guidance for one category from real datasheet page excerpts
trigger: manual
nodes:
  - id: extract
    agent: datasheet_guidance_extraction
  - id: validate
    handler: validate_datasheet_guidance
    inputs:
      message: "extract.text"
---
Extracts cited guidance items for a single category via the configured LLM (the `extract` node),
then validates each item deterministically -- the cited page must be a real page this category's
candidate pages actually included, and the quote must actually appear on that page's real
extracted text (the `validate` node, plain Python, no LLM call, no network) -- before an item is
trusted. An item that fails either check is dropped, not repaired or promoted (SPEC-205 §2.2's own
explicit assembly rule) -- a category with some invalid items still returns its real, valid ones,
rather than failing the whole category closed. See SPEC-205 for the full rationale.

Run once per real category with at least one candidate page (`datasheet_guidance.py`'s own
orchestration, not this file) -- a category with zero candidate pages never reaches this workflow
at all, matching `component_pipeline.explain_violations`'s own "empty input, no LLM call" pattern.
