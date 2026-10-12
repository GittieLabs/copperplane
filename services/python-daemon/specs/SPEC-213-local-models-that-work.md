---
id: SPEC-213
title: "Local Models That Actually Work"
status: Draft
type: Feature
created: 2026-10-11
last_updated: 2026-10-11
target_version: v0.7.1
location: "services/python-daemon/specs/SPEC-213-local-models-that-work.md"
parent_spec: "SPEC-208-provider-records-and-model-roles.md"
child_specs: []
user_facing: true
---

# SPEC-213: Local Models That Actually Work

## 1. Executive Summary & Goals

*   **High-Level Goal:** A maker with no API key can pick Ollama, during first-run setup or in
    Settings, and then get explanations, part lookup and chat from a local model. Today none of
    those work. `CTX-408.9` Phase 7 drove the frozen v0.7.0 sidecar against a real local Ollama
    and found four separate defects, listed below. Each one alone is enough to stop the local path.
    1. **The roles are not the source of truth.** Settings → Model roles writes `provider_roles`,
       but `llm.chat` and every agent-backed route still read the legacy `llm_provider` field. That
       field defaults to Anthropic. A user who picked Ollama has chat calling Anthropic and
       failing with a raw auth error.
    2. **The Ollama preset's model can't do the work.** `llama3.2:1b` honestly declares
       `tool_use: false, strict_json: false`. Every agent except `datasheet_guidance_synthesis`
       needs one or the other, so the capability gate (SPEC-208 §2.4) correctly refuses them all.
    3. **The refusals are mislabelled.** A capability refusal in part lookup comes out as
       *"Extraction did not return valid JSON … unusually long pin list. Trying again often
       works"*. The cause is wrong, and retrying cannot help. With no provider at all, a check's
       summary embeds the Anthropic SDK's raw *"Could not resolve authentication method"*.
    4. **First-run setup has no way to choose Ollama.** `GuidedSetup.tsx` lists only key-based
       providers, and the "no provider" requirement only counts keys.
*   **Business / Technical Value:** The outreach plan (*Copperplane: Reaching Makers*) sends makers
    who have no paid API key. Right now the honest answer for them is "the checks run, the
    explanations don't" (`docs/site/src/content/docs/install.md`). This spec changes that answer.
*   **Non-Goals:**
    *   No per-model capability database. A record still declares one set of `capabilities` (SPEC-208
        §2.4: a declaration is a claim, not a measurement). The claim changes because the preset's
        default model changes.
    *   Copperplane does not pull models itself. Pulling is a multi-GB download, and the user
        starts it. The app tells them the exact command.
    *   No managed or hosted access. That is SPEC-404.

## 2. System Architecture & Design Choices

### 2.1 Every route resolves through `provider_roles`

*   `llm.chat` resolves through `llm_providers.resolve()` with `model_role="reasoning"`. It no
    longer uses the legacy `llm_provider`/`_DEFAULT_PROVIDER` chain. An explicit per-call
    `provider`/`model` still wins, which is SPEC-208 §2.3.2 rule 1.
*   The agent-backed routes stop passing `CONFIG["llm_provider"]`/`["llm_model"]` into `resolve()`
    as an explicit override. That override outranked `provider_roles`, which is exactly the bug in
    §1 item 1. A config that has only the legacy fields still works, because
    `migrate_legacy_config` (SPEC-208 §2.5) already maps them onto both roles. So the legacy
    fields still count, but only where SPEC-208 said they should: when no roles are saved.
*   Provenance written beside a result (`extraction_provenance`, a stored review's
    `provider`/`model`) records the provider and model the role actually resolved to, not the
    legacy field.

### 2.2 Ollama's preset default is a model that can do the work

*   Ollama's preset `models` move from `llama3.2:1b` to `qwen2.5:7b` for both roles, with
    `capabilities: {tool_use: true, strict_json: true}`. A live run against a real local Ollama
    has to confirm this before it ships (SPEC-208 §2.2.2), on the frozen sidecar, for chat,
    explanations and part lookup.
