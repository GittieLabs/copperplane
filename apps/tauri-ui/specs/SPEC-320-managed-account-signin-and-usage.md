---
id: SPEC-320
title: "Managed Account Sign-In & Usage"
status: Draft
type: Feature
created: 2026-08-25
last_updated: 2026-08-25
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-320-managed-account-signin-and-usage.md"
parent_spec: "../../../specs/SPEC-404-managed-hosted-access.md"
child_specs: []
user_facing: true
---

# SPEC-320: Managed Account Sign-In & Usage

## 1. Executive Summary & Goals

*   **High-Level Goal:** Build the only part of `SPEC-404` a person actually touches: choosing
    Managed as a provider, signing in, seeing how much of the month's allowance is left, and — the
    part that matters most — getting a clear, actionable screen when the allowance runs out, the
    token is revoked, or the gateway is unreachable. Four failure states that `SPEC-207` already
    distinguishes with structured codes, rendered as four different answers instead of one error
    toast.

*   **Business / Technical Value:** `SPEC-404` exists to remove five out-of-product steps from
    first run. Every one of them is replaced by something in this spec, so if this surface is
    confusing the tier has no value — the user's alternative is the vendor key they were trying to
    avoid. The failure states carry disproportionate weight: a subscriber who hits the monthly
    ceiling and sees "LLM request failed" concludes the product is broken and churns, while one who
    sees "you've used this month's allowance, it resets on the 4th, or switch to your own key" has
    been given a working choice. Same event, opposite outcome.

*   **Non-Goals:**
    *   **No upsell surfaces anywhere in the application.** No nag banners, no "upgrade" badges on
        features, no post-install prompt, no interstitial. Managed is discoverable in exactly one
        place — the provider dropdown that already exists — and mentioned in the docs. This is a
        `SPEC-404` §3 mitigation held as a hard product constraint, not a v1 simplification to be
        relaxed later.
    *   **Not billing, plan changes, payment methods, or invoices.** Those live on the account
        website. The app links out; it never embeds a payment surface. An open-source binary is the
        wrong place to hold anything about a card.
    *   **Not a live usage meter.** Quota numbers are a snapshot from the last `GET /v1/account` read
        and go stale immediately. Nothing in the UI may imply a real-time gauge.
    *   **Not a redesign of `SPEC-303`.** Managed is a new option inside the settings surface that
        already exists, plus one panel below it.
    *   **Not a change to any AI feature.** Every stage behaves identically whichever provider is
        selected, right up until a managed-specific error arrives.

## 2. System Architecture & Design Choices

### 2.1 Managed is an option in the provider dropdown

**Decided: Managed appears in `SPEC-303`'s existing provider list, alongside Anthropic, OpenAI,
Google and Ollama — not on a separate "upgrade" or "account" screen.**

The rejected alternative was a dedicated account section in the rail. It fails on two counts: it
puts a commercial surface into the product's navigation spine, which `SPEC-300` reserves for
Projects, Library and Settings; and it misrepresents what Managed is. It is a choice of where
inference comes from, which is precisely what the provider control means. Framing it as one keeps
the paid tier a peer of Ollama rather than a tier above the product.

Selecting Managed swaps the API-key field for the sign-in panel (§2.2). Everything else in Settings
is untouched.

### 2.2 Sign-in: paste a token in v1

**Decided: the app opens the account website in the system browser; the user signs in there, copies
a device token, and pastes it into the app.**

This is the least elegant option and the correct one for v1. The two better flows both cost more
than they are worth right now:

*   **OAuth with a confidential client** is impossible here on principle — an open-source desktop
    binary cannot hold a client secret. Anyone can read it.
*   **OAuth with PKCE and a loopback redirect** is the right long-term answer and needs no secret,
    but it requires a local HTTP listener or a registered custom URL scheme, which means new
    entitlements and a new failure surface across three platforms whose packaging (`SPEC-401`) and
    signing (`SPEC-402`) were only recently stabilised, and whose CAD bridges are still unverified on
    two of them (`SPEC-403`).

