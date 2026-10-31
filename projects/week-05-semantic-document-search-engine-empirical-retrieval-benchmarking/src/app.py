"""Streamlit dashboard for search comparison and benchmarking."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
# Streamlit executes this file as a script and puts src/, not its parent, on sys.path.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.benchmarker import RetrievalBenchmarker
from src.search import SearchWorkbench

CORPUS_DIR = BASE_DIR / "corpus"
EVAL_PATH = BASE_DIR / "data" / "eval_queries.json"


@st.cache_resource(show_spinner=False)
def get_workbench() -> SearchWorkbench:
    return SearchWorkbench(corpus_dir=CORPUS_DIR)


@st.cache_data(show_spinner=False)
def run_benchmark(k: int) -> pd.DataFrame:
    workbench = get_workbench()
    benchmarker = RetrievalBenchmarker.from_json(workbench, EVAL_PATH)
    return benchmarker.run_as_dataframe(k=k)


def _render_result_column(title: str, payload: dict[str, object]) -> None:
    st.subheader(title)
    st.caption(f"Latency: {payload['latency_ms']:.2f} ms")

    results = payload["results"]
    if not results:
        st.info("No results")
        return

    for rank, result in enumerate(results, start=1):
        section_key = result.metadata.get("section_key", "n/a")
        st.markdown(f"**#{rank} · score={result.score:.4f} · section={section_key}**")
        st.write(result.content[:450] + ("..." if len(result.content) > 450 else ""))


def _failure_analysis_frame(workbench: SearchWorkbench, k: int) -> pd.DataFrame:
    benchmarker = RetrievalBenchmarker.from_json(workbench, EVAL_PATH)
    rows: list[dict[str, object]] = []

    for query in benchmarker.eval_queries:
        bm25, _ = workbench.search_bm25(query.query, k=k)
        dense, _ = workbench.search_dense(query.query, config="dense_structure", k=k)

        bm25_hit = any(r.metadata.get("section_key") in query.relevant_section_keys for r in bm25)
        dense_hit = any(r.metadata.get("section_key") in query.relevant_section_keys for r in dense)

        if bm25_hit == dense_hit:
            continue

        winner = "BM25" if bm25_hit else "Dense"
        reason = (
            "Exact technical identifier favored lexical matching"
            if winner == "BM25"
            else "Paraphrased conceptual language favored semantic matching"
        )

        rows.append(
            {
                "query_id": query.query_id,
                "query": query.query,
                "winner": winner,
                "reason": reason,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="Semantic Search Workbench", layout="wide")
    st.title("Semantic Document Search Engine & Empirical Retrieval Benchmarking")

    workbench = get_workbench()

    st.sidebar.header("Search Controls")
    k = st.sidebar.slider("Top-K", min_value=1, max_value=10, value=5)
    dense_config = st.sidebar.selectbox(
        "Dense configuration",
        options=["dense_256", "dense_1024", "dense_structure"],
        index=2,
    )

    tab_live, tab_benchmark = st.tabs(["Live Search Comparator", "Benchmark Dashboard"])

    with tab_live:
        query = st.text_input("Enter a technical query", value="default maxUnavailable rolling update")
        if st.button("Run Search"):
            comparison = workbench.compare(query=query, k=k, dense_config=dense_config)
            left, right = st.columns(2)
            with left:
                _render_result_column("BM25 Keyword Search", comparison["bm25"])
            with right:
                _render_result_column(f"Dense Search ({dense_config})", comparison["dense"])

    with tab_benchmark:
        if st.button("Run Benchmark"):
            frame = run_benchmark(k)
            st.dataframe(frame, use_container_width=True)

            chart = frame.set_index("strategy")[["hit_rate_at_k", "mrr_at_k"]]
            st.bar_chart(chart)

            latency_chart = frame.set_index("strategy")[["latency_p50_ms", "latency_p95_ms"]]
            st.line_chart(latency_chart)

            st.subheader("Failure Analysis")
            failure_df = _failure_analysis_frame(workbench, k)
            if failure_df.empty:
                st.success("No differential failures found between BM25 and dense retrieval.")
            else:
                st.dataframe(failure_df, use_container_width=True)


if __name__ == "__main__":
    main()
