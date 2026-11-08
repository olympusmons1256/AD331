"""Streamlit workbench for the existing RAG components."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import RLock

import streamlit as st
from dotenv import load_dotenv

# Streamlit may put src/, rather than the project root, on sys.path.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.pipeline import RAGPipeline
from src.generator import OpenAIGenerator
from src.reranker import CrossEncoderReranker
from src.retriever import ChromaRetriever, SentenceTransformerEmbedder
from src.rewriter import OpenAIQueryRewriter
from src.schemas import RewriteResult
from src.web_fallback import WebSearch, valid_web_url


class ConversationRewriter:
    """Append previous user questions, then optionally expand via the core rewriter."""

    def __init__(self, history: list[str], llm: OpenAIQueryRewriter | None = None):
        self.history, self.llm = history, llm

    def rewrite(self, query: str) -> RewriteResult:
        # Keep the new question verbatim; past answers are not treated as evidence.
        contextual = query
        if self.history:
            contextual += "\nPrevious user questions for context: " + " | ".join(self.history[-3:])
        if self.llm is None:
            return RewriteResult(query, contextual)
        result = self.llm.rewrite(contextual)
        return RewriteResult(query, result.query, result.used_fallback, result.reason)


class RecordingSearch:
    def __init__(self, delegate, label: str, trace: dict):
        self.delegate, self.label, self.trace = delegate, label, trace

    def search(self, query: str, k: int):
        documents = self.delegate.search(query, k=k)
        self.trace[self.label] = {"candidates": [d.to_dict() for d in documents], "reranked": []}
        return documents


class RecordingReranker:
    def __init__(self, delegate, trace: dict):
        self.delegate, self.trace = delegate, trace

    def rerank(self, query: str, documents: list, top_k: int):
        # Capture the full ordering before the pipeline applies top_k and threshold.
        ranked = self.delegate.rerank(query, documents, top_k=len(documents))
        label = "web" if documents[0].source_type == "web" else "local"
        self.trace[label]["reranked"] = [d.to_dict() for d in ranked]
        return ranked[:top_k]


@st.cache_resource(show_spinner=False)
def resources():
    embedder = SentenceTransformerEmbedder(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    retriever = ChromaRetriever(
        ROOT / "docs", os.getenv("CHROMA_DIR", str(ROOT / ".chroma")), embedder=embedder
    )
    reranker = CrossEncoderReranker(os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
    # Models and collection are shared across Streamlit sessions; serialize access.
    return retriever, reranker, RLock()


def run_question(query: str, history: list[str], settings: dict) -> dict:
    retriever, reranker, lock = resources()
    trace = {}
    with lock:
        sync = retriever.sync()
        web = None
        if settings["web"] != "disabled":
            web = RecordingSearch(WebSearch(provider=settings["web"]), "web", trace)
        rewriter = ConversationRewriter(
            history if settings["context"] else [],
            OpenAIQueryRewriter(model=settings["model"]) if settings["rewrite"] else None,
        )
        pipeline = RAGPipeline(
            retriever=RecordingSearch(retriever, "local", trace),
            reranker=RecordingReranker(reranker, trace),
            rewriter=rewriter,
            web_search=web,
            generator=OpenAIGenerator(model=settings["model"]) if settings.get("synthesize") else None,
            stage1_k=settings["stage1_k"], top_k=settings["top_k"],
            threshold=settings["threshold"], web_k=settings["stage1_k"],
        )
        result = pipeline.run(query)
    return {"result": result.to_dict(), "trace": trace, "sync": sync, "settings": settings.copy()}


def show_trace(trace: dict, settings: dict):
    for label, data in trace.items():
        st.markdown(f"**{label.title()} candidates**")
        ranks = {d["id"]: (rank, d) for rank, d in enumerate(data["reranked"], 1)}
        rows = []
        for rank, doc in enumerate(data["candidates"], 1):
            rerank_rank, reranked = ranks.get(doc["id"], (None, None))
            score = reranked["rerank_score"] if reranked else None
            rows.append({
                "First-stage rank": rank,
                "Source": doc["source"],
                "Chunk / ID": doc["id"],
                "Retrieval score": doc["retrieval_score"],
                "Rerank rank": rerank_rank,
                "Shift (up +)": rank - rerank_rank if rerank_rank is not None else None,
                "Rerank score": score,
                "Selected": bool(rerank_rank is not None and rerank_rank <= settings["top_k"]
                                 and score is not None and score >= settings["threshold"]),
            })
        if rows:
            st.dataframe(rows, hide_index=True)
        else:
            st.caption("No candidates returned.")
        if label == "web":
            st.caption("Web order is provider order; the adapter does not supply retrieval scores.")


def show_turn(turn: dict, turn_index: int):
    result, settings = turn["result"], turn["settings"]
    with st.chat_message("user"):
        st.text(result["query"])
    with st.chat_message("assistant"):
        local_ranked = turn["trace"].get("local", {}).get("reranked", [])
        top_score = local_ranked[0]["rerank_score"] if local_ranked else None
        route = "WEB_FALLBACK attempted" if result["used_web"] else (
            "INTERNAL_RAG" if result["sources"] and not result["abstained"] else "NO ROUTE / ABSTAINED"
        )
        st.caption(f"Route: {route} · Local top score: {top_score:.3f} · Threshold: {settings['threshold']:.2f}"
                   if top_score is not None else f"Route: {route} · Local top score unavailable · Threshold: {settings['threshold']:.2f}")
        if result["abstained"]:
            st.warning("Abstained: " + (result["reason"] or "Insufficient evidence"))
        for stage in result["telemetry"]:
            if stage["name"] == "web_search" and stage["status"] == "error":
                st.warning("Web search failed: " + stage["detail"])
        st.text(result["answer"])
        st.caption("Web fallback attempted: " + ("yes" if result["used_web"] else "no"))
        if result["sources"]:
            st.markdown("**Sources**")
            for index, doc in enumerate(result["sources"], 1):
                st.text(f"[{index}] {doc['title'] or doc['source']} — {doc['source']} ({doc['source_type']}; chunk {doc['id']})")
                if doc["source_type"] == "web" and valid_web_url(doc["source"]):
                    st.link_button(f"Open web source [{index}] · turn {turn_index + 1}", doc["source"])
                with st.expander(f"Evidence [{index}]"):
                    st.text(doc["content"])
        with st.expander("Rewrite, ranks, and stage telemetry"):
            st.markdown("**Query used for retrieval and reranking**")
            st.text(result["rewritten_query"])
            st.caption("Threshold: " + str(settings["threshold"]) + "; index sync: " + str(turn["sync"]))
            st.dataframe(result["telemetry"], hide_index=True)
            for stage in result["telemetry"]:
                if stage["status"] in {"error", "fallback"}:
                    st.warning(f"{stage['name']} ({stage['status']}): {stage['detail']}")
            show_trace(turn["trace"], settings)


def main():
    st.set_page_config(page_title="Infrastructure RAG lab", page_icon="🔎", layout="wide")
    st.title("Infrastructure RAG lab")
    st.caption("Explore fictional infrastructure documentation with two-stage retrieval and optional live web fallback.")
    st.info("Rerank scores are sigmoid-transformed model logits, not calibrated confidence or probabilities. "
            "The threshold is a heuristic; a citation marker does not verify correctness or entailment.")
    with st.sidebar:
        st.header("Retrieval settings")
        stage1_k = st.slider("First-stage candidates", 1, 50, 20)
        top_k = st.slider("Maximum cited sources", 1, 10, 5)
        threshold = st.slider("Rerank threshold (uncalibrated)", 0.0, 1.0, 0.55, 0.01)
        web = st.selectbox("Web fallback", ["duckduckgo", "disabled", "tavily"])
        context = st.checkbox("Include last 3 user questions as context", value=True)
        rewrite = st.checkbox("Expand query with OpenAI", value=False)
        synthesize = st.checkbox("Synthesize answer with OpenAI", value=False)
        model = st.text_input("OpenAI model", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        st.caption("DuckDuckGo uses live network access without an API key; Tavily and OpenAI require keys. "
               "Prior questions may be sent to selected providers; synthesis sends source text to OpenAI.")
        if st.button("Clear conversation"):
            st.session_state.turns = []
    settings = {"stage1_k": stage1_k, "top_k": top_k, "threshold": threshold, "web": web,
                "context": context, "rewrite": rewrite, "synthesize": synthesize, "model": model}
    if "turns" not in st.session_state:
        st.session_state.turns = []
    for turn_index, turn in enumerate(st.session_state.turns):
        show_turn(turn, turn_index)
    query = st.chat_input("Ask about the fictional infrastructure")
    if query:
        history = [turn["result"]["query"] for turn in st.session_state.turns]
        try:
            with st.spinner("Syncing documents and running retrieval…"):
                turn = run_question(query, history, settings)
            st.session_state.turns.append(turn)
            show_turn(turn, len(st.session_state.turns) - 1)
        except Exception as exc:
            st.error(f"Could not initialize or sync the local index: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()