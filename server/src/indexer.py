import hashlib
import logging
import re
import threading
from pathlib import Path

import chromadb
import numpy as np
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from config import determine_root_dir

logger = logging.getLogger(__name__)

COLLECTION_NAME = "obsidian"
INDEX_DIR = Path(__file__).resolve().parents[1] / ".chroma"

SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+|\n+")

MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 1500
MAX_SENTENCE_CHARS = 2000
BREAKPOINT_PERCENTILE = 50.0
EMBED_BATCH_SIZE = 256


class Indexer:
    def __init__(
        self,
        rootdir: Path,
        index_dir: Path = INDEX_DIR,
        embedding_function: object | None = None,
    ) -> None:
        self.rootdir = rootdir
        self.index_dir = index_dir
        self.embedding_function = embedding_function
        self._client: chromadb.ClientAPI | None = None
        self._ready = threading.Event()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            self._client = chromadb.PersistentClient(path=str(self.index_dir))
        return self._client

    def _collection(self) -> chromadb.Collection:
        return self.client.get_or_create_collection(
            COLLECTION_NAME, embedding_function=self.embedding_function
        )

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _documents(self) -> list[tuple[str, str, str]]:
        documents: list[tuple[str, str, str]] = []
        for path in sorted(self.rootdir.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                logger.warning("Skipping unreadable file: %s", path)
                continue
            if text.strip():
                relative = path.relative_to(self.rootdir).as_posix()
                documents.append((relative, text, self._sha(text)))
        return documents

    def _indexed_chunks(
        self, collection: chromadb.Collection
    ) -> dict[str, list[tuple[str, str, str]]]:
        indexed: dict[str, list[tuple[str, str, str]]] = {}
        result = collection.get(include=["metadatas"])
        for chunk_id, metadata in zip(result.get("ids") or [], result.get("metadatas") or []):
            file = (metadata or {}).get("file")
            if not file:
                continue
            indexed.setdefault(file, []).append(
                (chunk_id, metadata.get("sha") or "", metadata.get("file_sha") or "")
            )
        return indexed

    def build(self) -> int:
        collection = self._collection()
        indexed = self._indexed_chunks(collection)
        documents = self._documents()
        current_files = {doc_id for doc_id, _, _ in documents}

        removed_files = sorted(set(indexed) - current_files)
        if removed_files:
            collection.delete(where={"file": {"$in": removed_files}})

        indexed_files = 0
        unchanged_files = 0
        for doc_id, text, file_sha in documents:
            existing = indexed.get(doc_id)
            if existing and existing[0][2] == file_sha:
                unchanged_files += 1
                continue
            chunks = self._chunks(text)
            if existing:
                collection.delete(where={"file": doc_id})
            if chunks:
                collection.upsert(
                    ids=[f"{doc_id}::{i}" for i in range(len(chunks))],
                    documents=chunks,
                    metadatas=[
                        {
                            "file": doc_id,
                            "sha": self._sha(chunk),
                            "file_sha": file_sha,
                            "chunk": i,
                        }
                        for i, chunk in enumerate(chunks)
                    ],
                )
            indexed_files += 1

        self._ready.set()
        logger.info(
            "Indexed %d file(s) from %s (%d unchanged)",
            indexed_files,
            self.rootdir,
            unchanged_files,
        )
        return indexed_files

    def flush(self) -> None:
        names = {collection.name for collection in self.client.list_collections()}
        if COLLECTION_NAME in names:
            self.client.delete_collection(COLLECTION_NAME)
        logger.info("Flushed RAG index")

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        result = self._collection().query(query_texts=[query_text], n_results=n_results)
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        return [
            {
                "file": (metadata or {}).get("file", ""),
                "chunk": (metadata or {}).get("chunk", 0),
                "text": document,
                "score": distance,
            }
            for document, metadata, distance in zip(documents[0], metadatas[0], distances[0])
        ]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        sentences: list[str] = []
        for part in SENTENCE_BREAK_RE.split(text):
            part = part.strip()
            if not part:
                continue
            if len(part) <= MAX_SENTENCE_CHARS:
                sentences.append(part)
                continue
            sentences.extend(
                part[start : start + MAX_CHUNK_CHARS].strip()
                for start in range(0, len(part), MAX_CHUNK_CHARS)
                if part[start : start + MAX_CHUNK_CHARS].strip()
            )
        return sentences

    def _sentence_embedding_function(self) -> object:
        if self.embedding_function is not None:
            return self.embedding_function
        return DefaultEmbeddingFunction()

    def _chunks(self, text: str) -> list[str]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []
        try:
            embeddings = []
            embedding_function = self._sentence_embedding_function()
            for start in range(0, len(sentences), EMBED_BATCH_SIZE):
                embeddings.extend(embedding_function(sentences[start : start + EMBED_BATCH_SIZE]))
            similarities = self._adjacent_similarities(embeddings)
        except Exception:
            logger.warning("Semantic embedding failed; falling back to structural chunking")
            return self._fallback_chunks(sentences)
        threshold = float(np.percentile(similarities, BREAKPOINT_PERCENTILE)) if len(similarities) else 1.0
        return self._group_chunks(sentences, similarities, threshold)

    @staticmethod
    def _adjacent_similarities(embeddings: list) -> np.ndarray:
        vectors = np.asarray(embeddings, dtype=np.float32)
        if len(vectors) < 2:
            return np.zeros(0, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.maximum(norms, 1e-9)
        return np.sum(vectors[:-1] * vectors[1:], axis=1)

    @staticmethod
    def _group_chunks(
        sentences: list[str],
        similarities: np.ndarray,
        threshold: float,
        min_chunk_chars: int = MIN_CHUNK_CHARS,
        max_chunk_chars: int = MAX_CHUNK_CHARS,
    ) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        size = 0
        for index, sentence in enumerate(sentences):
            break_chunk = False
            if index > 0:
                length_limit = size >= max_chunk_chars
                semantic_break = similarities[index - 1] < threshold
                if (semantic_break or length_limit) and size >= min_chunk_chars:
                    break_chunk = True
            if break_chunk:
                chunks.append(" ".join(current).strip())
                current = []
                size = 0
            current.append(sentence)
            size += len(sentence) + 1
        if current:
            chunks.append(" ".join(current).strip())
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _fallback_chunks(sentences: list[str]) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        size = 0
        for sentence in sentences:
            is_heading = sentence.lstrip().startswith("#")
            if current and (size >= MAX_CHUNK_CHARS or is_heading):
                chunks.append(" ".join(current).strip())
                current = []
                size = 0
            current.append(sentence)
            size += len(sentence) + 1
        if current:
            chunks.append(" ".join(current).strip())
        return [chunk for chunk in chunks if chunk]


rag_index = Indexer(determine_root_dir())