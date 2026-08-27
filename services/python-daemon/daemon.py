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

# SPEC-407 §2.4: every optional module whose import failed, collected here at
# import time and reported on `daemon.ready`. The per-module `try/except`
# guards below are deliberate and stay exactly as they are -- a missing
# optional module must never take the whole daemon down (SPEC-407 §1
# Non-Goals). What was missing is that this state existed *only* in a log
# file: a mis-frozen sidecar could start, answer `daemon.ready` with KiCad
# and FreeCAD both live, heartbeat normally, and run with the entire AI
# surface disabled while looking completely healthy. Found for real on
# 2026-08-27 (SPEC-407 §2.1, failure mode 7).
#
# Never prints. `stdout` is the JSON-RPC wire (CLAUDE.md) and this runs at
# import time, before the first frame is ever written.
_DEGRADED_MODULES: list = []


def _note_degraded(module: str, capability: str) -> None:
    """Records one failed optional import for `daemon.ready` (SPEC-407 §2.4)."""
    _DEGRADED_MODULES.append({"module": module, "capability": capability})

try:
    import kicad_bridge
    from kicad_bridge import get_kicad_version
except Exception:
    logger.exception("kicad_bridge failed to import -- kicad.* routes will be unavailable")
    _note_degraded("kicad_bridge", "kicad.* routes")
    kicad_bridge = None
    get_kicad_version = None

try:
    import freecad_bridge
    from freecad_bridge import generate_enclosure, export_enclosure
except Exception:
    logger.exception("freecad_bridge failed to import -- freecad.* routes will be unavailable")
    _note_degraded("freecad_bridge", "freecad.* routes")
    freecad_bridge = None
    generate_enclosure = None
    export_enclosure = None

try:
    import llm_providers
except Exception:
    logger.exception("llm_providers failed to import -- llm.* routes will be unavailable")
    _note_degraded("llm_providers", "llm.* routes")
    llm_providers = None

try:
    import component_pipeline
except Exception:
    logger.exception("component_pipeline failed to import -- kicad.generate_component will be unavailable")
    _note_degraded("component_pipeline", "kicad.generate_component")
    component_pipeline = None

try:
    import library_store
except Exception:
    logger.exception("library_store failed to import -- library.*/project.* routes will be unavailable")
    _note_degraded("library_store", "library.*/project.* routes")
    library_store = None

try:
    import tool_registry
except Exception:
    logger.exception("tool_registry failed to import -- agent.dispatch_tool will be unavailable")
    _note_degraded("tool_registry", "agent.dispatch_tool")
    tool_registry = None

try:
    import fp_lib_table
except Exception:
    logger.exception("fp_lib_table failed to import -- kicad.search_footprints will be unavailable")
    _note_degraded("fp_lib_table", "kicad.search_footprints")
    fp_lib_table = None

try:
    import kicad_write
except Exception:
    logger.exception(
        "kicad_write failed to import -- kicad.generate_footprint_from_part will be unavailable"
    )
    _note_degraded("kicad_write", "kicad.generate_footprint_from_part")
    kicad_write = None

try:
    import kicad_cli
except Exception:
    logger.exception(
        "kicad_cli failed to import -- kicad.check_board/kicad.check_schematic will be unavailable"
    )
    _note_degraded("kicad_cli", "kicad.check_board/kicad.check_schematic")
    kicad_cli = None

try:
    import kicad_pcb_import
except Exception:
    logger.exception(
        "kicad_pcb_import failed to import -- file-based freecad.generate_enclosure will be unavailable"
    )
    _note_degraded("kicad_pcb_import", "file-based freecad.generate_enclosure")
    kicad_pcb_import = None

try:
    import community_libraries
except Exception:
    logger.exception(
        "community_libraries failed to import -- library.search_community_footprints will be unavailable"
    )
    _note_degraded("community_libraries", "library.search_community_footprints")
    community_libraries = None

try:
    import datasheet_guidance
except Exception:
    logger.exception("datasheet_guidance failed to import -- datasheet.generate_guidance will be unavailable")
    _note_degraded("datasheet_guidance", "datasheet.generate_guidance")
    datasheet_guidance = None

try:
    import datasheet_structure
except Exception:
    logger.exception("datasheet_structure failed to import -- datasheet.read_pages will be unavailable")
    _note_degraded("datasheet_structure", "datasheet.read_pages")
    datasheet_structure = None

try:
    import chat_agents
except Exception:
    logger.exception("chat_agents failed to import -- chat.send will be unavailable")
    _note_degraded("chat_agents", "chat.send")
    chat_agents = None

try:
    import context_index
except Exception:
    logger.exception("context_index failed to import -- context.search/context.rebuild_index will be unavailable")
    _note_degraded("context_index", "context.search/context.rebuild_index")
    context_index = None

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
CONFIG = {"secrets": {}, "llm_provider": None, "llm_model": None, "providers": None, "provider_roles": None}

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
    if kicad_cli is not None:
        # SPEC-311: kicad_cli.configure existed since SPEC-309 but was
        # never actually called here -- kicad.export_board_glb is this
        # module's first real, persistent-file-producing route, so it's
        # the first to need the same real output_dir (SPEC-301 §2)
        # freecad_bridge.configure already receives above.
        kicad_cli.configure(output_dir=env_config.get("output_dir"))
    if library_store is not None:
        library_store.configure(storage_root=env_config.get("storage_root"))

    CONFIG["llm_provider"] = env_config.get("llm_provider")
    CONFIG["llm_model"] = env_config.get("llm_model")
    # SPEC-321 §2.3: threads the two fields llm_providers.resolve()'s own
    # `config` parameter has been able to read since CTX-208.2, but which
    # nothing supplied until this route existed to write them. Both
    # default to None/absent exactly like a pre-SPEC-208 install --
    # migrate_legacy_config() already handles that case correctly.
    CONFIG["providers"] = env_config.get("providers")
    CONFIG["provider_roles"] = env_config.get("provider_roles")


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
        app_config=CONFIG,
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
        app_config=CONFIG,
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


