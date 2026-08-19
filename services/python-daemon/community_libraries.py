"""
Real footprint/symbol discovery and import across a small, curated
allowlist of GitHub-hosted KiCad community libraries. CTX-314.1 shipped
search-only (no fetch, no parse, no persistence). CTX-314.2 adds real
content fetch (`fetch_raw_content`) and real parsing/validation
(`parse_footprint`/`parse_symbol_library`) -- persistence itself lives
in `daemon.py`'s `library_import_community_footprint`, which calls
`library_store.save_footprint`/`save_symbol`.

Real, hand-verified allowlist, not a live GitHub-wide search:
`espressif/kicad-libraries` (148 commits, active, real LICENSE.md,
plain files -- no submodules -- in symbols/ and footprints/*.pretty/)
and `sparkfun/SparkFun-KiCad-Libraries` (1,488 commits, very active,
explicit CC-BY-4.0 license, plain files in symbols/ and footprints/).
`kitspace/kicad_footprints` -- SPEC-314's own original real find -- is
deliberately not here yet: it aggregates other repos via git
submodules, each needing its own separate resolution, real added
complexity this first slice defers.

Uses the GitHub Git Trees API (`GET /repos/{owner}/{repo}/git/trees/
{sha}?recursive=1`), not the code-search endpoint -- a real, considered
choice: code search requires authentication and caps at 10 requests/
minute even authenticated (confirmed directly against GitHub's own
rate-limit docs during SPEC-314's own planning), while the Trees API
falls under the general core limit (60/hour unauthenticated, 5,000/hour
with a token) and a curated allowlist never needs GitHub's own search
index -- it only ever walks repos it already knows about.

Real parsing-risk finding (CTX-314.1): kiutils 1.4.8 was verified
directly against real `.kicad_mod`/`.kicad_sym` files fetched live from
both allowlisted repos, across two different KiCad format generations
(Espressif's older `fp_text`-based format, SparkFun's newer `property`-
based one) -- both parse correctly. This is a real, different result
from `kicad_pcb_import.py`'s own finding that the same kiutils version
crashes on a full `.kicad_pcb` board file (SPEC-310): footprints and
symbols are simpler, self-contained S-expressions kiutils handles fine
even though full boards don't.
"""
import json
import ssl
import time
import urllib.error
import urllib.request

import certifi
import kiutils.footprint
import kiutils.symbol
from kiutils.utils.sexpr import parse_sexp

_GITHUB_API_BASE = "https://api.github.com"
_REQUEST_TIMEOUT_S = 15
# Matches library_store.py's own real, verified reason for using
# certifi's CA bundle explicitly rather than trusting this
# interpreter's own broken default SSL context.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# In-process only -- not persisted, not shared across daemon restarts.
# Scoped to this module rather than library_store.py's own cache
# convention (CTX-203.2 removed the one precedent for a persisted,
# TTL-checked external-content cache) since a repo's own file tree is
# regenerable from a single real API call, not worth writing to disk.
_TREE_CACHE_TTL_S = 15 * 60
_tree_cache: dict[str, tuple[float, list[dict]]] = {}


class CommunityLibraryError(Exception):
    """Raised on a real GitHub API failure (network, rate limit, a
    real non-200 response) -- never silently swallowed into an empty
    result, which would be indistinguishable from a genuine "no
    matches" outcome."""


# Real, hand-verified allowlist entries. Each records its own real
# license and subdirectory layout -- not assumed uniform across repos.
ALLOWLIST = [
    {
        "owner": "espressif",
        "repo": "kicad-libraries",
        "license": "See LICENSE.md in the repository",
        "footprint_dir_prefix": "footprints/",
        "symbol_dir_prefix": "symbols/",
    },
    {
        "owner": "sparkfun",
        "repo": "SparkFun-KiCad-Libraries",
        "license": "CC-BY-4.0",
        "footprint_dir_prefix": "footprints/",
        "symbol_dir_prefix": "symbols/",
    },
]


