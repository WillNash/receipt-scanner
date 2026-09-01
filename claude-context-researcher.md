# Research Findings — Store Dropdown & API Gateway Route

## Sources
- [MDN: datalist element](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/datalist)
- [Formspree: Complete Guide to select and Custom Dropdowns](https://formspree.io/blog/html-dropdown-menu/)
- [cloudonaut: CORS on API Gateway with Lambda proxy integration](https://cloudonaut.io/how-to-enable-cors-on-api-gateway-with-lambda-proxy-integration/)
- [7ton shark: API Gateway v1 in Terraform](https://7tonshark.com/posts/terraform-api-gateway/)
- [DevOps Daily: Fix Terraform Not Deploying API Gateway Stage](https://devops-daily.com/posts/terraform-api-gateway-stage-not-deploying)

---

## 1. Dropdown approach for ~200 store names in vanilla JS

**Native `<select>`:** Handles keyboard navigation, screen reader, and mobile OS picker automatically. Typing a letter jumps to first match — coarse, not filtering. Poor UX for 200 options.

**`input[type=text] + datalist`:** Browser natively filters `<option>` values as user types. Zero JS needed for filtering. Input remains open-ended (no enforcement). Cannot be styled. Substring vs prefix filtering behaviour varies by browser. Recommended for this project — lowest complexity for 200 options.

**Custom JS dropdown:** Full control, but you own all edge cases (focus, keyboard, ARIA, scroll). Only worth it if styling requirements demand it.

**Recommendation:** Use `input[type=text] + datalist`. The PATCH endpoint accepts any vendor string, so open-ended input is fine.

---

## 2. datalist pattern

```html
<label for="edit-vendor">Store / Vendor</label>
<input type="text" id="edit-vendor" list="store-options"
       placeholder="Type to search or enter custom name..."
       autocomplete="off">
<datalist id="store-options">
  <!-- options injected by JS from GET /stores -->
</datalist>
```

JS to populate:
```javascript
function populateStoreDatalist(names) {
  const dl = document.getElementById("store-options");
  dl.innerHTML = names.map(n => `<option value="${n}"></option>`).join("");
}
```

- No enforcement needed — the PATCH endpoint accepts free-text vendor.
- The existing `modal.querySelector("#edit-vendor").value.trim()` read in the PATCH save path works unchanged — `select`, `input`, and datalist-backed input all expose `.value` the same way.

---

## 3. API Gateway REST — adding GET /stores in Terraform

Resources required per new route:
- `aws_api_gateway_resource` — one per new path segment
- `aws_api_gateway_method` (GET) + `aws_api_gateway_integration` (AWS_PROXY → Lambda)
- `aws_api_gateway_method` (OPTIONS) + MOCK integration + method_response + integration_response (for CORS)

**Integration HTTP method for Lambda proxy must always be `"POST"` regardless of the `http_method` on the method.** Setting it to `"GET"` silently fails.

**Redeployment:** New resources/methods do NOT automatically redeploy the stage. The `triggers` block on `aws_api_gateway_deployment` must include the new resource/method/integration IDs. Without this the new route returns 404 in production after apply.

**`create_before_destroy = true` on the deployment** is critical — without it there is a brief downtime window.

---

## 4. CORS for new routes

Per-resource OPTIONS must be added unless a catch-all `{cors+}` resource already exists at the root. The Lambda already returns CORS headers in every response, so only the preflight OPTIONS needs the MOCK integration.

OPTIONS MOCK pattern:
```hcl
resource "aws_api_gateway_method" "stores_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.stores.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}
resource "aws_api_gateway_integration" "stores_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.stores.id
  http_method = aws_api_gateway_method.stores_options.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}
resource "aws_api_gateway_method_response" "stores_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.stores.id
  http_method = aws_api_gateway_method.stores_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
  response_models = { "application/json" = "Empty" }
}
resource "aws_api_gateway_integration_response" "stores_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.stores.id
  http_method = aws_api_gateway_method.stores_options.http_method
  status_code = aws_api_gateway_method_response.stores_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}
```

---

## 5. Gotchas

- `integration_http_method` must be `"POST"` for Lambda proxy — never `"GET"`.
- `depends_on` alone does NOT trigger redeployment. Only the `triggers` map does.
- datalist does not enforce value — open-ended is fine for vendor since PATCH accepts any string.
- `name` is a DynamoDB reserved word — requires `ExpressionAttributeNames = {"#n": "name"}` in scan.
- Items with `name = ""` must be filtered out before returning from GET /stores.
- Deduplicate store names before returning (multiple OSM nodes may share a name).
- The existing `modal.querySelector("#edit-vendor").value.trim()` in the PATCH save path works unchanged with a datalist-backed input.
