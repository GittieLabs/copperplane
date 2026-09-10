"""
LanceDB vector backend.

Implements the VectorBackend protocol using LanceDB for fully embedded
vector storage. No server process required — data is stored in a local
directory, making this ideal for desktop and edge deployments.

Requires:
    pip install agentflow[lancedb]
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("agentflow.memory.backends.lancedb")

try:
    import lancedb as _lancedb
    import pyarrow as pa
except ImportError:
    _lancedb = None  # type: ignore[assignment]
    pa = None  # type: ignore[assignment]


class LanceDBBackend:
    """VectorBackend implementation using LanceDB (embedded, serverless).

    Stores vectors and payloads in a local directory. Each collection maps
    to a LanceDB table with columns: ``id`` (str), ``vector`` (fixed-size
    list of float32), ``payload`` (JSON string).
    """

    def __init__(self, *, path: str = "./lancedb-storage") -> None:
        if _lancedb is None:
            raise ImportError("Install lancedb: pip install agentflow[lancedb]")
        self._db = _lancedb.connect(path)
        self._tables: dict[str, Any] = {}

    def ensure_collection(self, name: str, dim: int) -> None:
        existing = self._db.table_names()
        if name in existing:
            self._tables[name] = self._db.open_table(name)
            logger.debug("Opened existing LanceDB table: %s", name)
        else:
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
                pa.field("payload", pa.string()),
            ])
            self._tables[name] = self._db.create_table(name, schema=schema)
            logger.info("Created LanceDB table: %s (dim=%d)", name, dim)

    def upsert(
        self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None:
        table = self._tables[collection]
        table.add([{
            "id": point_id,
            "vector": vector,
            "payload": json.dumps(payload),
        }])

    def query(self, collection: str, vector: list[float], limit: int) -> list[dict[str, Any]]:
        table = self._tables[collection]
        results = table.search(vector).limit(limit).to_list()
        out: list[dict[str, Any]] = []
        for row in results:
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            out.append({
                "id": row["id"],
                "score": 1.0 - row.get("_distance", 0.0),
                "payload": payload,
            })
        return out

    def delete_points(self, collection: str, point_ids: list[str]) -> None:
        table = self._tables[collection]
        ids_str = ", ".join(f"'{pid}'" for pid in point_ids)
        table.delete(f"id IN ({ids_str})")