def freecad_generate_enclosure(
    height: float,
    width: float = None,
    depth: float = None,
    pcb_path: str = None,
    wall_thickness_mm: float = 2.0,
    clearance_mm: float = 0.5,
    fillet_radius_mm: float = 1.0,
    standoff_height_mm: float = 5.0,
    lid: bool = False,
    lid_thickness_mm: float = None,
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

    Generating no longer implicitly persists anything (`CTX-311.13`
    removed the `project_name`-gated `library_store.save_artifact` call
    this route used to make on every single call -- a real, confirmed,
    live bug: the frontend always supplied `project_name`, so every
    Generate wrote an Artifact record, and the very next regenerate's own
    leak-bounding cleanup deleted the files that record pointed at.
    `freecad.export_enclosure` is now the one real, explicit "keep this"
    action; Generate stays a cheap, repeatable preview step, matching
    `CTX-311.2`'s own explicit-save-only decision for real, not just in
    name).

    `lid` (SPEC-311) passes straight through to `generate_enclosure`,
    which raises a clean `ValueError` in manual mode -- no board-driven
    outline means no open top for a lid to close."""
    if width is not None and depth is not None:
        outline = None
        recognized_holes = []
        unrecognized_holes = []
    elif pcb_path:
        if kicad_pcb_import is None:
            raise RuntimeError(
                "File-based enclosure generation requires kicad_pcb_import, which failed to "
                "import."
            )
        outline = kicad_pcb_import.extract_board_outline(pcb_path)
        recognized_holes = kicad_pcb_import.extract_mounting_holes(pcb_path)
        unrecognized_holes = []
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
        lid=lid,
        lid_thickness_mm=lid_thickness_mm,
        timeout_s=timeout_s,
        cancel_event=cancel_event,
    )
    result = {**result, "unrecognized_holes": unrecognized_holes}
    if outline is not None:
        # SPEC-311 §2: the pre-existing unrecognized_holes warning above
        # only ever fires for a board that has *some* NPTH pads, just
        # not ones this app recognizes as mounting holes. A board with
        # *zero* holes of any kind -- recognized or not -- previously
        # triggered no warning at all, indistinguishable from "the
        # detection missed them." Only meaningful in file/live mode
        # (outline is not None); manual mode has no board data to have
        # found holes on in the first place.
        result["no_mounting_holes_found"] = not recognized_holes and not unrecognized_holes

    return result


def freecad_export_enclosure(
    parts: str,
    fmt: str,
    dest_path: str,
    glb_path: str = None,
    step_path: str = None,
    lid_glb_path: str = None,
    lid_step_path: str = None,
    timeout_s: float = 30.0,
    cancel_event=None,
) -> dict:
    """The freecad.export_enclosure route (`CTX-311.13`) -- the real,
    explicit "Save" action `SPEC-311` §2 named as an open question and
    `CTX-311.2` decided (explicit-save-only) but never actually wired up
    (see `freecad_generate_enclosure`'s own docstring for the real,
    confirmed auto-save bug this replaces). A thin wrapper over
    `freecad_bridge.export_enclosure` -- every source path comes straight
    from the caller's own already-completed Generate result (`EnclosurePanel`'s
    own `result` state), never looked up server-side, so this route has no
    hidden dependency on daemon-side "last generated" state."""
    export_enclosure(
        parts=parts,
        fmt=fmt,
        dest_path=dest_path,
        glb_path=glb_path,
        step_path=step_path,
        lid_glb_path=lid_glb_path,
        lid_step_path=lid_step_path,
        timeout_s=timeout_s,
        cancel_event=cancel_event,
    )
    return {"dest_path": dest_path}


# --- library.*/project.* routes (SPEC-304, CTX-304.1) -----------------
# Thin wrappers over library_store, matching kicad_generate_component's
# own pattern of naming daemon-level routes distinctly from the bridge
# module functions they delegate to.
def library_save_part(part: dict) -> dict:
    return library_store.save_part(part)


def library_load_part(part_id: str) -> dict:
    return library_store.load_part(part_id)


def library_list_parts(library_id: str = None) -> list:
    return library_store.list_parts(library_id)


def library_list_symbols(library_id: str = None) -> list:
    return library_store.list_symbols(library_id)


def library_list_footprints(library_id: str = None) -> list:
    return library_store.list_footprints(library_id)


def library_list_libraries() -> list:
    return library_store.list_libraries()


def library_create_library(name: str) -> dict:
    return library_store.create_library(name)


def library_tag_object(kind: str, object_id: str, library_ids: list) -> dict:
    return library_store.tag_object(kind, object_id, library_ids)


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


def library_render_symbol_preview(symbol_id: str) -> dict:
    """The library.render_symbol_preview route (CTX-306.7): real user
    feedback found Part Detail showing a footprint/symbol only as text
    -- a footprint's pad layout and a symbol's pin arrangement are
    inherently visual, and text alone doesn't let a user judge whether
    a match is right. Reuses `export_symbol_kicad_sym` (a cheap,
    idempotent text write) to guarantee a real, current `.kicad_sym`
    file exists before rendering it -- never assumes "Export Symbol"
    was already clicked. Returns the real SVG text itself, not a path
    -- an inline-renderable string needs no Tauri asset-protocol
    wiring, unlike `kicad.export_board_glb`'s binary `.glb`."""
    path = library_store.export_symbol_kicad_sym(symbol_id)
    svg_path = kicad_cli.export_symbol_svg(path)
    with open(svg_path, encoding="utf-8") as f:
        return {"svg": f.read()}