*   SPEC-209's merge-over-preset means existing installs move with the preset. Their saved config
    holds only deltas, and the old default was never a delta.

### 2.3 Setup errors say what is wrong and where to fix it

*   A new `ModelSetupError(LLMProviderError)` covers the two cases where the user's setup is the
    cause: (a) the record bound to a role needs a key and none is saved, raised by `resolve()`
    *before* any SDK client is built, so no SDK text can reach the user; (b) the capability gate
    refuses an agent. Its message names the problem in plain words and points to Settings →
    Model roles.
*   `component_pipeline.generate_component` raises a resolve-time `ModelSetupError` as itself,
    not as the JSON-parse error that its empty output would otherwise turn into, and does not
    retry it.
*   `_explain_or_report_plainly` uses the `ModelSetupError` message in the check summary, not
    the raw exception text.

### 2.4 First-run setup and the requirements banner know about local models

*   `daemon.get_capabilities` gains `llm_ready: bool`. It is true when every role resolves to a
    record that needs no key (local) or has its key saved. The check is cheap: no network call,
    per that function's contract. `requirements.ts` uses it for the "No AI provider is
    configured" requirement, and falls back to `llm_providers.length` for an older daemon.
*   `GuidedSetup.tsx` offers *"Run a model on this computer (Ollama)"* next to the key-based
    providers. Choosing it probes `localhost:11434` with the existing `llm.probe_endpoint` and
    shows one of three states:
    *   **Ollama not answering:** a link to download Ollama, plus "Check again".
    *   **Ollama answering, `qwen2.5:7b` not pulled:** the exact `ollama pull qwen2.5:7b` command
        with a copy button, plus "Check again".
    *   **Ready:** "Use Ollama", which calls `bindBothRolesTo('ollama')` and continues.

### 2.5 Cross-module impacts

*   `services/python-daemon`: `daemon.py`, `llm_providers.py`, `component_pipeline.py`. The
    sidecar must be re-frozen: everything in this spec ships inside it.
*   `apps/tauri-ui`: `GuidedSetup.tsx`, `requirements.ts`, `settings.ts` (the `llm_ready` type).
*   Docs: `docs/site/src/content/docs/install.md` and `docs/release-notes/v0.7.0.md`.

## 3. Known Constraints & Risks

*   **A 7B model is a floor, not a match for a frontier model.** Its explanations will be
    plainer, and its part extraction less reliable on long pin lists. The capability claim means
    it can hold the contract, not that it matches Claude.
*   **The record's capabilities are a claim about its default model.** A user who overrides
    Ollama's model to `llama3.2:1b` keeps a record that claims `strict_json`. SPEC-208 §2.4
    already accepts that a declaration catches honest mismatches, not optimistic ones.
*   **Memory.** A 7B model at Q4 needs about 5 GB resident. On an 8 GB Mac that competes with
    KiCad. The docs say so.
*   **Verified on one machine only:** an Apple-silicon Mac with 64 GB, running Ollama 0.40.0.

## 4. Module Map & Reference Links

```text
[SPEC-208 Provider Records & Model Roles](SPEC-208-provider-records-and-model-roles.md)
   └── [This Spec](SPEC-213-local-models-that-work.md)
          └── [Context 213.1](../context/CTX-213.1-local-models-that-work.md)
```

## 5. User & Interaction

*   **Product Stage:** First run and Settings, before the user's first explanation, part lookup or
    chat.
*   **What the user is trying to accomplish:** Use Copperplane's AI features without paying for an
    API key, on a model running on their own computer.
*   **What the user sees and does:** In first-run setup they choose "Run a model on this computer
    (Ollama)". The app tells them whether Ollama is running and whether the model is pulled,
    gives them the one command to run if it isn't, and then binds it. After that, a check's
    explanations, a part lookup and the Overview chat all answer from the local model. If
    nothing capable is set up, those surfaces say so and point to Settings → Model roles, not to
    a pin list or an SDK error.
