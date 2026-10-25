from __future__ import annotations

from src.extractor import StructuredDataExtractor


def test_reflection_loop_repairs_invalid_payload():
    extractor = StructuredDataExtractor()
    raw = (
        "Invoice INV-2045\n"
        "Vendor: Acme Supply Co.\n"
        "Date: 2024/10/15\n"
        "Widget A 2 @ $25.00 $60.00\n"
        "Widget B 1 @ $15.00 $15.00\n"
        "Subtotal $75.00\n"
        "Tax $7.50\n"
        "Total $82.50 USD"
    )
    result = extractor.extract_with_retry(raw, max_retries=3)
    assert result.execution_status in {"SUCCESS", "REPAIRED_VIA_REFLECTION", "DLQ_FAILED"}


def test_dlq_routing_on_hard_failures():
    extractor = StructuredDataExtractor()
    result = extractor.extract_with_retry("this is nonsense not an invoice", max_retries=3)
    assert result.execution_status == "DLQ_FAILED"
    assert result.validated_data is None
    assert result.error_log