def library_render_footprint_preview(footprint_id: str) -> dict:
    """The library.render_footprint_preview route (CTX-306.7): the
    footprint counterpart to library_render_symbol_preview above --
    same reasoning, same real-file-then-render shape."""
    path = library_store.export_footprint_kicad_mod(footprint_id)
    pretty_dir = os.path.dirname(path)
    svg_path = kicad_cli.export_footprint_svg(pretty_dir, footprint_id)
    with open(svg_path, encoding="utf-8") as f:
        return {"svg": f.read()}


def library_search_community_footprints(query: str) -> list:
    """CTX-314.1: search-only -- real candidates from the curated
    GitHub allowlist, no import/persistence. The optional github_token
    comes from CONFIG['secrets'], the same place every other configured
    secret already lives (SPEC-106 §2) -- a real KNOWN_SECRET_KEYS entry
    since CTX-314.2, so this is None only when the user hasn't
    configured one, meaning that search runs unauthenticated."""
    return community_libraries.search_community_footprints(
        query, github_token=CONFIG["secrets"].get("github_token")
    )


def library_import_community_footprint(
    owner: str,
    repo: str,
    path: str,
    kind: str,
    license: str,
    download_url: str,
    blob_sha: str | None = None,
    symbol_name: str | None = None,
) -> dict:
    """CTX-314.2: fetches a candidate's real content (from the
    raw.githubusercontent.com URL search_community_footprints already
    returned), real-verifies it by parsing with kiutils, and persists it
    with full provenance. A footprint is one file, imported directly. A
    `.kicad_sym` file is a real *library* of many symbols (see
    community_libraries.parse_symbol_library's own docstring) -- with no
    symbol_name given, this returns the real browse list
    (`{"symbols": [...]}`) and persists nothing; a second call with a
    real, chosen symbol_name actually imports. Never guesses "the first
    symbol in the file" -- SchemaValidationError, naming the real
    available symbols, if symbol_name doesn't match any of them."""
    content = community_libraries.fetch_raw_content(download_url)
    provenance = {
        "source": "community_library",
        "owner": owner,
        "repo": repo,
        "path": path,
        "license": license,
        "blob_sha": blob_sha,
    }

    if kind == "footprint":
        preview = community_libraries.parse_footprint(content)
        stem = path.rsplit("/", 1)[-1].removesuffix(".kicad_mod")
        footprint_id = f"{owner}__{repo}__{stem}"
        return library_store.save_footprint(
            {
                "footprint_id": footprint_id,
                "footprint_name": stem,
                "raw_kicad_mod": content,
                "pad_count": preview["pad_count"],
                "provenance": provenance,
            }
        )

    if kind == "symbol":
        symbols = community_libraries.parse_symbol_library(content)
        if symbol_name is None:
            return {"symbols": symbols}

        match = next((s for s in symbols if s["name"] == symbol_name), None)
        if match is None:
            available = ", ".join(s["name"] for s in symbols)
            raise library_store.SchemaValidationError(
                f"'{symbol_name}' is not a real symbol in {path}. Available symbols: {available}"
            )

        symbol_id = f"{owner}__{repo}__{symbol_name}"
        return library_store.save_symbol(
            {
                "symbol_id": symbol_id,
                "symbol_name": symbol_name,
                "raw_kicad_sym": content,
                "pin_count": match["pin_count"],
                "provenance": provenance,
            }
        )

    raise library_store.SchemaValidationError(f"Unknown kind '{kind}' -- expected 'footprint' or 'symbol'.")


def project_save(project: dict) -> dict:
    return library_store.save_project(project)


def project_load(name: str) -> dict:
    return library_store.load_project(name)


def project_list() -> list:
    return library_store.list_projects()


def project_open_from_directory(directory: str) -> dict:
    """CTX-312.3: the real backend for the native menu's "Open Project…"
    action -- restores a project from a real, already-linked folder
    (e.g. copied from another machine), the actual payoff of
    `CTX-312.1`'s own portability work. Thin passthrough, matching every
    other `project.*` route's own convention; `library_store`'s own
    `ProjectNotLinkedError` surfaces as a clean route error rather than
    silently creating a new project."""
    return library_store.open_project_from_directory(directory)


def project_get_directory(name: str) -> dict:
    """CTX-311.13: the real, single source of truth for a project's own
    real directory path -- used to default the Enclosure Export dialog's
    save location to the project's own folder, rather than a second copy
    of `library_store`'s own `<storage_root>/projects/<name>/` convention
    hand-built on the frontend.

    CTX-312.1: once a project is real-linked to a directory on disk
    (`Project.directory`), that becomes this route's own real return
    value instead -- the more correct save-dialog default once one
    exists."""
    return {"path": library_store.project_directory(name)}


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


