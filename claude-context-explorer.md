# Claude Context Explorer — Processor Vendor Fuzzy-Match via Haiku

## Task
Add Claude Haiku fuzzy-matching of the OCR vendor name against the DynamoDB stores table in the processor Lambda. Cache the stores list at module level (cold start only). Store a normalised store name alongside the raw OCR vendor. Add IAM permission for the processor to read the stores table.

---

## Files Examined

### 1. `/workspace/active_repo/lambda/processor/handler.py`

**Vendor extraction flow (key lines):**

- Line 261: `extracted, usage = _run_bedrock(tr.text)` — Bedrock returns a dict including `extracted["vendor"]` (raw OCR vendor string).
- Line 276–287: `ReceiptAnalysis` is constructed; `vendor` field is set to `extracted.get("vendor") or "Unknown vendor"`.
- Lines 153–168: `update_job(...)` writes the COMPLETE job to DynamoDB. The fields written include `"vendor": dyn_s(result.vendor)`. There is no `normalised_vendor` / `matched_store` field yet — that is what needs adding.
- Lines 170–181: `write_line_items(...)` is called with `ctx.vendor = result.vendor`. This will also want the normalised value if desired for analytics.

**ReceiptAnalysis dataclass (lines 38–48):** Fields are `store_category`, `vendor`, `receipt_date`, `total`, `items`, `price_check_warning`, `price_check_message`, `debug_s3_key`, `textract_debug_s3_key`, `cropped_s3_key`. A new optional field (`matched_store: str | None = None`) should be added here.

**Environment variables already read (lines 51–55):**
```
DYNAMODB_TABLE        = os.environ["DYNAMODB_TABLE"]
LINE_ITEMS_TABLE      = os.environ.get("LINE_ITEMS_TABLE", "")
IMAGE_HASHES_TABLE    = os.environ.get("IMAGE_HASHES_TABLE", "")
S3_BUCKET             = os.environ["S3_UPLOADS_BUCKET"]
PRIMARY_REGION        = os.environ.get("PRIMARY_REGION", "ap-southeast-2")
```
A new `STORES_TABLE = os.environ.get("STORES_TABLE", "")` env var must be added here and used by the stores-cache loader.

**Module-level AWS clients (lines 57–60):** `s3`, `dynamodb`, `bedrock`, `textract` are all created at module level — the stores cache scan should reuse the existing `dynamodb` client.

**Client injection pattern (lines 63–66):**
```python
import textract_pipeline as _tp
import bedrock_extraction as _be
_tp.set_textract_client(textract)
_be.set_bedrock_client(bedrock)
```
If the fuzzy-match logic is placed in `bedrock_extraction.py`, a `set_dynamodb_client(dynamodb)` injector should be added there too following the same pattern. Alternatively, the stores scan and cache can live entirely in `handler.py` and a list of name strings passed into `bedrock_extraction._match_store()`.

---

### 2. `/workspace/active_repo/lambda/processor/bedrock_extraction.py`

**Bedrock client:** `bedrock = None` at module level (line 144); injected via `set_bedrock_client(client)` (lines 147–149).

**Model ID (lines 12–14):**
```python
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"
)
```
This is the same model to use for the fuzzy-match call. The actual deployed value from `variables.tf` is `"au.anthropic.claude-haiku-4-5-20251001-v1:0"`.

**`_run_bedrock(receipt_text)` call pattern (lines 153–236):** Uses `bedrock.converse(modelId=BEDROCK_MODEL_ID, messages=[...], toolConfig={...})`. For the fuzzy-match call a simpler `converse` call can be used — either with a minimal single-field tool (e.g. `match_store` returning `{"matched_store": "..."}`) or a plain text message asking for a match with JSON in the reply. The existing tool-use pattern with `toolChoice: {"tool": {"name": "..."}}` is the most reliable way to force structured output.

Response parsing (lines 225–229): iterates `response["output"]["message"]["content"]` looking for a `toolUse` block with the expected tool name. Token usage is logged via `response.get("usage", {})`.

**`_validate_classification(extracted)` (lines 239–248):** Shows the pattern for in-place mutation of the `extracted` dict — the normalised vendor result can similarly be merged back into `extracted` before `ReceiptAnalysis` is constructed.

---

### 3. `/workspace/active_repo/lambda/api/handler.py` — JWKS cache pattern to replicate