def _github_request(path: str, github_token: str | None) -> dict:
    """A single real GET against the GitHub REST API. Raises
    CommunityLibraryError on any real failure -- a rate limit, a
    network error, a non-200 response -- rather than returning a value
    a caller could mistake for a real, empty result."""
    headers = {
        "User-Agent": "hardware-agent-studio/0.1",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    request = urllib.request.Request(f"{_GITHUB_API_BASE}{path}", headers=headers)
    try:
        with urllib.request.urlopen(
            request, timeout=_REQUEST_TIMEOUT_S, context=_SSL_CONTEXT
        ) as response:
            if response.status != 200:
                raise CommunityLibraryError(f"GitHub API returned HTTP {response.status} for {path}.")
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 403 and "rate limit" in (e.reason or "").lower():
            raise CommunityLibraryError(
                "GitHub API rate limit reached. Add a GitHub token in Settings for a higher limit, "
                "or try again later."
            ) from e
        raise CommunityLibraryError(f"GitHub API request for {path} failed: HTTP {e.code} {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # Matches library_store.cache_datasheet's own real finding: a
        # timeout during response.read() itself (not just the connect
        # phase) raises a bare TimeoutError/OSError, which URLError
        # alone would not catch.
        raise CommunityLibraryError(f"GitHub API request for {path} failed: {e}") from e


def _repo_tree(owner: str, repo: str, github_token: str | None) -> list[dict]:
    """Returns the real, full recursive file tree for a repo's default
    branch, real-cached in-process for `_TREE_CACHE_TTL_S` so repeated
    searches against the same small allowlist don't re-fetch the same
    multi-thousand-entry tree on every call."""
    cache_key = f"{owner}/{repo}"
    cached = _tree_cache.get(cache_key)
    if cached is not None:
        cached_at, tree = cached
        if time.monotonic() - cached_at < _TREE_CACHE_TTL_S:
            return tree

    repo_info = _github_request(f"/repos/{owner}/{repo}", github_token)
    default_branch = repo_info["default_branch"]
    tree_response = _github_request(
        f"/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1", github_token
    )
    tree = tree_response.get("tree", [])
    _tree_cache[cache_key] = (time.monotonic(), tree)
    return tree


def search_community_footprints(query: str, github_token: str | None = None) -> list[dict]:
    """Searches every allowlisted repo's real file tree for a
    `.kicad_mod`/`.kicad_sym` path whose filename contains `query`
    (case-insensitive), returning real candidates: repo, real file
    path, real download URL, real license, and which kind of file it
    is. No file content is fetched here -- matches CTX-308.1's own
    "list matches first, fetch geometry only on selection" shape.
    Returns an empty list for a query with no real match anywhere in
    the allowlist -- a normal, honest outcome, not an error."""
    query_lower = query.lower()
    candidates = []

    for entry in ALLOWLIST:
        tree = _repo_tree(entry["owner"], entry["repo"], github_token)
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item["path"]
            if not (path.endswith(".kicad_mod") or path.endswith(".kicad_sym")):
                continue
            if query_lower not in path.lower():
                continue

            kind = "footprint" if path.endswith(".kicad_mod") else "symbol"
            candidates.append(
                {
                    "owner": entry["owner"],
                    "repo": entry["repo"],
                    "path": path,
                    "kind": kind,
                    "license": entry["license"],
                    "blob_sha": item.get("sha"),
                    "download_url": (
                        f"https://raw.githubusercontent.com/{entry['owner']}/{entry['repo']}/HEAD/{path}"
                    ),
                }
            )

    return candidates


def fetch_raw_content(download_url: str) -> str:
    """CTX-314.2: a plain HTTPS GET against the real
    `raw.githubusercontent.com` URL `search_community_footprints` already
    returns -- deliberately not a GitHub REST API call (`_github_request`
    above), so fetching a file's real content never consumes the same
    60/hour-unauthenticated budget a tree search does. GitHub serves
    raw file content from a separate CDN (`raw.githubusercontent.com`),
    a real, different system from `api.github.com`. Reuses this module's
    own `_SSL_CONTEXT`/timeout/error-translation conventions exactly."""
    request = urllib.request.Request(
        download_url, headers={"User-Agent": "hardware-agent-studio/0.1"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=_REQUEST_TIMEOUT_S, context=_SSL_CONTEXT
        ) as response:
            if response.status != 200:
                raise CommunityLibraryError(
                    f"GitHub raw content returned HTTP {response.status} for {download_url}."
                )
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise CommunityLibraryError(
            f"GitHub raw content request for {download_url} failed: HTTP {e.code} {e.reason}"
        ) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CommunityLibraryError(f"GitHub raw content request for {download_url} failed: {e}") from e


def parse_footprint(content: str) -> dict:
    """CTX-314.2: real-verifies a fetched `.kicad_mod` file's content by
    actually parsing it with kiutils, returning its real pad count.
    Raises CommunityLibraryError (not a bare kiutils exception) on real
    unparseable content -- this app never persists a file that didn't
    actually parse. Real, direct verification during this context's own
    planning confirmed kiutils parses real footprint files from both
    allowlisted repos correctly (CTX-314.1's own earlier finding,
    reconfirmed here against the specific `Footprint.from_sexpr` call
    this function makes)."""
    try:
        parsed = kiutils.footprint.Footprint.from_sexpr(parse_sexp(content))
    except Exception as e:
        raise CommunityLibraryError(f"Could not parse this file as a real KiCad footprint: {e}") from e
    return {"pad_count": len(parsed.pads)}


def parse_symbol_library(content: str) -> list[dict]:
    """CTX-314.2: real-verifies a fetched `.kicad_sym` file's content the
    same way parse_footprint does, but a `.kicad_sym` file is a real
    *library* of many symbols (verified directly during planning against
    `sparkfun/SparkFun-KiCad-Libraries`'s own `SparkFun-Capacitor.
    kicad_sym`, 73 real symbols in one file) -- returns every real
    symbol's name (`libId`) and real pin count. A real symbol's own pins
    live on its sub-units (`Symbol.units`), not the top-level `Symbol`
    object itself -- verified directly, exactly like this app's own
    hand-built `_0_1`/`_1_1` sub-symbol convention
    (library_store._build_kicad_sym_text)."""
    try:
        lib = kiutils.symbol.SymbolLib.from_sexpr(parse_sexp(content))
    except Exception as e:
        raise CommunityLibraryError(f"Could not parse this file as a real KiCad symbol library: {e}") from e
    return [
        {"name": symbol.libId, "pin_count": sum(len(unit.pins) for unit in symbol.units)}
        for symbol in lib.symbols
    ]
