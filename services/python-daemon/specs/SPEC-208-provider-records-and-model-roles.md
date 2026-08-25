---
id: SPEC-208
title: "Provider Records & Model Role Resolution"
status: Draft
type: Feature
created: 2026-08-25
last_updated: 2026-08-25
target_version: v0.4.0
location: "services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md"
parent_spec: "SPEC-201-llm-provider-abstraction.md"
child_specs: []
user_facing: false
---

# SPEC-208: Provider Records & Model Role Resolution

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace three pieces of vendor coupling that `SPEC-201` left in place and
    that every spec since has inherited. (1) A provider is currently a *name* matched against a
    hardcoded if-chain with a hardcoded endpoint; it becomes a *record* — `{id, kind, base_url,
    api_key_ref, models}` — so any OpenAI-compatible server can be configured without a code change.
    (2) A `.prompt.md` currently names a vendor model (`claude-sonnet-5`); it names a **role**
    (`reasoning` / `fast`) that each provider record resolves to one of its own models, so a vendor
    swap does not flatten twelve deliberately-different agents onto one model. (3) An agent's real
    requirements — tool use, strict JSON — are currently undeclared and unchecked; they become
    frontmatter a preflight can verify, so an under-powered model fails loudly instead of returning
    empty results.

*   **Business / Technical Value:** `ROADMAP.md` §1's own scorecard quotes the product promise as
    "Local AI … plug in local Ollama models." What actually shipped supports exactly one local
    shape: Ollama, on this machine, on port 11434. An Ollama server on another box, LM Studio,
    `llama.cpp`'s server, vLLM, or an OpenAI-compatible aggregator all fail at
    `_build_provider` with `Unknown LLM provider`, and no config field exists that could carry the
    endpoint they need. Separately, the per-agent model differentiation the prompt files already
    encode (`datasheet_guidance_extraction` on `claude-sonnet-5`, the chat agents on
    `claude-sonnet-4-6`) is silently destroyed the moment anyone sets a model in Settings, because
    the override is one global pair applied to every agent. The two capabilities the product
    advertises — bring your own model, and use the right model for each job — are today mutually
    exclusive.

*   **Non-Goals:**
    *   **Not the Settings UI.** This spec defines the config schema and the daemon's resolution
        behaviour only. A provider record is more than the two flat fields `SPEC-303`'s picker
        writes, and the surface for editing one is a `3xx` spec that must be written before any of
        this is reachable by a person. Noted in `ROADMAP.md` §3.3 as a dependency of this spec, not
        smuggled in here.
    *   **Not a change to AgentFlow.** Verified against the installed source at
        `services/python-daemon/.venv/lib/python3.12/site-packages/agentflow/` on 2026-08-25, the
        discipline `SPEC-206` §3 and `SPEC-207` §2.2 both established: `AgentConfig`
        (`config/schemas.py` L23-36) has no `base_url` field and never will need one, because the
        endpoint belongs to the provider record, not to the agent. Everything this spec adds lives
        in the daemon's own resolution layer above AgentFlow's provider classes, exactly as
        `llm_providers.py` already does.
    *   **Not the Managed endpoint's configurability.** `SPEC-207` §2.1 rules that the gateway's
        `base_url` must stay a build-time constant because a settable managed endpoint is an
        exfiltration surface for a subscription token. This spec honours that: `managed` becomes a
        **locked** preset whose `base_url` is not writable from `config.json`, not a user-authored
        record. §2.2.3 defines what "locked" means mechanically.
    *   **Not secret storage.** `SPEC-106`'s keychain → Rust → spawn-time channel is unchanged. A
        provider record carries an `api_key_ref` — a *key name*, not a key — resolved against the
        same `CONFIG["secrets"]` dict the daemon already receives.
    *   **Not the `llm_providers.chat()` return-shape change.** `SPEC-207` §2.2 owns widening it to
        `{text, usage, model}` and says it should land as its own context file first. This spec
        touches the same function and must be sequenced around that, not tangled with it.
    *   **Not streaming, not model benchmarking, not automatic model selection.** A role maps to a
        model the user configured. Nothing here measures a model, ranks one, or picks one for the
        user.

