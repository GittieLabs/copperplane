---
name: router
routingRules:
  - if: "area == 'overview'"
    routeTo: chat_overview
  - if: "area == 'components'"
    routeTo: chat_components
  - if: "area == 'schematic'"
    routeTo: chat_schematic
  - if: "area == 'pcb'"
    routeTo: chat_pcb
  - if: "area == 'enclosure'"
    routeTo: chat_enclosure
fallback: chat_overview
llmFallback: false
---
SPEC-206 §2.5: there are exactly five real chat areas (Overview, Components, Schematic, PCB,
Enclosure), matching `SPEC-318` §2.3's own per-area scope table one for one. `llmFallback: false`
is deliberate, not the schema's own default -- a sixth, unrecognized area must be a hard error, not
an LLM guessing which of the five it most resembles (`PRODUCT-PLAN.md` §3.2's own "no silent
substitution" principle, applied to routing itself). `chat_agents.py`'s own `send()` validates
`area` against this same five-value set *before* ever calling this router, so `fallback` here is a
defensive value only -- a well-formed caller never reaches it in practice.
