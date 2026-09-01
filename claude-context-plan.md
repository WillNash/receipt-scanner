# Architecture Plan

## Context Summary

Add Claude Haiku fuzzy-matching of the raw OCR vendor name against the DynamoDB stores table (`receipt-scanner-stores`) inside the processor Lambda. A module-level cache holds the store name list after the first cold-start scan. The best-matched normalised store name is stored alongside the raw OCR vendor in the DynamoDB jobs table and exposed via the API Lambda to the frontend.

---

## Impacted Files

### Modified — Python Lambda

- `/workspace/active_repo/lambda/processor/bedrock_extraction.py`
  Add `_match_store(vendor: str, store_names: list[str]) -> str | None` function using `bedrock.converse()` with a `match_store` tool spec to force structured JSON output.

- `/workspace/active_repo/lambda/processor/handler.py`
  - Add `STORES_TABLE` env var read.
  - Add module-level `_STORES_CACHE: list[str] | None = None` sentinel and `_get_store_names() -> list[str]` loader function.
  - Add `matched_store: str | None = None` field to `ReceiptAnalysis` dataclass.
  - Call `_match_store()` in `analyze_receipt()` after the price-check block, wrapped in try/except.
  - Pass `matched_store=matched_store` into the `ReceiptAnalysis(...)` constructor.
  - Conditionally write `matched_store` to DynamoDB in `update_job()` call.

- `/workspace/active_repo/lambda/api/handler.py`
  - Add `matched_store: str | None = None` field to `JobRecord` dataclass (with default).
  - Populate it in `from_dynamo()`.
  - Expose it as `"matchedStore"` in `format_receipt()` return dict.

### Modified — Terraform

- `/workspace/active_repo/terraform/iam.tf`
  Add a `StoresRead` IAM statement granting `dynamodb:Scan` on `aws_dynamodb_table.stores.arn` to `aws_iam_role_policy.lambda_processor`.

- `/workspace/active_repo/terraform/lambda.tf`
  Add `STORES_TABLE = aws_dynamodb_table.stores.name` to the processor Lambda's `environment.variables` block.

---

## Step-by-Step Execution Plan

### Step 1 — Add `_match_store()` to `bedrock_extraction.py`

In `/workspace/active_repo/lambda/processor/bedrock_extraction.py`, add the following at the bottom of the file (after `_compute_net_prices`):

Define a module-level `MATCH_STORE_TOOL` dict using the same `toolSpec` pattern as `RECEIPT_TOOL`. The tool is named `match_store`. Its `inputSchema` has a single required property `matched_name` of type `"string"` only — do NOT use `["string", "null"]` or any array-type syntax, because the Bedrock Converse API may raise a `ValidationException` for non-scalar type values. To express the "no match" case, the system prompt instructs the model to return the literal string `"null"` when no confident match exists; the parser maps that sentinel back to Python `None`.

Define `_match_store(vendor: str, store_names: list[str]) -> str | None`:
- Return `None` immediately if `vendor` is falsy or `store_names` is empty (no Bedrock call).
- Call `bedrock.converse(modelId=BEDROCK_MODEL_ID, ...)` with:
  - A concise system prompt instructing the model to match on core brand name, ignore branch numbers and punctuation, return the exact string from the candidate list if a confident match exists, and return the literal string `"null"` if no confident match exists.
  - A user message containing the raw OCR vendor string and a bulleted list of candidate store names.
  - `toolConfig` with `tools=[MATCH_STORE_TOOL]` and `toolChoice={"tool": {"name": "match_store"}}` to force a structured response.
- Parse the response by iterating `response["output"]["message"]["content"]` for a `toolUse` block named `match_store`; extract `input["matched_name"]`.
- Map the result: if `matched_name` is `None` or the string `"null"`, return `None`; otherwise return the matched name string.
- Log token usage with the same `BEDROCK_USAGE` log line pattern used by `_run_bedrock`.

### Step 2 — Export `_match_store` from `bedrock_extraction.py` via `handler.py` import

In `/workspace/active_repo/lambda/processor/handler.py`, add `_match_store` to the existing `from bedrock_extraction import (...)` block (lines 23-28) so it is available in the handler module.

### Step 3 — Add stores cache and env var to `handler.py`

In `/workspace/active_repo/lambda/processor/handler.py`:

