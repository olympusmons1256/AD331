from __future__ import annotations

from src.chunking import FixedSizeChunker, StructureAwareChunker


def test_fixed_chunk_overlap_integrity() -> None:
    text = " ".join([f"token{i}" for i in range(120)])
    chunker = FixedSizeChunker(chunk_size=30, chunk_overlap=10)
    chunks = chunker.chunk_document("doc", text)

    assert len(chunks) > 1

    for prev, curr in zip(chunks, chunks[1:]):
        assert prev.metadata["token_end"] - curr.metadata["token_start"] == 10


def test_structure_chunker_preserves_code_fence_blocks() -> None:
    text = """
# API Guide

## Example
```python
def handler(config):
    return config.get(\"CUSTOM_CONFIG_FLAG_XYZ\", False)
```

## Notes
Do not split fenced code blocks.
""".strip()

    chunker = StructureAwareChunker()
    chunks = chunker.chunk_document("doc", text)

    example_chunk = [c for c in chunks if "Example" in c.metadata.get("section_key", "")][0]

    assert "```python" in example_chunk.content
    assert "```" in example_chunk.content
    assert example_chunk.content.count("```") % 2 == 0
