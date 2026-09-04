---
id: SPEC-324
title: "Model Identity Verification"
status: Completed
type: Feature
created: 2026-08-27
last_updated: 2026-09-03
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-324-model-identity-verification.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-324: Model Identity Verification

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let a user pick a model from what their provider actually offers, and check
    an id they typed themselves, before it fails at call time. A dropdown of real models where the
    provider can list them, free text everywhere, and an on-demand Validate that works either way.

*   **Business / Technical Value:** Today the model field is a bare text box. A typo saves cleanly,
    the provider record looks configured, and the first sign of trouble is a vendor error inside an
    AI feature — the same "looks fine, fails later" shape as `SPEC-407`'s sidecar, one layer up.
    `SPEC-322` §2.1 already surfaces a role bound to a provider with **no** model; this covers the
    case where a model id is present but wrong.

*   **This spec exists because `SPEC-322` §1's non-goal was based on a false premise.** That spec
    declined validation on the grounds that *"the app does not know a vendor's model list, and
    guessing would be worse than the honest text field."* Checked directly against the installed
    SDKs on 2026-08-27, all three provider kinds this repo has can list models, and two can
    retrieve one by id:

    | `kind` | `models.list` | `models.retrieve` |
    | :--- | :--- | :--- |
    | `anthropic` | yes | yes |
    | `openai_compat` | yes | yes |
    | `google` | yes | not probed |

    The app *can* know. `retrieve` in particular makes Validate cheap and side-effect free — an
    existence check rather than a completion, so it costs no tokens where supported.

*   **Non-Goals:**
    *   **Not a curated model catalogue shipped in the repo.** A hardcoded list goes stale the week
        a vendor ships something, and this project has already been bitten by a second copy of
        facts drifting (`CTX-322.1`'s agent-list reasoning).
    *   **Not blocking save on validation.** The honest text field stays the floor. Validation
        informs; it never gates. A private deployment, a brand-new model, or an offline machine
        must all remain configurable.
    *   **Not automatic validation.** On demand only — see §2.3.
    *   **Not pricing, context-window or capability metadata.** Vendors expose different subsets and
        the app has no use for most of it. `SPEC-208` §2.4's declared capabilities stay a user
        claim, not a fetched fact.
    *   **Not model selection for the managed tier.** `SPEC-404`'s gateway decides what it serves;
        a subscriber is not choosing model ids.

## 2. System Architecture & Design Choices

### 2.1 One daemon route, per record, on demand

**Decided: a `llm.list_models` route taking a provider record and returning the models that
provider actually offers, or an explicit "this provider cannot list".** The daemon already builds a
real client per `kind` (`_build_provider_from_record`), so listing reuses that construction rather
than inventing a second way to reach a vendor.

The rejected alternative was calling vendor APIs from the frontend. It would put the API key in the
renderer and bypass `SPEC-106`'s spawn-time secret channel — the same reason `CTX-320.1` rejected
it for the managed account read.

"Cannot list" is a real, first-class answer, not an error. `openai_compat` is the widest kind — it
covers Ollama, the managed gateway and any custom base URL — and what is on the other end may not
implement `/v1/models` at all.

### 2.2 A combobox, not a dropdown

**Decided: listed models are suggestions, and the field stays typeable.** Every path that produces
a valid model id the list does not contain must still work: a private deployment, a model newer
than the SDK's own list, a compat server with its own naming. This is the maintainer's own framing
— a dropdown *with* the option to add something not in it.

When no list is available the control degrades to exactly today's text field, so this is never
worse than what ships now.

### 2.3 Validate is on demand, and so is listing

**Decided: nothing calls a vendor unless the user asks.** The list is fetched when the dropdown is
opened; Validate runs when clicked. No startup cost, no call on save, no background refresh.

`SPEC-107` §3 already holds this line for capability detection — "cheap, non-blocking checks only"
— and a network round trip to a paid vendor is neither. Automatic validation would also spend real
quota on every save, which is a poor trade for catching a typo a second earlier.

Validate prefers `models.retrieve` where the kind supports it: an existence check that costs
nothing, rather than a completion that costs tokens.

### 2.4 Cross-Module Impacts

*   `services/python-daemon` — `llm.list_models` and a validate path, both per `kind`; an explicit
    "cannot list" result.
*   `apps/tauri-ui` — the combobox and Validate button in `SPEC-321`'s record editor.
*   `SPEC-322` — its §1 non-goal declining validation is superseded by this spec.
*   No schema change. `ProviderRecord.models` still holds two strings.

## 3. Known Constraints & Risks

*   **Listing needs a configured key and a reachable provider.** Before a key is saved, or offline,
    the dropdown is empty. The field must stay usable in that state, which is why §2.2 makes free
    text the floor rather than a fallback.
*   **`openai_compat` behaviour varies by server**, and it is the kind most users will hit through
    Ollama. Ollama lists locally pulled models, which is genuinely useful and also means the list
    is a different *kind* of thing than a vendor catalogue — local availability, not entitlement.
*   **Vendor lists can be long.** An OpenAI-compatible endpoint may return hundreds of entries,
    many irrelevant to chat. Filtering or search is a real design requirement, not polish.
*   **`retrieve` semantics differ per vendor**, and Google's was not probed. A validate path that
    assumes uniform behaviour will be wrong somewhere; each kind needs its own check confirmed
    against the real SDK, the way §1's table was.
*   **A model that exists is not a model that works.** Listing proves the id resolves, not that it
    supports tool use or strict JSON. `SPEC-208` §2.4's capability preflight remains the check that
    matters for whether an agent can actually run on it, and this must not be mistaken for it.
*   **Quota.** Even a cheap check is a call against someone's account. On-demand-only (§2.3) is the
    mitigation, and any future automatic validation should reopen this deliberately.

## 4. Module Map & Reference Links

```text
[SPEC-300 Product IA & Interaction Model](SPEC-300-product-ia-interaction-model.md)
   ├── [SPEC-322 Model Role Legibility](SPEC-322-model-role-legibility.md)
   ├── [SPEC-323 Advanced Per-Agent Configuration](SPEC-323-advanced-agent-configuration.md)
   └── [This Spec](SPEC-324-model-identity-verification.md)
```

*   [SPEC-321 Provider Configuration UI](SPEC-321-provider-configuration-ui.md) — owns the record
    editor this changes.
*   [SPEC-208 Provider Records & Model Role Resolution](../../../services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md)
    — owns `kind` and the client construction listing reuses, and §2.4's capability preflight,
    which this does not replace.
*   [SPEC-106 Configuration & Secrets Store](../../../specs/SPEC-106-configuration-secrets-store.md)
    — why listing runs in the daemon and not the renderer.
*   [SPEC-107 Structured Logging & Diagnostics](../../../specs/SPEC-107-structured-logging-diagnostics.md)
    — §3's cheap-checks-only rule, which is why nothing here runs at startup.

## 5. User & Interaction

*   **Product Stage:** Settings, in `SPEC-321`'s provider record editor, on the reasoning and fast
    model fields.
*   **What the user is trying to accomplish:** Set a model they can be confident is real, without
    memorising vendor id strings or discovering the typo later inside a failing AI feature.
*   **What the user sees and does:** Each model field offers the models that provider actually
    reports, and still accepts anything typed. A Validate button next to it reports whether the
    current id resolves — plainly, including when the provider could not be reached and why.
    Nothing is validated until asked, and a field that fails validation still saves.
