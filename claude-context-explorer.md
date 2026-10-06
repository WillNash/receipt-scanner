# Claude Context Explorer

## Task
Add a store name dropdown to the receipt edit UI. When the edit button on a receipt is clicked, the vendor/store name field should become a `<select>` populated from `DynamoDB receipt-scanner-stores`, rather than a plain text `<input>`. Selecting a value saves it via the existing `PATCH /receipts/{jobId}` endpoint.

---

## 1. frontend/app.js.template — Edit UI

**File:** `/workspace/active_repo/frontend/app.js.template`

### How the edit button is wired
- `buildHistoryCard()` (line 444) appends an Edit button to each COMPLETE history card.
- Its click handler calls `showEditModal(job)` (line 483).

### showEditModal() — full edit flow (lines 488–640)
- Creates a modal overlay via DOM manipulation (no innerHTML for user data — XSS safe pattern).
- The modal shell is set with `modal.innerHTML = ...` for the static structure only.
- **Vendor field** is currently a plain `<input id="edit-vendor" type="text">` declared inside the `modal.innerHTML` string (line 507).
- The value is set safely via DOM after injection: `modal.querySelector("#edit-vendor").value = job.vendor || ""` (line 527).
- Other editable fields: `receiptDate` (text input `#edit-date`), and line items rendered by `renderItems()` (description, quantity, package_size, unit_price, price, discount).

### How PATCH is called (lines 619–638)
```js
const vendor = modal.querySelector("#edit-vendor").value.trim();
const receiptDate = modal.querySelector("#edit-date").value.trim();
const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts/${job.jobId}`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ vendor, receiptDate, items: editItems }),
});
```
The vendor value is read from `#edit-vendor` using `.value`. Replacing the `<input>` with a `<select>` requires no change to the PATCH call — `select.value` returns the selected option's value identically.

### How stores data is currently fetched/displayed
- There is **no existing GET /stores call** anywhere in app.js.template.
- Stores appear on receipt cards only as `job.storeCategory` (a badge, line 396) and `job.vendor` (the receipt header, line 405). These come from the scanned job record, not from a frontend fetch of the stores table.
- Existing API calls from the frontend: `POST /upload-url`, `GET /jobs/{jobId}`, `GET /receipts`, `PATCH /receipts/{jobId}`.

---

## 2. lambda/api/handler.py — Routing and Edit Logic

**File:** `/workspace/active_repo/lambda/api/handler.py`

### _route() routing table (lines 149–164)
```python
def _route(method, path, user_id, user_email, event):
    job_id = (event.get("pathParameters") or {}).get("jobId")
    body = json.loads(event.get("body") or "{}") if method in ("POST", "PATCH") else {}

    if method == "POST"   and path.endswith("/upload-url"):   -> handle_upload_url
    if method == "GET"    and path.endswith("/receipts"):      -> handle_list_receipts
    if method == "GET"    and "/jobs/" in path:                -> handle_get_job
    if method == "DELETE" and "/receipts/" in path:            -> handle_delete_receipt
    if method == "PATCH"  and "/receipts/" in path:            -> handle_edit_receipt
    return make_response(404, {"error": "Not found"})
```
A new `GET /stores` handler needs a new branch before the final 404 return:
```python
if method == "GET" and path.endswith("/stores"):
    return handle_list_stores()
```

### handle_list_receipts pattern (lines 276–313)
- Queries the jobs GSI with `dynamodb.query()`, paginates, returns `{"receipts": [...], "lastKey": ...}`.
- The `GET /stores` handler can be simpler: a full `dynamodb.scan()` of the stores table, projecting only the `name` attribute, deduplicating and sorting, returning `{"stores": [...sorted name strings...]}`.

### handle_edit_receipt (lines 451–494)
- Calls `_validate_edit_body(body)`, fetches the job item, builds an `updates` dict, calls `update_job()`.
- Accepted body fields: `vendor` (string), `receiptDate` (string), `items` (list).
- Vendor update: `updates["vendor"] = dyn_s(str(body["vendor"]))` (line 462).
- **No change needed here** — the vendor value from a `<select>` is still a plain string.

