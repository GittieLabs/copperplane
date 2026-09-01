---
id: SPEC-321
title: "Provider Configuration UI"
status: Completed
type: Feature
created: 2026-08-26
last_updated: 2026-08-26
target_version: v0.2.0
location: "apps/tauri-ui/specs/SPEC-321-provider-configuration-ui.md"
parent_spec: "../../../services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md"
child_specs: []
user_facing: true
---

# SPEC-321: Provider Configuration UI

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace Settings' flat, hardcoded provider picker (one `<select>` over five
    fixed names, one free-text model field) with a real editor over `SPEC-208`'s provider records:
    add, edit, and remove records (including built-in presets), bind the `reasoning`/`fast` roles to
    them, and see a migrated install's own real resolved state — all without `SPEC-208`'s daemon-side
    work being wasted on a UI nobody can reach.

*   **Business / Technical Value:** `SPEC-208` closed the coupling between "bring your own model" and
    "the right model for each job" entirely on the daemon side — a `config.json` hand-edit can
    already express an Ollama server on another machine, or split `reasoning` and `fast` across two
    different providers. Confirmed directly against the running code that nothing in the app can do
    either of those things today: `Settings.tsx`'s picker writes exactly two flat fields
    (`llm_provider`/`llm_model`) via `setLlmProviderAndModel`, `settings.ts`'s `DaemonConfig`
    interface has no `providers`/`provider_roles` fields at all despite Rust's own `DaemonConfig`
    struct (`core/tauri-rust/src/config.rs`) carrying both since `CTX-208.1`, and `daemon.py` never
    reads either field into `CONFIG` at startup or through `daemon.configure` — confirmed by reading
    `_apply_env_config()` and `configure_daemon()` directly, not assumed. Every early adopter this
    product is being built for right now is exactly the audience who wants to point chat at a local
    Ollama box and extraction at a hosted model, and today literally cannot.

*   **Non-Goals:**
    *   **Not the Managed tier.** `managed` is a locked, code-constructed record
        (`SPEC-208` §2.2.3, `SPEC-207` §2.1) — never listed, never selectable, never editable here,
        under any circumstance. This is a hard product decision for this phase, not a placeholder:
        there is no hosting decided, no auth provider chosen, and no billing built, so there must be
        no path in this UI that makes Managed look like a real, working option. `SPEC-320` is where
        Managed actually gets a surface, whenever that work starts.
    *   **Not a capability probe.** `SPEC-208` §2.4 already deferred a real "does this model actually
        tool-call" test call; this spec doesn't revive it. A declared capability stays a claim the
        user makes, not a measurement.
    *   **Not new roles.** Exactly the two `SPEC-208` §2.3.1 already defined, `reasoning` and `fast`.
        Adding a third is that spec's call to make, not this UI's.
    *   **Not a settings-file format change.** This spec is the reader/writer for the schema
        `SPEC-208` §2.2/§2.5 already defines; it does not redesign `config.json`'s shape.

## 2. System Architecture & Design Choices

### 2.1 The real gap this spec closes, verified against the installed code

Three separate gaps, not one, each confirmed by reading the actual source rather than assumed from
`SPEC-208`'s own text:

1.  **The frontend type is missing the fields entirely.** `apps/tauri-ui/src/lib/settings.ts`'s
    `DaemonConfig` interface has no `providers`/`provider_roles` members. The Rust struct already has
    both (`core/tauri-rust/src/config.rs`, `CTX-208.1`) and `get_config`/`save_config_cmd` already
    round-trip whatever the struct carries — this is a pure TypeScript typing gap, not a missing IPC
    command.
2.  **The daemon never reads either field into `CONFIG`.** `daemon.py`'s `_apply_env_config()` (startup)
    and `configure_daemon()` (`daemon.configure`, live updates from Settings) both only ever touch
    `CONFIG["llm_provider"]`/`CONFIG["llm_model"]`. `llm_providers.resolve()`'s own `config` parameter
    — the thing that actually reads `provider_roles`/`providers` — has had nothing supplying it since
    the day it was written. Without this, the whole editor would be cosmetic: it could write
    `config.json`, but nothing at runtime would ever look at what it wrote until the next full daemon
    restart re-read the env var, and even then only if `_apply_env_config` were also fixed.