**`_JwksCache` class (lines 111–139):** Thread-safe double-checked locking:
```python
_JWKS_TTL_SECONDS = 3600

class _JwksCache:
    def __init__(self):
        self._data: dict | None = None
        self._fetched_at: datetime | None = None
        self._lock = threading.Lock()

    def get(self) -> dict:
        now = datetime.now(timezone.utc)
        # Fast path — no lock needed when cache is fresh.
        if (self._data is not None and self._fetched_at is not None
                and (now - self._fetched_at).total_seconds() <= _JWKS_TTL_SECONDS):
            return self._data
        with self._lock:
            now = datetime.now(timezone.utc)
            if self._data is None or (...TTL expired...):
                # fetch and populate self._data
                ...
            return self._data

_jwks_cache = _JwksCache()
```

**For the stores cache the pattern is simpler** — the stores list is loaded once at cold start (no TTL needed, since the stores table is only updated weekly by the stores_refresh Lambda). A module-level sentinel `_STORES_CACHE: list | None = None` populated on first call is sufficient. Because the processor Lambda has `batch_size=1` (one SQS message per execution environment at a time), there is no within-process concurrency, so no lock is strictly required. However, mirroring the locking pattern from `_JwksCache` is safe and idiomatic.

---

### 4. `/workspace/active_repo/lambda/shared/`

- **`dynamo.py`** — helpers: `now_iso()`, `dyn_s()`, `dyn_n()`, `dyn_bool()`, `get_job()`, `update_job()`. No scan helper exists — a raw `dynamodb.scan(TableName=STORES_TABLE)` in the handler with `LastEvaluatedKey` pagination is required.
- **`constants.py`** — only `VALID_ITEM_CATEGORIES`. No store-related constants.
- **`line_items.py`** — `LineItemContext` dataclass and `write_line_items()`. `vendor` is a plain string field. A `matched_store` field could optionally be added to `LineItemContext` if line-item analytics should carry the normalised name, but this is out of scope for the current task.
- **`pricing.py`** — not relevant to this task.

---

### 5. `/workspace/active_repo/terraform/iam.tf`

**Processor role policy (`aws_iam_role_policy.lambda_processor`, lines 24–107):**

Current DynamoDB statements:
```hcl
{
  Sid    = "DynamoDBWrite"
  Effect = "Allow"
  Action = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
  Resource = aws_dynamodb_table.jobs.arn
},
{
  Sid    = "LineItemsWrite"
  Effect = "Allow"
  Action = ["dynamodb:PutItem", "dynamodb:BatchWriteItem"]
  Resource = aws_dynamodb_table.line_items.arn
},
{
  Sid    = "ImageHashesReadWrite"
  Effect = "Allow"
  Action = ["dynamodb:GetItem", "dynamodb:PutItem"]
  Resource = aws_dynamodb_table.image_hashes.arn
},
```

**Missing:** No statement grants the processor access to `aws_dynamodb_table.stores`. A new statement must be appended inside the same `Statement = [...]` array:
```hcl
{
  Sid    = "StoresRead"
  Effect = "Allow"
  Action = ["dynamodb:Scan"]
  Resource = aws_dynamodb_table.stores.arn
},
```

The `BedrockInvokeModel` statement (lines 73–79) already covers the Haiku model via wildcard foundation-model and inference-profile ARNs — no change needed there.

---

### 6. `/workspace/active_repo/terraform/variables.tf`

**`bedrock_model_id` (lines 46–49):**
```hcl
variable "bedrock_model_id" {
  type    = string
  default = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
}
```
Already the Haiku model. Already injected into the processor Lambda as `BEDROCK_MODEL_ID` (see `lambda.tf` line 45). No variable change needed.

---

### 7. `/workspace/active_repo/terraform/lambda.tf` — processor env vars

**Processor Lambda environment block (lines 39–47):**
```hcl
environment {
  variables = {
    DYNAMODB_TABLE     = aws_dynamodb_table.jobs.name
    LINE_ITEMS_TABLE   = aws_dynamodb_table.line_items.name
    IMAGE_HASHES_TABLE = aws_dynamodb_table.image_hashes.name
    S3_UPLOADS_BUCKET  = aws_s3_bucket.uploads.bucket
    PRIMARY_REGION     = var.primary_region
    BEDROCK_MODEL_ID   = var.bedrock_model_id
  }
}
```
`STORES_TABLE` is absent and must be added: `STORES_TABLE = aws_dynamodb_table.stores.name`.

---

### 8. `/workspace/active_repo/terraform/dynamodb.tf` — stores table schema

**`aws_dynamodb_table.stores` (lines 69–88):**
- Name: `${var.project_name}-stores` (deployed as `receipt-scanner-stores`)
- Hash key: `store_id` (String), e.g. `"node/12345678"` (OSM type/id from stores_refresh)
- TTL attribute: `expires_at`
- No range key, no GSI