def project_set_intent(name: str, intent: str) -> dict:
    """CTX-206.1 (SPEC-206 §2.1): thin wrapper, matching every other
    `project.*` route's own convention. Synchronous, fast local file
    I/O -- no LLM call, unlike the chat routes SPEC-206's later slices
    add."""
    return library_store.set_project_intent(name, intent)


def project_add_part_reference(project_name: str, part_id: str) -> dict:
    """CTX-304.3 (SPEC-304 §2): thin wrapper, matching `project_save_artifact`'s
    own `project_name`-first-argument shape. Synchronous, fast local file
    I/O -- no LLM call."""
    return library_store.add_project_part_reference(project_name, part_id)


def project_set_footprint_override(project_name: str, part_id: str, footprint_id) -> dict:
    """CTX-308.9 (SPEC-308): thin wrapper, matching `project_add_part_reference`'s
    own convention. Synchronous, fast local file I/O -- no LLM call.
    `footprint_id: str | None` -- `None` clears an existing override."""
    return library_store.set_project_footprint_override(project_name, part_id, footprint_id)


def chat_load_thread(scope: str, scope_id: str) -> list:
    """CTX-206.3 (SPEC-206 §2.2): synchronous, real local file I/O
    (including a lazy, transparent migration of a legacy
    `conversation.jsonl` on a project's first `overview` read) -- no LLM
    call, unlike `chat.send`, a separate, later slice this route does
    not attempt to build."""
    return library_store.load_thread(scope, scope_id)


def chat_list_threads(project_name: str) -> list:
    return library_store.list_threads(project_name)


def chat_send(scope: str, scope_id: str, area: str, message: str, project_name: str = None) -> dict:
    """The chat.send route (CTX-206.6, SPEC-206 §2.5): the real thing
    `chat_load_thread`/`chat_list_threads`'s own docstrings named as "a
    separate, later slice" -- routes a scoped conversation turn to one
    of the five real SPEC-318 chat agents, threading CONFIG's own
    provider/model/secrets through exactly like every other real LLM
    route already does. A real LLM call (with an internal tool-use
    loop), so registered in ASYNC_ROUTES below."""
    return chat_agents.send(
        scope, scope_id, area, message, project_name=project_name,
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
        config=CONFIG,
    )


def chat_review(scope: str, scope_id: str, area: str, project_name: str = None) -> list:
    """The chat.review route (CTX-319.1, SPEC-319 §2.1): the seam
    SPEC-318 §2.5 defined but did not build. Real LLM call (reuses
    chat_agents._dispatch(), same as chat.send), so registered in
    ASYNC_ROUTES below."""
    return chat_agents.review(
        scope, scope_id, area, project_name=project_name,
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
        config=CONFIG,
    )


def context_search(query: str, part_id: str = None, project_name: str = None, limit: int = 8) -> list:
    """The context.search route (CTX-206.7, SPEC-206 §2.6): real, cheap
    local FTS5 (or LikeScanRetriever-fallback) lookup against the
    rebuildable retrieval index -- synchronous, matching
    kicad.search_footprints' own "real but cheap local computation"
    precedent, unlike chat.send's real LLM call. `part_id`/`project_name`
    are a friendlier, LLM-callable surface over context_index.search's
    own lower-level `scopes` list -- a chat agent tool call names one
    part or one project, never an arbitrary scope list."""
    scopes = []
    if part_id:
        scopes.append(("part", part_id))
    if project_name:
        scopes.append(("project", project_name))
    chunks = context_index.search(query, scopes=scopes, limit=limit)
    return [{"body": c.body, "source_ref": c.source_ref, "kind": c.kind, "score": c.score} for c in chunks]


def context_rebuild_index() -> dict:
    """The context.rebuild_index route (CTX-206.7, SPEC-206 §2.6): the
    manual trigger PRODUCT-PLAN.md §4 requires alongside the automatic
    staleness check `context.search` already runs on every call. A real
    full scan of every Part/Project record, so registered in
    ASYNC_ROUTES below -- unlike context.search, which only re-runs the
    scan when the automatic staleness check actually finds one stale."""
    return context_index.rebuild_index()


def chat_promote_turn(scope: str, scope_id: str, turn_id: str, target_scope: str, target_id: str) -> dict:
    """The chat.promote_turn route (CTX-206.8, SPEC-206 §2.7): always
    user-initiated -- an agent that wrote to the library on its own
    judgement would be exactly PRODUCT-PLAN.md §3.3's "apply a change
    the user didn't see first." Synchronous, real local file I/O, no
    LLM call."""
    return chat_agents.promote_turn(scope, scope_id, turn_id, target_scope, target_id)


class InvalidParamsError(Exception):
    """Raised when a request's params don't match the route's real signature."""


class JobNotFoundError(Exception):
    """Raised when job.cancel names a job_id that isn't (or is no longer) running."""


# Parameters a route function may declare for the daemon's own internal use
# (e.g. a per-job cancellation handle) that a client must never be able to
# supply directly over the wire.
_INTERNAL_ONLY_PARAMS = {"cancel_event"}

