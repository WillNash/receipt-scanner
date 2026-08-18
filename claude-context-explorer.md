# Claude Context Explorer — Flutter Mobile Client Research

## All .tf files present

/workspace/active_repo/terraform/api_gateway.tf
/workspace/active_repo/terraform/cloudfront.tf
/workspace/active_repo/terraform/cognito.tf
/workspace/active_repo/terraform/dynamodb.tf
/workspace/active_repo/terraform/iam.tf
/workspace/active_repo/terraform/lambda.tf
/workspace/active_repo/terraform/outputs.tf
/workspace/active_repo/terraform/providers.tf
/workspace/active_repo/terraform/s3.tf
/workspace/active_repo/terraform/sqs.tf
/workspace/active_repo/terraform/variables.tf

## Files read

- /workspace/active_repo/terraform/cognito.tf
- /workspace/active_repo/terraform/api_gateway.tf
- /workspace/active_repo/terraform/variables.tf
- /workspace/active_repo/terraform/outputs.tf
- /workspace/active_repo/terraform/terraform.tfvars.example
- /workspace/active_repo/terraform/terraform.tfvars  (actual deployed values)
- /workspace/active_repo/lambda/api/handler.py
- /workspace/active_repo/frontend/app.js.template

---

## Cognito

| Property | Value |
|---|---|
| User pool name | `bedrock-image-ai-users` (var.project_name + "-users") |
| User pool ID (runtime output) | `aws_cognito_user_pool.main.id` — emitted as Terraform output `cognito_user_pool_id` |
| App client name | `bedrock-image-ai-client` |
| App client ID (runtime output) | emitted as Terraform output `cognito_client_id` |
| Client secret | NONE (`generate_secret = false`) — safe for public mobile/SPA clients |
| Region | `ap-southeast-2` |
| Domain prefix (deployed) | `bedrock-image-ai-025423` |
| Hosted UI base URL | `https://bedrock-image-ai-025423.auth.ap-southeast-2.amazoncognito.com` |
| OAuth flows | `code` (Authorization Code flow only) |
| OAuth scopes | `email`, `openid`, `profile` |
| Identity providers | `COGNITO` (no social/federated IdPs) |
| Callback URL | `https://<cloudfront_domain>/callback` |
| Logout URL | `https://<cloudfront_domain>/` |
| Auto-verified attributes | `email` |
| Token: access_token validity | 60 minutes |
| Token: id_token validity | 60 minutes |
| Token: refresh_token validity | 30 days |
| JWKS endpoint | `https://cognito-idp.ap-southeast-2.amazonaws.com/<pool_id>/.well-known/jwks.json` |
| Password policy | min 8 chars, uppercase + lowercase + numbers required, symbols NOT required |

### Token endpoint (for code exchange)
`https://bedrock-image-ai-025423.auth.ap-southeast-2.amazoncognito.com/oauth2/token`

Token exchange is `POST`, `Content-Type: application/x-www-form-urlencoded`, body fields:
- `grant_type=authorization_code`
- `client_id=<client_id>`
- `code=<auth_code>`
- `redirect_uri=<redirect_uri>`

Note: for Flutter you must supply your own redirect URI (not the CloudFront one). The Cognito app client will need an additional callback URL added for your Flutter deep-link scheme (e.g. `com.example.app://callback`). This requires a Terraform change and redeploy.

---

## API Gateway

| Property | Value |
|---|---|
| API name | `bedrock-image-ai-api` |
| Type | REST API (v1), REGIONAL endpoint |
| Stage name | `v1` |
| Invoke URL pattern | `https://<api_id>.execute-api.ap-southeast-2.amazonaws.com/v1` |
| Terraform output key | `api_invoke_url` |

### Rate limits (applied at stage level)

| Scope | Rate (req/s) | Burst |
|---|---|---|
| All methods (`*/*`) | 10 | 20 |
| `POST /upload-url` only | 2 | 5 |

---

## API Endpoints

### 1. POST /upload-url

**Auth:** Bearer token (Cognito id_token) required in `Authorization` header. Validated by Lambda via JWKS/RS256. Returns 401 if missing or invalid.

**Authorization header format:** `Authorization: Bearer <id_token>`

**Request body (JSON):**
```json
{ "contentType": "image/jpeg" }
```
Supported values: `"image/jpeg"`, `"image/png"`. Any other value returns 400.

**Success response 200:**
```json
{
  "jobId": "<uuid>",
  "uploadUrl": "<presigned S3 PUT URL, valid 300 seconds>",
  "s3Key": "uploads/<user_sub>/<job_id>.<ext>"
}
```

**Error responses:**
- `400` — unsupported content type
- `401` — missing/invalid Bearer token
- `429` — global upload limit reached (100 total) OR daily per-user limit reached (50/day)

---

### 2. PUT <uploadUrl> (direct to S3 — not via API Gateway)

After receiving `uploadUrl` from the above endpoint, the client PUTs the image file directly to S3.

**Request:**
- Method: `PUT`
- URL: the full presigned URL from `uploadUrl`
- Header: `Content-Type: image/jpeg` (or `image/png` — must match what was requested)
- Body: raw image bytes
- No Authorization header (presigned URL carries auth)
- URL expires in 300 seconds (5 minutes)

**Success:** HTTP 200 with empty body from S3.

---

### 3. GET /jobs/{jobId}

**Auth:** Bearer token required. Returns 403 if the job belongs to a different user.