## 2. System Architecture & Design Choices

### 2.1 The finding — what is coupled, and what turned out not to be

Established by reading the code on 2026-08-25, and the first half is the opposite of what was
suspected, so it is recorded before the design.

**The call path is not hardcoded.** The `provider:`/`model:` keys in each `.prompt.md` are
*defaults*. `CONFIG["llm_provider"]`/`["llm_model"]` override them at every call site —
`chat_agents._dispatch` (~L483-491) and `component_pipeline._build_executor` (~L219-227) both build
an `overrides` dict and apply it with `model_copy(update=...)`, and `daemon.py` threads CONFIG
through every LLM route consistently. `CTX-303.2` already found and fixed the one route that
didn't. Switching provider in Settings genuinely changes which provider class gets constructed.

**Four things are coupled anyway:**

| # | Coupling | Where | Consequence |
| :--- | :--- | :--- | :--- |
| 1 | Provider names are a closed if-chain; endpoints are module constants | `llm_providers.py` L65-103; `_OLLAMA_BASE_URL` L29, `_PERPLEXITY_BASE_URL` L30 | Any local or self-hosted server that is not Ollama-on-localhost is unreachable, and no config field could express it |
| 2 | One global provider+model pair overrides every agent | `chat_agents.py` L483-491, `component_pipeline.py` L219-227 | Per-agent model differentiation and a non-Anthropic provider are mutually exclusive |
| 3 | Capability requirements are implicit | `agentflow/agents/*.prompt.md` `tools:` and the strict-JSON prompt bodies | A model that cannot tool-call returns plain text on round 1 and the loop simply ends — no error, ungrounded answer, every citation dropped by `chat_agents`' own source-ref validation |
| 4 | The local default is a 1B model | `_DEFAULT_MODELS["ollama"] = "llama3.2:1b"` L54 | Selecting Ollama without typing a model points a 1B model at 4096-token JSON extraction and a 4-round tool loop — coupling 3 firing on first use |

On coupling 3, verified in `agentflow/agent/runtime.py`: `AgentExecutor.run` passes
`config.temperature` and `config.max_tokens` per call (L117-118) and loops only while
`response.stop_reason == "tool_use"` (L156). A provider that returns text with no tool calls is
indistinguishable, to the executor, from a model that decided it needed no tools. There is no
error path, and there should not be one inside AgentFlow — the check belongs here.

The asymmetry in how the two structured pipelines handle a bad response makes coupling 3 worse in
one direction: `component_pipeline` retries on malformed JSON (~L565-615), while
`datasheet_guidance` drops the item by design ("drop, never repair", `datasheet_guidance.py` L28).
Under a model that cannot hold the JSON contract, the first path is slow and the second returns an
empty, *successful* result.

**Also found, minor but real:** `daemon.configure` (L847-866) accepts `llm_model` without
`llm_provider`, which grafts a foreign model name onto whatever the frontmatter declared —
reachable over the RPC even though `Settings.tsx` never does it (L327 gates the model save on a
provider being set). §2.5 closes it.

### 2.2 Provider records

#### 2.2.1 The record

A provider stops being a string and becomes a record. `config.json` gains a `providers` array and a
`provider_roles` map, replacing the flat `llm_provider`/`llm_model` pair (§2.5 covers migration):

```jsonc
{
  "providers": [
    {
      "id": "workshop-ollama",          // unique, user-chosen, referenced by role bindings
      "kind": "openai_compat",          // anthropic | openai_compat | google — the SDK shape
      "base_url": "http://nuc.local:11434/v1",
      "api_key_ref": null,              // a KEY NAME in SPEC-106's secret set, never a key
      "models": { "reasoning": "qwen2.5:32b", "fast": "qwen2.5:7b" },
      "capabilities": { "tool_use": true, "strict_json": true }   // declared; see §2.4
    }
  ],
  "provider_roles": { "reasoning": "workshop-ollama", "fast": "workshop-ollama" }
}
```

