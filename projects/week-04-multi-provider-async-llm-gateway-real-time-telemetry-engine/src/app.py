from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pypdf import PdfReader
import streamlit as st

from src.extractor import StructuredDataExtractor


def read_document_content(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".pdf":
        pdf_reader = PdfReader(uploaded_file)
        pages = [page.extract_text() or "" for page in pdf_reader.pages]
        return "\n".join(pages)
    return uploaded_file.read().decode("utf-8", errors="replace")


def main() -> None:
    st.title("Structured Data Extraction Audit Console")
    st.caption("LLM-first extraction with Pydantic validation, reflection repair, and DLQ fallback")

    default_text = (
        "Invoice INV-2045\n"
        "Vendor: Acme Supply Co.\n"
        "Date: 2024-10-15\n"
        "Widget A 2 @ $25.00 $50.00\n"
        "Widget B 1 @ $15.00 $15.00\n"
        "Subtotal $65.00\n"
        "Tax $6.50\n"
        "Total $71.50 USD"
    )

    raw_text = st.text_area("Paste raw invoice or HTML text", value=default_text, height=260)
    uploaded_file = st.file_uploader("Or upload a PDF or text file", type=["pdf", "txt", "html", "json"])
    use_llm = st.checkbox("Use live LLM extraction", value=True)

    if uploaded_file is not None:
        raw_text = read_document_content(uploaded_file)

    st.info("This project is designed to extract invoice records via the LLM. Non-invoice documents should fail safely and route to the DLQ, rather than returning a fake invoice payload.")

    if st.button("Run extraction"):
        extractor = StructuredDataExtractor(use_llm=use_llm)
        result = extractor.extract_with_retry(raw_text, max_retries=3, use_llm=use_llm)

        if result.validated_data is not None:
            st.success(f"Extraction succeeded with status: {result.execution_status}")
            st.json(result.validated_data.model_dump())
        else:
            st.error(f"Extraction failed with status: {result.execution_status}")
            if result.error_log:
                st.write("Validation history:")
                for message in result.error_log:
                    st.write(f"- {message}")


if __name__ == "__main__":
    main()