1. Add `STORES_TABLE = os.environ.get("STORES_TABLE", "")` alongside the existing env var reads (lines 51-55).
2. After the module-level client definitions (after line 60), add:
   - `_STORES_CACHE: list[str] | None = None`
   - A `_get_store_names() -> list[str]` function that:
     - Returns `_STORES_CACHE` immediately if it is not `None`.
     - Returns `[]` if `STORES_TABLE` is empty (guards against missing env var).
     - Performs a paginated `dynamodb.scan()` using `ProjectionExpression="#n"` and `ExpressionAttributeNames={"#n": "name"}` (required because `name` is a DynamoDB reserved word).
     - Follows `LastEvaluatedKey` until exhausted.
     - Filters out empty-string names (`n.strip()` must be truthy).
     - Assigns the resulting list to the `global _STORES_CACHE` and returns it.

### Step 4 — Add `matched_store` field to `ReceiptAnalysis`

In `/workspace/active_repo/lambda/processor/handler.py`, add `matched_store: str | None = None` as the last field of the `ReceiptAnalysis` dataclass (after `cropped_s3_key: str | None = None`, line 48). Using a default of `None` keeps the field optional and backward-compatible.

### Step 5 — Call `_match_store()` inside `analyze_receipt()`, wrapped in try/except

In `analyze_receipt()` in `/workspace/active_repo/lambda/processor/handler.py`, after the existing `_save_debug_payloads(...)` call and before the `return ReceiptAnalysis(...)` statement, add:

```python
raw_vendor = extracted.get("vendor") or ""
try:
    matched_store = _match_store(raw_vendor, _get_store_names())
    if matched_store:
        print(f"STORE_MATCH raw={raw_vendor!r} matched={matched_store!r}")
    else:
        print(f"STORE_MATCH raw={raw_vendor!r} no_match")
except Exception as exc:
    print(f"STORE_MATCH_ERROR raw={raw_vendor!r} error={exc} — falling back to None")
    matched_store = None
```

The try/except is mandatory: a transient Bedrock error during matching must not mark an otherwise-successfully-parsed receipt as FAILED, because `_match_store()` runs inside `analyze_receipt()` whose caller wraps any unhandled exception in `_mark_job_failed()`.

### Step 6 — Pass `matched_store` into `ReceiptAnalysis(...)` and write to DynamoDB

**Constructor call** — update the `return ReceiptAnalysis(...)` statement in `analyze_receipt()` to explicitly include `matched_store=matched_store`. The full updated constructor must be:

```python
return ReceiptAnalysis(
    store_category=extracted.get("store_category") or "other",
    vendor=extracted.get("vendor") or "Unknown vendor",
    receipt_date=extracted.get("receipt_date") or "",
    total=extracted.get("total") or "",
    items=extracted.get("items") or [],
    price_check_warning=price_check["warning"],
    price_check_message=price_check["message"],
    debug_s3_key=claude_debug_key,
    textract_debug_s3_key=textract_debug_key,
    cropped_s3_key=cropped_key,
    matched_store=matched_store,
)
```

Without this line the field defaults to `None` and the match is silently discarded regardless of what Haiku returned.

**DynamoDB write** — in the `update_job(...)` call at lines 153-168 of `_process_s3_record()`, add a conditional spread for `matched_store` alongside the existing one for `cropped_s3_key`:

```python
**( {"matched_store": dyn_s(result.matched_store)} if result.matched_store else {} ),
```

This ensures the attribute is only written when a confident match was found, avoiding storing empty strings or `None` values as DynamoDB attributes.

### Step 7 — Add IAM `StoresRead` statement to `terraform/iam.tf`

In `/workspace/active_repo/terraform/iam.tf`, inside the `Statement = [...]` array of `aws_iam_role_policy.lambda_processor` (after the `ImageHashesReadWrite` statement, before the closing `]`), add:

```hcl
{
  Sid    = "StoresRead"
  Effect = "Allow"
  Action = ["dynamodb:Scan"]
  Resource = aws_dynamodb_table.stores.arn
},
```

### Step 8 — Add `STORES_TABLE` env var to `terraform/lambda.tf`

In `/workspace/active_repo/terraform/lambda.tf`, inside the `environment { variables = { ... } }` block for `aws_lambda_function.bedrock_processor` (lines 38-47), add:

```hcl
STORES_TABLE = aws_dynamodb_table.stores.name
```

### Step 9 — Expose `matched_store` via API Lambda

