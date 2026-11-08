# Week 06: Two-stage infrastructure RAG lab

A Streamlit workbench around the existing RAG components. The eight original pages in `docs/` describe **fictional** Lattice Harbor services; they are illustrative, not operational instructions or claims about a real deployment. No benchmark, production deployment, or live video is claimed.

## How it works

1. The UI appends up to three prior user questions to the current question by default. It does not add past answers as evidence. This is context concatenation, not guaranteed coreference resolution. The optional OpenAI rewriter may expand that text, but the existing guard requires every original whitespace-delimited token (and quoted phrase) to survive exactly. The rewritten query and any rewrite fallback appear in the trace.
2. The UI synchronizes the Markdown/text corpus to a persistent Chroma collection on each question. `SentenceTransformerEmbedder` uses `all-MiniLM-L6-v2` by default, with normalized vectors and cosine retrieval; local first-stage scores are `1 - cosine distance`.
3. `CrossEncoderReranker` uses the real `cross-encoder/ms-marco-MiniLM-L-6-v2` model. A UI adapter records the entire reranked list before the pipeline takes its top K and filters by the threshold. Rank shift is first-stage rank minus rerank rank (positive means moved up). A web candidate's first-stage rank is provider order, and its retrieval score is unavailable.
4. If no local result meets the threshold, the pipeline optionally searches the web and reranks returned snippets. DuckDuckGo via `ddgs` is the default and needs no API key; select **disabled** for local-only queries or **tavily** with `TAVILY_API_KEY`. A web search is attempted only when local evidence is insufficient. Search failures appear in stage telemetry and the response can abstain; sources and snippets are never fabricated.
5. The default generator returns quoted extracts with numbered citations, not a synthesized answer. Optionally select OpenAI synthesis in the sidebar to send the question and retrieved evidence to OpenAI for a cited answer; this requires an API key and may transmit sensitive source content. Citation markers refer to the displayed source list; local sources show the document path and chunk ID and web sources link to the returned URL. The evidence expander shows the actual retrieved chunk or snippet.

**Scores are not confidence.** Rerank scores are sigmoid-transformed logits, not calibrated probabilities; the default `0.55` threshold is an unvalidated heuristic, not a measured operating point. Threshold decisions depend on model, corpus, and query; a high score does not establish truth or answerability. Citation validation checks marker structure, not entailment, factual accuracy, source trust, or prompt-injection resistance. Results require human review. Live web snippets are external, untrusted, and may be stale or unrelated to this fictional corpus.

## Local setup

Use Python 3.11–3.13 and a virtual environment. From this project directory:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
streamlit run src/app.py
```

Open the address printed by Streamlit, normally http://localhost:8501. Installation and the first model use require network access; the embedding model downloads during indexing and the cross-encoder downloads when candidates are first reranked. Model downloads and inference can be large and slow on CPU. Subsequent local-only runs can work offline if dependencies and both models are already cached. Set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` to prevent Hugging Face network access, and select **disabled** for web and leave OpenAI expansion off. An uncached model or missing package will still cause an error, not a simulated answer.

Optionally copy `.env.example` to `.env`. The app loads it without overriding existing environment variables. `OPENAI_API_KEY` is needed only for the optional OpenAI query expansion; `TAVILY_API_KEY` only for Tavily. The installed `ddgs` provider requires no key, but it does require a live network and can fail or be rate limited. Choosing OpenAI or web fallback sends the rewritten query, potentially including prior questions, to the selected external provider. Do not enter secrets or sensitive data. The optional OpenAI model is controlled by `OPENAI_MODEL` and the sidebar.

`EMBEDDING_MODEL`, `RERANKER_MODEL`, and `CHROMA_DIR` override defaults. The core fingerprints a collection using the resolved corpus path, chunk settings, and embedding model. If the corpus is moved or embedding model changes while reusing the same Chroma directory, initialization rejects the incompatible collection. Stop the app and move or delete the dedicated `.chroma` directory (or choose a fresh `CHROMA_DIR`) to rebuild. Never point it at an unrelated collection: synchronization removes obsolete IDs from its dedicated collection. The UI serializes model/index access within one process, not across multiple processes; use a single app process per persistent index.

## Docker

From the project directory, optionally create `.env` for provider keys, then run:

```sh
docker compose up --build
```

Visit http://localhost:8501. The image installs CPU PyTorch wheels and project dependencies; build and first-run downloads need network access. Compose publishes the port only on loopback, mounts `docs/` read-only, and persists the Chroma index and Hugging Face cache in named volumes. Compose loads `.env` for its explicit environment substitutions; the container always uses `/data/chroma`. `docker compose down` stops it; `docker compose down -v` also **deletes** the named index and model caches. Rebuild the index after changing the embedding model or changing corpus paths/configuration; a named volume can retain an incompatible fingerprint. Docker support and CPU wheel availability depend on host architecture and upstream package releases.

## Tests and limitations

Run `pytest -v` for the offline QA suite. It injects fake embedders, cross-encoder models, and web clients and exercises local Chroma persistence; no model downloads or network should be needed. A full integration test with real models requires the model files; live DuckDuckGo, Tavily, or OpenAI checks require network and any applicable credentials and are not deterministic. Offline test doubles do not demonstrate real retrieval quality.

The UI shows per-stage statuses, timings, errors, ranks, scores, and whether web fallback was attempted. Index synchronization occurs before pipeline execution; an index/sync failure is reported directly rather than invoking web fallback. The core pipeline can fall back to web after a retrieval or rerank failure. Its threshold is applied separately to local and web candidates, not to a combined result set. A reranker failure, web error, or failed citation validation can lead to abstention; telemetry distinguishes these cases. `used_web` means attempted, not necessarily successful. Query history is in the Streamlit session only and can be cleared; it is not a durable conversation store.

This is a local demonstration, not a hardened production service: no authentication or tenant isolation is provided, external results are untrusted, and the UI has no evaluation dataset, calibrated thresholds, or demonstrated latency/quality metrics.