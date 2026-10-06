# Architecture Plan

## Context Summary
Add a store-name autocomplete field to the receipt edit modal. When a user clicks Edit on a receipt, the vendor/store field becomes a text input backed by a `<datalist>` populated from a new `GET /stores` API endpoint, which scans the DynamoDB stores table. Selecting a value and saving uses the existing `PATCH /receipts/{jobId}` path unchanged.

## Impacted Files

### Modified
- `/workspace/active_repo/terraform/lambda.tf` — add `STORES_TABLE` env var to the `aws_lambda_function.api_handler` environment block (lines 78–96).
- `/workspace/active_repo/terraform/iam.tf` — add a `StoresRead` IAM statement (`dynamodb:Scan` on `aws_dynamodb_table.stores.arn`) to `aws_iam_role_policy.lambda_api` (lines 178–247).
- `/workspace/active_repo/terraform/api_gateway.tf` — add 7 new Terraform resources for the `/stores` route, and update the `aws_api_gateway_deployment.main` `triggers` block and `depends_on` list.
- `/workspace/active_repo/lambda/api/handler.py` — add `STORES_TABLE` env var read, a `handle_list_stores()` function, and a routing branch in `_route()`.
- `/workspace/active_repo/frontend/app.js.template` — replace the plain `<input id="edit-vendor">` in the `showEditModal()` `modal.innerHTML` string with an `<input>` + `<datalist>` pair, and add a `GET /stores` fetch after modal mount to populate the datalist.

### New Files
None.

## Step-by-Step Execution Plan

- Step 1 — `terraform/lambda.tf`: Inside the `aws_lambda_function.api_handler` `environment.variables` block (after `GLOBAL_UPLOAD_LIMIT`), add the line:
  ```hcl
  STORES_TABLE = aws_dynamodb_table.stores.name
  ```
  This is the prerequisite for all other changes — without it the Lambda cannot resolve the table name at runtime.

- Step 2 — `terraform/iam.tf`: Inside the `policy` JSON of `aws_iam_role_policy.lambda_api`, append a new statement after the `S3DeleteReceipt` block:
  ```json
  {
    "Sid": "StoresRead",
    "Effect": "Allow",
    "Action": ["dynamodb:Scan"],
    "Resource": "<aws_dynamodb_table.stores.arn reference>"
  }
  ```
  Use the HCL reference `aws_dynamodb_table.stores.arn` (not a string literal) to match the pattern already used in `aws_iam_role_policy.lambda_processor` at lines 106–110.

- Step 3 — `terraform/api_gateway.tf`: Add the following 7 resources directly before the `## Gateway-level responses` comment block. Use the `/receipts` resource block (lines 164–226) as the exact structural template:
  1. `aws_api_gateway_resource.stores` — `path_part = "stores"`, `parent_id = aws_api_gateway_rest_api.main.root_resource_id`.
  2. `aws_api_gateway_method.stores_get` — `http_method = "GET"`, `authorization = "COGNITO_USER_POOLS"`, `authorizer_id = aws_api_gateway_authorizer.cognito.id`.
  3. `aws_api_gateway_integration.stores_get` — `type = "AWS_PROXY"`, `integration_http_method = "POST"` (must be POST for Lambda proxy regardless of route method), `uri = aws_lambda_function.api_handler.invoke_arn`.
  4. `aws_api_gateway_method.stores_options` — `http_method = "OPTIONS"`, `authorization = "NONE"`.
  5. `aws_api_gateway_integration.stores_options` — `type = "MOCK"`, `request_templates = { "application/json" = "{\"statusCode\": 200}" }`.
  6. `aws_api_gateway_method_response.stores_options_200` — `status_code = "200"`, three `response_parameters` keys set to `true`: `method.response.header.Access-Control-Allow-Headers`, `method.response.header.Access-Control-Allow-Methods`, `method.response.header.Access-Control-Allow-Origin`.
  7. `aws_api_gateway_integration_response.stores_options` — `response_parameters` must set:
     - `method.response.header.Access-Control-Allow-Origin = "'*'"` (or the configured origin)
     - `method.response.header.Access-Control-Allow-Methods = "'GET,OPTIONS'"`
     - `method.response.header.Access-Control-Allow-Headers = "'Content-Type,Authorization,X-Amz-Date,X-Api-Key'"`

     The `Access-Control-Allow-Headers` value `'Content-Type,Authorization,X-Amz-Date,X-Api-Key'` must match exactly the value used in every other OPTIONS integration response in the file (lines 84, 156, 222, 305).

- Step 4 — `terraform/api_gateway.tf` (continued): Update `aws_api_gateway_deployment.main`:
  - In the `triggers.redeployment` `sha1(jsonencode([...]))` list, append:
    ```
    aws_api_gateway_resource.stores.id,
    aws_api_gateway_method.stores_get.id,
    aws_api_gateway_integration.stores_get.id,
    ```
  - In the `depends_on` list, append:
    ```
    aws_api_gateway_integration.stores_get,
    aws_api_gateway_integration.stores_options,
    ```

