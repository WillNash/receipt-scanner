# Architecture Plan

## Context Summary

Add a new DynamoDB table (`receipt-scanner-stores`) to store retail shop records near Palmerston North NZ, and create a one-off Python script (`scripts/populate_stores.py`) that queries the OpenStreetMap Overpass API and upserts those records into the table using the operator's ambient AWS credentials.

---

## Impacted Files

### Modified
- `/workspace/active_repo/terraform/dynamodb.tf` — append new `aws_dynamodb_table.stores` resource block

### Created
- `/workspace/active_repo/scripts/populate_stores.py` — new one-off populate script

### Not modified (confirmed)
- `/workspace/active_repo/terraform/iam.tf` — no Lambda accesses the stores table; IAM change is not required for the script (runs with operator credentials)
- `/workspace/active_repo/terraform/outputs.tf` — stores table name is not needed by the frontend or any Lambda
- `/workspace/active_repo/Makefile` — one-off scripts are not wired into Makefile targets per project convention

---

## Step-by-Step Execution Plan

### Step 1 — Append the `aws_dynamodb_table.stores` resource block to `/workspace/active_repo/terraform/dynamodb.tf`

Append after the existing `aws_dynamodb_table.jobs` block. The new block must follow the exact pattern of the three existing tables:

- `name = "${var.project_name}-stores"` — deployed name will be `receipt-scanner-stores`
- `billing_mode = "PAY_PER_REQUEST"`
- `hash_key = "store_id"` — no sort key; this is a simple key-value lookup table
- A single `attribute` block declaring `store_id` of type `S`; no other attributes declared (schema-free non-key attrs must NOT appear in attribute blocks per existing convention)
- `ttl` block with `attribute_name = "expires_at"` and `enabled = true` (no TTL values set on items — matches existing tables)
- `tags` block: `Project = var.project_name` and `Environment = var.environment`
- No GSI in the initial version

### Step 2 — Create `/workspace/active_repo/scripts/populate_stores.py`

The script must follow the canonical pattern from `scripts/export_receipts.py`:

**2a. Module-level constants:**
- `TABLE = "receipt-scanner-stores"` — hardcoded to the actual deployed value from `terraform.tfvars` (the variable default in `variables.tf` is `"bedrock-image-ai"` but the deployed value is `"receipt-scanner"`, as documented in CLAUDE.md)
- `REGION = "ap-southeast-2"`
- `OVERPASS_URL = "https://overpass-api.de/api/interpreter"`
- `OVERPASS_QUERY` — a multiline string with the following Overpass QL query. The `[timeout:90]` directive sets the server-side query budget; the socket timeout (step 2b) must be set larger than this value to avoid the client hanging after the server has already aborted:
  ```
  [out:json][timeout:90][maxsize:10000000];
  (
    node["shop"](around:10000,-40.3523,175.6082);
    way["shop"](around:10000,-40.3523,175.6082);
  );
  out center tags;
  ```

**2b. `fetch_shops()` function:**
- POST to `OVERPASS_URL` using `urllib.request` (stdlib; no third-party dependencies; consistent with `scripts/smoke_test.py`)
- Body: `urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode()`
- Headers: `{"User-Agent": "receipt-scanner-store-scraper/1.0 will@koan.co.nz"}` — required by Overpass etiquette
- `urllib.request.urlopen(req, timeout=95)` — socket timeout must be set larger than the Overpass `[timeout:90]` server-side query timeout (95 > 90), so the server always aborts first and returns a parseable error body rather than the client socket timing out mid-stream
- Catch `urllib.error.HTTPError`: print the status code and response body to `sys.stderr`, then call `sys.exit(1)`
- After a successful HTTP response, parse JSON. Then immediately apply two guards:
  1. If `data.get("remark")` is present, print the remark value to `sys.stderr` and call `sys.exit(1)` — Overpass encodes server-side timeout and maxsize errors as HTTP 200 with a `remark` field and an empty `elements` list; without this guard the script silently writes zero records and exits 0
  2. If `data.get("elements", [])` is empty after no remark, print a warning to `sys.stderr` (non-fatal — the area may genuinely have no shops in OSM, though unlikely) and return the empty list so the caller can report a zero count rather than crashing
- Return `data["elements"]`

**2c. `build_item(element)` helper:**
- `store_id`: `f"{element['type']}/{element['id']}"` — uses the OSM element reference as a stable, unique PK (e.g. `"node/12345678"` or `"way/98765432"`)
- `lat`/`lon`: for `type == "node"`, use `element["lat"]` and `element["lon"]`; for `type == "way"`, use `element["center"]["lat"]` and `element["center"]["lon"]` (ways do not have top-level `lat`/`lon` — only `center` from `out center`)
- Store lat/lon as DynamoDB `{"S": str(value)}` — avoids `TypeError: Float types are not supported` and is simpler than `Decimal`
- `name`: `element.get("tags", {}).get("name", "")` — stored as `{"S": value}`; empty string for unnamed shops (items kept, not skipped — preserves the full OSM dataset)
- `shop_type`: `element.get("tags", {}).get("shop", "")` — stored as `{"S": value}`
- `osm_type`: `element["type"]` — stored as `{"S": value}`
- All attributes use the low-level typed dict format (`{"S": ...}`, `{"N": ...}`) — consistent with all other scripts and Lambdas in this codebase
- Returns `None` and prints a warning to `sys.stderr` if `element["type"]` is neither `"node"` nor `"way"` (defensive guard for future OSM relation elements)

