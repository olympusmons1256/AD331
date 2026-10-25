# AI Prompt Audit Log

## Prompt used for generation

"You are a Staff AI Systems Engineer... build a production-ready extraction pipeline for messy invoice text with strict Pydantic validation and reflection repair."

## Initial AI-generated issues found

1. Mixed Pydantic v1 and v2 usage: the initial draft used `@validator` instead of `@field_validator` / `@model_validator` for v2.
2. Retry loop stuffed the full raw document into each reflection prompt, creating token bloat and unstable responses.
3. Validation failures were being swallowed in fallback logic and returned as `None` values without an explicit audit record.
4. Date parsing was too brittle for values like `12th of Oct, 2024` and other irregular formats.

## Corrective changes made

- Switched all validation to Pydantic v2 style decorators and `model_validate` flows.
- Added context trimming and explicit validation error extraction in the reflection prompt generation.
- Ensured any failed payload is routed to a DLQ log and marked with an execution status.
- Added a pre-parser to normalize common date variants before Pydantic evaluation.
- Added deterministic retry bounds so the system fails safely and predictably.

## Verification summary

The pipeline now validates invoice data with explicit field constraints and root-level reconciliation checks, then repairs or logs irrecoverable cases without crashing the application.
