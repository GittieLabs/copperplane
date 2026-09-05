---
id: SPEC-404
title: "Managed Hosted Access"
status: Draft
type: System
created: 2026-08-25
last_updated: 2026-09-05
target_version: v0.4.0
location: "specs/SPEC-404-managed-hosted-access.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs:
  - "../services/python-daemon/specs/SPEC-207-managed-provider-adapter.md"
  - "../apps/tauri-ui/specs/SPEC-320-managed-account-signin-and-usage.md"
user_facing: false
---

# SPEC-404: Managed Hosted Access

## 0. Why this is not being built yet

**Recorded 2026-09-05, in the maintainer's own terms.** Two reasons, neither of them technical:

1.  **There is no SaaS application to sign in to.** The gateway, the accounts, the metering and the
    billing do not exist. This spec describes a client for a service that has not been built.

2.  **Charging for work that only one person has validated would be wrong.** Every live CAD path in
    this project has been verified on exactly one machine, macOS on Apple silicon
    (`SPEC-403`). Taking money for a hosted tier before users other than the maintainer have
    confirmed the product works on their platform puts the charge before the evidence.

The consequence for the product today: the welcome screen shows **Managed by Copperplane** as a
card marked *COMING SOON*, with its **Sign in** button visibly disabled. That is deliberate and
honest — the option is real, it is not available, and nothing pretends otherwise.

**What would change this.** Not a decision to build a gateway. Evidence from `SPEC-403` that the
app works for people who are not the maintainer, followed by those people wanting a version they
do not have to bring a key to. In that order.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Define an optional, paid managed tier — LLM inference supplied through a
    GittieLabs-operated gateway — so that a user can install Copperplane and use every AI
    feature in it without first holding an account with a model vendor. The application remains
    entirely Apache-2.0 and functionally complete with a personal API key or a local Ollama model.
    **The tier sells operation, not capability.** This spec owns the offering's shape, its licence
    and vendor-terms position, and the wire contract the app depends on; the gateway service itself
    is an external system specced and built outside this repository.

*   **Business / Technical Value:** Bring-your-own-key is a real adoption cliff, and the repo already
    documents it. `SPEC-303` exists because `CTX-302.1`'s Plan Drift recorded a live
    `"No LLM provider configured"` failure on a fresh install; that spec gave the setting a UI, but
    it did not remove the underlying requirement. As of today the first-run path for a new user is:
    install the app, leave the app, create an account with Anthropic or OpenAI or Google, add a
    payment method there, generate an API key, come back, paste it. Five steps outside the product
    before a single feature does anything. For a hardware engineer who wants to look up a part — not
    to become an LLM-API customer — that is where the funnel ends. The managed tier is the path for
    that user, and it funds the maintenance of the free one.

*   **Non-Goals:**
    *   **Not a hosted version of the application.** The app stays a local desktop binary. A
        browser-based Copperplane would contradict two settled decisions at once:
        `PRODUCT-PLAN.md`'s files-are-the-source-of-truth model, and `SPEC-103`/`SPEC-104`'s reliance
        on locally-installed KiCad and FreeCAD processes. What is hosted here is inference, and
        nothing else.
    *   **Not a code embargo.** No source is ever withheld from the public repository — not
        temporarily, not behind an early-access window, not per-feature. Every merge lands in the
        open repo when it lands. Subscribers may receive *builds* earlier (§2.8), which is a
        different thing and is the only permitted form of "subscribers first".
    *   **Not a paid feature gate.** No route, stage, or capability is withheld from the free build.
        Every daemon route behaves identically on Managed and on a personal key. If a future spec
        proposes a Managed-only feature, that proposal contradicts this one and must say so
        explicitly.
    *   **Not paid updates.** `SPEC-402` already ships auto-update to every installed copy for free,
        via `tauri-plugin-updater` and a signed `latest.json`. Selling "updates" would require
        degrading the free build to create the difference. Refused. This is named here because
        "hosting, updates and support" is the intuitive framing of a tier like this one, and two
        thirds of it is wrong for this project.
    *   **Not the gateway's own implementation.** Metering internals, billing integration, subscriber
        database, and abuse tooling are the service's design, not this repository's. This spec
        defines only the contract the client is written against — see §2.3 and §2.7.
    *   **Not API-key resale.** The gateway never returns a vendor API key to the client, and no
        endpoint in the contract exposes one. See §2.5.
    *   **Not teams, shared workspaces, or multi-seat licensing.** One account, one subscriber.
    *   **Not supplier or distributor data.** `SPEC-203` was retired 2026-08-18 and nothing here
        revives it.