**`kind`, not `id`, selects the SDK.** `_build_provider` becomes a three-way switch on `kind` —
`AnthropicProvider`, `OpenAICompatProvider`, `GoogleGenAIProvider` — with `base_url` supplied by the
record rather than by a constant. Every currently-supported provider is expressible: `anthropic` and
`google` are their own kinds; `openai`, `perplexity`, `ollama`, and `SPEC-207`'s `managed` are all
`openai_compat` records that differ only in `base_url`. The if-chain that has to grow a branch per
vendor stops growing.

**`Unknown LLM provider` stops being the error for a valid setup.** It survives, correctly, for an
unknown *kind* — three values, closed on purpose, because each maps to an SDK this daemon actually
depends on. A fourth kind is a real dependency decision, not a config entry.

#### 2.2.2 Built-in presets

The five names that work today ship as seeded records with today's exact values —
`_DEFAULT_MODELS` and the two base-URL constants become preset data, not code paths. An existing
install keeps working with no user action (§2.5). A preset is an ordinary record: editable,
removable, and copyable as the starting point for a new one.

**One preset value changes.** `llama3.2:1b` is replaced as the Ollama preset's `reasoning` model.
A 1B model cannot hold this repo's JSON contracts or tool-call, and shipping it as the default is
the single most likely way a user concludes the *app* is broken. The replacement must be chosen by
running the real `component_extraction` and `datasheet_guidance_extraction` prompts against
candidates on a real local server and recording what actually passed — the `CTX-201.1` discipline
of confirming a default against a live call rather than assuming it — and the preset should leave
`fast` and `reasoning` pointing at genuinely different sizes so the role split is exercised by the
default configuration, not only by hand-built ones.

#### 2.2.3 The `managed` exception

`SPEC-207` §2.1 forbids a user-settable managed endpoint. Mechanically: the `managed` record is
**locked** — it is not read from `config.json` at all. It is constructed in code from the build-time
constant `SPEC-207` defines, injected into the resolved provider set at load time, and a
`config.json` entry whose `id` is `managed` is **ignored with a logged warning**, not merged. A
record cannot claim that id, and the id is reserved rather than validated by shape, so a future
gateway change cannot accidentally open the hole by making a user record look legitimate.

Its `models` map is the gateway's alias namespace, which `SPEC-207` §2.1 says the daemon must not
validate. Roles resolve through it exactly as for any record; an unknown alias remains the
gateway's `400` to explain.

### 2.3 Model roles

#### 2.3.1 The change to `.prompt.md`

A `.prompt.md` stops naming a vendor model and names a role:

```yaml
# before
provider: anthropic
model: claude-sonnet-5

# after
model_role: reasoning
```

Two roles, deliberately: **`reasoning`** for the agents whose output is parsed, validated, and
stored — `component_extraction`, `component_search`, `connection_guidance`,
`datasheet_guidance_extraction`, `board_advisor`, `footprint_query_suggestion` — and **`fast`** for
the conversational and summarising agents where a wrong word costs a re-read rather than a bad
record: the five `chat_*` agents and `datasheet_guidance_synthesis`.

**Two, not five.** A role vocabulary is a contract every provider record must satisfy: each added
role is another model a user has to nominate before their configuration is complete, and a role
nobody can distinguish in practice gets filled with the same model twice. Two is the smallest split
that reproduces the distinction the current frontmatter already makes — sonnet-5 for extraction,
sonnet-4-6 for chat — and it is the split a person running local models can actually act on, because
"the big one I run when it matters" and "the small fast one" is how a local setup is already
organised. If a third is genuinely needed later, adding one is a preset migration, not a redesign;
removing one is not.

Note what stays in frontmatter: `temperature`, `max_tokens`, `max_tool_rounds`, and `tools` are
properties of the *task*, not of the vendor, and are unaffected.

#### 2.3.2 Resolution order

For an agent, in order, first hit wins:

1.  An explicit per-call `provider`/`model` argument on the route (`SPEC-303`'s existing per-call
    override, `CTX-303.2`, and the diagnostic path — unchanged).
2.  `provider_roles[agent.model_role]` → that record → `record.models[agent.model_role]`.
3.  The seeded default record for that role.

