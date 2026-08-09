"""
Connection lifecycle to a running KiCad instance via the IPC API
(SPEC-103). The connection is opened lazily on first use and held open
for the rest of the daemon's life, to avoid paying a handshake on every
call.
"""
import logging

from kipy import KiCad
from kipy.errors import ApiError, ConnectionError as KiCadConnectionError, FutureVersionError

logger = logging.getLogger(__name__)


class KiCadUnavailableError(Exception):
    """Raised whenever KiCad can't be reached, with a clean, user-facing
    message instead of a raw kipy traceback."""


_client = None
_socket_path_override = None
_timeout_ms_override = None


def configure(socket_path=None, timeout_ms=None):
    """Applies CTX-106.1's daemon-injected config. Resets the held-open
    client so the *next* `get_client()` call reconnects using these
    settings -- without this, a config change wouldn't take effect until
    a full daemon restart, since the client is normally held open for the
    daemon's whole life (SPEC-103 §2)."""
    global _socket_path_override, _timeout_ms_override, _client
    _socket_path_override = socket_path
    _timeout_ms_override = timeout_ms
    _client = None


def get_client() -> KiCad:
    """Returns the held-open KiCad client, connecting on first use with
    any configured `socket_path`/`timeout_ms` override (SPEC-106)."""
    global _client
    if _client is not None:
        return _client

    kwargs = {}
    if _socket_path_override:
        kwargs["socket_path"] = _socket_path_override
    if _timeout_ms_override:
        kwargs["timeout_ms"] = _timeout_ms_override

    client = KiCad(**kwargs)
    try:
        client.check_version()
    except FutureVersionError:
        # kicad-python's declared API version routinely lags a few patch
        # releases behind the actual KiCad app (e.g. package built against
        # 10.0.1, app is 10.0.3) — this is normal and not worth blocking
        # the connection over, since patch releases don't break the wire
        # protocol. Only a genuine unreachable/incompatible KiCad (caught
        # below) should stop the daemon from connecting.
        logger.warning(
            "KiCad reports a newer version than kicad-python declares support "
            "for; continuing anyway since this is usually just package lag."
        )
    except (KiCadConnectionError, ApiError) as e:
        raise KiCadUnavailableError(
            "Could not connect to KiCad. Ensure KiCad 9 or later is running "
            "with the IPC API enabled (Preferences > Plugins)."
        ) from e

    _client = client
    return _client


def reset_connection() -> None:
    """Drops the held connection so the next call reconnects from scratch.
    Call this after a broken-pipe/State-Desync error (SPEC-103 §3) — the
    old client's socket is unusable once the connection has failed."""
    global _client
    _client = None


def get_kicad_version() -> dict:
    """Real, read-only round trip proving the bridge: returns KiCad's own
    version. A mid-call disconnect (e.g. the user closes KiCad) is caught
    and re-raised as `KiCadUnavailableError` rather than an unhandled
    exception that would take down the daemon."""
    client = get_client()
    try:
        version = client.get_version()
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    return {
        "full_version": version.full_version,
        "major": version.major,
        "minor": version.minor,
        "patch": version.patch,
    }
