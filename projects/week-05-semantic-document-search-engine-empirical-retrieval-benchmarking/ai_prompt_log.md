# AI Prompt Log - Week 05

## Baseline Prompt Used

```text
You are a Staff Information Retrieval and Search Engineer. I need a modular Python 3.11+ semantic search and evaluation pipeline that indexes technical Markdown documentation, evaluates multiple chunking strategies, and benchmarks dense vector retrieval against BM25 keyword search.
```

## Initial AI Draft Audit Findings

### 1) Ground-truth leakage by positional chunk indices
- **Issue:** Baseline prototype mapped labels to chunk array offsets (e.g., `chunk_17`) that changed when chunk size changed.
- **Risk:** Invalid benchmark comparison across chunking strategies.
- **Fix:** `data/eval_queries.json` now labels relevance using stable semantic `relevant_section_keys` instead of strategy-dependent index offsets.

### 2) Distance/similarity inversion in dense search
- **Issue:** Baseline treated Chroma cosine distance as a direct score where lower was ranked lower relevance.
- **Risk:** Relevance order inverted.
- **Fix:** Converted with `score = 1.0 - distance` before ranking in dense retrieval.

### 3) BM25 tokenization asymmetry
- **Issue:** Documents were lowercased and stripped of punctuation, but queries were not normalized.
- **Risk:** False negatives on exact technical identifiers.
- **Fix:** Shared tokenizer used for corpus and query path in `BM25Indexer._tokenize()`.

### 4) Structure-aware code fence corruption
- **Issue:** Naive header splitting could break fenced blocks at header-like strings inside code.
- **Risk:** Corrupted code snippets and poor retrieval coherence.
- **Fix:** `StructureAwareChunker` tracks fence state and avoids header splitting inside fenced code blocks.

### 5) MRR outside top-K counting bug
- **Issue:** Baseline awarded reciprocal score when first relevant result occurred outside `K`.
- **Risk:** Inflated ranking quality.
- **Fix:** `mrr_at_k()` now scans only `results[:k]` and returns `0.0` when missed.

## Refactor Notes
- Added dense configs: `dense_256`, `dense_1024`, `dense_structure`.
- Added latency tracking with p50/p95.
- Added deterministic `HashingEmbedder` fallback for offline and test stability.