A missing role binding, an `id` with no matching record, or a record whose `models` map has no entry
for the role is a **configuration error surfaced as `LLMProviderError` before any network call** —
never a silent fall-through to a default provider. The current code's habit of quietly substituting
(`_DEFAULT_PROVIDER` at `daemon.py` L897, `_DEFAULT_MODELS.get(provider, agent_config.model)` at
`chat_agents.py` L489) is what makes a half-configured install look like a working one; the seeded
records in §2.2.2 mean a *fresh* install is fully configured, so a resolution failure after that
point is real and worth reporting.

This is what closes coupling 2: because the binding is per role and an agent declares its role, a
user can run chat on a local model and keep extraction on a hosted one. That configuration is the
main thing this spec exists to make expressible.

#### 2.3.3 How the new frontmatter reaches the resolver — AgentFlow drops it

**Verified against the installed source on 2026-08-25, and the answer is the awkward one.**
`AgentConfig` (`config/schemas.py` L23) is a plain pydantic v2 `BaseModel` with no `model_config`,
so `extra` defaults to `"ignore"`, and `ConfigLoader._load_agents` (`config/loader.py` L135) builds
it with a bare `AgentConfig(**meta)`. **`model_role` and `requires` are parsed out of the YAML and
silently discarded** — `loader.get_agent()` can never return them, and nothing raises.

Three ways out, and the choice matters enough to make here rather than in the context file:

*   *Change AgentFlow to `extra="allow"`* — rejected. It is a real upstream release for a schema
    that is not this app's to define, and `SPEC-207` §1's non-goal ("not a change to AgentFlow")
    holds for the same reason.
*   *Smuggle the role through the existing `model` field* (`model: role:reasoning`) — rejected. It
    type-checks, which is exactly the problem: any code path that does not know the convention
    passes the literal string to a provider as a model name.
*   **Adopted: a thin local sidecar.** The daemon re-reads the same `.prompt.md` files with
    AgentFlow's own `parse_prompt_file`, keeps `{agent_name: {model_role, requires}}` in a dict
    beside the loader, and hands both to the resolver. AgentFlow's loader stays the source of truth
    for everything it does model; this adds one small map for the two keys it does not, with no
    fork and no vendored schema.

**Gotcha to carry into the context file:** because `extra="ignore"` never errors, a *typo* in
`model_role` is discarded just as silently as a valid unknown key was. The sidecar reader must
validate its own two keys itself — an agent file with neither `model_role` nor a recognised role
value is a load-time error, not a fall-through to a default role.

### 2.4 Capability declarations and preflight

An agent declares what it actually needs:

```yaml
requires: [tool_use]        # the five chat_* agents
requires: [strict_json]     # every agent whose prompt body says "respond with ONLY"
```

A provider record declares what it offers (`capabilities`, §2.2.1). Before the first call of a
session for a given (record, role) pair, the resolver checks the agent's `requires` against the
record's `capabilities` and, on a mismatch, raises a `LLMProviderError` naming **the agent, the
requirement, and the record** — not a generic failure, because the fix is a specific one the user
has to make in a specific place.

**A declaration is a claim, not a measurement, and the spec should not pretend otherwise.** For the
seeded presets the claim is trustworthy — those are known hosted APIs. For a user-authored record it
is whatever the user ticked. Two consequences to accept explicitly rather than design around:

*   A preflight catches the *honest* misconfiguration — a user who knows their 3B model does not
    tool-call and said so — which is the common case and worth catching. It does not catch an
    optimistic tick.
*   A real capability probe (send a trivial tool-use request, see what comes back) is the only way
    to know. It costs a call, and the result is per model, not per record. **Deferred, and named
    here so it is deferred rather than forgotten:** if it is added, it belongs behind an explicit
    "Test this provider" action, cached per (record, role, model), and must never run at daemon
    start — `SPEC-201` §2 and `SPEC-000` §3's constraint that nothing may delay the `daemon.ready`
    handshake applies with full force, and a probe is a network call, which is worse than the SDK
    import that constraint was written about.

Capability checking cannot become a quality check, and the spec should not let a later reader think
it did. A model can tool-call correctly and still give bad hardware advice. Nothing here replaces
`SPEC-202`'s validation layer, `SPEC-205`'s citation validation, or `SPEC-319`'s confirmation gate.

