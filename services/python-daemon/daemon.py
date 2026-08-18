import hashlib
import inspect
import logging
import logging.handlers
import os
import platform
import re
import sys
import json
import threading
import time
import uuid


def _default_log_dir() -> str:
    """A per-OS log directory, chosen without needing Rust to pass one in
    -- SPEC-107 §2 keeps this spec's Rust-side changes scoped to the macOS
    heartbeat signal, not a new config channel."""
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Logs")
    elif system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(base, "hardware-agent-studio")


# The real, resolved log file path, if the file handler below was set up
# successfully -- None if only stderr is active (e.g. a read-only log
# dir). Exposed via _detect_capabilities() (SPEC-303 Tier 3) so Settings'
# "Copy Diagnostics" can name it without duplicating this resolution logic.
_LOG_FILE_PATH = None


def _configure_logging() -> None:
    """stderr is the log channel, unconditionally -- stdout is the
    JSON-RPC wire and must never carry a log line (CLAUDE.md's "stdout is
    sacred" norm). This runs before any bridge-module import below, so an
    import failure that would otherwise kill the daemon silently still
    reaches the log (SPEC-107 §2)."""
    global _LOG_FILE_PATH
    handlers = [logging.StreamHandler(sys.stderr)]

    try:
        log_dir = _default_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "daemon.log")
        handlers.append(
            logging.handlers.RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
        )
        _LOG_FILE_PATH = log_path
    except OSError:
        pass  # stderr alone is still a real log path; a read-only log dir isn't fatal.

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


_configure_logging()
logger = logging.getLogger("daemon")

try:
    import kicad_bridge
    from kicad_bridge import get_kicad_version
except Exception:
    logger.exception("kicad_bridge failed to import -- kicad.* routes will be unavailable")
    kicad_bridge = None
    get_kicad_version = None

try:
    import freecad_bridge
    from freecad_bridge import generate_enclosure
except Exception:
    logger.exception("freecad_bridge failed to import -- freecad.* routes will be unavailable")
    freecad_bridge = None
    generate_enclosure = None

try:
    import llm_providers
except Exception:
    logger.exception("llm_providers failed to import -- llm.* routes will be unavailable")
    llm_providers = None

try:
    import component_pipeline
except Exception:
    logger.exception("component_pipeline failed to import -- kicad.generate_component will be unavailable")
    component_pipeline = None

try:
    import library_store
except Exception:
    logger.exception("library_store failed to import -- library.*/project.* routes will be unavailable")
    library_store = None

try:
    import tool_registry
except Exception:
    logger.exception("tool_registry failed to import -- agent.dispatch_tool will be unavailable")
    tool_registry = None

try:
    import fp_lib_table
except Exception:
    logger.exception("fp_lib_table failed to import -- kicad.search_footprints will be unavailable")
    fp_lib_table = None

try:
    import kicad_write
except Exception:
    logger.exception(
        "kicad_write failed to import -- kicad.generate_footprint_from_part will be unavailable"
    )
    kicad_write = None

try:
    import kicad_cli
except Exception:
    logger.exception(
        "kicad_cli failed to import -- kicad.check_board/kicad.check_schematic will be unavailable"
    )
    kicad_cli = None

try:
    import kicad_pcb_import
except Exception:
    logger.exception(
        "kicad_pcb_import failed to import -- file-based freecad.generate_enclosure will be unavailable"
    )
    kicad_pcb_import = None

# Env var Rust's spawn_daemon (CTX-106.1) sets non-secret config on --
# must match core/tauri-rust/src/config.rs's DAEMON_CONFIG_ENV_VAR. Applied
# once, at import time, before the read loop starts, so every route sees
# a fully-configured bridge module on its very first call.
_DAEMON_CONFIG_ENV_VAR = "HAS_DAEMON_CONFIG"

# In-memory config the daemon.configure route (below) fills in. Holds
# secrets Rust injects over stdin as the daemon's first-ever request --
# never written to disk, never logged (SPEC-106 §3). llm_provider/
# llm_model existed on Rust's DaemonConfig since CTX-106.1 but were never
# read on this side until SPEC-201 -- its first real consumer.
CONFIG = {"secrets": {}, "llm_provider": None, "llm_model": None}

# Providers that need a stored API key to be usable (SPEC-303) -- matches
# core/tauri-rust/src/daemon.rs's KNOWN_SECRET_KEYS allowlist and
# llm_chat's own f"{provider}_api_key" lookup convention. Ollama needs no
# key (a local server), so it's never reported here.
_KEY_BASED_PROVIDERS = ("anthropic", "google", "openai", "perplexity")


def _apply_env_config() -> None:
    raw = os.environ.get(_DAEMON_CONFIG_ENV_VAR)
    if not raw:
        return

    try:
        env_config = json.loads(raw)
    except json.JSONDecodeError:
        return

    if freecad_bridge is not None:
        freecad_bridge.configure(
            path_override=env_config.get("freecadcmd_path_override"),
            output_dir=env_config.get("output_dir"),
        )
    if kicad_bridge is not None:
        kicad_bridge.configure(
            socket_path=env_config.get("kicad_socket_path"),
            timeout_ms=env_config.get("kicad_timeout_ms"),
        )
    if library_store is not None:
        library_store.configure(storage_root=env_config.get("storage_root"))

    CONFIG["llm_provider"] = env_config.get("llm_provider")
    CONFIG["llm_model"] = env_config.get("llm_model")


_apply_env_config()

