---
id: SPEC-322
title: "Model Role Legibility in Settings"
status: In-Progress
type: Feature
created: 2026-08-27
last_updated: 2026-08-27
target_version: v0.2.1
location: "apps/tauri-ui/specs/SPEC-322-model-role-legibility.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-322: Model Role Legibility in Settings

## 1. Executive Summary & Goals

*   **High-Level Goal:** Make `SPEC-321`'s shipped provider screen explain itself. A person who has
    not read `SPEC-208` should be able to look at it and understand what a model role is, which
    provider and model answers each one, and what they can and cannot change.

*   **Business / Technical Value:** `SPEC-321` shipped on 2026-08-26 with every route real and its
    tests green. On 2026-08-27 the maintainer opened the resulting screen for the first time and
    reported: *"I see a reasoning with a dropdown list and fast with a dropdown list. This isn't
    self explanatory."* Nothing on the screen said what a role was, which features used it, or
    that the model itself is configured one level up on the provider record.

    This is `SPEC-302`'s failure repeating in a different surface, and `CLAUDE.md` already names
    the lesson: *"A spec can be mechanically perfect — every route real, every test green — and
    still be the wrong thing to build."* The difference is that this time it was caught by someone
    actually using the surface, which is the norm working rather than failing.

    There is also a real broken state the screen rendered as normal: a role bound to a provider
    that has no model for that role. `SPEC-321`'s own record editor allows it — the field's
    placeholder says "(blank = can't serve this role)" — but the role dropdown showed that provider
    exactly like any other. Every feature asking for that role then fails at call time, with
    nothing in Settings hinting why.

*   **Non-Goals:**
    *   **Not adding a third role, and not per-agent model binding.** `SPEC-208` §2.3.1 decided
        "exactly two roles, deliberately", and reopening that is a different piece of work with a
        different argument. This spec makes the existing two legible; it does not change them.
    *   **Not adding reasoning-effort or thinking-budget control.** A real gap — provider records
        carry a model id per role and nothing else — but it is new capability requiring a
        `SPEC-208` schema change, not a legibility fix. Named here so it is not mistaken for
        something this spec delivers.
    *   **Not a redesign of the provider record editor.** The per-record model fields already
        exist and work. What was missing is the connection between them and the role dropdowns.
    *   **Not validation that a model id is real.** The app does not know a vendor's model list,
        and guessing would be worse than the honest text field `SPEC-321` already ships.

## 2. System Architecture & Design Choices

### 2.1 Say what the role resolves to, not just which provider serves it

**Decided: each role shows the model it will actually use, resolved from the bound provider
record.** The screen had two levels — role → provider record, and record → model per role — and
exposed them in two places with nothing linking them. A user reading "Reasoning: google" has no way
to know which Google model that means without opening the record editor.

The rejected alternative was a tooltip. It fails the same way the original did: the information is
only available to someone who already suspects it exists.

When the bound record has no model for that role, the line says so explicitly and states the
consequence — that the role cannot run — rather than rendering an ordinary-looking selection.

### 2.2 Name the work each role does, in the user's terms

**Decided: describe the kind of work, not an enumerated agent list.** The twelve agents each
declare `model_role` in their own `.prompt.md` frontmatter, so an enumerated list in the UI would
be a second copy that silently goes stale the moment an agent is re-bound. Describing the category
— part lookup and datasheet extraction versus in-app chat — stays true across that drift.

### 2.3 Say what is not configurable

**Decided: state plainly that which role a feature asks for is fixed by the app.** The maintainer's
report asked for "a way to address agents in general or by agent types". That is a real product
question (§1 Non-Goals), but leaving it unanswered on the screen means every user re-derives the
same confusion. A sentence closes it.

### 2.5 Say which providers are actually called

**Decided: each provider row states the roles it serves, and an unbound record says "not in use".**
Reported after using the `CTX-322.1` screen: *"we are misleading a user that adds multiple providers
bc only one would be used and it is not clear as to which provider would be used."* The substance is
right — up to **two** records are live at once, one per role, and every other configured provider,
with its API key, is inert with nothing saying so.

The rejected alternative was a boolean "active" badge. It hides the two-role structure the user was
already confused by; listing the roles teaches it in passing.

### 2.6 Name the per-provider button for what it opens

**Decided: `Edit` becomes `Edit provider`.** The same report proposed "Edit Agents". That button
opens a form holding provider id, kind, base URL, the two model ids and the two capability
checkboxes — **no agents at all** — so "Edit Agents" would promise agent configuration and deliver a
provider form, making the screen more misleading rather than less. The underlying want was an agent
surface that does not exist yet, which is [SPEC-323](SPEC-323-advanced-agent-configuration.md).

### 2.4 Cross-Module Impacts

*   `apps/tauri-ui` — `ProviderConfigEditor.tsx` only. Copy, layout, and one derived string.
*   No daemon change, no schema change, no IPC change. `SPEC-208`'s `ProviderRecord` and
    `provider_roles` are read exactly as they already are.

## 3. Known Constraints & Risks

*   **The copy describes agent categories, which can drift.** Nothing enforces that "part lookup,
    datasheet extraction, board review, connection guidance" still matches what declares
    `model_role: reasoning`. A test asserting the split against the real `.prompt.md` files would
    close it, and is not built here.
*   **Legibility does not make the model choice good.** A user can still bind a role to a model
    that cannot do the job — a model without tool use serving an agent that requires it. That is
    `SPEC-208` §2.4's capability preflight, already shipped, and separate from this.
*   **The unanswered question stays unanswered.** Saying "fixed by the app" is honest but is not
    the same as the per-agent control that was asked for. If that request recurs, this spec's §1
    Non-Goals is where the decision to defer it is recorded.

## 4. Module Map & Reference Links

```text
[SPEC-300 Product IA & Interaction Model](SPEC-300-product-ia-interaction-model.md)
   └── [This Spec](SPEC-322-model-role-legibility.md)
```

*   [SPEC-321 Provider Configuration UI](SPEC-321-provider-configuration-ui.md) — the screen this
    makes legible; shipped correct and unreadable.
*   [SPEC-208 Provider Records & Model Role Resolution](../../../services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md)
    — owns the two-role model and the record schema, both unchanged here.
*   [SPEC-303 Settings UI](SPEC-303-settings-ui.md) — the surface this lives inside.

## 5. User & Interaction

*   **Product Stage:** Settings, in the provider configuration section — the one place a user
    chooses where inference comes from.
*   **What the user is trying to accomplish:** Point the app's AI features at the models they want
    to pay for, and understand what they have chosen — including noticing when they have picked
    something that cannot work.
*   **What the user sees and does:** Under a "Model roles" heading, one sentence explains that
    features ask for a role rather than naming a model. Each role's dropdown now carries the model
    it resolves to underneath it ("Uses claude-opus-5"), or a warning naming the provider and
    saying the role cannot run when no model is set, plus a short line naming the kind of work that
    role does. A closing sentence says which role a feature asks for is fixed by the app.
