# AI assistance audit

## Current request (concise)

Inspect the existing Week 6 core, then add a UI, container/configuration files, project metadata, a substantive fictional infrastructure corpus, documentation, an honest AI audit, and the projects index entry. Do not modify the core modules or tests. Integrate the actual API, show rewriting, retrieval/rerank traces, citations, web errors and abstentions, use real models and a suitable default web provider, and avoid unsupported claims about confidence, deployment, video, or results.

## Observed design and implementation tradeoffs

These are observations from reading the supplied core, not claims about an earlier failed draft or test run:

- `RAGPipeline.run` accepts only a query and returns threshold-passing sources, not all intermediate candidate lists. The UI adds a conversation rewriter and recording adapters instead of changing the core. Recording a full reranked ordering scores the same input documents and then returns the requested top K; it does not fabricate lower ranks. It has a memory/display cost.
- The core rewriter guard requires **all** whitespace-delimited original tokens, including punctuation, to be preserved. This protects identifiers but prevents many normal rewrites. The UI appends the previous three user questions as context, not a true standalone-question rewrite, and optionally delegates expansion to the existing OpenAI component. Previous answers are excluded, but unrelated prior questions can still harm retrieval or be transmitted externally.
- The reranker transforms logits with sigmoid, but those values are not calibrated probabilities. The pipeline applies a fixed threshold without any labeled calibration; the UI exposes it as a heuristic, not confidence. A relevant document can be rejected, and an irrelevant one accepted.
- The core accepts or rejects citations structurally. It does not establish entailment or truth. The UI keeps the default extractive generator and displays evidence text; even literal excerpts may be irrelevant or misleading.
- The pipeline handles individual stage exceptions, but index `sync()` is outside `run()`. The UI reports synchronization failure before running the pipeline, so it does not try web on a sync failure. Inside the pipeline, retrieval or rerank errors can trigger web fallback. Web search may fail, and `used_web` records an attempt rather than a successful search.
- Chroma synchronization deletes records not present in the current corpus, and its fingerprint includes the absolute corpus path and model settings. The UI uses a dedicated collection, documents rebuild behavior, and serializes access in one process. It does not provide multi-process locking or a safe shared multi-tenant deployment.
- DDGS avoids a key but remains a live third-party dependency with availability, rate-limit, privacy, and snippet-trust concerns. OpenAI and Tavily are opt-in and require keys. Real model files require downloads unless already cached. No test double is presented as a live result.

## Validation performed

- Built a wheel without installing dependencies, and resolved the declared dependencies with a Python 3.11 pip dry run on macOS; neither verifies a full clean installation.
- Ran a Streamlit initial render and a two-turn interaction with injected embedding/rerank methods. A separate injected-model check used real Chroma and exercised rank capture, citations, web error telemetry, and abstention. Inspection of the minimum Streamlit release also showed that its link buttons do not accept explicit keys, so per-turn labels are used to distinguish repeated citations.
- Downloaded and ran the real default embedding and cross-encoder models against the fictional corpus and a temporary Chroma index, with web disabled and the threshold set to zero for the smoke check. A Streamlit query was also exercised offline using the cached models. These were functionality checks, not evaluations of relevance or threshold quality. The existing workspace interpreter was Python 3.14 with newer installed packages, outside the project's declared Python 3.11–3.13 range; the declared dependency set was not installed or exercised in those runs.
- Compose configuration validation passed, but the Docker daemon was unavailable, so no image build or container startup was verified. No live web provider, hosted model, video, benchmark, or deployment was tested.

The fictional corpus and documentation were created for this project. These observations do not imply an earlier failed draft or before-and-after performance comparison.

## Follow-up audit and regression test

An offline regression test exposed an actual preservation flaw in the initial rewrite guard: using a set of whitespace tokens accepted a rewrite that dropped one occurrence of a repeated identifier. The guard now compares token counts using `Counter`, and the test checks that such a rewrite falls back to the original. This conservative guard still does not guarantee semantic preservation or successful pronoun resolution.

The offline suite now includes 53 passing tests in the existing Python 3.14 environment, which remains outside the declared supported range. This does not replace a clean Python 3.11 container build, live web verification, calibration, or human review.