def kicad_generate_component(part_number: str) -> dict:
    """The real kicad.generate_component route (SPEC-202): runs the
    component_intelligence.workflow.md DAG (LLM extraction + deterministic
    validation) and returns the validated schema, or raises
    ComponentValidationError -- replacing the old time.sleep(1.5) mock
    that fabricated filenames and never validated anything.

    Passes CONFIG["llm_provider"]/["llm_model"] (SPEC-303's Settings UI)
    through to override the extraction agent's own hardcoded
    `component_extraction.prompt.md` default when set (CTX-303.1 Plan
    Drift Deviation 2 -- this route used to always run that hardcoded
    provider regardless of what was selected in Settings; only llm_chat
    ever respected it)."""
    return component_pipeline.generate_component(
        part_number,
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
    )


def component_search(query: str) -> list:
    """The component.search route (SPEC-306): a free-text query in,
    ranked candidates out. Threads CONFIG["llm_provider"]/["llm_model"]
    through exactly like kicad_generate_component does, for the same
    reason -- a fresh install with nothing configured in Settings yet
    must still use whichever provider IS configured, not a hardcoded
    default baked into the prompt file."""
    return component_pipeline.search_components(
        query,
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
    )


def component_cache_datasheet(part_number: str, datasheet_url: str) -> dict:
    """The component.cache_datasheet route (SPEC-306): fetches and caches
    a confirmed candidate's datasheet -- a real network call, registered
    as an async route below for the same reason freecad.generate_enclosure
    is."""
    path = library_store.cache_datasheet(part_number, datasheet_url)
    return {"path": path}


def kicad_inject_component(schema: dict, x_mm: float, y_mm: float) -> dict:
    """The kicad.inject_component route (SPEC-108, CTX-108.1): writes a
    SPEC-202-validated component schema into the board KiCad already
    has open, at (x_mm, y_mm). Mutates the board the instant it's
    called -- the caller (eventually SPEC-204's confirmation gate) is
    solely responsible for only invoking this after approval."""
    return kicad_bridge.inject_component(schema, (x_mm, y_mm))