- Step 5 — `lambda/api/handler.py`: After the existing env var block (around line 28), add:
  ```python
  STORES_TABLE = os.environ.get("STORES_TABLE", "")
  ```
  This must use `.get()` with a default of `""` so the Lambda does not crash on cold start if deployed before Step 1 is applied.

- Step 6 — `lambda/api/handler.py`: Add a module-level stores cache variable immediately after the `STORES_TABLE` line:
  ```python
  _STORES_CACHE: list[str] | None = None
  ```
  Use uppercase `_STORES_CACHE` to match the naming convention established by the processor Lambda at `lambda/processor/handler.py` line 71.

  Then add the `handle_list_stores()` function before `_route()`. Model the scan loop on the processor's `_get_store_names()` (processor/handler.py lines 74–96), but with one critical addition: after collecting all names from the paginated scan, apply `sorted(set(...))` before assigning to `_STORES_CACHE`. The processor's version stores a raw unsorted list without deduplication; copying it verbatim would produce unsorted, potentially duplicated names in the API response. The corrected function must:
  - Declare `global _STORES_CACHE`.
  - If `_STORES_CACHE is not None`, return the cached result immediately.
  - If `STORES_TABLE` is empty, return `make_response(200, {"stores": []})` immediately.
  - Run the paginated `dynamodb.scan()` using `ProjectionExpression = "#n"` and `ExpressionAttributeNames = {"#n": "name"}`, stripping whitespace and filtering empty strings.
  - Apply `_STORES_CACHE = sorted(set(names))` before returning.
  - Return `make_response(200, {"stores": _STORES_CACHE})`.

- Step 7 — `lambda/api/handler.py`: In `_route()`, add a new branch before the final `return make_response(404, ...)` line:
  ```python
  if method == "GET" and path.endswith("/stores"):
      return handle_list_stores()
  ```
  Note: `handle_list_stores()` takes no `user_id` argument because stores are global (not user-scoped) — every authenticated user sees the same list. Authentication is still enforced at the Lambda entry point in `lambda_handler()` before `_route()` is ever called, so the omission of `user_id` is deliberate and safe, not an oversight.

  Also note this branch must be added carefully — it cannot match before the `/receipts` branch, and path-based matching is already done by `endswith`, so there is no collision risk.

- Step 8 — `frontend/app.js.template`: In the `modal.innerHTML` template string inside `showEditModal()` (around line 507), replace the vendor `<input>` element:

  From:
  ```html
  <input id="edit-vendor" type="text" style="width:100%;padding:0.4rem;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
  ```

  To:
  ```html
  <input id="edit-vendor" type="text" list="store-options" placeholder="Loading stores..." autocomplete="off" style="width:100%;padding:0.4rem;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
  <datalist id="store-options"></datalist>
  ```

  The `list="store-options"` attribute wires the native browser autocomplete. The placeholder serves as the loading indicator. No other change to the modal shell is needed.

- Step 9 — `frontend/app.js.template`: The existing `modal.querySelector("#edit-vendor").value = job.vendor || ""` line (around line 527) sets the vendor value after the modal innerHTML is set — this remains correct and should stay in place. After the `overlay.appendChild(modal)` / `document.body.appendChild(overlay)` lines (around line 531), add an async stores fetch to populate the datalist:
  ```javascript
  // Populate store name datalist from GET /stores
  apiFetch(`${CONFIG.apiBaseUrl}/stores`)
    .then(r => r.json())
    .then(data => {
      const dl = modal.querySelector("#store-options");
      const vendorInput = modal.querySelector("#edit-vendor");
      if (!dl) return;
      const names = (data.stores || []);
      names.forEach(n => {
        const opt = document.createElement("option");
        opt.value = n;
        dl.appendChild(opt);
      });
      if (vendorInput) vendorInput.placeholder = "";
    })
    .catch(() => {
      const vendorInput = modal.querySelector("#edit-vendor");
      if (vendorInput) vendorInput.placeholder = "";
    });
  ```
  DOM element creation (`document.createElement("option")` + `opt.value = n`) is used instead of `innerHTML` with template literals. Store names originate from OpenStreetMap via the Overpass scrape and can contain characters such as `"`, `<`, `>`, and `&` that would be interpreted as HTML markup if interpolated into an `innerHTML` string. Using DOM methods eliminates this XSS surface entirely.

  The existing `.value` assignment on line 527 already runs before this fetch and is unaffected. The datalist population does not reset `.value`.

- Step 10 — Rebuild and deploy: Run `make deploy` to (a) repackage the API Lambda zip with the updated `handler.py`, (b) apply the Terraform changes (new IAM statement, new env var, new API Gateway route, forced redeployment), and (c) inject the frontend config into `app.js`.