Paste-a-token reuses the secret path `SPEC-106` and `SPEC-303` already ship — it is, mechanically,
the API-key field with a different label and a different keychain entry. **PKCE with a loopback
redirect is the named successor**, and this decision should be revisited once `SPEC-403` closes,
rather than left as an accident of v1.

The pasted token is written to the OS keychain by Rust and reaches the daemon only over `SPEC-106`'s
spawn-time secret channel. It is never logged, never included in `SPEC-107`'s diagnostics bundle, and
never rendered back in full after being saved — the same treatment `SPEC-303` already gives an API
key.

### 2.3 Usage display

Below the sign-in panel, once signed in: plan name, tokens used against the allowance, and the reset
date. **Sourced entirely from `GET /v1/account`** — on sign-in, on Settings open, and after a
completed job. Per-call token counts also become available for the first time via `SPEC-207` §2.2,
but they answer "what did that cost", not "how much is left", and must not be summed client-side
into a period total: the client is open source, its arithmetic is not authoritative, and the account
endpoint already knows the answer.

Displayed as "used of allowed, resets on <date>" — a factual statement with its own as-of time —
rather than a percentage bar, which reads as live. A warning appears only in the last stretch of the
allowance, and the threshold is defined here, in presentation, because `SPEC-207` §2.2 deliberately
declines to decide what "low" means.

### 2.4 The early-access channel toggle

`SPEC-404` §2.8 gives subscribers earlier *builds* of source that is already public. The surface for
that is one control, and it belongs beside the existing update settings rather than in the account
panel — it is an update preference that happens to require a subscription, not an account feature.

*   A single "Receive early-access builds" toggle, visible and enabled only while signed in to
    Managed. Signing out returns the app to `stable` at the next update check.
*   The copy must not imply exclusivity of *code*, because there is none. Something close to:
    "Early-access builds come from the same public source, a few weeks ahead of the stable release."
    Anything that reads as "subscriber-only features" misdescribes the product and creates exactly
    the expectation `SPEC-404` §1 refuses.
*   Switching to `early` needs a plain warning that these builds are less tested, and switching back
    to `stable` needs to be one click and to never require a reinstall.

The manifest, promotion process, and updater plumbing are `SPEC-402`'s to extend; this spec owns
only the control and its wording.

### 2.5 The four failure states

`SPEC-207` §2.3 delivers structured codes precisely so this layer never has to inspect a message
string. **A screen is selected by code — never by string-matching prose.** This is the same rule
`PRODUCT-PLAN.md` §2 established for user input after `parseCommand` was deleted, applied to an
inter-layer payload.

| Code | What the user sees | Choices offered |
| :--- | :--- | :--- |
| `managed_quota_exhausted` | "You've used this month's allowance. It resets on <date>." | Switch to my own key · Manage plan (opens browser) · Dismiss |
| `managed_auth_invalid` | "Your Copperplane account couldn't be verified." | Sign in again · Switch to my own key |
| `managed_unreachable` | "Can't reach the managed service. Your network or the service is down." | Retry · Switch to my own key |
| `managed_upstream_unavailable` | "The model provider is having trouble. This isn't your account." | Retry · Dismiss |

Each is a **structured choice card**, not a toast and not a modal — the shape `PRODUCT-PLAN.md`
already requires for a "did you mean" disambiguation, reused because the requirement is the same
one: the app hit a fork it cannot resolve alone and must hand the user real options instead of
silently picking. The card renders inside whichever stage dispatched the call, so the user stays
where they were.

"Switch to my own key" deep-links to Settings with the provider control focused. It does not
silently reconfigure anything — provider selection stays the user's decision.

### 2.6 Sign out

Clears the token from the keychain and returns the provider selection to unconfigured, surfacing the
same first-run state `SPEC-303` already handles. It does not cancel a subscription, and the UI must
say so — signing out of a desktop app and cancelling a paid plan are different actions and users
routinely conflate them.