### 2.5 Config schema, migration, and the Rust side

`core/tauri-rust/src/config.rs`'s `DaemonConfig` (L15-49) carries `llm_provider`/`llm_model` as
`Option<String>` and serialises the whole struct into the spawn-time env var `CTX-106.1`
established. It gains `providers: Option<Vec<ProviderRecord>>` and `provider_roles:
Option<HashMap<String, String>>`. Rust does not interpret either — it carries them, exactly as it
carries every other field it does not read.

**Migration is one-way and automatic.** On load, a `config.json` with `llm_provider` set and no
`providers` array is read as "bind both roles to the preset with that id, using `llm_model` for
`reasoning` if it is set." The legacy fields are then re-serialised alongside the new ones for one
release so a downgrade does not strand a user, and are removed in the release after. No user action,
no settings screen appearing empty after an update.

**`daemon.configure`'s partial-update bug closes here.** Role bindings arrive as a complete map or
not at all — the same "always the complete current set" contract `CTX-303.1` established for
`secrets` — which removes the possibility of a model without a provider (§2.1, last paragraph)
rather than adding a guard against it.

**Stored provenance is unaffected.** `library_store` validates that a `Part.connection_guidance`
carries `provenance: {provider, model}` (L293-296) and records already on disk carry real vendor
strings. Provenance keeps recording the *resolved* provider id and concrete model — what actually
answered — never the role. A role is how the call was routed; it is not a fact about the record, and
a stored fact that changes meaning when a user edits their config would be worse than no fact.

### 2.6 One resolver, and the three call sites

`SPEC-207` §2.2.1 established that three sites construct a provider —
`llm_providers.chat()` (~L162), `chat_agents._dispatch` (~L494), and
`component_pipeline._build_executor` (~L230) — and that the latter two legitimately bypass
`llm_providers.chat()` because `AgentExecutor` needs the client, not a convenience wrapper. Its
warning applies directly to this spec: **anything added only to `chat()` is invisible to two of the
three paths.**

So resolution lands in one new function — `llm_providers.resolve(agent_config, config) -> (client,
resolved_provider_id, resolved_model)` — that all three call, and the duplicated `overrides` blocks
in `chat_agents.py` and `component_pipeline.py` are deleted rather than adapted. Those two blocks
are already near-identical copies of each other; a third copy of the role logic is how the next
provider feature ends up only half-applied. This is the same consolidation `SPEC-207` needs for its
error taxonomy and usage capture, which is an argument for sequencing this spec's first context file
before or alongside that work rather than after it.

### 2.7 Cross-Module Impacts

*   `services/python-daemon` — `llm_providers.py` (records, kinds, the resolver, presets),
    `chat_agents.py` and `component_pipeline.py` (override blocks deleted, resolver called),
    `daemon.py` (`CONFIG` shape, `configure_daemon`, `_KEY_BASED_PROVIDERS` L185 becomes
    record-derived rather than a literal tuple, `daemon.ready`'s `llm_providers` capability field
    L1700 reports configured records), all twelve `agentflow/agents/*.prompt.md` (`provider`/`model`
    → `model_role`, plus `requires`).
*   `core/tauri-rust` — `config.rs` two new fields and the migration read; `KNOWN_SECRET_KEYS` stops
    being a fixed allowlist that has to match a hardcoded provider list.
*   `apps/tauri-ui` — `src/lib/settings.ts`'s `KEY_BASED_PROVIDERS`/`ALL_PROVIDERS` literals (L10,
    L15) and `Settings.tsx`'s picker are **knowingly left stale by this spec** and continue to work
    against the migrated legacy fields. The follow-up `3xx` spec replaces them. Recorded so the next
    reader knows it is deferred, not missed.
*   **Upstream:** none. `gittielabs-agentflow` is unchanged (§1, non-goals).
*   **Downstream:** `SPEC-207` — `managed` becomes a preset record instead of a sixth if-branch.
    Strictly less work for that spec, but it is a real coordination point: whichever lands second
    adapts. `SPEC-207` is Draft and unstarted, which is the argument for doing this first.

## 3. Known Constraints & Risks