## Risks & Blockers

- **`integration_http_method` must be `"POST"` for Lambda proxy**: Setting it to `"GET"` on the `stores_get` integration causes silent failures. The existing routes all use `"POST"` correctly — the new route must follow the same pattern.
- **Deployment trigger omission**: If the new route's resource/method/integration IDs are not added to `aws_api_gateway_deployment.main.triggers`, Terraform will create the route resources but not redeploy the stage, and `GET /stores` will return 404 in production. Steps 3 and 4 address this explicitly.
- **`name` is a DynamoDB reserved word**: The scan in `handle_list_stores()` must use `ExpressionAttributeNames = {"#n": "name"}` with `ProjectionExpression = "#n"`. Omitting this causes a `ValidationException` at runtime. The processor's `_get_store_names()` already demonstrates the correct pattern.
- **Table name ambiguity**: The stores table name depends on the `project_name` Terraform variable (defaults to `"bedrock-image-ai"`, not `"receipt-scanner"`). Always reference `aws_dynamodb_table.stores.name` in Terraform and `STORES_TABLE` env var in Python — never hardcode either name.
- **STORES_TABLE env var gap on partial deploy**: If the Lambda code is deployed before the Terraform env var is applied, `os.environ.get("STORES_TABLE", "")` returns `""` and `handle_list_stores()` must return an empty list rather than raise a `KeyError`. Step 5 uses `.get()` with a default for exactly this reason.
- **Stores cache in API Lambda**: The module-level `_STORES_CACHE` added in Step 6 mirrors the processor pattern. On a warm invocation the cached list is returned without a DynamoDB scan. On cold start or Lambda recycle it is refreshed. This is appropriate given the weekly stores refresh cadence. The cache holds a sorted, deduplicated list (unlike the processor's raw list) so the same invariant is maintained across all warm invocations.
- **CORS `Access-Control-Allow-Headers` must match all other routes**: Every existing OPTIONS integration response in `api_gateway.tf` sets `Access-Control-Allow-Headers` to `'Content-Type,Authorization,X-Amz-Date,X-Api-Key'`. The new `stores_options` integration response must use this exact value or browsers may reject preflight responses for the `/stores` route while accepting them for all other routes.

## Testing Strategy

1. **Lambda console integration test**: In the AWS Lambda console, create a test event with body `{"httpMethod": "GET", "path": "/stores", "headers": {"Authorization": "Bearer <valid-id-token>"}, "pathParameters": null, "queryStringParameters": null}` and invoke the `api_handler` function directly. Confirm the response body contains `{"stores": [...sorted, deduplicated name strings...]}` and that an empty string is not present. This requires a live Lambda with `STORES_TABLE` set and DynamoDB accessible — it is a Lambda console integration test, not a unit test.

2. **Terraform plan**: Run `make plan` and confirm the plan shows exactly the expected new resources: one `aws_api_gateway_resource`, two `aws_api_gateway_method`, two `aws_api_gateway_integration`, one `aws_api_gateway_method_response`, one `aws_api_gateway_integration_response`, one modified `aws_iam_role_policy.lambda_api`, one modified `aws_lambda_function.api_handler` (env vars), and one replaced `aws_api_gateway_deployment.main`.

3. **Post-deploy smoke test**: After `make deploy`, run:
   ```
   curl -H "Authorization: Bearer <valid-id-token>" \
        https://<api-base-url>/v1/stores
   ```
   Expect HTTP 200 with `{"stores": [...]}`. A 403 means the IAM statement was not applied. A 404 means the deployment trigger was not updated. A 500 with a DynamoDB error mentioning `name` means the reserved-word workaround is missing.

4. **CORS preflight**: Run:
   ```
   curl -X OPTIONS \
        -H "Origin: https://<cloudfront-domain>" \
        -H "Access-Control-Request-Method: GET" \
        https://<api-base-url>/v1/stores
   ```
   Expect HTTP 200 with `Access-Control-Allow-Methods: GET,OPTIONS` and `Access-Control-Allow-Headers: Content-Type,Authorization,X-Amz-Date,X-Api-Key` in the response headers.

5. **Frontend integration**: Open the app in a browser, click Edit on any COMPLETE receipt, and verify:
   - The vendor field shows the current vendor value.
   - Typing in the vendor field shows matching store names from the datalist.
   - Selecting a store name and clicking Save sends the selected name as `vendor` in the PATCH body and the history card updates to reflect the change.
   - If `GET /stores` fails (e.g. network error), the vendor field remains a usable free-text input with no JS error.

---

**IMPORTANT — handoff to main agent:** This plan is now written to `claude-context-plan.md`. The Plan Reviewer agent MUST be run next before any implementation begins. No source files should be modified until the Reviewer has issued its verdict.
