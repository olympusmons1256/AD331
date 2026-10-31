"""Corpus coverage and preservation of the existing evaluation references."""

import json
from pathlib import Path

from src.chunking import StructureAwareChunker, load_markdown_corpus
from src.search import SearchWorkbench


ROOT = Path(__file__).resolve().parents[1]


def test_corpus_is_loaded_and_indexed_by_all_strategies() -> None:
    documents = load_markdown_corpus(ROOT / "corpus")
    assert len(documents) >= 20
    assert len({doc.doc_id for doc in documents}) == len(documents)
    pages = [doc for doc in documents if doc.doc_id != "api_spec_sample"]
    assert len(pages) >= 20
    assert all(len(doc.text.split()) >= 300 for doc in pages)

    workbench = SearchWorkbench(ROOT / "corpus")
    expected = {doc.doc_id for doc in documents}
    for index in (workbench.bm25, *workbench.dense_indices.values()):
        assert {chunk.parent_doc for chunk in index._chunks} == expected


def test_existing_labels_resolve_in_structure_aware_corpus() -> None:
    documents = load_markdown_corpus(ROOT / "corpus")
    chunks = StructureAwareChunker().chunk_documents(documents)
    keys = {chunk.metadata["section_key"] for chunk in chunks}
    queries = json.loads((ROOT / "data" / "eval_queries.json").read_text(encoding="utf-8"))
    assert len(queries) >= 15
    for query in queries:
        assert query["relevant_section_keys"]
        assert set(query["relevant_section_keys"]) <= keys
