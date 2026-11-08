from types import SimpleNamespace

import pytest

from src.rewriter import OpenAIQueryRewriter
from src.reranker import CrossEncoderReranker, sigmoid
from conftest import document


class Completion:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))])


def client(completion):
    return SimpleNamespace(chat=SimpleNamespace(completions=completion))


def test_rewrite_preserves_identifiers_and_passes_timeout():
    query = 'What does /v1/jobs do for "Tenant A" with X-Trace-ID?'
    completion = Completion(query + " Context: Crane scheduling.")
    result = OpenAIQueryRewriter(client=client(completion), timeout=1.25).rewrite(query)
    assert result.query == completion.text
    assert not result.used_fallback
    assert completion.calls[0]["timeout"] == 1.25
    assert completion.calls[0]["messages"][1]["content"] == query


@pytest.mark.parametrize("rewrite", [
    'What does /v1/job do for "Tenant A" with X-Trace-ID?',
    'What does /v1/jobs do for "Tenant B" with X-Trace-ID?',
    'What does /v1/jobs do for "Tenant A" with x-trace-id?',
    'What does /v1/jobs do for "A Tenant" with X-Trace-ID?',
    "  ", None,
])
def test_rewrite_rejects_lost_identifiers_phrases_and_blank_output(rewrite):
    query = 'What does /v1/jobs do for "Tenant A" with X-Trace-ID?'
    result = OpenAIQueryRewriter(client=client(Completion(rewrite))).rewrite(query)
    assert result.query == query
    assert result.used_fallback
    assert result.reason


def test_rewrite_timeout_falls_back_without_claiming_deadline_enforcement():
    completion = Completion(error=TimeoutError("provider timed out"))
    result = OpenAIQueryRewriter(client=client(completion), timeout=2).rewrite("What is it?")
    assert result.query == "What is it?"
    assert result.used_fallback and "TimeoutError" in result.reason
    assert completion.calls[0]["timeout"] == 2


def test_rewrite_rejects_dropped_repeated_identifier():
    query = "Compare tenant-7 to tenant-7"
    completion = Completion("Compare tenant-7 to")
    result = OpenAIQueryRewriter(client=client(completion)).rewrite(query)
    assert result.used_fallback and result.query == query


@pytest.mark.parametrize("query", ["", " \n", None])
def test_rewrite_rejects_blank_input_before_calling_provider(query):
    completion = Completion("irrelevant")
    with pytest.raises(ValueError):
        OpenAIQueryRewriter(client=client(completion)).rewrite(query)
    assert not completion.calls


@pytest.mark.parametrize(("logit", "expected"), [(-1000, 0.0), (0, 0.5), (1000, 1.0)])
def test_sigmoid_extreme_finite_logits(logit, expected):
    assert sigmoid(logit) == pytest.approx(expected)


@pytest.mark.parametrize("logit", [float("nan"), float("inf"), -float("inf")])
def test_sigmoid_rejects_nonfinite_logits(logit):
    with pytest.raises(ValueError):
        sigmoid(logit)


def test_reranker_uses_raw_logits_and_returns_sorted_copies():
    class Model:
        def predict(self, pairs, activation_fn):
            assert pairs == [("query", "A local excerpt."), ("query", "second")]
            assert activation_fn(2.0) == 2.0
            return [-2.0, 2.0]

    docs = [document(), document(id="b", content="second")]
    ranked = CrossEncoderReranker(model=Model()).rerank("query", docs, top_k=2)
    assert [doc.id for doc in ranked] == ["b", "local-1"]
    assert [doc.rerank_score for doc in ranked] == pytest.approx([sigmoid(2), sigmoid(-2)])
    assert all(doc.rerank_score is None for doc in docs)


def test_reranker_rejects_wrong_number_of_logits():
    class Model:
        def predict(self, pairs, activation_fn):
            return [0, 1]

    with pytest.raises(ValueError, match="number of logits"):
        CrossEncoderReranker(model=Model()).rerank("query", [document()])