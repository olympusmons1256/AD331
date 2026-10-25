# Week 3: Resilient Unstructured Data Extraction & Pydantic Validation Pipelines

This project folder is the starter workspace for the current AD331 assignment.

## Goals

- Parse messy or unstructured input data consistently.
- Normalize extracted values into validated Pydantic models.
- Build a small pipeline that is resilient to malformed records, empty values, and schema drift.
- Keep the implementation readable and testable.

## Suggested structure

```text
week-03-resilient-unstructured-data-extraction-pydantic-validation-pipelines/
├── README.md
├── src/
│   ├── __init__.py
│   ├── models.py
│   ├── extractors.py
│   ├── validators.py
│   └── pipeline.py
├── tests/
│   ├── test_extractors.py
│   ├── test_validators.py
│   └── test_pipeline.py
├── notebooks/
│   └── exploration.ipynb
└── data/
    └── sample_input.json
```

## Getting started

Use this folder as the working project for your code and tests this week.

## Notes

- Prefer explicit validation with Pydantic v2 models.
- Handle bad input gracefully rather than failing the whole pipeline.
- Log and isolate extraction errors while continuing to process valid records.
