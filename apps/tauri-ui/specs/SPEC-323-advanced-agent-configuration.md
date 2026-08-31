---
id: SPEC-323
title: "Advanced Per-Agent Configuration"
status: Draft
type: Feature
created: 2026-08-27
last_updated: 2026-08-27
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-323-advanced-agent-configuration.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-323: Advanced Per-Agent Configuration

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let a contributor or advanced user bind an individual agent to a specific
    provider, model and reasoning effort, behind an Advanced toggle that is off by default, with a
    reset back to the role defaults. Everyone else keeps today's two-role model untouched and never
    sees the surface.

*   **Business / Technical Value:** Stated directly by the maintainer, and the tiering is the
    design constraint rather than an afterthought:

    > "In a managed setup, the user would not care. In a basic user that brings their own key,
    > being able to choose exact models for each agent is also less important. [...] For a
    > contributor, we would want to have an advanced config that a user selects which shows a view
    > with every agent and allows the user to change all of the settings we add for each agent,
    > plus a reset to go back to defaults. [...] I only want per agent configs to be an advanced
    > option."

    The value is fine-tuning for people building the product: trying a cheaper model on one chat
    agent, giving datasheet extraction a larger thinking budget, or pointing a single agent at a
    local Ollama model while the rest stay on a vendor. Today that requires editing `config.json`
    by hand, or changing a role binding and moving five other agents with it.

*   **Non-Goals:**
    *   **Not replacing the two-role model.** `SPEC-208` §2.3.1's "exactly two roles, deliberately"
        stands as the default path. This layers an escape hatch on top; it does not reopen that
        argument, and an agent with no override resolves exactly as it does today.
    *   **Not exposed to basic or managed users.** Off by default, and nothing outside the Advanced
        disclosure references it. `SPEC-404` §3 and `SPEC-320` §1's hard line against upsell and
        clutter applies to complexity too.
    *   **Not per-agent prompt editing.** The `.prompt.md` bodies stay repo content.
    *   **Not a model catalogue.** The app does not know a vendor's model list, and `SPEC-322` §1
        already declined to guess one. Model stays a text field.
    *   **Not changing which role an agent declares.** `model_role` in each `.prompt.md` remains
        the default; an override replaces the resolved provider/model, not the declaration.

## 2. System Architecture & Design Choices

### 2.1 An override layer, not a second resolution path

**Decided: resolution becomes agent override → role binding → today's behaviour, checked in that
order.** An agent with no override takes a code path identical to the current one, so the default
experience cannot regress. `SPEC-208`'s `provider_roles` stays exactly as it is.

The rejected alternative was making `provider_roles` per-agent outright, which would have made
every install carry twelve bindings to express what two express today, and would have made the
basic case worse to improve the advanced one.

### 2.2 Overrides are config, the toggle is UI

**Decided: the override map lives in `config.json` and reaches the daemon through `SPEC-106`'s
existing channel; the Advanced disclosure state lives in `localStorage`.** The daemon must know the
overrides to resolve them. It has no reason to know whether a checkbox is expanded — the same split
`SPEC-317` made for the theme preference, and for the same reason.

Shape, an addition to the existing `DaemonConfig`, absent by default:

    agent_overrides: { "<agent_name>": { provider?, model?, reasoning_effort? } }

Absent, empty, and all-fields-null must all behave identically to no override at all, so a
half-filled entry can never half-apply.

### 2.3 Reasoning effort needs a portable representation

**This is the hard part of the spec and is deliberately not decided here.** Vendors express it
differently — Anthropic a token budget, OpenAI an effort level, Google its own thinking
configuration — and the daemon's provider records already abstract over exactly this kind of
difference by `kind`.

The proposal, for §3 to resolve: a small ordered enum (`off` / `low` / `medium` / `high`) mapped
per provider `kind` in the daemon, with `off` meaning "send nothing and let the vendor default
apply". A raw per-vendor value is rejected: it would leak vendor shape into a UI that is supposed to
be provider-agnostic, and would silently mean nothing when the agent's provider changes.