In `/workspace/active_repo/lambda/api/handler.py`:

1. Add `matched_store: str | None = None` as the last field in the `JobRecord` dataclass (after `s3_key: str | None`). The default `= None` is mandatory — all existing fields in `JobRecord` are non-defaulted, so without a default this new field would become a new required positional parameter and break every existing `JobRecord(...)` call site with a `TypeError`.

2. In `from_dynamo()`, add:
   ```python
   matched_store=item.get("matched_store", {}).get("S"),
   ```

3. In `format_receipt()`, add `"matchedStore": job.matched_store` to the returned dict.

---

## Risks & Blockers

- **Bedrock `ValidationException` for non-scalar type values:** The existing `RECEIPT_TOOL` uses only single-string `"type"` values. The `match_store` tool spec must likewise use `"type": "string"` only — not `["string", "null"]`. The "no match" case is handled by instructing the model to return the literal string `"null"` and mapping that sentinel to Python `None` in the parser.
- **Silent discard of `matched_store` if not passed to constructor:** Step 6 is explicit: the full `ReceiptAnalysis(...)` constructor call must include `matched_store=matched_store`. If omitted, the dataclass default of `None` silently wins and the match is discarded.
- **TypeError on existing `JobRecord` call sites:** The `matched_store` field in `JobRecord` must have a default of `None`. Without it, all existing instantiation paths (e.g. from `handle_upload_url`, `handle_edit_receipt`, and `handle_delete_receipt` which call `JobRecord.from_dynamo()` on old items lacking the attribute) would raise `TypeError` at runtime.
- **Transient Bedrock error during matching fails the job:** The `_match_store()` call is wrapped in a `try/except Exception` block (Step 5). Any Bedrock error is logged and `matched_store` falls back to `None`, leaving the receipt as COMPLETE with no matched store rather than incorrectly marking it FAILED.
- **Bedrock latency:** A second `bedrock.converse()` call per receipt adds approximately 300–800 ms for Haiku. This is acceptable given the processor Lambda's generous timeout, but should be logged to track cost and latency trends.
- **Empty stores table on first deploy:** If the stores table has never been populated, `_get_store_names()` returns `[]` and `_match_store()` short-circuits without calling Bedrock. This is safe by design.
- **`name` is a DynamoDB reserved word:** The `ProjectionExpression` scan must use `ExpressionAttributeNames={"#n": "name"}` and reference `#n` in the expression — failing to do this will raise a `ValidationException` at runtime.
- **Cache staleness:** The module-level cache is per-execution-environment and is never invalidated. If stores are refreshed weekly, the worst-case lag is the execution environment's lifetime (typically hours). This is an acceptable trade-off per the spec.
- **No new Python dependencies required:** The Bedrock SDK (`boto3`) is already bundled. Zip size and the S3-upload deployment path are unaffected.

---

## Testing Strategy

1. **Unit-level (manual invocation):**
   - Set `STORES_TABLE` to the deployed table name in the environment and invoke the processor Lambda manually with a test SQS event pointing to a known receipt S3 key.
   - Check CloudWatch Logs for `STORE_MATCH raw=... matched=...` or `STORE_MATCH raw=... no_match`.
   - Inspect the DynamoDB jobs table item for the `matched_store` attribute.

2. **API round-trip:**
   - Upload a receipt via the frontend or API, wait for COMPLETE status.
   - Call `GET /jobs/{jobId}` and verify the response JSON includes `"matchedStore"` (either a store name string or `null`).

3. **Empty-stores guard:**
   - Temporarily set `STORES_TABLE=""` in a test invocation and confirm the processor completes successfully without errors and stores no `matched_store` attribute.

4. **Bedrock error fallback:**
   - Temporarily remove the `bedrock:InvokeModel` permission (or inject a bad model ID) for the processor Lambda and upload a receipt. Confirm the job reaches COMPLETE status (not FAILED) and `matched_store` is absent from the DynamoDB item.

5. **Terraform plan:**
   - Run `make plan` and verify the plan includes:
     - An update to `aws_iam_role_policy.lambda_processor` adding the `StoresRead` statement.
     - An update to `aws_lambda_function.bedrock_processor` environment adding `STORES_TABLE`.
   - No destroy/recreate of the Lambda or DynamoDB tables should appear.

6. **Full smoke test:**
   - After `make deploy`, run `make smoke` to confirm CloudFront and API Gateway are still healthy.