## 2. System Architecture & Design Choices

### 2.1 What is actually being sold

| | Free (Apache-2.0 build) | Managed |
| :--- | :--- | :--- |
| Every feature and route | ✅ | ✅ |
| Auto-update (`SPEC-402`) | ✅ | ✅ |
| Full source, the moment it merges | ✅ | ✅ |
| Buildable from source, including pre-release | ✅ | ✅ |
| Pre-built early-access binaries (§2.8) | — | ✅ |
| Works fully offline (Ollama) | ✅ | — (requires network) |
| Requires a vendor account and key | Yes | No |
| Inference paid for by | The user, to their vendor | The subscription |
| Support | Community issues | Defined response commitment |

The right-hand column contains no capability and no source the left-hand column lacks. The single
asymmetry is *when a compiled binary is handed to you*, and anyone who builds from source erases
even that, on the same day, with no subscription. That is the design constraint, not an accident of
the current scope.

### 2.2 Managed is a provider, not a product fork

**Decided: "Managed" is one more entry in the provider abstraction `SPEC-201` already built, not a
parallel build, a separate binary, or a compile-time flag.**

This is the load-bearing decision in the spec, and it is what makes the whole tier cheap. Three
mechanisms already exist and are already `Completed`:

*   `SPEC-201` routes every LLM call through AgentFlow's provider layer, and `OpenAICompatProvider`
    already serves OpenAI, Azure **and Ollama** by base-URL configuration alone. A gateway that
    speaks the OpenAI-compatible wire format is, from the daemon's perspective, one more base URL.
*   `SPEC-106` already stores `llm_provider`/`llm_model` in `config.json` and a provider secret in
    the OS keychain, injected to the daemon over the tighter secret channel at spawn. A subscription
    token is a secret with the same lifecycle as an API key and needs no new storage mechanism.
*   `SPEC-303` already renders the provider dropdown and the secret field. Managed is a new option in
    an existing control.

The client-side delta is therefore a base URL, a token, and quota handling — not an architecture.
The alternative considered and rejected was a separate "cloud edition" build; it would have forked
packaging (`SPEC-401`), signing and update channels (`SPEC-402`), and the settings surface, to
deliver a difference that is one config value wide.

### 2.3 The wire contract

The gateway is an external system. This is the boundary the app is written against, and the app may
depend on nothing else about it.

*   **Transport:** HTTPS, versioned path prefix (`/v1/...`). TLS required; the client refuses plain
    HTTP even if configured with it.
*   **`POST /v1/chat/completions` — OpenAI-compatible request and response bodies.** Chosen so that
    `SPEC-201`'s existing `OpenAICompatProvider` can serve this provider unchanged. The gateway may
    route to any vendor behind that surface.
*   **Model names are gateway-side aliases, never vendor model IDs.** The contract defines a small
    stable set — for example `has-standard` and `has-deep` — and the gateway maps them to whatever
    vendor and model it currently uses. Two reasons: the app stops breaking when a vendor deprecates
    a model ID, and the offering is visibly a product rather than a passthrough (§2.5). The daemon
    must not validate a Managed model name against any vendor's catalogue.
*   **Auth: `Authorization: Bearer <subscription token>`.** The token is opaque, long-lived, and
    revocable server-side. **Decided: no refresh-token rotation in v1.** A desktop app that may sit
    closed for a month makes a short-lived-access-token state machine a source of failure modes
    (refresh while offline, refresh during a long job, clock skew) for a benefit — limiting the blast
    radius of a stolen token — that server-side revocation already provides. Recorded as a
    deliberate trade, revisitable if token theft becomes a real observed problem rather than a
    theoretical one.
*   **`GET /v1/account` is the single source of quota state** — plan name, period bounds, tokens used
    and allowed, account status. Called on sign-in, on Settings open, and after a completed job.
    **Revised 2026-08-25:** an earlier draft of this contract put `X-HAS-Quota-*` headers on every
    completion response. That was dropped after checking the installed AgentFlow source, which does
    not surface raw HTTP response headers to its caller — the app could not have read them. It does
    return per-call token counts (`SPEC-207` §2.2), which covers "what did that cost", and the
    account endpoint covers "how much is left". No header plumbing is needed on either side, and the
    gateway should not build any.
*   **Error taxonomy.** Each maps to a distinct user-visible state in `SPEC-320`; none may collapse
    into a generic "LLM error":
    *   `401` — token invalid, revoked, or belongs to a cancelled account
    *   `402` — period allowance exhausted (body carries the reset timestamp)
    *   `429` — rate limited; `Retry-After` required
    *   `503` — upstream vendor unavailable; the subscriber's account is fine