3.  **A custom provider's secret has nowhere to be validated or synced.** `core/tauri-rust/src/
    secrets.rs`'s `validate_known_key` and `daemon.rs`'s `collect_known_secrets` both operate over the
    fixed `KNOWN_SECRET_KEYS` array. A user-authored record's `api_key_ref` (`SPEC-208` §2.2.1: "a KEY
    NAME... never a key") is by definition not in that array — `save_secret` would reject it outright,
    and even if it didn't, `collect_known_secrets` would never read it back out of the keychain to
    push to the daemon. `SPEC-208` §2.7 already named the shape of the fix ("`KNOWN_SECRET_KEYS`
    stops being a fixed allowlist that has to match a hardcoded provider list") but never built it,
    correctly, since it had no real caller yet.

### 2.2 Rust: secret validation becomes config-aware, not open

`validate_known_key`/`collect_known_secrets` both gain access to the current `DaemonConfig` (already
loadable via `config::load_config(app)`, an `AppHandle` is already in scope at every call site of
both functions — confirmed directly, no new plumbing needed to reach one). A key is valid if it is
either in the fixed `KNOWN_SECRET_KEYS` array (the five vendor/GitHub presets, unchanged), **or** it
appears as some `providers[].api_key_ref` in the currently-saved config. This is not "anything goes":
a key name that isn't the fixed allowlist and isn't currently referenced by a real, saved provider
record is still rejected. Consequence worth stating plainly: **a record must be saved before its key
can be**, so the editor's own save flow is record-first, key-second — attempting the reverse order is
a real, specific error, not a confusing generic one.

`collect_known_secrets` (and therefore every `sync_secrets_to_daemon` call — after every key
save/clear, and at daemon spawn) reads the same config to enumerate custom refs, so a custom
provider's key reaches `CONFIG["secrets"]` through the exact same path every vendor key already does.
No second sync mechanism, no special case for "custom" keys once the record naming them is saved.

### 2.3 Daemon: `providers`/`provider_roles` actually reach `CONFIG`

*   `_apply_env_config()` gains `CONFIG["providers"] = env_config.get("providers")` and
    `CONFIG["provider_roles"] = env_config.get("provider_roles")` alongside the two existing lines —
    both default to `None`/absent exactly like today's fresh-install case, so `llm_providers
    .migrate_legacy_config` (`CTX-208.2`, already real and already tested) does exactly what it
    already does for an install that predates this spec.
*   `configure_daemon()` gains `providers`/`provider_roles` parameters, following the exact contract
    `SPEC-208` §2.5 already named for this: **always the complete current set, or not sent at all** —
    the same discipline `CTX-303.1` established for `secrets`, applied here rather than merged. A
    partial role-binding update (e.g. "just change `fast`") is expressed by the *client* re-sending
    both roles, never by the daemon guessing what stayed the same.
*   `chat_agents.send`/`review` and every `component_pipeline.py` entry point already thread a
    `config`/`app_config` parameter all the way to `resolve()` (`CTX-208.2`/`CTX-208.3`) — this spec
    changes nothing there. The only gap was CONFIG never having real data in those two keys to hand
    them in the first place.

### 2.4 A new route: the resolved provider set, for the UI to render

The presets (`anthropic`/`google`/`openai`/`perplexity`/`ollama`, and their exact current
`models`/`capabilities`) are Python data (`llm_providers._preset_records()`) with no TypeScript
mirror, deliberately — duplicating them in the frontend would drift the moment either side changed a
default. A new route, `llm.get_provider_records`, calls `llm_providers._resolve_provider_records`
(already real, already tested since `CTX-208.1`) against the current `CONFIG`, and returns the merged
set **with `managed` filtered out** before it ever serializes — the reservation already stops a
`config.json` entry from claiming that id; this route is what stops it from being *rendered*, which
`_resolve_provider_records`'s own contract never promised on its own. Synchronous (a dict lookup and
a filter, no network, no LLM call) — not registered in `ASYNC_ROUTES`.

### 2.5 The editor itself

Replaces `Settings.tsx`'s provider `<select>` + free-text model field + four hardcoded key rows with:

*   **A list of provider records**, sourced from `llm.get_provider_records` — each row shows id,
    kind, and whether a key is currently saved for it (if `api_key_ref` is non-null). Preset rows are
    pre-populated and editable in place; a user can also add a new record from scratch.
*   **Add/Edit a record:** id (immutable once saved — changing it is delete-and-recreate, since it's
    the join key `provider_roles` binds against), kind (`anthropic` / `openai_compat` / `google` —
    never `managed`, that value does not appear in this picker), base URL (required for a new
    `openai_compat` record pointing anywhere other than a real vendor's own default — presets like
    `openai` leave it blank on purpose), a model field per role (`reasoning`/`fast` — either can be
    left blank, meaning "this record can't serve that role," matching `SPEC-208` §2.3.2's own
    resolution-failure contract rather than inventing a default), and two capability checkboxes
    (`tool_use`/`strict_json`) with a one-line reminder that these are a claim, not a measurement
    (`SPEC-208` §2.4).
*   **The key field**, shown only once a record with a non-null `api_key_ref` exists and is saved —
    the exact same enter-and-save, never-redisplayed pattern `Settings.tsx` already uses for the four
    vendor keys today, reused rather than reinvented.
*   **Role binding:** two dropdowns, `reasoning` and `fast`, each listing only record ids that are
    currently saved (including presets) and populated from `provider_roles` — saving either writes
    the complete pair to `configure_daemon`/`config.json` per §2.3's contract.
*   **The inherited warning, verbatim from `SPEC-208` §3:** a record pairing a non-`null`
    `api_key_ref` with a non-loopback `base_url` sends that key to whatever host the record names.
    Shown inline on that record, not as a blocking validation error — a self-hosted relay is a real,
    legitimate use of exactly this shape, so the UI states the fact and lets the user decide, rather
    than refusing to save.
*   **Migration display:** if the loaded config has no `provider_roles` at all (a pre-`SPEC-208`
    install), the panel shows what `migrate_legacy_config` would produce from the legacy
    `llm_provider`/`llm_model` fields *before* anything is saved — "both roles are currently bound to
    `<preset>`" — so a user editing for the first time sees their real current state, not a blank
    slate that looks like nothing is configured.

### 2.6 Cross-Module Impacts

*   `core/tauri-rust` — `secrets.rs`'s `validate_known_key`, `daemon.rs`'s `collect_known_secrets`
    (both gain config-awareness); no schema change (`config.rs` already carries `providers`/
    `provider_roles` from `CTX-208.1`).
*   `services/python-daemon` — `daemon.py`'s `_apply_env_config`/`configure_daemon` (both gain the two
    fields), one new synchronous route (`llm.get_provider_records`).
*   `apps/tauri-ui` — `lib/settings.ts` (`DaemonConfig` interface, new functions), `components/
    Settings.tsx` (the picker section replaced).
*   **Downstream:** none. `chat_agents.py`/`component_pipeline.py`'s own `resolve()` call sites are
    unchanged — they already thread `config` through; this spec is only what puts real data into it.

## 3. Known Constraints & Risks

*   **Removing a record that a role is still bound to is a real, reachable misconfiguration** — the
    UI must warn before letting a save proceed that would leave `provider_roles` pointing at a
    deleted id, since `resolve()`'s own behavior for that case is a real `LLMProviderError` at the
    next chat/extraction call, not a friendly message.
*   **Editing a preset in place changes what "the default install" looks like for that user, forever**
    (until they delete their override) — since presets are merged in Python fresh on every call
    (`_preset_records()`), a saved `config.json` entry with a preset's own id permanently shadows it.
    Worth a short inline note in the editor, not a blocking confirmation.
*   **The record-must-exist-before-its-key-can-save ordering (§2.2) is a real UX trap** if the editor
    doesn't enforce it structurally — the key input for a not-yet-saved record should be disabled
    with a reason, not merely error after the fact.
*   **`managed` must never leak into this surface by omission**, not just by design — `CTX-321.1`'s
    own test suite needs a real assertion that `llm.get_provider_records` filters it out even if a
    future edit to `_resolve_provider_records` ever stopped doing so at that layer, since this route
    is the only remaining place that guarantees it before the value ever reaches a renderer.

## 4. Module Map & Reference Links

```text
[SPEC-000 Root Architecture](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-208 Provider Records & Model Role Resolution](../../../services/python-daemon/specs/SPEC-208-provider-records-and-model-roles.md)
          └── [SPEC-321 Provider Configuration UI](SPEC-321-provider-configuration-ui.md)   ← this spec
                 ├── (planned) CTX-321.1 — Rust secret validation + daemon CONFIG threading + the resolved-records route
                 └── (planned) CTX-321.2 — the real editor UI
