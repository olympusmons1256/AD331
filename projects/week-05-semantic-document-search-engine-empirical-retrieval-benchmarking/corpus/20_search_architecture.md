# Search Architecture and Evaluation

Meridian is a fictional documentation platform. Its search pipeline and example parameters are illustrative, not the interface of a real search vendor.

## Ingestion and representation

When a document revision commits, an asynchronous indexing job extracts text, preserves the workspace and document identifiers, and divides content into overlapping passages. A chunk should retain its heading path and source offsets so results can link back to the original material. For example, a target of 400 tokens with 60 tokens of overlap can preserve context across boundaries, but the tokenizer, document structure, and embedding model determine the best values.

Attach the revision number and access-control metadata to each indexed passage. Apply updates monotonically so a delayed job for an older revision cannot overwrite a newer one. Deletions and permission changes must propagate too; deleting only the document body while retaining searchable snippets can leak information.

## Retrieval and ranking

Lexical retrieval is effective for exact identifiers, error codes, and unusual terms. Vector retrieval can find conceptually related passages with different wording. A hybrid pipeline retrieves candidates from both sources, combines ranks, and optionally reranks a bounded candidate set. Raw scores from different methods are not necessarily comparable; rank-based fusion or a calibrated model avoids assuming they share a scale.

```text
query -> lexical candidates + vector candidates
      -> permission filter -> rank fusion -> top results
```

This diagram is conceptual. Apply authorization within each retrieval path or otherwise ensure unauthorized content cannot influence exposed results, snippets, or counts. Filtering only after a small global top-k can also suppress relevant authorized results; retrieval must account for the user's accessible corpus.

## Evaluation protocol

Maintain a versioned set of queries with independently judged relevant documents or passages. Include exact API terms, paraphrases, ambiguous queries, and permission-restricted cases. Measure recall at a fixed candidate depth, ranking quality such as reciprocal rank, and latency percentiles. Define whether relevance is judged at document or chunk level; multiple chunks from one document can otherwise distort results.

Compare systems on the same corpus snapshot, access rules, and query set. Record chunking settings, embedding model version, index build identifier, and random seeds where applicable. A small benchmark can show regressions but does not establish production relevance for every workspace.

## Freshness and failure

Monitor indexing lag from committed revision to searchable revision, failed jobs, retrieval errors, and empty-result rates. If vector generation is unavailable, lexical search may provide a documented degraded mode; do not silently claim equivalent relevance. Test reindexing after model changes, stale permission metadata, duplicate jobs, and rollback to a compatible index. Keep authoritative documents outside the search index so it can be rebuilt.