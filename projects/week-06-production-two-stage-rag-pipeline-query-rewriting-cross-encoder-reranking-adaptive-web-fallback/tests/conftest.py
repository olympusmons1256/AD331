"""Offline test doubles; no model or provider is initialized by these tests."""

from dataclasses import replace
import socket

import pytest

from src.schemas import Document


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket.socket, "sendto", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def document(id="local-1", content="A local excerpt.", source="one.md", score=None,
             source_type="local"):
    return Document(id=id, content=content, source=source, source_type=source_type,
                    rerank_score=score)


class Search:
    def __init__(self, documents=(), error=None):
        self.documents = list(documents)
        self.error = error
        self.calls = []

    def search(self, query, k):
        self.calls.append((query, k))
        if self.error:
            raise self.error
        return list(self.documents)


class Reranker:
    def __init__(self, scores=None, error=None):
        self.scores = scores or {}
        self.error = error
        self.calls = []

    def rerank(self, query, documents, top_k):
        self.calls.append((query, list(documents), top_k))
        if self.error:
            raise self.error
        ranked = [replace(doc, rerank_score=self.scores.get(doc.id, 0.9)) for doc in documents]
        return sorted(ranked, key=lambda doc: doc.rerank_score, reverse=True)[:top_k]


def stages(result):
    return {stage.name: stage for stage in result.telemetry}