**2d. `upsert_stores(dynamodb, elements, table)` function:**
- Use `boto3.client` low-level API exclusively — NOT `boto3.resource` (which is never used anywhere in this codebase)
- Build items with `build_item()`, skip any that return `None`
- Use `dynamodb.batch_write_item(RequestItems={table: [{"PutRequest": {"Item": item}} for item in batch]})` with batches of up to 25 items (DynamoDB's hard limit per batch call)
- After each `batch_write_item` call, check `response["UnprocessedItems"]` — if non-empty, retry up to 3 times with exponential back-off. Each retry must pass `response["UnprocessedItems"]` directly as the `RequestItems` argument (not the original full batch) — this is essential because `UnprocessedItems` is already in the `{table: [...]}` shape that `batch_write_item` expects, and resubmitting the full original batch would duplicate already-written items and waste capacity. Print a warning to `sys.stderr` if items remain unprocessed after all retries.
- Track and return the count of successfully written items
- Print progress per batch to `sys.stderr` (e.g., `"Upserted batch N (running total: M)"`)

**2e. `main()` function with `argparse`:**
- `--table` argument (default: `TABLE` constant) — allows override without editing the file
- `--dry-run` flag — fetches from Overpass and prints the element count to `sys.stderr`, but does not touch DynamoDB
- Instantiate `dynamodb = boto3.client("dynamodb", region_name=REGION)`
- Call `fetch_shops()`, then (if not dry-run) `upsert_stores()`, then print the final count to `sys.stderr`

**2f. Script header and structure:**
- `#!/usr/bin/env python3` shebang
- Module docstring with description, usage examples (including `--table` and `--dry-run`), and the deployment prerequisite (`make apply` must run before this script)
- Imports: `argparse`, `json`, `sys`, `time`, `urllib.request`, `urllib.parse`, `boto3`
- `if __name__ == "__main__": main()` guard

---

## Risks & Blockers

1. **Overpass QL output modifier — `out center tags;`:** The query uses `out center tags;`. Including the `tags` keyword is explicit and harmless; it ensures tag data is returned alongside geometry. The `out center;` form without `tags` may also return tags in practice (the keyword is not always required), but including it avoids any ambiguity and is the safer choice.

2. **boto3 float rejection:** The low-level `dynamodb.client` API accepts typed attribute dicts and does not directly reject Python floats, but the high-level resource API does. Lat/lon must be stored as `{"S": str(value)}` to be safe and forward-compatible.

3. **`batch_writer` vs `batch_write_item`:** The researcher context showed the high-level resource API's `batch_writer` context manager (`table.batch_writer()`). This project uses exclusively the low-level client. The implementation must use `dynamodb.batch_write_item(RequestItems={...})` on the client object, not `table.batch_writer()` on a resource object.

4. **Deployment prerequisite:** Terraform must be applied (`make apply` or `make deploy`) before the script can write to the table. Running the script against a non-existent table raises `ResourceNotFoundException`. The script does not create the table itself — it is infrastructure, managed by Terraform.

5. **Overpass API availability:** The public endpoint has occasional downtime and rate-limiting (HTTP 429/406). For a one-shot seed script this risk is low, but `urllib.error.HTTPError` must be caught explicitly and the status code surfaced clearly.

6. **Overpass HTTP 200 error body:** Overpass returns timeout and maxsize errors as HTTP 200 with a `remark` field and an empty `elements` list. Without an explicit `remark` guard (step 2b), the script would silently write zero records and exit 0. The `remark` check is therefore mandatory for correct failure reporting.

7. **OSM data completeness:** Many shops in OSM will have no `name` tag. The plan stores them with an empty string `name` rather than skipping them — this preserves the full dataset. The `store_id` (OSM element reference) is always populated and unique.

8. **IAM not required now — but documented for future:** Neither Lambda role currently has access to the `stores` table. If any Lambda (e.g., the API Lambda) ever needs to query stores, a new IAM statement must be added to the `lambda_api` policy in `/workspace/active_repo/terraform/iam.tf` granting `dynamodb:Query` or `dynamodb:GetItem` against `aws_dynamodb_table.stores.arn`.

---

## Testing Strategy

1. **Terraform plan check (before apply):** Run `make plan` and confirm the plan output shows exactly one new resource being added: `aws_dynamodb_table.stores`. Confirm no existing resources are modified or destroyed.

2. **Dry-run test (after apply):** Run:
   ```
   python3 scripts/populate_stores.py --dry-run
   ```
   Confirm it exits 0, prints a non-zero element count to stderr, and does not write to DynamoDB.

3. **Live upsert test:** Run:
   ```
   python3 scripts/populate_stores.py
   ```
   Confirm it exits 0 and prints a count of upserted stores (expect tens to a few hundred shops for the Palmerston North 10 km radius).

4. **Spot-check records in DynamoDB:** Use the AWS CLI to verify written items:
   ```
   aws dynamodb scan --table-name receipt-scanner-stores --max-items 5 --region ap-southeast-2
   ```
   Confirm items have `store_id`, `name`, `shop_type`, `lat`, `lon`, and `osm_type` attributes, all as DynamoDB `S` typed values (not `N` or missing).

5. **Idempotency check:** Run the script a second time. Confirm it completes without error — `put_item` replaces on matching key by definition, so the item count in DynamoDB must not increase.

6. **Table-override flag error handling:** Run with a deliberately wrong table name:
   ```
   python3 scripts/populate_stores.py --table does-not-exist
   ```
   Confirm a clear error is printed to stderr (DynamoDB `ResourceNotFoundException` or similar) and the script exits non-zero.

7. **`--help` sanity check:** Run `python3 scripts/populate_stores.py --help` and confirm `--table` and `--dry-run` flags are documented.

---

**IMPORTANT — handoff to main agent:** This plan is now written to `claude-context-plan.md`. The Plan Reviewer agent MUST be run next before any implementation begins. No source files should be created or modified until the Reviewer has issued its verdict.
