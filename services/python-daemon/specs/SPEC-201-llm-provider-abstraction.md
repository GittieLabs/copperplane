---
id: SPEC-201
title: "LLM Provider Abstraction"
status: Completed
type: Feature
created: 2026-08-09
last_updated: 2026-08-25
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs:
  - "SPEC-208-provider-records-and-model-roles.md"
user_facing: false
---

# SPEC-201: LLM Provider Abstraction

## 1. Executive Summary & Goals

*   **High-Level Goal:** Adopt AgentFlow's (`gittielabs-agentflow`) provider layer —
    `AnthropicProvider`, `OpenAICompatProvider` (covers OpenAI, Azure, and Ollama — Ollama rides the
    OpenAI-compatible provider, not a bespoke client), `GoogleGenAIProvider`, `MockLLMProvider` for
    tests — as the daemon's one path to calling an LLM. AgentFlow already solves the provider
    protocol, streaming, and per-agent model selection via `.prompt.md` front-matter; there is no
    reason to write a second one.
*   **Business / Technical Value:** This is the first real dependency-chain link toward M1's demo
    goal (`ROADMAP.md` §4): `kicad.generate_component` today is `time.sleep(1.5)` plus fabricated
    filenames. Nothing downstream (`SPEC-202`'s component pipeline, `SPEC-108`'s KiCad injection) can
    exist without a real, working way to call an LLM first.
*   **Non-Goals:**
    *   **Not session/workflow state.** AgentFlow also ships `SessionManager`, `Scratchpad`,
        `ArtifactStore`, and `MemoryManager` — this spec adopts none of them. `SPEC-201`'s own scope
        (per `ROADMAP.md` §3.2) is a single LLM call per request, matching M1's actual demo shape
        ("type a part number, watch an AI generate a real footprint" — one call, not a multi-turn
        workflow). Whether `SPEC-202`'s component pipeline needs session/memory state is that spec's
        decision to make when it actually needs multi-step orchestration, not this one's to
        pre-empt. Deferring this was `ROADMAP.md` §3.2's own open question; resolved here by scoping
        it out rather than deciding it for a spec that doesn't yet exist.
    *   **Not the component-generation pipeline itself, or any prompt content.** `SPEC-202` is where
        an actual `.prompt.md` gets written for "generate a KiCad symbol/footprint from a part
        number." This spec only makes calling *some* configured LLM possible and safe.
    *   **Not a hallucination-safety net.** A generated footprint reaching a real board unchecked is
        `SPEC-202`'s validation layer and `SPEC-204`'s confirmation gate to own (`ROADMAP.md` §6's
        risk register already names both). This spec's job ends at "the daemon can get a response
        back from the LLM you configured."

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Decided: AgentFlow's own `agents/`/`workflows`/`domains`/`shared` tree lives at
        `services/python-daemon/agentflow/`, not `services/python-daemon/context/`.** This was
        `ROADMAP.md` §3.2's first open question, raised rather than pre-decided: `context/` already
        means something specific and unrelated in this repo (`CTX-*.md` implementation plans, per
        `CONTRIBUTING.md` §3). A plain, visible `agentflow/` directory — not a dotfile, matching the
        visibility of `specs/`/`context/`/`tests/` elsewhere in this module — avoids the name
        collision without hiding AgentFlow's config from a human browsing the module.
    *   **Provider SDKs are optional installs, lazy-imported.** `gittielabs-agentflow` on PyPI
        (confirmed via its real package metadata, not assumed) ships `anthropic`/`openai`/
        `google-genai` as separate extras (`[anthropic]`, `[openai]`, `[google]`), not baked into
        the base install. `requirements.txt` pins `gittielabs-agentflow[anthropic,openai,google]`
        — every provider this daemon might route to, without pulling in unrelated extras (`chromadb`,
        `qdrant-client`, `boto3`, `langfuse` — vector stores and telemetry SPEC-201 has no use for).
        The actual provider client class is imported only inside the route that uses it, not at
        daemon startup — `SPEC-000` §3's constraint (heavy provider SDK imports can block `stdout`
        for 2-4 seconds) means the `daemon.ready` handshake (`SPEC-107`) must never wait on a
        provider the user hasn't selected.
    *   **Model selection reuses `SPEC-106`'s existing config fields.** `DaemonConfig.llm_provider`/
        `llm_model` (`CTX-106.1`) were added to that struct in anticipation of exactly this spec —
        this is their first real consumer. No new config-injection mechanism needed.
    *   **The "Local AI (Privacy First)" README claim gets a written, honest answer, not a code
        interface.** Which provider is configured determines what leaves the machine — Ollama via
        `OpenAICompatProvider` pointed at a local endpoint sends nothing off-device; Anthropic/
        OpenAI/Google send the prompt (and whatever context it includes) to that provider's API.
        AgentFlow picks the provider you configure; it makes no privacy guarantee on its own. This
        spec's job is stating that plainly (in a doc a human reads before configuring a provider),
        not building a code path that enforces it.
