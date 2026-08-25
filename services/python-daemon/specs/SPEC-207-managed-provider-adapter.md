---
id: SPEC-207
title: "Managed Provider Adapter"
status: Draft
type: Feature
created: 2026-08-25
last_updated: 2026-08-25
target_version: v0.4.0
location: "services/python-daemon/specs/SPEC-207-managed-provider-adapter.md"
parent_spec: "../../../specs/SPEC-404-managed-hosted-access.md"
child_specs: []
user_facing: false
---

# SPEC-207: Managed Provider Adapter

## 1. Executive Summary & Goals

*   **High-Level Goal:** Teach the daemon one new value for `llm_provider` — `managed` — implemented
    as a configuration of `SPEC-201`'s existing `OpenAICompatProvider` pointed at `SPEC-404`'s
    gateway, plus the two things a gateway has that a vendor API does not: quota telemetry, and an
    error taxonomy that distinguishes "your allowance ran out" from "the service is down" from "your
    token was revoked". Those distinctions have to survive the trip back to the UI as structured
    codes, because `SPEC-320` renders a different screen for each one.

*   **Business / Technical Value:** This is the entire daemon-side cost of `SPEC-404`. Because the
    gateway speaks the OpenAI-compatible wire format by contract (`SPEC-404` §2.3), the call path
    itself is a base URL and a bearer token — no new provider class, no new SDK, no change to any
    route that calls an LLM. What is genuinely new is narrow and worth specifying properly: getting
    quota numbers out of the response, and refusing to let four distinct failure modes collapse into
    one string.

*   **Non-Goals:**
    *   **Not a new AgentFlow provider class.** If this spec ends up writing one, the gateway
        contract has drifted from OpenAI-compatible and `SPEC-404` §2.3 is what should change, not
        this.
    *   **Not a change to AgentFlow.** Established by reading the installed source (§2.2): AgentFlow
        already returns the token usage this tier needs. If a change to `gittielabs-agentflow` turns
        out to be required after all, that is a finding for the context file's Plan Drift and a
        release of that package, not a silent local patch.
    *   **Not quota enforcement.** The daemon reports what the gateway tells it. It never decides
        whether a request is allowed, never pre-emptively blocks a call to save quota, and never
        caches a quota verdict. Enforcement is server-side by `SPEC-404` §3 — a client that enforced
        anything would be enforcing it against its own open-source, editable self.
    *   **Not sign-in, token acquisition, or any UI.** `SPEC-320`. The daemon receives a token; it
        has no idea how it was obtained.
    *   **Not a change to secret storage.** `SPEC-106`'s keychain → Rust → spawn-time secret channel
        carries the subscription token exactly as it carries an API key today. The daemon still never
        reads a config file or touches the keychain itself.
    *   **Not prompt, model, or routing changes.** Every existing route calls the LLM the same way it
        does now. Which vendor ultimately serves the call is the gateway's business.

## 2. System Architecture & Design Choices

### 2.1 Provider selection

The daemon's existing provider wrapper module (`SPEC-201`) gains a `managed` branch that constructs
`OpenAICompatProvider` with:

*   `base_url` — the gateway's `/v1` prefix, a build-time constant with an env-var override for
    development against a local gateway. **Not user-configurable through `config.json`**: a settable
    managed endpoint is an exfiltration surface (point a user's token at someone else's host) with
    no legitimate user-facing use, and `SPEC-303` has no field for it.
*   `api_key` — the subscription token, arriving over `SPEC-106`'s secret channel under its own
    key name, distinct from the vendor key names.
*   `model` — the gateway alias from `config.json`'s existing `llm_model` field.

**The daemon must not validate a Managed model name.** Aliases are the gateway's namespace
(`SPEC-404` §2.3); a client-side allow-list would break every time the gateway adds one, which is
exactly the coupling aliases exist to prevent. An unknown alias is the gateway's `400` to explain.

The lazy-import rule from `SPEC-201` §2 still applies: the provider SDK is imported inside the route
that uses it, never at startup, so the `daemon.ready` handshake (`SPEC-107`) never waits on it.

### 2.2 Token usage — AgentFlow already returns it; this repo throws it away

**Verified against the installed source at
`services/python-daemon/.venv/.../agentflow/`, 2026-08-25, rather than assumed** — the discipline
`SPEC-206` §3 and `CTX-401.1`'s corrected prediction both established for AgentFlow claims.

