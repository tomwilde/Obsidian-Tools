import hashlib
import logging
import threading
from pathlib import Path

import chromadb

from config import determine_root_dir

logger = logging.getLogger(__name__)

COLLECTION_NAME = "obsidian"
INDEX_DIR = Path(__file__).resolve().parents[1] / ".chroma"


class Indexer:
    def __init__(self, rootdir: Path, index_dir: Path = INDEX_DIR) -> None:
        self.rootdir = rootdir
        self.index_dir = index_dir
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
        return self.client.get_or_create_collection(COLLECTION_NAME)

    def _documents(self) -> list[tuple[str, str]]:
        documents: list[tuple[str, str]] = []
        for path in sorted(self.rootdir.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                logger.warning("Skipping unreadable file: %s", path)
                continue
            if text.strip():
                documents.append((path.relative_to(self.rootdir).as_posix(), text))
        return documents

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _indexed_files(self, collection: chromadb.Collection) -> dict[str, str]:
        indexed: dict[str, str] = {}
        result = collection.get(include=["metadatas"])
        for doc_id, metadata in zip(result.get("ids") or [], result.get("metadatas") or []):
            if metadata and metadata.get("sha"):
                indexed[doc_id] = metadata["sha"]
        return indexed

    def build(self) -> int:
        collection = self._collection()
        indexed = self._indexed_files(collection)
        documents = self._documents()
        current = {doc_id for doc_id, _ in documents}

        removed = sorted(indexed.keys() - current)
        if removed:
            collection.delete(ids=removed)

        updated: list[tuple[str, str, str]] = []
        for doc_id, text in documents:
            sha = self._sha(text)
            if indexed.get(doc_id) == sha:
                continue
            updated.append((doc_id, text, sha))

        if updated:
            collection.upsert(
                ids=[doc_id for doc_id, _, _ in updated],
                documents=[text for _, text, _ in updated],
                metadatas=[{"file": doc_id, "sha": sha} for doc_id, _, sha in updated],
            )
        self._ready.set()
        logger.info(
            "Indexed %d document(s) from %s (%d unchanged)",
            len(updated),
            self.rootdir,
            len(documents) - len(updated),
        )
        return len(updated)

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
            {"file": (metadata or {}).get("file", ""), "text": document, "score": distance}
            for document, metadata, distance in zip(documents[0], metadatas[0], distances[0])
        ]


rag_index = Indexer(determine_root_dir())