def _board_revision_for(outline: dict, recognized_holes: list) -> str:
    """SPEC-109: a real sha256 of the exact board data actually used to
    build the enclosure -- deterministic and self-contained (no extra
    KiCad calls, no dependency on a board file path this bridge never
    has direct filesystem access to). Only recognized holes are hashed,
    since only they affect the physical geometry that was built."""
    payload = json.dumps({"outline": outline, "holes": recognized_holes}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freecad_generate_enclosure(
    height: float,
    width: float = None,
    depth: float = None,
    pcb_path: str = None,
    wall_thickness_mm: float = 2.0,
    clearance_mm: float = 0.5,
    fillet_radius_mm: float = 1.0,
    standoff_height_mm: float = 5.0,
    project_name: str = None,
    timeout_s: float = 30.0,
    cancel_event=None,
) -> dict:
    """The freecad.generate_enclosure route (SPEC-109, CTX-109.1;
    file-based mode added by SPEC-310, CTX-310.1): composes a real
    board outline/mounting-hole source with
    freecad_bridge.generate_enclosure's real geometry, replacing the
    direct `generate_enclosure` route binding SPEC-104/CTX-105.1 first
    set up.

    Mode selection is explicit, not connection-sniffed, in a fixed
    priority order: `width`+`depth` (manual) > `pcb_path` (file,
    SPEC-310) > live board (the original, still-default board-driven
    mode) -- a caller who explicitly chose one mode is never silently
    overridden by another just because, say, a KiCad connection happens
    to also be open. File mode needs no live KiCad connection at all
    (only `kicad_pcb_import`, a real subprocess wrapper around
    `kicad-cli` -- unlike live mode, `kicad_bridge`/kipy failing to
    import doesn't block it).

    Only `recognized: True` mounting holes become real standoff
    cylinders (both `kicad_bridge.get_mounting_holes` live and
    `kicad_pcb_import.extract_mounting_holes` from a file already return
    only ever-recognized-or-real-NPTH holes in that shape). An
    unrecognized PT_NPTH pad (live mode only -- file mode has no
    unrecognized case, see SPEC-310 §2) does not fail the whole build --
    SPEC-109 §3's real risk is drilling a standoff where one doesn't
    belong, not refusing to build at all over an unrelated test point or
    thermal via -- but it's still named in this route's own
    `unrecognized_holes` return value, for a future UI to surface rather
    than the daemon silently dropping it.

    `library_store.save_artifact` (kind: "enclosure", a real
    `board_revision`) only runs when the caller supplies `project_name`
    (optional, default None) -- keeping today's frontend contract
    (`App.tsx`'s `dims` object, no `project_name`) working unmodified
    until the UI-wiring child context SPEC-109 already names lands."""
    if width is not None and depth is not None:
        outline = None
        recognized_holes = []
        unrecognized_holes = []
        board_revision = f"manual:{width}x{depth}x{height}"
    elif pcb_path:
        if kicad_pcb_import is None:
            raise RuntimeError(
                "File-based enclosure generation requires kicad_pcb_import, which failed to "
                "import."
            )
        outline = kicad_pcb_import.extract_board_outline(pcb_path)
        recognized_holes = kicad_pcb_import.extract_mounting_holes(pcb_path)
        unrecognized_holes = []
        board_revision = f"file:{pcb_path}:{_board_revision_for(outline, recognized_holes)}"
    else:
        if kicad_bridge is None:
            raise RuntimeError(
                "Board-driven enclosure generation requires kicad_bridge, which failed to "
                "import. Supply width and depth for the no-board-data fallback, or pcb_path "
                "for the file-based mode, instead."
            )
        outline = kicad_bridge.get_board_outline()
        holes = kicad_bridge.get_mounting_holes()
        recognized_holes = [h for h in holes if h["recognized"]]
        unrecognized_holes = [h for h in holes if not h["recognized"]]
        board_revision = _board_revision_for(outline, recognized_holes)

    result = generate_enclosure(
        height=height,
        width=width,
        depth=depth,
        board_outline=outline,
        wall_thickness_mm=wall_thickness_mm,
        clearance_mm=clearance_mm,
        standoffs=[
            {
                "x_mm": h["x_mm"],
                "y_mm": h["y_mm"],
                "diameter_mm": h["diameter_mm"],
                "height_mm": standoff_height_mm,
            }
            for h in recognized_holes
        ],
        fillet_radius_mm=fillet_radius_mm,
        timeout_s=timeout_s,
        cancel_event=cancel_event,
    )
    result = {**result, "unrecognized_holes": unrecognized_holes}

    if project_name:
        if library_store is None:
            raise RuntimeError(
                "Saving an enclosure Artifact requires library_store, which failed to import."
            )
        artifact_id = uuid.uuid4().hex
        library_store.save_artifact(project_name, {
            "artifact_id": artifact_id,
            "kind": "enclosure",
            "board_revision": board_revision,
            "glb_path": result["glb_path"],
            "step_path": result["step_path"],
        })
        result["artifact_id"] = artifact_id

    return result


# --- library.*/project.* routes (SPEC-304, CTX-304.1) -----------------
# Thin wrappers over library_store, matching kicad_generate_component's
# own pattern of naming daemon-level routes distinctly from the bridge
# module functions they delegate to.
def library_save_part(part: dict) -> dict:
    return library_store.save_part(part)


def library_load_part(part_id: str) -> dict:
    return library_store.load_part(part_id)


def library_list_parts() -> list:
    return library_store.list_parts()


def library_save_symbol(symbol: dict) -> dict:
    return library_store.save_symbol(symbol)


def library_load_symbol(symbol_id: str) -> dict:
    return library_store.load_symbol(symbol_id)


def _derive_symbol_id(package: str, pin_count: int) -> str:
    """SPEC-307 §3's own named gotcha: Symbols are meant to be shared
    across Parts (SPEC-300 §2.1), so symbol_id is derived from a
    package + pin-count signature rather than a random id -- two Parts
    with an identical pinout converge on one Symbol record instead of
    silently duplicating. Sanitized for filesystem safety since it
    becomes part of a real file path (export_symbol_kicad_sym)."""
    safe_package = re.sub(r"[^A-Za-z0-9_-]", "_", package or "unknown")
    return f"{safe_package}_{pin_count}pin"


def library_save_confirmed_part(candidate: dict, extraction: dict) -> dict:
    """The library.save_confirmed_part route (SPEC-307): assembles Part
    provenance from two calls this route already has rather than
    reopening component_pipeline.py's own output shape --
    manufacturer/datasheet_url from SPEC-306's search candidate
    (source: "search", the candidate's own confidence), package/pins
    from this route's own extraction call (source: "llm_extraction").
    Saves the Symbol first (Parts reference it by id), then the Part.

    The extraction's real provider/model come from CONFIG, resolved the
    same way kicad_generate_component itself resolves them -- the
    frontend only ever calls kicad.generate_component, it never learns
    which provider/model CONFIG actually picked, so this route must
    look it up itself rather than trust a caller-supplied value."""
    pins = extraction.get("pins", [])
    symbol_id = _derive_symbol_id(extraction.get("package"), len(pins))

    symbol = library_store.save_symbol({
        "symbol_id": symbol_id,
        "reference_prefix": "U",
        "pins": pins,
    })

    search_provenance = {"source": "search", "confidence": candidate.get("confidence")}
    extraction_provenance = {
        "source": "llm_extraction",
        "provider": CONFIG.get("llm_provider"),
        "model": CONFIG.get("llm_model"),
    }

    part = library_store.save_part({
        "part_id": extraction.get("part_number") or candidate.get("part_number"),
        "manufacturer": candidate.get("manufacturer"),
        "package": extraction.get("package"),
        "pins": pins,
        # CTX-308.5: previously dropped on the floor even though the
        # extraction call already returns them -- component_extraction's
        # own schema (agentflow/agents/component_extraction.prompt.md)
        # includes package_dimensions/courtyard alongside package/pins.
        # Persisting them here is what makes SPEC-308's datasheet-
        # generated footprint source possible without a second LLM call:
        # kicad_write.generate_pad_layout only needs package + pin
        # numbers + package_dimensions, all already produced by this
        # same extraction.
        "package_dimensions": extraction.get("package_dimensions"),
        "courtyard": extraction.get("courtyard"),
        "datasheet_url": candidate.get("datasheet_url"),
        "footprint_id": None,
        "symbol_id": symbol_id,
        "provenance": {
            "manufacturer": search_provenance,
            "datasheet_url": search_provenance,
            "package": extraction_provenance,
            "pins": extraction_provenance,
            "package_dimensions": extraction_provenance,
            "courtyard": extraction_provenance,
        },
    })

    return {"part": part, "symbol": symbol}


def library_export_symbol(symbol_id: str) -> dict:
    return {"path": library_store.export_symbol_kicad_sym(symbol_id)}


def library_save_footprint(footprint: dict) -> dict:
    return library_store.save_footprint(footprint)


def library_load_footprint(footprint_id: str) -> dict:
    return library_store.load_footprint(footprint_id)


def library_export_footprint(footprint_id: str) -> dict:
    return {"path": library_store.export_footprint_kicad_mod(footprint_id)}


def project_save(project: dict) -> dict:
    return library_store.save_project(project)


def project_load(name: str) -> dict:
    return library_store.load_project(name)


def project_list() -> list:
    return library_store.list_projects()


def project_save_artifact(project_name: str, artifact: dict) -> dict:
    return library_store.save_artifact(project_name, artifact)


def project_load_artifact(project_name: str, artifact_id: str) -> dict:
    return library_store.load_artifact(project_name, artifact_id)


def project_list_artifacts(project_name: str) -> list:
    return library_store.list_artifacts(project_name)


def project_append_conversation_turn(project_name: str, turn: dict) -> dict:
    library_store.append_conversation_turn(project_name, turn)
    return {"appended": True}


def project_load_conversation(project_name: str) -> list:
    return library_store.load_conversation(project_name)


class InvalidParamsError(Exception):
    """Raised when a request's params don't match the route's real signature."""


class JobNotFoundError(Exception):
    """Raised when job.cancel names a job_id that isn't (or is no longer) running."""


# Parameters a route function may declare for the daemon's own internal use
# (e.g. a per-job cancellation handle) that a client must never be able to
# supply directly over the wire.
_INTERNAL_ONLY_PARAMS = {"cancel_event"}

def configure_daemon(secrets: dict = None, llm_provider: str = None, llm_model: str = None) -> dict:
    """The daemon.configure route (SPEC-106 §2, extended by SPEC-303):
    merges secrets Rust hands over on the daemon's very first request into
    CONFIG. Ordinary route, dispatched through the normal ROUTES registry
    like anything else -- Rust's spawn_daemon (CTX-106.1) is what
    guarantees this line reaches stdin before any other, not any
    special-casing here.

    Also callable again later, live, from the Settings UI (SPEC-303) --
    `secrets` is always the *complete* current set when sent that way
    (core/tauri-rust's collect_known_secrets/sync_secrets_to_daemon), so
    replacing CONFIG["secrets"] wholesale is correct either way, not a
    partial-update bug. `llm_provider`/`llm_model` default to None meaning
    "leave unchanged" -- Rust's spawn-time call never passes them, so this
    extension can't regress that call."""
    if secrets is not None:
        CONFIG["secrets"] = dict(secrets)
    if llm_provider is not None:
        CONFIG["llm_provider"] = llm_provider
    if llm_model is not None:
        CONFIG["llm_model"] = llm_model
    return {"configured": True}


def get_daemon_capabilities() -> dict:
    """The daemon.get_capabilities route (SPEC-303): re-runs the same
    cheap, non-blocking checks daemon.ready reports once at boot, on
    demand -- so the Settings UI can refresh what's actually configured
    right after a save/clear, without waiting for the next restart."""
    return _detect_capabilities()


def llm_chat(
    prompt: str, provider: str = None, model: str = None, system: str = "", history: list = None
) -> str:
    """The llm.chat route (SPEC-201): resolves the configured provider/
    model from CONFIG (SPEC-106's daemon.configure/env-config handshake)
    and the matching secret, then delegates to llm_providers.chat.
    Registered as an async route (SPEC-105) -- a real LLM call is almost
    always multi-second, the same reasoning freecad.generate_enclosure
    already established.

    `history` (SPEC-302) is a real, existing provider capability
    llm_providers.chat now exposes -- see its own docstring.

    Falls back to llm_providers._DEFAULT_PROVIDER when neither an
    explicit `provider` nor CONFIG["llm_provider"] is set (SPEC-303's
    settings UI, which would let a human choose, doesn't exist yet --
    found by actually running the real chat surface against a real,
    never-configured install, CTX-302.1 Plan Drift)."""
    provider_name = provider or CONFIG.get("llm_provider") or llm_providers._DEFAULT_PROVIDER

    model_name = model or CONFIG.get("llm_model")
    api_key = CONFIG.get("secrets", {}).get(f"{provider_name}_api_key", "")

    return llm_providers.chat(
        prompt, provider=provider_name, api_key=api_key, model=model_name, system=system, history=history
    )


def cancel_job(job_id: str) -> dict:
    """Signals a running async job to cancel. Real cancellation (actually
    killing the underlying work, not just stopping its being reported on)
    is up to the route itself -- see SPEC-105 §3. This only sets the flag;
    _run_job's except branch is what turns that into a `job.cancelled`
    notification once the route's own code observes it."""
    entry = JOBS.get(job_id)
    if entry is None:
        raise JobNotFoundError(f"No such job: {job_id}")
    entry["cancel_event"].set()
    return {"job_id": job_id, "cancelling": True}


def agent_dispatch_tool(tool_name: str, tool_input: dict = None, confirmed: bool = False) -> dict:
    """SPEC-204/CTX-204.1 Phase 2: the real JSON-RPC entry point for
    tool_registry's confirmation-gating policy. Deliberately does NOT go
    through tool_registry.build_tool_registry()'s ToolRegistry -- that
    object exists for a future AgentExecutor conversation loop
    (SPEC-204 SS1's own non-goal against a chat UI in this spec), not for
    this route. This route reuses submit_job (SPEC-105) directly for the
    real dispatch, exactly like every other ASYNC_ROUTES caller, rather
    than reinventing job tracking/progress notification for tool calls.

    tool_input's own `confirmed` key (if the caller nested it there
    instead of passing the top-level parameter) is intentionally never
    read -- only the top-level `confirmed` argument gates dispatch, so
    there is exactly one place this decision is made."""
    tool_input = tool_input or {}
    if tool_name not in tool_registry.TOOL_DEFINITIONS or tool_name not in ROUTES:
        raise InvalidParamsError(f"Unknown or unavailable tool: {tool_name}")

    if tool_name in tool_registry.CONFIRMATION_REQUIRED_TOOLS and not confirmed:
        return {"status": "pending_confirmation", "tool": tool_name, "input": tool_input}

    return submit_job(tool_name, tool_input)


def kicad_search_footprints(query: str) -> list:
    """SPEC-308/CTX-308.1/CTX-308.4: merges the two footprint sources
    PRODUCT-PLAN.md §8 item 3 ranks first -- KiCad's own installed
    libraries (fp_lib_table.py; no kipy IPC call is possible here at
    all, verified directly against its own source), then footprints this
    app has already saved (library_store.py) -- each tagged with a real
    `source` field so the UI can tell them apart. Still local disk I/O
    only, so unlike every other kicad.*/freecad.* route this is NOT
    registered in ASYNC_ROUTES below -- a synchronous return is the
    honest reflection of its real cost. Source three (datasheet
    generation) remains fully open, not attempted here."""
    kicad_results = [{**r, "source": "kicad_library"} for r in fp_lib_table.search_footprints(query)]

    saved_results = []
    if library_store is not None:
        for r in library_store.search_footprints(query):
            saved_results.append({
                "library": r.get("library", ""),
                "footprint_name": r.get("footprint_name") or r["footprint_id"],
                "source": "your_library",
            })

    return kicad_results + saved_results


def kicad_generate_footprint_from_part(part_id: str) -> dict:
    """The kicad.generate_footprint_from_part route -- SPEC-308/CTX-308.5:
    PRODUCT-PLAN.md §8 item 3's third and, until now, fully open footprint
    source (datasheet generation), for a Part whose own package_dimensions/
    courtyard the LLM extraction already returned (CTX-308.5's own fix to
    library_save_confirmed_part, which previously dropped them).

    No second LLM call: kicad_write.generate_pad_layout is the same pure
    geometry function SPEC-108's live inject path already uses, given
    exactly the fields a saved Part already carries. Synchronous, like
    kicad.search_footprints -- pure computation over already-known data,
    no network, no live KiCad IPC round trip, so this is NOT registered
    in ASYNC_ROUTES below.

    Fails closed for a package outside kicad_write.SUPPORTED_PACKAGES --
    the same fail-closed choice component_pipeline.validate_schema
    already makes for a package outside its own PACKAGE_REFERENCE, not a
    silent guess at pad geometry."""
    part = library_store.load_part(part_id)

    missing = [f for f in ("package", "pins", "package_dimensions", "courtyard") if not part.get(f)]
    if missing:
        raise library_store.SchemaValidationError(
            f"Part '{part_id}' is missing {', '.join(missing)} -- cannot generate a footprint "
            f"without the datasheet dimensions the extraction step returns. Parts saved before "
            f"CTX-308.5 don't have these; re-run generate + save to pick them up."
        )

    pin_numbers = [pin["number"] for pin in part["pins"]]
    pads = kicad_write.generate_pad_layout(part["package"], pin_numbers, part["package_dimensions"])

    footprint_id = f"generated__{part_id}"
    return library_store.save_footprint({
        "footprint_id": footprint_id,
        "footprint_name": f"{part['package']} (generated)",
        "pads": pads,
        "courtyard": part["courtyard"],
        "provenance": {
            "source": "datasheet_generation",
            "generated_from_part_id": part_id,
            "verified": False,
        },
    })


def kicad_generate_connection_guidance(part_id: str) -> dict:
    """The kicad.generate_connection_guidance route -- SPEC-308's third
    named concern (decoupling, protection, power), once a part and its
    footprint are both real (PRODUCT-PLAN.md §6 M3's own framing). A
    real LLM call, so registered in ASYNC_ROUTES below like
    kicad.generate_component/component.search -- unlike
    kicad.generate_footprint_from_part, this genuinely needs one.

    Threads CONFIG["llm_provider"]/["llm_model"] through exactly like
    kicad_generate_component/component_search already do, for the same
    reason: a fresh install with nothing configured in Settings yet must
    still use whichever provider IS configured, not a hardcoded default
    baked into connection_guidance.prompt.md."""
    part = library_store.load_part(part_id)
    return component_pipeline.generate_connection_guidance(
        part["part_id"], part["package"], part["pins"],
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
    )


def kicad_list_open_boards() -> dict:
    """The kicad.list_open_boards route (CTX-309.4): a real, cheap,
    read-only lookup of every board currently open in KiCad, decoupled
    from actually running a check. Feeds the Board (DRC) picker UI's
    real, always-shown "here's what's open, pick one" flow -- real user
    feedback exercising the actual running app found the old
    auto-resolve-silently-when-exactly-one-is-open behavior (CTX-309.3)
    still too opaque for someone new to KiCad: it never showed *which*
    board was about to be checked, and the flat "no board open" state
    never offered to open KiCad itself. Sync, not async -- this is a fast
    IPC lookup, no subprocess or LLM call, unlike kicad_check_board below.

    *   Zero boards open: {"status": "no_board_open"}.
    *   One or more open: {"status": "boards_found", "candidates":
        [{"path", "label"}, ...]} -- always a real list, even a single
        entry, so the user always sees and picks the exact board before
        any check ever runs, never a silent auto-resolution."""
    candidates = kicad_bridge.list_open_boards()
    if not candidates:
        return {"status": "no_board_open"}
    return {
        "status": "boards_found",
        "candidates": [
            {"path": path, "label": os.path.basename(path)}
            for path in candidates
        ],
    }


def kicad_check_board(pcb_path: str) -> dict:
    """The kicad.check_board route (SPEC-309): a real DRC via kicad-cli
    against an explicit `pcb_path`. Explains the real violations via a
    real LLM call. Async: a real subprocess plus a real LLM call, both
    genuinely multi-second, like every other real kicad.*/component.*
    route in ASYNC_ROUTES below.

    CTX-309.4 removed the old default-`None`/auto-resolve-when-omitted
    behavior (CTX-309.3) in favor of `kicad.list_open_boards` feeding a
    real picker UI first -- the user always explicitly picks which board
    before this route ever runs, the same explicit-path contract
    `kicad_check_schematic` already used. `pcb_path` is required now, not
    optional."""
    report = kicad_cli.run_drc(pcb_path)
    result = component_pipeline.explain_violations(
        report["violations"], "drc",
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
    )
    result["source_path"] = pcb_path
    result["status"] = "ok"
    return result


def kicad_list_project_schematics() -> dict:
    """The kicad.list_project_schematics route: real user feedback asked
    why Schematic checking couldn't work like Board checking, with a
    live list instead of a blind file dialog. KiCad's IPC server has no
    handler for listing open schematics at all (confirmed live,
    unconditionally, unlike PCB's transient "nothing open yet" case --
    see `kicad_bridge.list_project_schematics`'s own docstring), so this
    derives each currently open board's project's own root schematic
    path instead, and only returns ones that actually exist on disk.

    *   Nothing derivable: {"status": "no_schematic_found"}.
    *   One or more real, existing schematic files: {"status":
        "schematics_found", "candidates": [{"path", "label"}, ...]} --
        mirrors kicad_list_open_boards's own shape so the frontend can
        reuse the same picker pattern. Sync, not async, like that route,
        for the same reason: a fast IPC lookup plus filesystem checks,
        no subprocess or LLM call."""
    candidates = kicad_bridge.list_project_schematics()
    if not candidates:
        return {"status": "no_schematic_found"}
    return {
        "status": "schematics_found",
        "candidates": [
            {"path": path, "label": os.path.basename(path)}
            for path in candidates
        ],
    }


def kicad_check_schematic(sch_path: str) -> dict:
    """The kicad.check_schematic route (SPEC-309): a real ERC via
    kicad-cli against `sch_path` -- always an explicit path, whether
    picked from `kicad.list_project_schematics`'s derived candidates or
    a manually-chosen file (the picker's own fallback for a schematic
    that isn't alongside any currently open board).

    ERC's real JSON nests violations per schematic sheet
    (kicad_cli.run_erc's own docstring); flattened here into one list,
    each violation tagged with its real sheet_path, before handing off
    to the same explain_violations component_pipeline function
    kicad_check_board uses."""
    report = kicad_cli.run_erc(sch_path)
    flattened = [
        {**violation, "sheet_path": sheet["path"]}
        for sheet in report["sheets"]
        for violation in sheet["violations"]
    ]
    result = component_pipeline.explain_violations(
        flattened, "erc",
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
    )
    result["source_path"] = sch_path
    return result


def _build_routes() -> dict:
    """kicad.*/freecad.* are only registered if their bridge module
    actually imported (SPEC-107 §2) -- a broken kipy install shouldn't
    take down the daemon's ability to serve FreeCAD requests, or vice
    versa. A function (not a bare literal) so this registration logic is
    directly testable without needing to simulate a real import failure."""
    routes = {
        "job.cancel": cancel_job,
        "daemon.configure": configure_daemon,
        "daemon.get_capabilities": get_daemon_capabilities,
    }
    if get_kicad_version is not None:
        routes["kicad.get_version"] = get_kicad_version
    if kicad_bridge is not None:
        routes["kicad.inject_component"] = kicad_inject_component
    if generate_enclosure is not None:
        routes["freecad.generate_enclosure"] = freecad_generate_enclosure
    if llm_providers is not None:
        routes["llm.chat"] = llm_chat
    if component_pipeline is not None:
        routes["kicad.generate_component"] = kicad_generate_component
        routes["component.search"] = component_search
    if library_store is not None:
        routes["component.cache_datasheet"] = component_cache_datasheet
        routes["library.save_part"] = library_save_part
        routes["library.load_part"] = library_load_part
        routes["library.list_parts"] = library_list_parts
        routes["library.save_symbol"] = library_save_symbol
        routes["library.load_symbol"] = library_load_symbol
        routes["library.save_confirmed_part"] = library_save_confirmed_part
        routes["library.export_symbol"] = library_export_symbol
        routes["library.save_footprint"] = library_save_footprint
        routes["library.load_footprint"] = library_load_footprint
        routes["library.export_footprint"] = library_export_footprint
        routes["project.save"] = project_save
        routes["project.load"] = project_load
        routes["project.list"] = project_list
        routes["project.save_artifact"] = project_save_artifact
        routes["project.load_artifact"] = project_load_artifact
        routes["project.list_artifacts"] = project_list_artifacts
        routes["project.append_conversation_turn"] = project_append_conversation_turn
        routes["project.load_conversation"] = project_load_conversation
    if tool_registry is not None:
        routes["agent.dispatch_tool"] = agent_dispatch_tool
    if fp_lib_table is not None:
        routes["kicad.search_footprints"] = kicad_search_footprints
    if kicad_write is not None and library_store is not None:
        routes["kicad.generate_footprint_from_part"] = kicad_generate_footprint_from_part
    if component_pipeline is not None and library_store is not None:
        routes["kicad.generate_connection_guidance"] = kicad_generate_connection_guidance
    if kicad_bridge is not None:
        routes["kicad.list_open_boards"] = kicad_list_open_boards
        routes["kicad.list_project_schematics"] = kicad_list_project_schematics
    if kicad_cli is not None and component_pipeline is not None:
        if kicad_bridge is not None:
            routes["kicad.check_board"] = kicad_check_board
        routes["kicad.check_schematic"] = kicad_check_schematic
    return routes


# Route Registry mapping string methods to Python functions.
ROUTES = _build_routes()

# Methods that run off the read loop: a request for one of these returns
# {"job_id": ...} immediately, and the real result/failure/cancellation
# arrives later as a job.* notification (SPEC-105 §2).
ASYNC_ROUTES = {
    "freecad.generate_enclosure", "llm.chat", "kicad.generate_component", "kicad.inject_component",
    "component.search", "component.cache_datasheet", "kicad.generate_connection_guidance",
    "kicad.check_board", "kicad.check_schematic",
} & ROUTES.keys()

# job_id -> {"cancel_event": threading.Event()} for every job currently
# in flight. Entries are removed once the job's worker thread finishes.
JOBS = {}

# Every stdout write (a request's response, or an async job's notification)
# must go through _write_line so two workers can never interleave partial
# writes onto the same line (SPEC-105 §3's stdout-atomicity constraint).
_stdout_lock = threading.Lock()


def _write_line(text: str) -> None:
    with _stdout_lock:
        sys.stdout.write(text + '\n')
        sys.stdout.flush()  # CRITICAL: Ensures Tauri receives the payload immediately


def emit(notification: dict) -> None:
    """Writes a JSON-RPC notification (no 'id') -- job.progress/completed/
    failed/cancelled -- through the same atomic path as a request's own
    response."""
    _write_line(json.dumps(notification))


def validate_params(method: str, params) -> None:
    """Checks `params` against the route function's real signature before
    dispatch, so a typo'd or missing key returns the JSON-RPC standard
    -32602 Invalid params instead of an opaque -32000 Server error raised
    from deep inside a TypeError (SPEC-105 §2)."""
    if not isinstance(params, dict):
        return

    sig = inspect.signature(ROUTES[method])
    accepted = set(sig.parameters.keys()) - _INTERNAL_ONLY_PARAMS
    required = {
        name for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty and name not in _INTERNAL_ONLY_PARAMS
    }

    unexpected = set(params.keys()) - accepted
    if unexpected:
        raise InvalidParamsError(f"Unexpected parameter(s): {', '.join(sorted(unexpected))}")

    missing = required - set(params.keys())
    if missing:
        raise InvalidParamsError(f"Missing required parameter(s): {', '.join(sorted(missing))}")


def _run_job(job_id: str, method: str, params: dict, cancel_event: threading.Event) -> None:
    """Runs an async route's real work on a worker thread, off the read
    loop, and reports the outcome as a job.* notification. Whether the
    underlying exception was actually a cancellation (vs. a genuine
    failure) is judged by cancel_event's own state, not by the specific
    exception type the route happened to raise -- this keeps daemon.py
    from needing to know about any one bridge module's exception classes."""
    emit({"jsonrpc": "2.0", "method": "job.progress", "params": {"job_id": job_id, "status": "running"}})

    func = ROUTES[method]
    kwargs = dict(params) if isinstance(params, dict) else {}
    if "cancel_event" in inspect.signature(func).parameters:
        kwargs["cancel_event"] = cancel_event

    try:
        result = func(**kwargs)
        emit({"jsonrpc": "2.0", "method": "job.completed", "params": {"job_id": job_id, "result": result}})
    except Exception as e:
        if cancel_event.is_set():
            emit({"jsonrpc": "2.0", "method": "job.cancelled", "params": {"job_id": job_id}})
        else:
            emit({"jsonrpc": "2.0", "method": "job.failed", "params": {"job_id": job_id, "error": str(e)}})
    finally:
        JOBS.pop(job_id, None)


def submit_job(method: str, params: dict) -> dict:
    """Starts an async route's work on a daemon worker thread and returns
    its job_id immediately -- the read loop never blocks on the route's
    actual work (SPEC-105 §2)."""
    job_id = str(uuid.uuid4())
    cancel_event = threading.Event()
    JOBS[job_id] = {"cancel_event": cancel_event}

    thread = threading.Thread(target=_run_job, args=(job_id, method, params, cancel_event), daemon=True)
    thread.start()

    return {"job_id": job_id}


def handle_request(line: str) -> str:
    """
    Parses a single JSON-RPC line, executes the routed function,
    and returns a JSON-RPC formatted response string.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        })

    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    # Validate Request Format
    if not method:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request: Missing 'method'"},
            "id": req_id
        })

    # Validate Route Exists
    if method not in ROUTES:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id
        })

    try:
        validate_params(method, params)
    except InvalidParamsError as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32602, "message": f"Invalid params: {e}"},
            "id": req_id
        })

    # Execute Route Handler
    try:
        if method in ASYNC_ROUTES:
            result = submit_job(method, params if isinstance(params, dict) else {})
        elif isinstance(params, dict):
            # Dynamically unpack params dictionary as kwargs
            result = ROUTES[method](**params)
        else:
            result = ROUTES[method]()

        return json.dumps({
            "jsonrpc": "2.0",
            "result": result,
            "id": req_id
        })

    except Exception as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": f"Server error: {str(e)}"},
            "id": req_id
        })

# How often the heartbeat fires. Rust's macOS crash-signal path (CTX-107.1)
# treats a gap of roughly 2x this as evidence the daemon hard-crashed, not
# just that one heartbeat happened to be delayed.
_HEARTBEAT_INTERVAL_S = 5.0


def _detect_capabilities() -> dict:
    """Cheap, non-blocking checks only (SPEC-107 §3) -- SPEC-103/104 both
    connect to KiCad/FreeCAD lazily on first real use, and this probe must
    not itself pay for a slow handshake on every single startup."""
    # CTX-303.4: the real path actually checked, reported unconditionally
    # (whether or not it exists) -- so a real "not reachable" state in
    # Settings can say exactly where it looked instead of leaving the
    # user to guess. The check itself stays the same cheap, non-blocking
    # os.path.exists (see docstring); only its own diagnostic detail was
    # ever being discarded.
    kicad_socket_path_checked = None
    kicad_available = False
    if kicad_bridge is not None:
        kicad_socket_path_checked = kicad_bridge._socket_path_override or "/tmp/kicad/api.sock"
        kicad_available = os.path.exists(kicad_socket_path_checked)

    # CTX-303.4: find_freecadcmd() already returns the real, resolved path
    # on success or raises a real, specific FreeCADUnavailableError message
    # on failure -- both were being computed and immediately discarded down
    # to a bare boolean. Captured here so Settings can show the user the
    # real reason instead of a flat "not reachable".
    freecad_available = False
    freecad_path_checked = None
    freecad_error = None
    if freecad_bridge is not None:
        try:
            freecad_path_checked = freecad_bridge.find_freecadcmd()
            freecad_available = True
        except Exception as e:
            freecad_available = False
            freecad_error = str(e)

    # SPEC-309: whether kicad-cli was actually located on this machine --
    # a broken/missing kicad-cli shouldn't take down the rest of the app,
    # it should surface as an honest capability gap, same pattern
    # freecad_available already established for freecadcmd.
    kicad_cli_available = False
    if kicad_cli is not None:
        try:
            kicad_cli.find_kicad_cli()
            kicad_cli_available = True
        except Exception:
            kicad_cli_available = False

    configured_secrets = CONFIG.get("secrets", {})

    return {
        "kicad_available": kicad_available,
        "kicad_socket_path_checked": kicad_socket_path_checked,
        "freecad_available": freecad_available,
        "freecad_path_checked": freecad_path_checked,
        "freecad_error": freecad_error,
        "kicad_cli_available": kicad_cli_available,
        # SPEC-303: reflects which providers actually have a key configured
        # right now, fixed from a hardcoded [] that predated any real
        # settings surface to populate it.
        "llm_providers": [p for p in _KEY_BASED_PROVIDERS if configured_secrets.get(f"{p}_api_key")],
        # SPEC-303 Tier 3: for the Settings screen's "Copy Diagnostics"
        # bundle. log_path is None if only stderr is active (e.g. a
        # read-only log dir) -- reported honestly, not papered over.
        "log_path": _LOG_FILE_PATH,
        "python_version": platform.python_version(),
        # SPEC-110: the real, currently-active storage root -- whether
        # the app's default data directory or a user's real
        # storage_root_override -- so Settings can display it without
        # config.json ever needing to hold the Rust-computed value.
        "storage_root": library_store.current_storage_root() if library_store is not None else None,
        # SPEC-203 (CTX-203.1): mirrors freecad_available's own real
        # capability-gating pattern. digikey_available requires both real
        # OAuth2 client-credentials secrets, not just one -- a lone
        # digikey_client_id with no matching secret can't actually
        # authenticate. True here means "ready to call," not "a real call
        # has been made" -- no per-supplier HTTP client exists yet.
        "digikey_available": bool(
            configured_secrets.get("digikey_client_id") and configured_secrets.get("digikey_client_secret")
        ),
        "mouser_available": bool(configured_secrets.get("mouser_api_key")),
        "octopart_available": bool(configured_secrets.get("octopart_api_key")),
    }


def _emit_heartbeat() -> None:
    emit({"jsonrpc": "2.0", "method": "daemon.heartbeat", "params": {}})


def _heartbeat_loop() -> None:
    """Runs on its own thread, independent of request handling, so a
    long-running freecadcmd call in flight can never starve it and produce
    a false "crashed" signal on the Rust side (SPEC-107 §3)."""
    while True:
        time.sleep(_HEARTBEAT_INTERVAL_S)
        _emit_heartbeat()


def main():
    """
    The infinite event loop listening to standard input.
    """
    emit({"jsonrpc": "2.0", "method": "daemon.ready", "params": _detect_capabilities()})
    threading.Thread(target=_heartbeat_loop, daemon=True).start()

    for line in sys.stdin:
        if not line.strip():
            continue

        response = handle_request(line.strip())
        _write_line(response)

if __name__ == '__main__':
    main()