The finding is the opposite of what was expected, and it splits in two:

*   **AgentFlow does report token usage, on every provider.** `providers/openai_compat.py` (~L150)
    populates `usage` from `response.usage.prompt_tokens`/`completion_tokens`;
    `providers/anthropic.py` (~L149) from `response.usage.input_tokens`/`output_tokens`;
    `providers/google_genai.py` (~L196) from `usage_metadata.prompt_token_count`/
    `candidates_token_count`. All three normalise to the same `{input_tokens, output_tokens}` shape
    and attach it to the response object. **No change to AgentFlow is required.**
*   **This repository discards it.** `llm_providers.py`'s `chat()` ends with `return response.text`
    — the usage dict is constructed by the provider, handed back, and dropped on the floor one line
    from the caller. Nothing downstream has ever been able to see a token count, which is why it
    looks like AgentFlow does not report one.

So the work is local and small: widen the daemon's return shape to carry `{text, usage, model}`
instead of a bare string, and let it reach the job result. That is worth doing on its own merits,
independent of this spec — a project whose whole premise is provenance on every field
(`PRODUCT-PLAN.md`) currently cannot say what any AI call cost. **The return-shape change is a
breaking change to every caller of `llm_providers.chat()`** and should be its own context file,
landed before the managed branch rather than tangled with it.

**What AgentFlow genuinely does not expose is raw HTTP response headers.** That is why `SPEC-404`
§2.3 dropped the `X-HAS-Quota-*` header design: the app could not have read those headers without
either forking AgentFlow or bypassing the provider layer, and it does not need to. Period quota
state comes from `GET /v1/account`; per-call cost comes from the usage above.

The daemon does not interpret usage — it does not warn, threshold, or decide when a number is low.
Thresholds are presentation, and presentation is `SPEC-320`.

### 2.2.1 The three call sites — and the good news about naked calls

Keith's concern was direct vendor-SDK calls bypassing AgentFlow. **Checked across the whole daemon,
excluding `.venv` and tests: there are none.** No `import anthropic`, no `import openai`, no
`google.genai` in application code. The only non-AgentFlow network calls are `urllib.request` in
`library_store.py` and `community_libraries.py`, which fetch community footprint libraries
(`SPEC-314`) and touch no LLM. The provider abstraction is intact.

There is a real issue, but it is one layer in from where it was expected. **Three call sites build a
provider client directly via `llm_providers._build_provider()` and call `.chat()` on it, bypassing
`llm_providers.chat()`:**

| Site | Why it bypasses |
| :--- | :--- |
| `llm_providers.py` (~L162) | The wrapper itself — the intended path. |
| `chat_agents.py` (~L494) | Runs through AgentFlow's `AgentExecutor`, which calls the provider directly. |
| `component_pipeline.py` (~L230) | Same, and its own comment (~L192) documents the bypass and the client-close handling it had to duplicate. |

Both bypasses are legitimate — `AgentExecutor` needs the client, not a convenience wrapper. But they
mean **anything added only to `llm_providers.chat()` is invisible to two of the three paths**:
managed error mapping (§2.3), usage capture (§2.2), and the client-close handling `CTX-201.1` already
had to duplicate once.

**Decided: the managed branch and the error mapping belong in `_build_provider` and a shared
post-call helper, not in `chat()`.** `chat()` becomes one caller of that helper rather than the place
the logic lives. `component_pipeline.py`'s duplicated close handling is the existing evidence for
what happens otherwise — the same bug, fixed twice, in two files.

### 2.3 Error mapping

Gateway HTTP status → structured error code on the `SPEC-105` job-failure payload. A code, not
prose: `SPEC-320` selects a screen from it, and a screen must never be selected by string-matching a
message — the same rule `PRODUCT-PLAN.md` applies to user input applies to inter-layer payloads.

| Gateway | Code | Meaning to the layer above |
| :--- | :--- | :--- |
| `401` | `managed_auth_invalid` | Token bad, revoked, or account cancelled. Re-authentication needed. |
| `402` | `managed_quota_exhausted` | Allowance spent. Payload carries the reset timestamp. |
| `429` | `managed_rate_limited` | Payload carries `Retry-After` seconds. |
| `503` | `managed_upstream_unavailable` | The subscriber's account is fine; the vendor is not. |
| network/TLS/DNS failure | `managed_unreachable` | Distinct from all of the above, and from a daemon crash. |
| any other non-2xx | `managed_error` | Carries status and body excerpt for diagnostics. |