*   **A declared capability is not a verified one.** §2.4 is explicit about this. The failure mode
    this spec does *not* close is a user who ticks `tool_use: true` for a model that cannot do it,
    and gets exactly today's silent degradation. Accepted deliberately: closing it needs a live
    probe, and a probe at the wrong moment breaks the `daemon.ready` handshake.
*   **Two roles will not fit every setup.** Someone running one local model binds both roles to it
    and gets today's flat behaviour — correctly, and now visibly, because they said so in config
    rather than discovering it. Someone wanting three tiers cannot express it. Judged the right
    trade (§2.3.1); worth revisiting only with a real user configuration that needs the third, not
    on principle.
*   **A user-settable `base_url` is an exfiltration surface for the user's own key.** A record
    pairing a vendor `api_key_ref` with an attacker-chosen `base_url` would send that key to the
    attacker's host. Three mitigations, and none of them is "don't allow it," because a settable
    endpoint is the entire point of the spec: presets ship locked to their real endpoints and a user
    must deliberately author a record to deviate; a record with a non-loopback `base_url` **and** a
    non-null `api_key_ref` is the case the `3xx` Settings spec must warn on explicitly; and
    `managed` is out of reach entirely (§2.2.3). Recorded here because the `3xx` spec inherits the
    requirement and must not rediscover it.
*   **`llama3.2:1b`'s replacement must be verified live, not chosen from reputation.** §2.2.2. This
    is exactly the trap `CTX-201.1` and `CTX-202.1`'s Plan Drift both recorded — a default model
    name that was plausible, assumed, and wrong. A candidate that has not actually run this repo's
    real prompts on a real local server does not go in.
*   **The `datasheet_guidance` drop-vs-retry asymmetry is not fixed here.** A weak model still
    produces an empty, successful-looking guidance result (§2.1). The capability preflight makes the
    *cause* legible; it does not make an empty result distinguishable from "this datasheet has
    nothing to say about this category." That distinction is `SPEC-205`'s to draw and should be
    raised there rather than absorbed here.
*   **Ordering against `SPEC-207`.** Both specs edit the same three call sites and the same
    function. Landing this one first makes `SPEC-207` smaller; landing `SPEC-207` first means it
    writes an if-branch this spec then deletes. Neither is broken, but the second wastes work and
    leaves a branch in the tree that reads as the sanctioned pattern.
*   **AgentFlow silently discards the new frontmatter keys.** Resolved in §2.3.3 with a local
    sidecar reader, but the underlying hazard outlives this spec: `AgentConfig` ignores every
    unknown frontmatter key without error, so *any* future key added to a `.prompt.md` is inert
    until something in this repo reads it deliberately. A key that looks configured and does
    nothing is worse than one that fails, and nothing upstream will warn about it.
*   **Twelve prompt files change frontmatter in one edit.** Mechanical, and safe only because
    §2.3.3's sidecar validates its own keys — without that validation the edit could half-land
    across twelve files and still load cleanly.

## 4. Module Map & Reference Links

```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-201: LLM Provider Abstraction](SPEC-201-llm-provider-abstraction.md)
          └── [This Spec](SPEC-208-provider-records-and-model-roles.md)
                 ├── (planned) CTX-208.1 — provider records, kinds, presets, one resolver
                 ├── (planned) CTX-208.2 — model roles across the twelve prompt files
                 └── (planned) CTX-208.3 — capability declarations and preflight
```

Related, not children:

*   [SPEC-207: Managed Provider Adapter](SPEC-207-managed-provider-adapter.md) — `managed` becomes a
    preset record here; §2.2.3 and §3 are the coordination points.
*   [SPEC-303: Settings UI](../../../apps/tauri-ui/specs/SPEC-303-settings-ui.md) — its §1 non-goal
    "Not Ollama's endpoint … deferred, not forgotten" is what this spec closes on the daemon side.
    Its provider picker is superseded by the follow-up `3xx` spec, not by this one.
*   [SPEC-205: Datasheet-Driven Design Guidance](SPEC-205-datasheet-design-guidance.md) — owns the
    empty-vs-nothing-to-say distinction §3 raises.