def configure_daemon(
    secrets: dict = None, llm_provider: str = None, llm_model: str = None,
    providers: list = None, provider_roles: dict = None,
) -> dict:
    """The daemon.configure route (SPEC-106 §2, extended by SPEC-303, then
    SPEC-321): merges secrets Rust hands over on the daemon's very first
    request into CONFIG. Ordinary route, dispatched through the normal
    ROUTES registry like anything else -- Rust's spawn_daemon (CTX-106.1)
    is what guarantees this line reaches stdin before any other, not any
    special-casing here.

    Also callable again later, live, from the Settings UI (SPEC-303) --
    `secrets` is always the *complete* current set when sent that way
    (core/tauri-rust's collect_known_secrets/sync_secrets_to_daemon), so
    replacing CONFIG["secrets"] wholesale is correct either way, not a
    partial-update bug. `llm_provider`/`llm_model` default to None meaning
    "leave unchanged" -- Rust's spawn-time call never passes them, so this
    extension can't regress that call.

    `providers`/`provider_roles` (SPEC-321 §2.3) follow the identical
    "None means leave unchanged, otherwise replace wholesale" contract --
    SPEC-208 §2.5's own rule that a role-binding update is always the
    complete current pair, never a partial delta, applied at the CONFIG
    layer exactly like `secrets` already is."""
    if secrets is not None:
        CONFIG["secrets"] = dict(secrets)
    if llm_provider is not None:
        CONFIG["llm_provider"] = llm_provider
    if llm_model is not None:
        CONFIG["llm_model"] = llm_model
    if providers is not None:
        CONFIG["providers"] = list(providers)
    if provider_roles is not None:
        CONFIG["provider_roles"] = dict(provider_roles)
    return {"configured": True}


def get_daemon_capabilities() -> dict:
    """The daemon.get_capabilities route (SPEC-303): re-runs the same
    cheap, non-blocking checks daemon.ready reports once at boot, on
    demand -- so the Settings UI can refresh what's actually configured
    right after a save/clear, without waiting for the next restart."""
    return _detect_capabilities()


