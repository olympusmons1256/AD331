from __future__ import annotations

from pydantic import ValidationError

from src.extractor import StructuredDataExtractor
from src.schemas import InvoiceExtraction


def test_golden_document_extraction_success():
    extractor = StructuredDataExtractor()
    raw = (
        "Invoice INV-2045\n"
        "Vendor: Acme Supply Co.\n"
        "Date: 2024-10-15\n"
        "Widget A 2 @ $25.00 $50.00\n"
        "Widget B 1 @ $15.00 $15.00\n"
        "Subtotal $65.00\n"
        "Tax $6.50\n"
        "Total $71.50 USD"
    )
    result = extractor.extract_with_retry(raw, max_retries=3)
    assert result.execution_status == "SUCCESS"
    assert result.validated_data is not None
    assert result.validated_data.invoice_number == "INV-2045"
    assert result.validated_data.currency == "USD"


def test_schema_constraint_rejects_invalid_quantities():
    try:
        InvoiceExtraction.model_validate(
            {
                "invoice_number": "INV-1",
                "vendor_name": "Acme",
                "invoice_date": "2024-10-15",
                "line_items": [{"description": "Widget", "quantity": 0, "unit_price": 9.5, "line_total": 0}],
                "subtotal": 0,
                "tax_amount": 0,
                "total_amount": 0,
                "currency": "USD",
            }
        )
        raise AssertionError("ValidationError should have been raised")
    except ValidationError:
        pass


def test_cross_field_reconciliation_fails_on_mismatch():
    try:
        InvoiceExtraction.model_validate(
            {
                "invoice_number": "INV-2",
                "vendor_name": "Acme",
                "invoice_date": "2024-10-16",
                "line_items": [{"description": "Widget", "quantity": 2, "unit_price": 10, "line_total": 15}],
                "subtotal": 40,
                "tax_amount": 4,
                "total_amount": 44,
                "currency": "USD",
            }
        )
        raise AssertionError("Reconciliation validation should fail")
    except ValidationError:
        pass