*   **Version negotiation.** The client sends `X-HAS-Client-Version`. The gateway must serve the
    contract version of every app release still inside its support window; breaking the contract for
    an in-support release is a gateway defect, not a client one. This obligation exists because the
    app auto-updates but users can decline, and an open-source binary can be pinned indefinitely.

### 2.4 Data flow

```text
Tauri UI (SPEC-320)                Rust core (SPEC-106)         Python daemon (SPEC-207)
      │                                   │                              │
 pick "Managed",  ────────────────▶  token → OS keychain                 │
 paste token                              │                              │
      │                             on daemon spawn:                     │
      │                             secret channel ──────────────▶ provider = managed
      │                                                                  │  base_url = gateway
      │                                                                  ▼
      │                                                        OpenAICompatProvider
      │                                                        (SPEC-201, unchanged)
      │                                                                  │  HTTPS + Bearer
      │                                                                  ▼
      │                                                        ┌──────────────────┐
      │                                                        │ GittieLabs       │  external
      │                                                        │ gateway          │  system
      │                                                        │ meter · enforce  │
      │                                                        │ quota · route    │
      │                                                        └────────┬─────────┘
      │                                                                 │
      │                                                                 ▼
      │                                                        vendor API (Anthropic /
      │                                                        OpenAI / Google)
      │                                                                 │
      │◀── token usage + errors, over SPEC-105's job protocol ──────────┘
      │        (period totals come from GET /v1/account, not from the call)
```

### 2.5 Vendor terms: a product on the API, not resale

**Verified against both vendors' current terms, 2026-08-25 — not assumed.** Both draw the same line
in the same place, and both draw it explicitly:

*   **Anthropic Commercial Terms §A.1** grants permission to use the Services "*including to power
    products and services Customer makes available to its own customers and end users*." That
    sentence describes this tier exactly.
*   **Anthropic Commercial Terms §D.4** prohibits accessing the Services "*to build a competing
    product or service … or resell the Services except as expressly approved by Anthropic*."
*   **OpenAI Services Agreement §2.2** grants "*the right to use OpenAI's API to integrate the
    Services into Customer Applications and to make Customer Applications available to End Users*"
    — with no requirement that those End Users hold OpenAI accounts.
*   **OpenAI Services Agreement §3.1** prohibits reselling or leasing "*access to its Account or any
    End User Account*."

So the permitted thing is a Customer Application serving End Users, and the prohibited thing is
handing over account or API access itself. The contract in §2.3 is built to sit unambiguously on
the permitted side:

*   The gateway is the API customer of record. Vendor keys live only in the gateway and are never
    returned to a client, under any endpoint.
*   The exposed surface is aliased models and a metered subscription, not vendor endpoints and
    vendor model IDs.
*   The gateway applies its own acceptable-use policy and per-account rate limits, and can suspend
    one subscriber without affecting others.

**One concrete trap, worth naming because it is easy to fall into and unambiguously prohibited: the
gateway must be funded by a paid API account, never by a consumer Claude Pro or Max subscription.**
Anthropic clarified in February 2026 that OAuth tokens from consumer subscription tiers are intended
only for Claude Code and claude.ai, and using them from third-party harnesses violates the Consumer
Terms. The commercial API is a different product under different terms — §A.1 above is an API
clause. Routing a paid tier through a personal subscription would be the one genuine grey area in
this whole design, and it is avoided simply by not doing it.

**Remaining gate:** each vendor's *usage policies* (as distinct from the commercial terms quoted
above) still need to be read and their obligations recorded in the context file — chiefly what the
operator must pass through to subscribers, since some vendor policies require flowing specific
restrictions down to end users. Terms: verified. Usage policies: not yet.

### 2.6 Licence position

Apache-2.0 §2 grants everyone, the author included, the right to use the work commercially, and it
has no network-use clause. Keith is the sole copyright holder of both this repository and
`gittielabs-agentflow` (see `SPEC-904`), so no third-party consent is implicated.

Two consequences worth stating so they are not rediscovered later:

*   **The Managed client code ships in this repository under Apache-2.0, like everything else.** A
    fork can point it at its own gateway. That is permitted, expected, and not a problem — the
    gateway, its keys, and its subscriber base are what is scarce, not the HTTP client that talks to
    it.
