from __future__ import annotations

from typing import Protocol


class RetrievalDependencyError(RuntimeError):
    pass


class EmbeddingModel(Protocol):
    name: str

    def embed(self, text: str) -> list[float]:
        ...


class BgeEmbeddingModel:
    dims = 384

    def __init__(self, name: str = "BAAI/bge-small-en-v1.5"):
        self.name = name
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RetrievalDependencyError(
                    "Missing local embedding dependency. Install the retrieval extra and rebuild the index."
                ) from exc
            try:
                self._model = SentenceTransformer(self.name)
            except Exception as exc:
                raise RetrievalDependencyError(
                    f"Could not load embedding model {self.name}. Install retrieval dependencies, ensure the model is available locally, and rebuild the index."
                ) from exc
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load()
        try:
            vector = model.encode(text, normalize_embeddings=True)
        except Exception as exc:
            raise RetrievalDependencyError(
                f"Could not encode text with embedding model {self.name}. Rebuild the index after fixing the local model runtime."
            ) from exc
        return [float(value) for value in vector]