### 2.4 Reset must exist at both levels

**Decided: per-agent reset and a reset-all.** An advanced surface a user cannot back out of is a
trap, especially one whose failure mode is an agent quietly using a model it should not. Reset
deletes the override rather than writing today's default into it, so an agent returns to *following*
the role binding rather than being pinned to whatever it happened to resolve to.

### 2.5 The view lists every agent, including ones with no override

Twelve agents today, each showing its declared role, what it currently resolves to, and whether an
override is in force. Listing only overridden agents would hide the thing the user came to see —
what everything is currently doing.

Agent names and roles come from the daemon, which already parses them (`agent_roles.py`), never
from a list hardcoded in the UI. `CTX-322.1` recorded that reasoning: a second copy of `.prompt.md`
frontmatter goes stale silently.

### 2.6 Cross-Module Impacts

*   `apps/tauri-ui` — the Advanced disclosure, the agent list, per-agent controls, reset.
*   `services/python-daemon` — `agent_overrides` in config; resolution before the role binding; a
    route exposing agent names, declared roles and resolved bindings; the effort mapping per
    provider kind.
*   `core/tauri-rust` — one new `DaemonConfig` field, passed through unchanged.
*   `SPEC-208` — extended, not revised: its role model is the fallback this layers on.

## 3. Known Constraints & Risks

*   **Open question — the reasoning-effort representation** (§2.3). The enum is a proposal, not a
    decision. It needs checking against what each provider `kind` in the daemon can actually send
    today, which is real work against the installed SDKs rather than a design call.
*   **An override can point at a provider that cannot serve the agent.** `SPEC-208` §2.4's
    capability preflight already checks a role binding against an agent's `requires`; it must run
    on overrides too, or the advanced path becomes the one place that skips the safety check.
*   **An override can name a deleted provider.** Deleting a provider record already warns when it
    is role-bound (`confirmRemoveRoleBoundProvider`). That check must learn about overrides, or
    deletion silently breaks one agent.
*   **Twelve agents is a lot of surface for a settings panel**, and it grows with every new agent.
    The layout has to stay legible at twenty, which is a real design constraint rather than a
    styling detail.
*   **This is the third consecutive spec in this area written from a maintainer's own report.**
    `SPEC-321` shipped correct and unreadable, `SPEC-322` made it readable, and this adds what was
    actually wanted. Worth noting that none of the three would have been caught by a test — only by
    someone using the surface.

## 4. Module Map & Reference Links

```text
[SPEC-300 Product IA & Interaction Model](SPEC-300-product-ia-interaction-model.md)
   ├── [SPEC-322 Model Role Legibility](SPEC-322-model-role-legibility.md)
   └── [This Spec](SPEC-323-advanced-agent-configuration.md)
```

*   [SPEC-208 Provider Records & Model Role Resolution](../../../services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md)
    — the two-role default this layers on, extended rather than revised.
*   [SPEC-321 Provider Configuration UI](SPEC-321-provider-configuration-ui.md) — the provider list
    this sits beside.
*   [SPEC-106 Configuration & Secrets Store](../../../specs/SPEC-106-configuration-secrets-store.md)
    — the channel `agent_overrides` reaches the daemon through.
*   [SPEC-317 Theme System](SPEC-317-theme-system.md) — the precedent for a pure-UI preference
    living in `localStorage` rather than the daemon's config.

## 5. User & Interaction

*   **Product Stage:** Settings, inside the provider configuration section, behind an Advanced
    disclosure that is collapsed by default.
*   **What the user is trying to accomplish:** A contributor fine-tuning the product — trying a
    cheaper model on one chat agent, giving datasheet extraction more thinking budget, or pointing
    one agent at a local model — without moving the five other agents that share its role.
*   **What the user sees and does:** Expanding "Advanced" reveals every agent with its declared
    role and what it currently resolves to. Each row can override provider, model and reasoning
    effort, and shows a reset that returns the agent to following its role. A reset-all clears
    every override. Collapsed, none of this is visible, and a user who never opens it is
    unaffected.