*   **Data Flow / Interactions:**

    ```text
    daemon.py route calls into a thin wrapper module (not the daemon's
    ROUTES registry directly) that:
       │
       ▼
    Reads llm_provider/llm_model from CONFIG (SPEC-106's daemon.configure
    handshake already populated this)
       │
       ▼
    Lazily imports and constructs the matching AgentFlow provider class
    (only at this point -- never at daemon startup)
       │
       ▼
    Calls the provider with the prompt, returns the response
       │
       ▼
    A provider-specific failure (bad API key, unreachable Ollama endpoint,
    rate limit) surfaces as a clean, specific daemon error -- never a raw
    SDK traceback reaching the frontend
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: new `agentflow/` directory (AgentFlow's own config tree, distinct
        from `context/`); `requirements.txt` gains `gittielabs-agentflow[anthropic,openai,google]`;
        a new thin provider-wrapper module `daemon.py` routes to.
    *   No impact on `core/tauri-rust` or `apps/tauri-ui` — this spec is entirely
        `services/python-daemon`-internal. The API key secrets it needs ride `SPEC-106`'s existing
        `daemon.configure` handshake once a real key name exists to add to Rust's
        `KNOWN_SECRET_KEYS` allowlist.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   None yet — no LLM client exists in this repo today; this spec has no existing broken
        behavior to fix, only a real gap to close.
*   **Gotchas & Hazards:**
    *   **A provider SDK import at the wrong time reintroduces the exact startup-latency problem
        `SPEC-107` was written to catch.** The lazy-import discipline here isn't optional polish —
        it's the difference between `daemon.ready` firing promptly and firing 2-4 seconds late for
        every user, including ones who never touch the LLM feature this session.
    *   **`MockLLMProvider` (AgentFlow's own, not a bespoke daemon mock) must be the one used in
        tests that don't want a real network call.** Writing a second, parallel mock would duplicate
        AgentFlow's own test-support surface for no reason.
    *   **A real end-to-end test against a live provider needs a real API key or a real local Ollama
        instance — this repo has neither committed, for good reason.** Matching `CTX-103.1`/`104.1`'s
        "verify for real, skip cleanly when unavailable" pattern: a real-provider test should skip
        itself when no credential/local-endpoint is configured on the machine running it, not be
        skipped from the suite entirely or, worse, silently mocked and called "real."
    *   **Whichever secret key name this spec introduces (e.g. `anthropic_api_key`) must be added to
        `core/tauri-rust/src/daemon.rs`'s `KNOWN_SECRET_KEYS` allowlist (`CTX-106.1`) in the same
        context that starts using it** — that allowlist was deliberately left empty until a spec had
        a real key to add; this is that spec.

## 4. Module Map & Reference Links

*   [ROADMAP.md](../../../ROADMAP.md) §3.2, §4 — this spec's backlog entry, its two open questions
    (resolved above), and the M1 critical path it unblocks.
*   [SPEC-106](../../../specs/SPEC-106-configuration-secrets-store.md) / [CTX-106.1](../../../context/CTX-106.1-config-secrets-store.md) —
    the `llm_provider`/`llm_model` config fields and secrets-injection mechanism this spec is the
    first real consumer of.
*   [SPEC-107](../../../specs/SPEC-107-structured-logging-diagnostics.md) — the `daemon.ready`
    handshake this spec's lazy-import discipline must not delay.
*   [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) — the async job
    protocol an LLM call (almost certainly multi-second) should very likely dispatch through, same
    as `freecad.generate_enclosure` — this context's call to confirm when it wires the real route.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-201] LLM Provider Abstraction
          └── [Context 201.1] (not yet written)
```