*   **The name is not granted.** Apache-2.0 §6 explicitly withholds trademark rights. Registering and
    consistently marking "Copperplane" is what prevents a third party from operating a
    competing hosted service under the project's own name. This is a separate action from anything
    in this repo and is the actual defensible asset.

**Decided: DCO, not CLA.** The contributor policy falls due at the same time, and the choice follows
from the constraint that contributors carry no restrictions they would not carry on any other
Apache-2.0 project. A DCO is a `Signed-off-by:` line asserting the contributor had the right to
submit the code — no copyright assignment, no grant to the maintainer that other contributors don't
also receive, nothing a contributor has to take to an employer's legal team. A CLA would buy the
ability to relicense the project unilaterally later; that ability is only worth having if
closing the source is on the table, and it is not (§1 Non-Goals). Trading contributor friction for
an option nobody intends to exercise is the wrong trade.

The cost is real and should be stated: with a DCO and outside contributors, the project can no
longer be relicensed without their consent. That is the intended outcome, not an oversight.

### 2.7 Privacy documentation is part of this spec's deliverable

`docs/site/src/content/docs/privacy.md` currently tells the user exactly what leaves the machine
under each provider, and offers Ollama as the answer for anyone who needs nothing to leave. Managed
introduces a party that page does not mention: with Managed selected, prompts reach the GittieLabs
gateway and are then forwarded to a vendor. That must be stated as plainly as the existing cases —
what the gateway logs, what it retains, for how long, and which vendors it may route to. A managed
tier that quietly weakens the honesty of that page would cost more trust than it earns revenue.

### 2.8 Early access is a build channel, not a code embargo

Subscribers get new features first. **The mechanism is which binary you are handed, never which
source exists.**

The distinction is the whole point, so it is worth being precise about what is rejected. A
delayed-source model — merge to a private branch, ship to subscribers, open the source N weeks later
— would be a restriction on the code, and it fails on three separate counts: it makes a contributor's
own patch reach paying customers before it reaches them, which is the exact dynamic that turns
communities against a maintainer; it forces a private fork of a public repo, with the merge pain that
implies; and it puts a licence question where none needs to exist. Refused.

What replaces it costs almost nothing, because `SPEC-402` already built most of it:

*   **Source lands in the public repository on merge, unchanged from today.** No private branch, no
    holding period, no per-feature gate. A person watching the repo sees a feature the moment it
    exists, and can build and run it that day.
*   **Two updater channels instead of one.** `SPEC-402`'s `tauri-plugin-updater` reads a signed
    `latest.json`; a second manifest at a second URL is the entire mechanism. `early` is built from
    the same public source at a shorter cadence; `stable` is promoted from `early` once it has held
    up.
*   **The channel is what the subscription buys, and it is the only thing gated.** Both manifests are
    signed with the same key (`SPEC-402` §2), both point at builds of public source, and the
    early-access manifest URL requires the subscription token.

Two benefits fall out that are worth more than the differentiation itself. First, it closes a real
gap: `SPEC-403` observes that every live CAD test to date has run on exactly one machine, Keith's
Mac. An early-access fleet with a support relationship is precisely the live-test population that
spec says does not exist, and on Windows and Linux it is the only realistic path to retiring the
pre-release label on `CTX-402.5`'s builds. Second, it makes the value proposition honest and easy
to state: *you're paying to be early and to be supported, and everything you get, you could have
built yourself the same day.*

**Constraint:** early access must never become the only place a feature is exercised before it
reaches stable. If a release reaches `stable` having been tested exclusively by paying subscribers,
the free build has quietly become the beta, which inverts the promise. CI (`SPEC-903`) and the
maintainer's own testing remain the gate; early access is additional signal, not a substitute.

Scope note: the channel toggle, its manifest, and the promotion process extend `SPEC-402` and are
not specified here beyond the constraint above. `SPEC-320` §2.4 covers only where a subscriber sees
the choice.

### 2.9 Cross-Module Impacts

*   `services/python-daemon` — new `managed` provider branch (`SPEC-207`).
*   `apps/tauri-ui` — provider option, sign-in, usage display, exhaustion states (`SPEC-320`).
*   `specs/SPEC-106` — one new permitted value for `llm_provider`, and a keychain entry name for the
    subscription token. No change to the storage mechanism.
*   `docs/site` — `privacy.md` (§2.7), `first-run.md`, `install.md`.
*   `NOTICE` / `SPEC-904` — unaffected. No new bundled third-party code is implied; the gateway is a
    network service, not a dependency.