**Retry policy:** `503` with backoff, and `429` honouring `Retry-After`. Never retry `402` — the
answer will not change until the reset date, and a retry loop against an exhausted quota is a
support ticket generator. Never retry `401`.

`managed_unreachable` must not reach `SPEC-101`'s crash shield. A gateway that cannot be resolved is
an expected operational condition on a laptop that moved networks, not a daemon fault, and it must
not read as one to the user.

### 2.4 Timeouts

The gateway adds a hop and may itself be retrying upstream, so the client timeout must exceed the
direct-vendor value. `SPEC-205`'s datasheet extraction is the long pole and sets the floor. The
value belongs in the context file with the measurement behind it, not guessed here.

### 2.5 Testing

*   **No test may contact the real gateway.** Fixtures serve the contract: a fake gateway responding
    with OpenAI-shaped bodies plus the quota headers, and one canned response per row of §2.3's
    table.
*   `SPEC-201`'s `MockLLMProvider` covers "an LLM replied" and models neither quota headers nor the
    gateway's error taxonomy, so it does not fit here. A stub HTTP layer is the right seam.
*   Every row of the §2.3 table needs a test, including `managed_unreachable`, and the retry policy
    needs one asserting `402` is **not** retried.

### 2.6 Cross-Module Impacts

*   `services/python-daemon` — provider wrapper module (`managed` branch), error-code constants,
    job-payload quota fields, fixtures.
*   `specs/SPEC-106` — one new `llm_provider` value; one new keychain key name. Mechanism unchanged.
*   `apps/tauri-ui` — consumes the codes and quota fields (`SPEC-320`). Downstream only.
*   `services/python-daemon/requirements.txt` — no change expected; the OpenAI extra is already
    pinned by `SPEC-201`.

## 3. Known Constraints & Risks

*   **The `llm_providers.chat()` return-shape change (§2.2) is a breaking change to every caller**,
    and it should land as its own context file before the managed branch rather than inside it. It
    is also the single highest-value piece of this spec for the free build, which gets token
    accounting it has never had.
*   **The three-call-site problem (§2.2.1) is the real design risk here**, not the gateway. Any
    managed logic placed where only one of the three paths can see it will produce a provider that
    works in `llm.chat` and fails in the component pipeline — with a plausible-looking error that
    points at the wrong layer.
*   **A token can be revoked mid-job.** A datasheet extraction that fails at minute three must
    surface `managed_auth_invalid` cleanly and leave no partial artifact — `SPEC-108`'s write path is
    the thing that must not be entered with a failed generation behind it.
*   **Managed requires the network; Ollama does not.** A user who switched from Ollama to Managed has
    silently traded away offline operation. The daemon cannot fix this, but it must report
    `managed_unreachable` precisely enough that `SPEC-320` can explain it.
*   **The `stdout` rule** (`SPEC-000` §3, `SPEC-107`): the gateway client must never print. An HTTP
    library that logs to `stdout` by default would corrupt the JSON-RPC wire — verify the configured
    logger, do not assume it.
*   **Quota numbers are a snapshot, not a subscription.** They are correct as of the last call and go
    stale immediately. Anything in the UI implying a live meter is misrepresenting this data
    (`SPEC-320` §2).
*   **The base URL constant is a release-coupling risk.** A gateway migration would strand every
    installed copy pinned to an old build. Mitigation belongs to the gateway — keep the hostname
    stable and move things behind it — and is called out here so it is not solved by adding a
    user-editable endpoint field, which §2.1 rejects.

## 4. Module Map & Reference Links

```text
[SPEC-000 Root Architecture](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-404 Managed Hosted Access](../../../specs/SPEC-404-managed-hosted-access.md)
          ├── [SPEC-207 Managed Provider Adapter](SPEC-207-managed-provider-adapter.md)   ← this spec
          └── [SPEC-320 Managed Account Sign-In & Usage](../../../apps/tauri-ui/specs/SPEC-320-managed-account-signin-and-usage.md)
```

Builds directly on [SPEC-201 LLM Provider Abstraction](SPEC-201-llm-provider-abstraction.md),
[SPEC-105 Async Job & Progress Protocol](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md),
and [SPEC-106 Configuration & Secrets Store](../../../specs/SPEC-106-configuration-secrets-store.md).