**Path parameter:** `jobId` (UUID string)

**Success response 200 — job object:**
```json
{
  "jobId": "string",
  "status": "PENDING | COMPLETE | FAILED",
  "vendor": "string | null",
  "receiptDate": "string | null",
  "total": "string | null",
  "items": [
    {
      "description": "string",
      "quantity": "string",
      "unit_price": "string",
      "price": "string",
      "discount": "string | null"
    }
  ],
  "debugUrl": "presigned S3 GET URL (1 hour) | null",
  "createdAt": "ISO8601 UTC string",
  "updatedAt": "ISO8601 UTC string"
}
```

**Error responses:**
- `400` — jobId missing
- `401` — unauthorized
- `403` — job belongs to another user
- `404` — job not found

**Polling strategy (from frontend):** poll every 3000 ms, maximum 60 attempts (3 minutes total). Stop when `status` is `"COMPLETE"` or `"FAILED"`.

---

### 4. GET /receipts

**Auth:** Bearer token required.

**No query parameters.** Returns last 20 jobs for the authenticated user, sorted newest-first (DynamoDB GSI `user-jobs-index`, `ScanIndexForward=False`, `Limit=20`).

**Success response 200:**
```json
{
  "receipts": [ /* array of job objects — same shape as GET /jobs/{jobId} */ ]
}
```

---

## CORS Headers

All endpoints return these CORS headers (set by Lambda in every response, including OPTIONS preflight):

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type,Authorization
Access-Control-Allow-Methods: GET,POST,OPTIONS
Content-Type: application/json
```

OPTIONS is handled at Lambda level (returns 200 immediately before auth check). API Gateway also injects CORS headers on its own 4xx/5xx gateway errors via `aws_api_gateway_gateway_response`.

Note: `Access-Control-Allow-Headers` in the Lambda response is `Content-Type,Authorization`. The API Gateway OPTIONS integration response additionally lists `X-Amz-Date,X-Api-Key`. For a mobile client this is irrelevant — just send `Authorization` and `Content-Type`.

---

## Auth Flow for Flutter

The Lambda validates **id_token** (not access_token) — it reads `sub` and `email` claims. The frontend stores and uses `id_token` as the Bearer token. Flutter should do the same.

JWT validation in Lambda:
- Algorithm: RS256
- JWKS URL: `https://cognito-idp.ap-southeast-2.amazonaws.com/<pool_id>/.well-known/jwks.json`
- `verify_aud` is disabled (no audience check)
- `verify_at_hash` is disabled
- `sub` claim used as user_id
- `email` claim used as user_email

---

## Presigned URL Upload Flow (step by step)

1. Client obtains Cognito id_token via Authorization Code + PKCE flow.
2. Client calls `POST /upload-url` with `Authorization: Bearer <id_token>` and JSON body `{"contentType": "image/jpeg"}`.
3. Lambda validates token, checks rate limits, creates a DynamoDB job record with status `PENDING`, generates a presigned S3 PUT URL (expires 300 s).
4. Lambda returns `{"jobId": "...", "uploadUrl": "...", "s3Key": "..."}`.
5. Client PUTs the raw image bytes to `uploadUrl` with `Content-Type: image/jpeg` header. No auth header needed. S3 URL is pre-authenticated.
6. S3 event triggers the processor Lambda which runs Textract, updates DynamoDB job with `COMPLETE`/`FAILED` status and parsed receipt fields.
7. Client polls `GET /jobs/{jobId}` every 3 s (max 60 polls / 3 min) until status is `COMPLETE` or `FAILED`.
8. On completion, client reads `vendor`, `receiptDate`, `total`, `items` from the job response.

---

## Key Variables (deployed values from terraform.tfvars)

| Variable | Deployed Value |
|---|---|
| project_name | `bedrock-image-ai` |
| aws_account_id | `097583025423` |
| cognito_domain_prefix | `bedrock-image-ai-025423` |
| primary_region | `ap-southeast-2` |
| environment | `demo` |
| daily_upload_limit | `50` (default) |
| global_upload_limit | `100` (default) |

---

## Side Effects / Caveats for Flutter Integration

1. **Redirect URI must be added to Cognito app client.** The current `callback_urls` only contains the CloudFront URL. For Flutter, a custom scheme URI (e.g. `com.example.receipts://callback`) must be added — this requires a Terraform change and redeploy.
2. **No client secret.** `generate_secret = false`, so PKCE is the correct flow — do not expect or send a client_secret.
3. **id_token, not access_token.** The Lambda extracts `sub` and `email` from the Bearer token using JWKS. Cognito id_tokens carry `email`; access_tokens may not. Use id_token.
4. **Token lifetime.** id_token expires in 60 minutes. Flutter must handle token refresh using the refresh_token (30-day validity) via the Cognito token endpoint with `grant_type=refresh_token`.
5. **File size.** Backend does not enforce a size limit — the 20 MB cap is frontend-only. S3 presigned PUT has no explicit size constraint set in this code.
6. **Accepted MIME types.** Only `image/jpeg` and `image/png` — HEIC conversion is done client-side in the web app before upload. Flutter must do the same conversion before calling `/upload-url`.
7. **Rate limits.** Global cap: 100 uploads ever. Per-user daily cap: 50/day. Both return HTTP 429.
8. **JWKS cached per Lambda container.** No impact on client, but cold starts will fetch JWKS — first request may be slightly slower.
