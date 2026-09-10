"""
Qdrant vector backend.

Implements the VectorBackend protocol using qdrant-client.

Requires:
    pip install agentflow[vector]
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("agentflow.memory.backends.qdrant")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        PointStruct,
        VectorParams,
    )
except ImportError:
    QdrantClient = None  # type: ignore[assignment,misc]
    PointStruct = None  # type: ignore[assignment,misc]
    VectorParams = None  # type: ignore[assignment,misc]
    Distance = None  # type: ignore[assignment,misc]


class QdrantBackend:
    """VectorBackend implementation using Qdrant.

    Wraps ``qdrant-client`` and exposes the four operations that
    ``VectorMemory`` needs: ensure_collection, upsert, query, delete_points.
    """

    def __init__(self, *, url: str = "http://localhost:6333", api_key: str | None = None) -> None:
        if QdrantClient is None:
            raise ImportError("Install qdrant-client: pip install agentflow[vector]")

        if not url.startswith("http"):
            url = f"http://{url}"

        self._client = QdrantClient(url=url, api_key=api_key)

    def ensure_collection(self, name: str, dim: int) -> None:
        collections = [c.name for c in self._client.get_collections().collections]
        if name in collections:
            info = self._client.get_collection(name)
            existing_dim = info.config.params.vectors.size  # type: ignore[union-attr]
            if existing_dim != dim:
                logger.warning(
                    "Qdrant collection '%s' has dim=%d but expected dim=%d — recreating",
                    name, existing_dim, dim,
                )
                self._client.delete_collection(name)
            else:
                return
        logger.info("Creating Qdrant collection: %s (dim=%d)", name, dim)
        self._client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def upsert(
        self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None:
        self._client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    def query(self, collection: str, vector: list[float], limit: int) -> list[dict[str, Any]]:
        results = self._client.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return [
            {"id": str(point.id), "score": point.score, "payload": dict(point.payload)}
            for point in results.points
        ]

    def delete_points(self, collection: str, point_ids: list[str]) -> None:
        self._client.delete(
            collection_name=collection,
            points_selector=point_ids,
        )