```

Extends [SPEC-303 Settings UI](SPEC-303-settings-ui.md) inside the shell defined by
[SPEC-300 Product IA & Interaction Model](SPEC-300-product-ia-interaction-model.md). Explicitly does
not touch [SPEC-320 Managed Account Sign-In & Usage](SPEC-320-managed-account-signin-and-usage.md) —
`managed` stays invisible here by design; that spec is what would ever change this.

## 5. User & Interaction

*   **Product Stage:** Settings — the same persistent, non-project-scoped rail destination
    `SPEC-303`'s existing provider picker already lives in.
*   **What the user is trying to accomplish:** Point different kinds of AI work (a quick chat answer
    vs. a structured extraction that has to hold a strict JSON contract) at different models or
    servers, including ones this app has never hardcoded — a local Ollama box on another machine, a
    second local server, or simply "extraction on Anthropic, chat on a cheaper model" — without
    hand-editing `config.json`.
*   **What the user sees and does:** In Settings, where the single provider dropdown used to be, they
    now see a list of provider records (the familiar five, already there) with an "Add provider"
    action. Adding one asks for a name, an endpoint, and which of the two roles (if any) it should
    handle, with its API key entered the same way every existing key already is. Two dropdowns just
    below let them say which saved record handles `reasoning` work and which handles `fast` work.
    Nothing about Managed appears anywhere on this screen.
