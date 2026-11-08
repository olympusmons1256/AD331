import pytest

from src.retriever import ChromaRetriever


class Embedder:
    model_name = "offline-fixed"

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[1.0, float(len(text) + 1)] for text in texts]


class Collection:
    def __init__(self):
        self.rows = {}
        self.upserts = []
        self.deletes = []
        self.fail_upsert = False

    def get(self, include):
        assert include == ["metadatas"]
        return {"ids": list(self.rows), "metadatas": [row[1] for row in self.rows.values()]}

    def upsert(self, ids, documents, metadatas, embeddings):
        if self.fail_upsert:
            raise RuntimeError("upsert failed")
        self.upserts.append(list(ids))
        for id, text, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            self.rows[id] = (text, metadata, embedding)

    def delete(self, ids):
        self.deletes.append(list(ids))
        for id in ids:
            del self.rows[id]


def test_sync_idempotent_updates_changed_chunks_and_removes_stale(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    first, second = corpus / "one.md", corpus / "two.txt"
    first.write_text("abcdefghijklmno", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    (corpus / "ignored.json").write_text("ignored", encoding="utf-8")
    embedder, collection = Embedder(), Collection()
    retriever = ChromaRetriever(corpus, tmp_path / "db", embedder=embedder,
                                collection=collection, chunk_size=10, chunk_overlap=0)
    assert retriever.sync() == {"total": 3, "upserted": 3, "deleted": 0}
    old_ids = set(collection.rows)
    old_calls = list(embedder.calls)
    assert retriever.sync() == {"total": 3, "upserted": 0, "deleted": 0}
    assert embedder.calls == old_calls
    first.write_text("changed", encoding="utf-8")
    second.unlink()
    assert retriever.sync() == {"total": 1, "upserted": 1, "deleted": 2}
    assert len(collection.rows) == 1 and set(collection.rows) < old_ids
    assert next(iter(collection.rows.values()))[0] == "changed"
    assert retriever.sync() == {"total": 1, "upserted": 0, "deleted": 0}


def test_sync_does_not_delete_stale_records_when_upsert_fails(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    path = corpus / "old.md"
    path.write_text("old", encoding="utf-8")
    collection = Collection()
    retriever = ChromaRetriever(corpus, tmp_path / "db", embedder=Embedder(), collection=collection)
    retriever.sync()
    original = dict(collection.rows)
    path.unlink()
    (corpus / "new.md").write_text("new", encoding="utf-8")
    collection.fail_upsert = True
    with pytest.raises(RuntimeError, match="upsert failed"):
        retriever.sync()
    assert collection.rows == original
    assert not collection.deletes


def test_real_chroma_sync_offline_with_injected_embedder(tmp_path, monkeypatch):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    path = corpus / "one.md"
    path.write_text("first", encoding="utf-8")
    retriever = ChromaRetriever(corpus, tmp_path / "chroma", embedder=Embedder())
    assert retriever.sync() == {"total": 1, "upserted": 1, "deleted": 0}
    assert retriever.sync() == {"total": 1, "upserted": 0, "deleted": 0}
    found = retriever.search("query", k=3)
    assert len(found) == 1 and found[0].source == "one.md" and found[0].content == "first"
    path.unlink()
    assert retriever.sync() == {"total": 0, "upserted": 0, "deleted": 1}
    assert retriever.search("query") == []
    assert retriever.sync() == {"total": 0, "upserted": 0, "deleted": 0}


def test_corpus_fingerprint_rejects_reuse_with_different_chunk_settings(tmp_path, monkeypatch):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "one.md").write_text("text", encoding="utf-8")
    db = tmp_path / "chroma"
    ChromaRetriever(corpus, db, embedder=Embedder()).sync()
    other = ChromaRetriever(corpus, db, embedder=Embedder(), chunk_size=30, chunk_overlap=2)
    with pytest.raises(ValueError, match="configuration differs"):
        other.sync()