### _validate_edit_body (lines 416–448)
- `vendor`: must be `str`, max 200 chars. Store names from the Overpass scrape are well under this limit.
- `receiptDate`: must match `\d{4}-\d{2}-\d{2}`.
- `items`: list, max 200 entries with per-field validation.
- No `storeCategory` field is accepted. The dropdown should only set `vendor`, not `storeCategory`.

### Environment variables for the API Lambda (from terraform/lambda.tf lines 78–96)
```
DYNAMODB_TABLE, LINE_ITEMS_TABLE, IMAGE_HASHES_TABLE,
UPLOADS_BUCKET, COGNITO_USER_POOL_ID, COGNITO_APP_CLIENT_ID,
PRIMARY_REGION, ALLOWED_ORIGIN, DAILY_UPLOAD_LIMIT, GLOBAL_UPLOAD_LIMIT
```
**`STORES_TABLE` is NOT in the API Lambda's environment.** It is passed only to the Processor and Stores Refresh Lambdas. It must be added to the API Lambda block in `terraform/lambda.tf`.

---

## 3. terraform/api_gateway.tf — Route Registration Pattern

**File:** `/workspace/active_repo/terraform/api_gateway.tf`

### Pattern for a new GET /stores route
Every REST API route needs these 7 resources (using `/receipts` as the reference):

1. `aws_api_gateway_resource` — `path_part = "stores"`, `parent_id = root_resource_id`.
2. `aws_api_gateway_method` (GET) — `authorization = "COGNITO_USER_POOLS"`, `authorizer_id = aws_api_gateway_authorizer.cognito.id`.
3. `aws_api_gateway_integration` (GET) — `type = "AWS_PROXY"`, `integration_http_method = "POST"`, `uri = aws_lambda_function.api_handler.invoke_arn`.
4. `aws_api_gateway_method` (OPTIONS) — `authorization = "NONE"`.
5. `aws_api_gateway_integration` (OPTIONS) — `type = "MOCK"`, `request_templates = { "application/json" = "{\"statusCode\": 200}" }`.
6. `aws_api_gateway_method_response` (OPTIONS 200) — declares the three CORS response header parameter keys.
7. `aws_api_gateway_integration_response` (OPTIONS) — sets CORS header values (origin `'*'`, methods `'GET,OPTIONS'`).

The `aws_api_gateway_deployment.main` `triggers` block (lines 335–352) and `depends_on` list (lines 359–369) **must both be updated** to include the new resource, method, and integration — otherwise Terraform will not force a redeployment when the route is added.

---

## 4. terraform/iam.tf — API Lambda Role Policy

**File:** `/workspace/active_repo/terraform/iam.tf`

### API Lambda role (`lambda_api`) — lines 160–247
The `DynamoDBReadWrite` Sid (lines 192–199) covers only the jobs table and its index. Other statements cover `image_hashes`, `line_items`, and S3.

**The stores table is entirely absent from the API Lambda's policy.**

A new statement must be added to `aws_iam_role_policy.lambda_api`:
```hcl
{
  Sid    = "StoresRead"
  Effect = "Allow"
  Action = ["dynamodb:Scan"]
  Resource = aws_dynamodb_table.stores.arn
}
```
The processor role already has an identical `StoresRead` statement (iam.tf lines 106–110) as a reference.

---

## 5. DynamoDB Stores Table Schema

**File:** `/workspace/active_repo/terraform/dynamodb.tf` (lines 69–88)
- Table name: `${var.project_name}-stores` — deployed as `bedrock-image-ai-stores` with the default `project_name`, or `receipt-scanner-stores` if `project_name` is overridden in tfvars.
- Hash key: `store_id` (String). No range key, no GSI.
- TTL attribute: `expires_at`.

**Attributes written by the stores_refresh lambda** (`/workspace/active_repo/lambda/stores_refresh/handler.py` lines 57–64):
- `store_id`: `"{type}/{id}"` e.g. `"node/12345678"`
- `osm_type`: `"node"` or `"way"`
- `name`: the shop name string (e.g. `"Countdown"`) — this is the value to populate the dropdown
- `shop_type`: OSM `shop` tag (e.g. `"supermarket"`)
- `lat`, `lon`: coordinate strings

**What the processor currently reads from the stores table:** Only the `name` attribute is projected (via `_get_store_names()` in processor handler.py lines 81–95). The new `GET /stores` API handler should use the same projection.

---

## Summary of All Required Changes