**Item attributes written by stores_refresh Lambda** (`/workspace/active_repo/lambda/stores_refresh/handler.py` lines 57–64):
```python
{
  "store_id":  {"S": f"{el['type']}/{el['id']}"},
  "osm_type":  {"S": el["type"]},
  "name":      {"S": tags.get("name", "")},   # <-- the store name to match against
  "shop_type": {"S": tags.get("shop", "")},
  "lat":       {"S": lat},
  "lon":       {"S": lon},
}
```
The `name` attribute is the canonical store name to fuzzy-match against. The Haiku prompt should receive a list of `name` strings from a full table scan.

---

## Summary of All Required Changes

### `lambda/processor/handler.py`
1. Add `STORES_TABLE = os.environ.get("STORES_TABLE", "")` alongside existing env var reads.
2. Add module-level stores cache: `_STORES_CACHE: list | None = None` (list of store name strings).
3. Add a `_load_stores() -> list` function that scans `STORES_TABLE` with `LastEvaluatedKey` pagination, extracts the `name` attribute from each item (skipping empty names), populates and returns `_STORES_CACHE`. Returns `[]` if `STORES_TABLE` is unset.
4. Add `matched_store: str | None = None` as an optional field in `ReceiptAnalysis`.
5. In `analyze_receipt()`, after `_run_bedrock()` returns: call `_match_store_name(extracted.get("vendor", ""), _load_stores())` (or equivalent from `bedrock_extraction`). Assign the result to `result.matched_store`.
6. In `update_job(...)` call, conditionally add `"matched_store": dyn_s(result.matched_store)` if the value is truthy.

### `lambda/processor/bedrock_extraction.py`
1. Add a new exported function `_match_store(vendor: str, store_names: list[str]) -> str | None`.
2. If `store_names` is empty or `vendor` is empty, return `None` immediately (no Bedrock call).
3. Use `bedrock.converse(modelId=BEDROCK_MODEL_ID, ...)` with a concise prompt listing the candidate store names and asking for the single best match or explicit "no match". A minimal `toolSpec` forcing a JSON response like `{"matched": "Countdown", "confident": true}` or `{"matched": null, "confident": false}` is the most reliable approach.
4. Return the matched name if `confident` is true, else `None`.

### `terraform/iam.tf`
- Add a `StoresRead` statement to `aws_iam_role_policy.lambda_processor`:
  ```hcl
  {
    Sid    = "StoresRead"
    Effect = "Allow"
    Action = ["dynamodb:Scan"]
    Resource = aws_dynamodb_table.stores.arn
  },
  ```

### `terraform/lambda.tf`
- Add `STORES_TABLE = aws_dynamodb_table.stores.name` to the processor Lambda's `environment.variables` block.

### `lambda/api/handler.py` (optional, if frontend needs the field)
- Add `matched_store: str | None` to `JobRecord` dataclass and `from_dynamo()`.
- Add `"matchedStore": job.matched_store` to the `format_receipt()` return dict.

---

## Potential Side-Effects and Watch-outs

- **Bedrock latency:** A second `bedrock.converse()` call adds latency to every processor invocation (typically 300–800 ms for Haiku). The stores scan is cached at cold start only, so DynamoDB is only hit once per execution environment lifetime.
- **Empty stores table:** The stores table may be empty before the first stores_refresh run. `_match_store` must short-circuit and return `None` without calling Bedrock when the store list is empty.
- **DynamoDB scan pagination:** The scan must follow `LastEvaluatedKey` until exhausted. The Overpass query in stores_refresh covers a 10 km radius and returns at most a few hundred results — well within a single scan for a PAY_PER_REQUEST table.
- **Names with empty string:** The stores_refresh Lambda uses `tags.get("name", "")`, so items with no OSM name tag will have `name = ""`. The cache loader should skip empty-string names to avoid polluting the candidate list.
- **`matched_store` in DynamoDB jobs table:** If the API Lambda's `format_receipt()` and `JobRecord` are not updated, the field will be silently stored in DynamoDB but never returned to the frontend. Decide whether frontend exposure is in scope.
- **`project_name` vs `"receipt-scanner"`:** The actual deployed stores table name is `receipt-scanner-stores` (set in `terraform.tfvars`), not `bedrock-image-ai-stores` (the `variables.tf` default). Always use `aws_dynamodb_table.stores.name` in Terraform and the `STORES_TABLE` env var in Python — never hardcode the table name in Lambda code.
- **Processor zip size:** No new third-party libraries are needed (Bedrock SDK already bundled). No impact on zip size or the S3-upload deployment path.
- **Thread safety:** The processor's SQS event source has `batch_size=1`, so each execution environment handles one message at a time. A `None`-sentinel module-level cache without a lock is safe, but adding a `threading.Lock()` (as in `_JwksCache`) is fine for consistency.
