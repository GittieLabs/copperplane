"""
ChromaDB vector backend.

Implements the VectorBackend protocol using ChromaDB for embedded or
client-server vector storage.

Requires:
    pip install agentflow[chroma]
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("agentflow.memory.backends.chroma")

try:
    import chromadb as _chromadb
except ImportError:
    _chromadb = None  # type: ignore[assignment]


class ChromaBackend:
    """VectorBackend implementation using ChromaDB.

    By default uses a persistent local client (no server required).
    Pass a custom ``chromadb.ClientAPI`` instance for client-server mode.
    """

    def __init__(
        self,
        *,
        path: str = "./chroma-storage",
        client: Any | None = None,
    ) -> None:
        if _chromadb is None:
            raise ImportError("Install chromadb: pip install agentflow[chroma]")
        self._client = client or _chromadb.PersistentClient(path=path)
        self._collections: dict[str, Any] = {}

    def ensure_collection(self, name: str, dim: int) -> None:
        self._collections[name] = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Ensured ChromaDB collection: %s", name)

    def upsert(
        self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None:
        coll = self._collections[collection]
        # Chroma stores documents separately from metadata.
        # We put the full content in documents and everything in metadatas.
        document = payload.get("content", "")
        coll.upsert(
            ids=[point_id],
            embeddings=[vector],
            documents=[document],
            metadatas=[payload],
        )

    def query(self, collection: str, vector: list[float], limit: int) -> list[dict[str, Any]]:
        coll = self._collections[collection]
        results = coll.query(
            query_embeddings=[vector],
            n_results=limit,
            include=["metadatas", "distances"],
        )

        out: list[dict[str, Any]] = []
        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
            distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)
            for point_id, metadata, distance in zip(ids, metadatas, distances):
                out.append({
                    "id": point_id,
                    "score": 1.0 - distance,
                    "payload": metadata or {},
                })
        return out

    def delete_points(self, collection: str, point_ids: list[str]) -> None:
        coll = self._collections[collection]
        coll.delete(ids=point_ids)
