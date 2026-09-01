---
id: SPEC-209
title: "Provider Parameter Contract & Model Defaults"
status: Draft
type: Feature
created: 2026-08-31
last_updated: 2026-08-31
target_version: v0.4.0
location: "services/python-daemon/specs/SPEC-209-provider-parameter-contract-and-model-defaults.md"
parent_spec: "SPEC-208-provider-records-and-model-roles.md"
child_specs: []
user_facing: true
---

# SPEC-209: Provider Parameter Contract & Model Defaults

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give this app a way to send provider-specific parameters — reasoning
    effort first, anything a vendor adds later — without predicting what any model supports, and
    give shipped model defaults a path to move on app update without overwriting what a user
    deliberately chose. The parameter channel is added to AgentFlow, not worked around here.

*   **Business / Technical Value:** `SPEC-323` set out to add per-agent reasoning effort and found
    two walls, both recorded in `CTX-323.1` §4:

    1.  **There is no channel.** AgentFlow's `chat()` takes a fixed signature on all three
        providers — `(messages, system, tools, max_tokens, temperature)` — with no `**kwargs`.
        Nothing in this repository can send a parameter the framework does not already name.
    2.  **The one mechanism that exists is a hack.** AgentFlow already supports effort for
        `anthropic` and `google` by parsing a `-low`/`-medium`/`-high` **suffix off the model
        name** and calling `rsplit('-', 1)`. It is undiscoverable, silently a no-op on
        `openai_compat`, would be reported as an unlisted model by `SPEC-324`'s validation, and
        silently truncates any legitimate model whose real name ends in one of those three words.

    The maintainer's decision, which sets this spec's whole shape:

    > "It's still possible to pick a model that doesn't support reasoning and apply a flag/param
    > only to discover it does nothing. Or that the convention changes. [...] If this same user
    > were using Agentflow, they have complete control and are responsible for choosing models and
    > params. Therefore, we should expect users wanting to make model modifications to also have
    > the same responsibility."

    That resolves the hardest problem by declining it. The app does not need a capability model
    for every vendor's every parameter — an impossible thing to keep current. It needs good
    defaults, honest documentation, and a passthrough whose correctness the user owns.

*   **A second, pre-existing defect this spec must fix to deliver the first.** The app **cannot
    currently tell a shipped default from a user's choice.** `saveProviderConfig` persists all
    provider records as a whole — `SPEC-208` §2.5's own contract — and `_resolve_provider_records`
    does `records[record_id] = entry`, replacing a preset outright rather than merging. So the
    first time anyone opens Settings and saves, all five presets freeze into their `config.json`
    verbatim, and no future release can move any default for them. Verified against a real
    install on 2026-08-31. Updating defaults on app update is impossible until this changes.

*   **Non-Goals:**
    *   **Not a capability model of which models support which parameters.** Explicitly rejected,
        per the reasoning above. The app states defaults and documents them; it does not promise a
        parameter will do anything on a model the user chose.
    *   **Not per-agent overrides, the Advanced surface, or reset-all.** `SPEC-323` owns those.
        This spec provides the transport and the defaults model they depend on.
    *   **Not model validation.** `SPEC-324` owns it. This spec must not break it — which the
        model-suffix convention would.
    *   **Not a general AgentFlow redesign.** One parameter added to one protocol method, plus
        removing the suffix hack it replaces.
    *   **Not automatic parameter tuning or cost estimation.**

## 2. System Architecture & Design Choices

### 2.1 One explicit passthrough, not `**kwargs`

**Decided: `chat(..., params: dict[str, Any] | None = None)` on AgentFlow's provider protocol,
merged into the vendor call verbatim.**

Bare `**kwargs` was considered and rejected. It removes the boundary between "an AgentFlow
parameter" and "a vendor parameter", so a misspelled known argument — `temprature=0.5` — stops
being an error and silently becomes a vendor argument that either 400s at call time or is quietly
ignored. That is the same "looks fine, fails later" shape `SPEC-407` and `SPEC-324` were both
written about. An explicit dict keeps the typed core checkable, keeps the escape hatch documented,
and makes "the user owns what is in here" a visible property rather than an implicit one.

The typed parameters that exist today (`tools`, `max_tokens`, `temperature`) stay exactly as they
are. This is additive; no existing call changes.

### 2.2 The model-suffix convention is removed, not deprecated

**Decided: delete `-low`/`-medium`/`-high` parsing from both providers in the same AgentFlow
release that adds `params`.**

It is a naming-convention hack whose failure mode is silent: `rsplit('-', 1)` mangles any
legitimate model ending in those words, and the app has no way to know it happened. Keeping it
alongside an explicit parameter would leave two mechanisms for one concept, disagreeing whenever a
model name is unlucky.

Checked before deciding: no provider record in this repository's presets or in a real install's
`config.json` uses a suffix today (`claude-sonnet-5`, `gemini-flash-latest`, `gpt-4o`, `sonar`,
`llama3.2:1b`). So removal breaks nothing here. It is still a breaking change for any other
AgentFlow consumer, which is what the version bump is for.

### 2.3 Defaults are what the app ships; config stores only differences

**Decided: `config.json` holds only fields that differ from the shipped preset, and
`_resolve_provider_records` merges field-by-field instead of replacing the record.**

This makes "was this overridden?" structurally true rather than separately tracked. A field the
user never touched is simply absent, so a new release's preset value applies automatically with no
migration, no version stamp, and no marker that can drift from the data it describes.

