from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from src.app import ConversationRewriter
from src.reranker import CrossEncoderReranker
from src.retriever import ChromaRetriever
from src.schemas import RewriteResult
from conftest import document


def test_conversation_context_contains_last_three_questions_not_answers():
    rewriter = ConversationRewriter(["old", "About Crane?", "How does it retry?", "Which queue?"])
    result = rewriter.rewrite("Does it expire?")
    assert result.original == "Does it expire?"
    assert result.query == ("Does it expire?\nPrevious user questions for context: "
                            "About Crane? | How does it retry? | Which queue?")
    assert "old" not in result.query
    # Context is concatenated, not a claim that pronouns are resolved.


def test_conversation_rewriter_preserves_delegated_fallback():
    class Delegate:
        def rewrite(self, query):
            assert "What is Crane?" in query and "Does it retry?" in query
            return RewriteResult(query, query, True, "timeout")

    result = ConversationRewriter(["What is Crane?"], Delegate()).rewrite("Does it retry?")
    assert result.original == "Does it retry?" and result.used_fallback and result.reason == "timeout"


def test_streamlit_two_turns_with_injected_local_components(monkeypatch):
    calls = []

    def sync(self):
        return {"total": 1, "upserted": 0, "deleted": 0}

    def search(self, query, k):
        calls.append(query)
        return [document(content="Fixture evidence.")]

    def rerank(self, query, documents, top_k):
        return [replace(doc, rerank_score=0.9) for doc in documents][:top_k]

    monkeypatch.setattr(ChromaRetriever, "sync", sync)
    monkeypatch.setattr(ChromaRetriever, "search", search)
    monkeypatch.setattr(CrossEncoderReranker, "rerank", rerank)
    app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    app.selectbox[0].set_value("disabled").run()
    app.chat_input[0].set_value("What is Crane?").run()
    assert not app.exception and calls == ["What is Crane?"]
    assert any("Fixture evidence." in item.value for item in app.text)
    app.chat_input[0].set_value("Does it retry?").run()
    assert not app.exception
    assert calls == ["What is Crane?", "Does it retry?\nPrevious user questions for context: What is Crane?"]
    assert len(app.session_state["turns"]) == 2
    assert all(not turn["result"]["used_web"] for turn in app.session_state["turns"])
    app.button[0].click().run()
    assert not app.exception and app.session_state["turns"] == []