*   `specs/SPEC-402` — a second updater channel and manifest (§2.8). Extension, not a redesign.
*   `CONTRIBUTING.md` — DCO sign-off requirement and its CI check (§2.6).
*   **External:** the gateway service, its billing integration, and the account website.

## 3. Known Constraints & Risks

*   **Cost of goods is unbounded per subscriber until metering exists, and metering must be
    server-side.** The client is open source: any counting, capping, or model selection it performs
    is advisory and trivially bypassed by editing the source and rebuilding. The gateway must treat
    every client-supplied value as untrusted — quota state, model alias, and identity are all decided
    server-side. Enforced metering is a prerequisite to the first paying subscriber, not a follow-up.
*   **The subscription token is extractable by its owner**, from their own keychain. This is expected
    and harmless: the token *is* the account, and using it from a modified build consumes that
    account's own allowance. The failure mode to guard is a shared or leaked token, which is what
    server-side revocation and per-account rate limits exist for.
*   **Single operator, single point of failure.** A gateway outage blocks every Managed subscriber
    completely, while personal-key and Ollama users are unaffected. `SPEC-320` must make the app
    degrade into a clear, actionable state — "the managed service is unreachable; use your own key" —
    rather than into something that looks like the app is broken. `SPEC-101`'s crash shield must not
    be the thing that catches this.
*   **A vendor account suspension is an existential single dependency.** One subscriber's abuse can
    jeopardise the account every subscriber depends on. Per-account abuse controls and the ability to
    suspend one subscriber must exist before launch, and routing to more than one vendor is the
    structural mitigation.
*   **Support obligation scales worse than inference for a solo maintainer.** Inference cost is
    capped by the token ceiling; support requests are not capped by anything. What "support" means —
    channel, scope, response window — has to be written down and bounded before it is sold, or it
    becomes an unbounded liability attached to a fixed monthly fee.
*   **Open-core resentment is a real failure mode for this kind of tier**, and the mitigation is
    structural rather than rhetorical: no capability behind the paywall (§2.1), no source withheld
    for any period (§2.8), the Managed client in the public repo (§2.6), a DCO rather than a CLA
    (§2.6), and no upsell surfaces inside the app (`SPEC-320`'s non-goal). If any of those is ever
    traded away for conversion rate, this risk returns immediately.
*   **Early access degrading into a two-tier product** is the specific way §2.8 could go wrong: a
    stable channel that lags far enough behind, or that receives materially less attention, stops
    being the same product. The guard is a bounded, published promotion cadence — "early leads
    stable by roughly N weeks" — rather than an open-ended one. Choosing N is a launch decision, and
    it should err short.
*   **Selling a subscription creates tax, invoicing, and refund obligations** in the operator's
    jurisdiction and possibly the subscriber's. Named so it is not discovered at launch; out of scope
    for this repository to solve.
*   **Open question — promotion cadence for §2.8.** How far `early` leads `stable`. Bounded and
    published, or the previous risk materialises.
*   **Open question — milestone placement.** `ROADMAP.md` §4 currently ends at M3/`v0.3.0`. This spec
    is tagged `v0.4.0`, which does not yet exist as a milestone. Where this lands relative to
    `SPEC-403`'s cross-platform verification is a scheduling decision, not a technical one — though
    the ordering argument is that selling a subscription to Windows users before their CAD bridges
    have ever been live-tested would be selling an untested claim.

## 4. Module Map & Reference Links

```text
[SPEC-000 Root Architecture](SPEC-000-architecture-overview.md)
   └── [SPEC-404 Managed Hosted Access](SPEC-404-managed-hosted-access.md)   ← this spec
          ├── [SPEC-207 Managed Provider Adapter](../services/python-daemon/specs/SPEC-207-managed-provider-adapter.md)
          └── [SPEC-320 Managed Account Sign-In & Usage](../apps/tauri-ui/specs/SPEC-320-managed-account-signin-and-usage.md)
```

Depends on, and changes nothing in: [SPEC-201 LLM Provider Abstraction](../services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md),
[SPEC-106 Configuration & Secrets Store](SPEC-106-configuration-secrets-store.md),
[SPEC-303 Settings UI](../apps/tauri-ui/specs/SPEC-303-settings-ui.md),
[SPEC-402 Release, Signing & Auto-Update](SPEC-402-release-signing-and-auto-update.md),
[SPEC-904 License & Attribution Consistency](SPEC-904-license-attribution-consistency.md).

`user_facing: false` is deliberate and is why §5 is absent: this spec adds no surface of its own.
Every pixel a person interacts with belongs to `SPEC-320`, which carries the required
User & Interaction section as its §5.