Two alternatives were rejected. A `defaults_version` stamp cannot distinguish "never touched" from
"deliberately typed the same string as the current default", so it would silently overwrite a
choice the user made on purpose. A per-field provenance marker is a second source of truth about
the same data, and every writer has to maintain it correctly forever.

The cost is real and must be planned, not discovered: this changes `SPEC-208` §2.5's whole-record
save contract, the editor's save path, and needs a migration for installs that already froze all
five presets — which is every install that has opened Settings.

### 2.4 Defaults move on update; changed defaults appear in release notes

**Decided: shipped preset changes are a documented, release-noted event.** A user who never touched
a model gets the new default silently — that is the point of §2.3 — but a release that moves one
must say so, because the observable behaviour of their install changed without them acting.
`SPEC-402`'s release-notes generation is where that lands.

### 2.5 A models table in the docs, maintained as models change

**Decided: a `docs/` table of recommended models and parameters per provider — the shipped
defaults, plus one or two real Ollama models — and it is the source the presets are documented
from.** The table exists because §1's responsibility argument only works if the user has somewhere
to look. Recommendations without documentation is just an undocumented default.

### 2.6 Reset at two levels, and it never touches secrets

**Decided: reset-to-defaults per provider record, and a global revert that restores every default
without removing any configured API key.** Deleting a key on a settings reset would be a
destructive surprise, and keys are `SPEC-106`'s keychain concern rather than config data.

Under §2.3 reset is a deletion — remove the differing fields and the preset applies again — rather
than writing today's default into the record, which would re-pin it and defeat the mechanism.

### 2.7 Cross-Module Impacts

*   **AgentFlow** (`~/repos/agentflow`, `gittielabs-agentflow`) — `params` on the provider
    protocol and all three providers; suffix parsing removed; tests; changelog; version bump; PyPI
    release. Per the standing rule, fixed upstream rather than worked around here.
*   `services/python-daemon` — pin bump; field-by-field preset merge; delta-only writes; passing
    `params` through `chat()`; migration for already-frozen configs.
*   `apps/tauri-ui` — per-provider reset, global revert, and whatever surfaces `params`.
*   `docs/` — the models and parameters table.
*   `SPEC-208` — its §2.5 whole-record contract is amended by §2.3, not silently contradicted.
*   `SPEC-323` — unblocked by this; its Phase 1 is void until `params` exists.
*   `SPEC-324` — must keep working; §2.2 exists partly to protect it.
*   `SPEC-402` — release notes must carry changed defaults.

## 3. Known Constraints & Risks

*   **The migration is the risky part, not the feature.** Every existing install has all five
    presets written into `config.json`. Converting those to deltas means deciding, for each field,
    whether a value equal to the current preset was chosen or merely persisted — and that
    information is genuinely gone. Whatever this spec's contexts decide, they must state the
    assumption in the file rather than let it be inferred from behaviour.
*   **A passthrough parameter can be silently ignored by a vendor.** Accepted deliberately (§1).
    Verified live on 2026-08-31: a local Ollama accepted `reasoning_effort: "low"` and answered
    normally, neither honouring nor rejecting it. Whether Perplexity rejects it is **unverified** —
    checking spends real quota against a maintainer key, which `SPEC-324` §2.3 holds is not spent
    unasked. Contexts must treat a rejected parameter as a recoverable state.
*   **Two repositories, one behaviour.** The AgentFlow release must land, be published, and be
    pinned here before any consuming work can be verified end to end. A context that assumes the
    pin is a context that cannot be tested.
*   **`params` is an unvalidated surface reaching a network call.** It is user-authored config
    forwarded to a vendor SDK. Contexts should decide what, if anything, is refused — an
    `api_key` key inside `params`, for instance, would be a real hazard.

## 4. Module Map & Reference Links

*   `~/repos/agentflow/src/agentflow/providers/{anthropic,openai_compat,google_genai}.py`
*   `services/python-daemon/llm_providers.py` — `chat`, `_resolve_provider_records`,
    `_preset_records`, `migrate_legacy_config`
*   `services/python-daemon/requirements.txt` — the `gittielabs-agentflow` pin
*   `apps/tauri-ui/src/lib/settings.ts` — `saveProviderConfig`
*   `apps/tauri-ui/src/components/ProviderConfigEditor.tsx`
*   [SPEC-208](SPEC-208-provider-records-and-model-roles.md) — parent; §2.5 amended by §2.3
*   [SPEC-323](../../../apps/tauri-ui/specs/SPEC-323-advanced-agent-configuration.md) — blocked on this
*   [SPEC-324](../../../apps/tauri-ui/specs/SPEC-324-model-identity-verification.md) — protected by §2.2
*   [CTX-323.1](../../../apps/tauri-ui/context/CTX-323.1-agent-overrides-foundation.md) §4 — where both walls were found

## 5. User & Interaction

*   **Product Stage:** Configuration. Reached from Settings, after a user has a working install and
    wants to change what a provider actually runs.
*   **What the user is trying to accomplish:** Run a specific model with specific behaviour — a
    cheaper model, more reasoning effort on one task — and get back to a known-good state when an
    experiment does not work out. Secondarily: not be silently left behind on defaults they never
    chose.
*   **What the user sees and does:** In the provider editor, the model fields they already have,
    plus a place to set parameters the app does not name and a **Reset to defaults** for that
    provider. At the Settings level, a global revert that restores every default and leaves API
    keys untouched. The documentation table is what tells them which values are worth setting.