def llm_chat(
    prompt: str, provider: str = None, model: str = None, system: str = "", history: list = None
) -> dict:
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
    never-configured install, CTX-302.1 Plan Drift).

    CTX-207.1 (SPEC-207 §2.2): returns `llm_providers.chat`'s own real
    `{"text", "usage", "model"}` dict as the job result, not just a bare
    string -- the free build's first real per-call token accounting.
    `Overview.tsx`'s `llm.chat` call site is this route's only real
    frontend consumer and was updated alongside this change."""
    provider_name = provider or CONFIG.get("llm_provider") or llm_providers._DEFAULT_PROVIDER

    model_name = model or CONFIG.get("llm_model")
    api_key = CONFIG.get("secrets", {}).get(f"{provider_name}_api_key", "")

    return llm_providers.chat(
        prompt, provider=provider_name, api_key=api_key, model=model_name, system=system, history=history
    )


def llm_get_provider_records() -> dict:
    """The llm.get_provider_records route (SPEC-321 §2.4/§2.5): the
    resolved provider set -- the five built-in presets plus whatever
    custom records `CONFIG["providers"]` currently carries -- for
    Settings' editor to render. Reuses `llm_providers
    ._resolve_provider_records` (real and tested since CTX-208.1) rather
    than duplicating preset knowledge in TypeScript, which would drift
    the moment either side changed a default.

    `managed` is filtered out here, unconditionally -- SPEC-208 §2.2.3
    already stops a config.json entry from *claiming* that id, but this
    route is the one place that stops it from ever being *rendered*, a
    distinct guarantee that spec's own contract never made on its own
    (SPEC-321 §3).

    `provider_roles` in the response is always the real, resolved
    binding -- run through `migrate_legacy_config` first, so a
    pre-SPEC-208 install (no `provider_roles` saved at all) sees what it
    would actually get today, not an empty map that reads as
    unconfigured. `provider_roles_saved` distinguishes that from a real,
    explicit save, so the editor's migration display (SPEC-321 §2.5) can
    say "currently bound to X, not yet saved" instead of implying the
    user already made this choice.

    Synchronous: a dict lookup and a filter, no network, no LLM call --
    not registered in ASYNC_ROUTES."""
    migrated = llm_providers.migrate_legacy_config(CONFIG)
    records = llm_providers._resolve_provider_records(migrated)
    return {
        "records": [record for record_id, record in records.items() if record_id != "managed"],
        "provider_roles": migrated.get("provider_roles") or {},
        "provider_roles_saved": bool(CONFIG.get("provider_roles")),
    }


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
    baked into connection_guidance.prompt.md.

    CTX-206.1 (SPEC-206 §2.4): previously returned this result and
    nothing else -- the caller (`PartDetail.tsx`) held it in `useState`
    and lost it on unmount, and it was gone the next time this Part was
    opened. Now persists it onto the real Part record via
    `library_store.save_part_connection_guidance` before returning, so
    it's a durable record `SPEC-318`'s Components agent (and any future
    caller) can read without re-generating it. The wire response to the
    frontend is unchanged -- same dict, same keys -- this route just
    also writes it to disk now."""
    part = library_store.load_part(part_id)
    result = component_pipeline.generate_connection_guidance(
        part["part_id"], part["package"], part["pins"],
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
        app_config=CONFIG,
    )
    library_store.save_part_connection_guidance(
        part_id,
        pin_guidance=result["pin_guidance"],
        general_notes=result["general_notes"],
        provenance=result["provenance"],
    )
    return result


def kicad_suggest_footprint_query(part_id: str) -> dict:
    """The kicad.suggest_footprint_query route (CTX-308.10): thin
    wrapper, matching kicad_generate_connection_guidance's own shape and
    the same CONFIG["llm_provider"]/["llm_model"] threading. Deliberately
    NOT persisted onto the Part record (unlike connection guidance) --
    a search-term suggestion has no durable value once the user has run
    the search; nothing else ever reads it back."""
    part = library_store.load_part(part_id)
    return component_pipeline.suggest_footprint_query(
        part["part_id"], part["manufacturer"], part["package"],
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
        app_config=CONFIG,
    )


def datasheet_generate_guidance(part_id: str, cancel_event=None) -> dict:
    """The datasheet.generate_guidance route (SPEC-205, CTX-205.3): loads
    the real Part, ensures its datasheet PDF is really cached locally
    (SPEC-306's own caching is best-effort and non-gating at Part-save
    time -- `library_store.ensure_datasheet_cached` fetches it here if
    it never was), runs CTX-205.1/.2's real structure-pass + Class B
    extraction pipeline, persists the real, cited result onto the Part
    record, and returns the updated Part. A real, multi-category LLM
    pipeline (~20+s observed for a real 8-category document), so
    registered in ASYNC_ROUTES below and threading `cancel_event`
    through, matching `freecad_generate_enclosure`'s own real pattern --
    checked once per category, not mid-call, in
    `datasheet_guidance._run_all_categories_and_close`.

    CTX-205.7: `generate_datasheet_guidance` now also returns a real
    `summaries` dict (SPEC-205 §2.1.1's plain-language layer) alongside
    `categories` -- both are threaded through to storage."""
    part = library_store.load_part(part_id)
    pdf_path = library_store.ensure_datasheet_cached(part["part_id"], part["datasheet_url"])
    guidance = datasheet_guidance.generate_datasheet_guidance(
        pdf_path,
        secrets=CONFIG.get("secrets", {}),
        provider=CONFIG.get("llm_provider"),
        model=CONFIG.get("llm_model"),
        cancel_event=cancel_event,
        app_config=CONFIG,
    )
    content_hash = library_store.content_hash_of_file(pdf_path)
    return library_store.save_part_design_guidance(
        part["part_id"], content_hash, guidance["categories"], guidance["summaries"],
    )


def datasheet_read_pages(part_id: str, pages: list) -> dict:
    """The datasheet.read_pages route (SPEC-206 SS2.5): a real chat-agent
    tool -- lets an agent check a specific page itself rather than only
    trusting already-generated guidance. Reuses ensure_datasheet_cached
    rather than re-fetching; datasheet_structure.extract_pages has no
    page selector of its own (it always extracts the whole document), so
    this route is the filter. Registered async for the same reason
    component_cache_datasheet is -- ensure_datasheet_cached can still be a
    real, first-time network fetch."""
    part = library_store.load_part(part_id)
    pdf_path = library_store.ensure_datasheet_cached(part["part_id"], part["datasheet_url"])
    wanted = {int(p) for p in pages}
    all_pages = datasheet_structure.extract_pages(pdf_path)
    return {
        "content_hash": library_store.content_hash_of_file(pdf_path),
        "pages": [p for p in all_pages if p["page"] in wanted],
    }


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
        app_config=CONFIG,
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
        app_config=CONFIG,
    )
    result["source_path"] = sch_path
    return result


def kicad_get_component_heights() -> dict:
    """The kicad.get_component_heights route (SPEC-311): real, honest
    per-component height derivation, composing `kicad_bridge`'s real
    per-footprint model list with `freecad_bridge`'s real STEP
    bounding-box reader -- the same composition pattern
    `freecad_generate_enclosure` already uses for board outline plus
    mounting holes. Async: a real `freecadcmd` subprocess runs per
    component with an attached STEP model, like every other real
    kicad.*/freecad.* route in ASYNC_ROUTES below.

    Never guesses: a footprint with no visible model, only a non-STEP
    model, an unresolved path, or a real `freecadcmd` read failure is
    reported unknown, not defaulted to a fallback number.

    Scope, decided honestly rather than silently (SPEC-311 §2's own
    named gap): only `.step`/`.stp` models are read. KiCad's own
    `.wrl`/VRML fallback format is not -- its real coordinate-unit
    convention is unverified as of this context, so it is not silently
    assumed to already be millimeters. A model's own `scale`/
    `rotation`/`offset` transform is also not yet applied to the
    computed bounding box (also named there) -- a rotated component's
    reported height may not be its true installed height.

    Returns {"known": [{"reference", "height_mm"}, ...], "unknown":
    ["<reference>", ...]} -- both real, reference-designator-keyed
    lists, so a caller can report exactly which components it does and
    doesn't have real data for, never a single opaque number.

    CTX-311.15: a real click-through found this route flagging a board's
    own real, unannotated MountingHole footprints (KiCad's own default
    placeholder reference, literally the same "REF**" text repeated once
    per unannotated footprint) as "missing a 3D model" -- true, but
    misleading and indistinguishable to a caller: a screw hole was never
    expected to have a rendered model, and it's already represented by
    the enclosure's own standoff geometry, not this route's own output.
    Skipped entirely here (`kicad_bridge.list_footprint_models`'s own
    `is_mounting_hole`, reusing `get_mounting_holes`'s real recognition
    convention) -- neither known nor unknown, since it was never a real
    candidate for a rendered 3D model in the first place."""
    if kicad_bridge is None:
        raise RuntimeError(
            "Component height derivation requires kicad_bridge, which failed to import."
        )
    if freecad_bridge is None:
        raise RuntimeError(
            "Component height derivation requires freecad_bridge, which failed to import."
        )

    footprints = kicad_bridge.list_footprint_models()
    known = []
    unknown = []
    for fp in footprints:
        if fp["is_mounting_hole"]:
            continue
        step_model = next(
            (
                m for m in fp["models"]
                if m["visible"] and m["resolved_path"]
                and os.path.splitext(m["resolved_path"])[1].lower() in (".step", ".stp")
            ),
            None,
        )
        if step_model is None:
            unknown.append(fp["reference"])
            continue
        try:
            bbox = freecad_bridge.get_step_bounding_box_mm(step_model["resolved_path"])
        except Exception:
            logger.exception(
                "get_step_bounding_box_mm failed for %s (%s)",
                fp["reference"], step_model["resolved_path"],
            )
            unknown.append(fp["reference"])
            continue
        known.append({"reference": fp["reference"], "height_mm": bbox["z_mm"]})

    return {"known": known, "unknown": unknown}


def kicad_export_board_glb(pcb_path: str) -> dict:
    """The kicad.export_board_glb route (SPEC-311): a real, assembled-
    board `.glb` via `kicad_cli.export_board_glb` -- the real visual
    source for the board-inside-enclosure preview `CTX-311.15` wires
    into `EnclosureViewer.tsx`. Async: a real `kicad-cli` subprocess,
    like every other real kicad.*/freecad.* route in ASYNC_ROUTES below.

    `kicad-cli`'s own export silently omits any component with no 3D
    model at all -- this route is the visual, not the source of truth
    for "is every component's height accounted for"; that honesty
    requirement is `kicad.get_component_heights`'s job, not this one.

    CTX-311.15: real-origins the export to the board's own bounding-box
    corner (`kicad_cli.export_board_glb`'s own `origin_x_mm`/`origin_y_mm`,
    real-verified live against `kicad-cli`) so `EnclosureViewer.tsx` can
    composite it inside the enclosure's own glb with a simple, already-
    known constant translation.

    Deliberately always derives the outline from *this exact `pcb_path`
    file* via `kicad_pcb_import.extract_board_outline` -- never
    `kicad_bridge.get_board_outline()`, which reads whatever board
    happens to be live in KiCad right now, not necessarily the same
    file this route was actually asked to export (a real, live-open
    board and an explicit `pcb_path` can genuinely differ, e.g. a
    manually-picked file). `freecad_generate_enclosure`'s own board-
    driven enclosure build already uses this same file-based extraction
    for every real call from `EnclosurePanel.tsx`'s Board mode (which
    always supplies `pcb_path`) -- matching that exact source, not just
    a similar one, is what guarantees this overlay's own origin lines
    up with the enclosure it's being placed inside."""
    if kicad_cli is None:
        raise RuntimeError(
            "Board .glb export requires kicad_cli, which failed to import."
        )
    if kicad_pcb_import is None:
        raise RuntimeError(
            "Board .glb export requires kicad_pcb_import, which failed to import."
        )
    outline = kicad_pcb_import.extract_board_outline(pcb_path)
    glb_path = kicad_cli.export_board_glb(pcb_path, outline["x_mm"], outline["y_mm"])
    return {"glb_path": glb_path}


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
    if export_enclosure is not None:
        routes["freecad.export_enclosure"] = freecad_export_enclosure
    if llm_providers is not None:
        routes["llm.chat"] = llm_chat
        routes["llm.get_provider_records"] = llm_get_provider_records
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
        routes["library.list_symbols"] = library_list_symbols
        routes["library.list_footprints"] = library_list_footprints
        routes["library.list_libraries"] = library_list_libraries
        routes["library.create_library"] = library_create_library
        routes["library.tag_object"] = library_tag_object
    if library_store is not None and kicad_cli is not None:
        routes["library.render_symbol_preview"] = library_render_symbol_preview
        routes["library.render_footprint_preview"] = library_render_footprint_preview
    if library_store is not None:
        routes["project.save"] = project_save
        routes["project.load"] = project_load
        routes["project.list"] = project_list
        routes["project.save_artifact"] = project_save_artifact
        routes["project.load_artifact"] = project_load_artifact
        routes["project.list_artifacts"] = project_list_artifacts
        routes["project.append_conversation_turn"] = project_append_conversation_turn
        routes["project.load_conversation"] = project_load_conversation
        routes["project.get_directory"] = project_get_directory
        routes["project.open_from_directory"] = project_open_from_directory
        routes["project.set_intent"] = project_set_intent
        routes["project.add_part_reference"] = project_add_part_reference
        routes["project.set_footprint_override"] = project_set_footprint_override
        routes["chat.load_thread"] = chat_load_thread
        routes["chat.list_threads"] = chat_list_threads
    if chat_agents is not None and library_store is not None and tool_registry is not None:
        routes["chat.send"] = chat_send
        routes["chat.review"] = chat_review
    if chat_agents is not None and library_store is not None:
        # CTX-206.8: unlike chat.send, promote_turn never touches the
        # tool registry at all (it's plain local read/write, no agent
        # dispatch), so it doesn't need tool_registry to be real.
        routes["chat.promote_turn"] = chat_promote_turn
    if context_index is not None and library_store is not None:
        routes["context.search"] = context_search
        routes["context.rebuild_index"] = context_rebuild_index
    if community_libraries is not None:
        routes["library.search_community_footprints"] = library_search_community_footprints
        routes["library.import_community_footprint"] = library_import_community_footprint
    if tool_registry is not None:
        routes["agent.dispatch_tool"] = agent_dispatch_tool
    if fp_lib_table is not None:
        routes["kicad.search_footprints"] = kicad_search_footprints
    if kicad_write is not None and library_store is not None:
        routes["kicad.generate_footprint_from_part"] = kicad_generate_footprint_from_part
    if component_pipeline is not None and library_store is not None:
        routes["kicad.generate_connection_guidance"] = kicad_generate_connection_guidance
        routes["kicad.suggest_footprint_query"] = kicad_suggest_footprint_query
    if datasheet_guidance is not None and library_store is not None:
        routes["datasheet.generate_guidance"] = datasheet_generate_guidance
    if datasheet_structure is not None and library_store is not None:
        routes["datasheet.read_pages"] = datasheet_read_pages
    if kicad_bridge is not None:
        routes["kicad.list_open_boards"] = kicad_list_open_boards
        routes["kicad.list_project_schematics"] = kicad_list_project_schematics
    if kicad_cli is not None and component_pipeline is not None:
        if kicad_bridge is not None:
            routes["kicad.check_board"] = kicad_check_board
        routes["kicad.check_schematic"] = kicad_check_schematic
    if kicad_bridge is not None and freecad_bridge is not None:
        routes["kicad.get_component_heights"] = kicad_get_component_heights
    if kicad_cli is not None:
        routes["kicad.export_board_glb"] = kicad_export_board_glb
    return routes


# Route Registry mapping string methods to Python functions.
ROUTES = _build_routes()

# Methods that run off the read loop: a request for one of these returns
# {"job_id": ...} immediately, and the real result/failure/cancellation
# arrives later as a job.* notification (SPEC-105 §2).
ASYNC_ROUTES = {
    "freecad.generate_enclosure", "freecad.export_enclosure", "llm.chat", "kicad.generate_component",
    "kicad.inject_component", "component.search", "component.cache_datasheet",
    "kicad.generate_connection_guidance", "kicad.suggest_footprint_query", "kicad.check_board", "kicad.check_schematic",
    "kicad.get_component_heights", "kicad.export_board_glb", "datasheet.generate_guidance",
    "datasheet.read_pages", "library.render_symbol_preview", "library.render_footprint_preview",
    "chat.send", "chat.review", "context.rebuild_index",
    # CTX-314.2: both make real GitHub network calls (community_libraries.py's
    # own _github_request/fetch_raw_content) -- a real bug in CTX-314.1's own
    # shipped code (search_community_footprints was never added here) meant
    # any real GitHub round trip blocked the daemon's entire stdin read loop
    # (main()'s `for line in sys.stdin` calls handle_request synchronously),
    # freezing every other IPC command for the duration. Fixed here rather
    # than left in place, since CTX-314.2 builds directly on this same route.
    "library.search_community_footprints", "library.import_community_footprint",
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
            failure = {"job_id": job_id, "error": str(e)}
            # SPEC-207 §2.3: a structured `code` (e.g. `managed_quota_exhausted`)
            # alongside its own real extra fields (`reset_at`/`retry_after`),
            # duck-typed via getattr rather than importing
            # llm_providers.ManagedProviderError here -- this function stays
            # decoupled from any one bridge module's exception classes, same
            # as the cancellation check above. Absent for every other
            # exception, so this is a strictly additive, backward-compatible
            # payload change.
            code = getattr(e, "code", None)
            if code:
                failure["code"] = code
                failure.update(getattr(e, "extra", None) or {})
            emit({"jsonrpc": "2.0", "method": "job.failed", "params": failure})
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

    # CTX-206.7 (SPEC-206 §3): FTS5 is a compile-time SQLite option that
    # can differ between this dev venv and the frozen PyInstaller
    # sidecar -- surfaced here (real-probed, never sniffed from
    # sqlite3.sqlite_version) so SPEC-303's "Copy Diagnostics" reports
    # it. A cheap, real, non-blocking in-memory check, matching this
    # whole function's own "cheap checks only" contract.
    fts5_available = context_index.fts5_available() if context_index is not None else False

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
        # SPEC-321 §2.5: the editor's per-record "is a key saved for this
        # one" display needs to ask about an arbitrary custom
        # `api_key_ref`, not just the four fixed vendor names above --
        # `configured_secrets` already holds every key `collect_known_secrets`
        # (Rust) found in the real keychain, vendor or custom alike, since
        # CTX-321.1; this just stops truncating that down to the fixed list.
        "configured_secret_refs": sorted(key for key, value in configured_secrets.items() if value),
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
        # CTX-314.1: always False today -- no real KNOWN_SECRET_KEYS
        # entry for github_token exists yet (CTX-314.2's job); real,
        # honest interim state, not a placeholder pretending to be
        # wired up. Community-library search still works unauthenticated,
        # just at GitHub's lower 60-requests/hour rate limit.
        "github_token_configured": bool(configured_secrets.get("github_token")),
        "fts5_available": fts5_available,
        # SPEC-407 §2.4: the optional modules that failed to import at
        # startup, each with the capability it takes down. Empty on a
        # healthy build. Non-empty means the artifact is broken -- most
        # often a mis-frozen sidecar -- and both `verify_sidecar.py` and
        # the app treat it as a hard failure rather than letting a daemon
        # that answers `daemon.ready` pass for a working one.
        "degraded_modules": list(_DEGRADED_MODULES),
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