### terraform/lambda.tf
- Add `STORES_TABLE = aws_dynamodb_table.stores.name` to the `aws_lambda_function.api_handler` `environment.variables` block (lines 78–96).

### terraform/iam.tf
- Add a `StoresRead` statement to `aws_iam_role_policy.lambda_api` granting `dynamodb:Scan` on `aws_dynamodb_table.stores.arn`.

### terraform/api_gateway.tf
- Add 7 new resources for the `/stores` route following the `/receipts` pattern (resource, GET method, GET integration, OPTIONS method, OPTIONS integration, OPTIONS method_response, OPTIONS integration_response).
- Add the new resource/method/integration IDs to the `aws_api_gateway_deployment.main` `triggers` block and `depends_on` list.

### lambda/api/handler.py
- Add `STORES_TABLE = os.environ.get("STORES_TABLE", "")` near the other env var reads at the top (around line 21).
- Add a `handle_list_stores()` function: paginated `dynamodb.scan()` of `STORES_TABLE` projecting only `#n` (`name`), deduplicate, sort, return `make_response(200, {"stores": sorted_names})`. Return `make_response(200, {"stores": []})` if `STORES_TABLE` is unset.
- Add a routing branch in `_route()`: `if method == "GET" and path.endswith("/stores"): return handle_list_stores()`.

### frontend/app.js.template
- In `showEditModal()`, replace the `<input id="edit-vendor" type="text">` in the `modal.innerHTML` string with a `<select id="edit-vendor">` element (or build it via DOM).
- After the modal is mounted, call `apiFetch(`${CONFIG.apiBaseUrl}/stores`)` to load store names. Populate the `<select>` with one `<option>` per name, plus an initial blank/placeholder option.
- Set the selected option to `job.vendor` if it matches one of the store names; otherwise add a free-text option for the current vendor or fall back gracefully.
- The existing PATCH save code (`modal.querySelector("#edit-vendor").value.trim()`) works unchanged — `select.value` returns the selected option's value identically to `input.value`.
- Show a loading/disabled state while the stores fetch is in-flight; handle fetch errors gracefully (e.g. fall back to a plain text input or show an error message).

---

## Key Side-Effects and Watch-outs

- **STORES_TABLE env var gap:** The API Lambda currently has no `STORES_TABLE` env var. If the handler code references it before the Terraform change is deployed, `os.environ.get("STORES_TABLE", "")` will return `""` and `handle_list_stores()` must handle this gracefully (return empty list, not crash).
- **Table name ambiguity:** `project_name` defaults to `"bedrock-image-ai"` in `variables.tf`, so the stores table is `bedrock-image-ai-stores` in the default deployment, not `receipt-scanner-stores`. Always use `aws_dynamodb_table.stores.name` in Terraform and the `STORES_TABLE` env var in Python — never hardcode.
- **Duplicate names:** The Overpass scrape can produce multiple records with the same shop name (e.g. multiple Countdown branches). The handler must deduplicate the name list before returning it.
- **Empty name values:** `stores_refresh` uses `tags.get("name", "")` — items with no OSM name tag get `name = ""`. Skip empty strings in the scan result.
- **Dropdown UX when vendor is not in the list:** If `job.vendor` was set by OCR and does not exactly match any store name, the dropdown will not pre-select it. Consider adding a free-text option showing the current vendor, or a "Custom..." option that reveals a text input. At minimum, add the current vendor as an option so Save does not silently blank it.
- **Store list size:** The Overpass query covers a 10 km radius — expect tens to low hundreds of results, deduplicated. This is small enough for a simple `<select>` without search/filter, but good to confirm after first data load.
- **Scan cost:** A full table scan runs on every `GET /stores` call. With PAY_PER_REQUEST billing and a small table this is negligible, but consider caching at the module level in the API Lambda (similar to the JWKS cache) to avoid repeated scans on warm invocations.
- **CORS on /stores OPTIONS:** The OPTIONS integration_response for `/stores` must include `'GET,OPTIONS'` in `Access-Control-Allow-Methods` so the browser preflight succeeds.
- **Deployment trigger:** The `aws_api_gateway_deployment.main` `triggers` block uses a `sha1(jsonencode([...ids...]))`. Forgetting to add the new route's IDs there means the stage will not be redeployed after `terraform apply`, and the new route will return 404 in production even though it was created.