### 2.7 Cross-Module Impacts

*   `apps/tauri-ui` — provider option, sign-in panel, usage panel, the four cards, deep-link to
    Settings.
*   `core/tauri-rust` — one new keychain entry name; reuses `SPEC-106`'s existing secret write path.
*   `services/python-daemon` — upstream only; consumes nothing from this spec (`SPEC-207`).
*   `docs/site` — `first-run.md` gains the Managed path; `privacy.md` is `SPEC-404` §2.7's
    deliverable and must land with, or before, this surface.

## 3. Known Constraints & Risks

*   **Paste-a-token will generate support contacts.** Users will paste with whitespace, paste the
    wrong string, or paste an expired token. Trim aggressively, validate against `GET /v1/account`
    before saving rather than at first use, and fail with a specific message. The cost of getting
    this wrong is a first-run failure for the exact user who chose Managed to avoid fiddling.
*   **Quota display is stale by construction** (§2.3). The risk is a user acting on a number that was
    true an hour ago. Showing the as-of time is what keeps it honest.
*   **Switching provider mid-job.** Settings can be changed while an async job (`SPEC-105`) is in
    flight. Existing behaviour applies unchanged; this spec must not introduce a special case, and
    the context file should confirm what that behaviour actually is rather than assume it.
*   **The exhaustion card can fire from any stage**, including one mid-flow. It must not destroy
    unsaved stage state — the user should be able to dismiss it, switch provider, and re-run without
    losing where they were.
*   **`managed_unreachable` and a daemon crash must never look alike.** `SPEC-101`'s crash shield
    produces its own surface; a network failure reaching a paid service is an ordinary condition and
    must read as one.
*   **Testing needs a fake gateway, not the real one** — the same fixture `SPEC-207` §2.5 builds.
    Every one of §2.5's four cards needs a test that drives it from its code, and the "switch to my
    own key" path needs one that asserts nothing is reconfigured without the user's click.
*   **Open question:** whether a signed-in user with an exhausted allowance and a personal key
    configured should fall back automatically. Recommendation is **no** — a silent switch to a
    provider the user pays for directly is a surprise with a bill attached, and it violates the same
    "surface the choice, don't pick for them" rule §2.5 rests on. Flagged rather than buried, because
    it is the kind of convenience that looks obviously right until it charges someone.

## 4. Module Map & Reference Links

```text
[SPEC-000 Root Architecture](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-404 Managed Hosted Access](../../../specs/SPEC-404-managed-hosted-access.md)
          ├── [SPEC-207 Managed Provider Adapter](../../../services/python-daemon/specs/SPEC-207-managed-provider-adapter.md)
          └── [SPEC-320 Managed Account Sign-In & Usage](SPEC-320-managed-account-signin-and-usage.md)   ← this spec
```

Extends [SPEC-303 Settings UI](SPEC-303-settings-ui.md) inside the shell defined by
[SPEC-300 Product IA & Interaction Model](SPEC-300-product-ia-interaction-model.md), over
[SPEC-106 Configuration & Secrets Store](../../../specs/SPEC-106-configuration-secrets-store.md).

## 5. User & Interaction

*   **Product Stage:** Settings — the persistent, non-project-scoped rail destination `SPEC-300` §2
    anchors beside Library. The four failure cards (§2.5) are cross-stage: they render inside
    whichever stage dispatched the AI call, so the user is never navigated away from their work.
*   **What the user is trying to accomplish:** Use the app's AI features without creating an account
    with a model vendor and generating an API key — and, when those features stop working, find out
    why and what to do about it without leaving the app to guess.
*   **What the user sees and does:** In Settings they pick "Managed" from the provider dropdown, click
    through to the account site in their browser, and paste the token it gives them back into the
    app; underneath it they see their plan, how much of the month's allowance they've used, and when
    it resets. If the allowance runs out mid-task, the stage they're working in shows a card naming
    the reset date, with buttons to switch to their own key or manage the plan.
