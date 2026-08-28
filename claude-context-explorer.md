# Context Explorer Findings

## Task
Summarise API response fields, DynamoDB line_item fields, and frontend composable structure for the receipt scanner app.

---

## 1. GET /receipts and GET /jobs/{jobId} — API Response Fields

Source: `/workspace/active_repo/lambda/api/handler.py`, `format_receipt()` (line 504–545)

Both endpoints return the same shape via `format_receipt()`. The only difference is:
- **GET /receipts** (list): `include_urls=False` — `debugUrl`, `textractDebugUrl`, `croppedImageUrl` are always `null`
- **GET /jobs/{jobId}** (single): `include_urls=True` — those three fields are populated with presigned S3 URLs

### Returned JSON fields (camelCase, sent to frontend)

| Field | Type | Notes |
|---|---|---|
| `jobId` | string | UUID |
| `status` | string | PENDING / PROCESSING / COMPLETE / FAILED / DUPLICATE |
| `storeCategory` | string or null | e.g. "grocery", "other" |
| `vendor` | string or null | |
| `receiptDate` | string or null | ISO date string |
| `total` | string or null | |
| `items` | array | Parsed from `items` JSON column — see item fields below |
| `priceCheckWarning` | boolean | |
| `priceCheckMessage` | string or null | |
| `debugUrl` | string or null | Presigned S3 URL — only from single-job endpoint |
| `textractDebugUrl` | string or null | Presigned S3 URL — only from single-job endpoint |
| `croppedImageUrl` | string or null | Presigned S3 URL — only from single-job endpoint |
| `hasCroppedImage` | boolean | True if cropped_s3_key exists — available from both endpoints |
| `createdAt` | string | ISO datetime |
| `updatedAt` | string or null | ISO datetime |

### items array — per-item fields (from Bedrock/Textract extraction, no fixed schema enforced)

Fields accessed in `ReceiptCard.vue` and `_validate_edit_body`:
- `description` (string)
- `quantity` (string)
- `unit_price` (string)
- `price` (string)
- `discount` (string, optional)
- `package_size` (string, optional — displayed in ReceiptCard)

Additional fields written to `line_items` DynamoDB table (may be present in items array):
- `line_total` (string)
- `item_category` (string)
- `nova_group` (integer 1–4, optional)

---

## 2. DynamoDB line_items Table — Written Fields

Source: `/workspace/active_repo/lambda/shared/line_items.py`

Table PK: `user_id` (S), SK: `item_sk` (S, format: `{created_at}#{job_id}#{index:03d}`)

| Field | DynamoDB type | Source |
|---|---|---|
| `user_id` | S | from LineItemContext |
| `item_sk` | S | composite: `created_at#job_id#index` |
| `job_id` | S | from LineItemContext |
| `description` | S | from item dict |
| `desc_created` | S | composite: `description#created_at` (GSI key) |
| `email` | S | from LineItemContext |
| `vendor` | S | from LineItemContext |
| `receipt_date` | S | from LineItemContext |
| `store_category` | S | from LineItemContext |
| `created_at` | S | from LineItemContext |
| `expires_at` | N | from LineItemContext |
| `quantity` | N | optional, from item |
| `unit_price` | N | optional, from item |
| `line_total` | N | optional, from item |
| `price` | N | optional, from item |
| `discount` | N | optional, from item |
| `package_size` | S | optional, from item |
| `item_category` | S | from item, clamped to VALID_ITEM_CATEGORIES or "other" |
| `nova_group` | N | optional int 1–4, from item |

---

## 3. DynamoDB jobs Table — Written Fields (processor)

Source: `/workspace/active_repo/lambda/processor/handler.py`, `_process_s3_record()` (line 153–168)

On COMPLETE:
- `status` = "COMPLETE"
- `store_category` (S)
- `price_check_warning` (BOOL)
- `price_check_message` (S)
- `vendor` (S)
- `receipt_date` (S)
- `total` (S)
- `items` (S) — JSON-serialised list
- `debug_s3_key` (S)
- `textract_debug_s3_key` (S)
- `cropped_s3_key` (S) — optional, only if cropping was applied
- `image_hash` (S)
- `updated_at` (S)
- `expires_at` (N)

---

## 4. Frontend — HistorySection.vue

Source: `/workspace/active_repo/frontend/src/components/HistorySection.vue`

- Fetches `GET /receipts` on `onMounted`, stores result in `receipts` ref
- Renders one `ReceiptCard` per receipt, passing `job` and `show-actions=true`
- Opens `EditModal` when a card emits `edit`
- Reloads history after a successful edit save
- No filtering, sorting, or pagination — renders whatever the API returns (up to 20 items per RECEIPTS_PAGE_SIZE)

---

## 5. Frontend — ReceiptCard.vue

Source: `/workspace/active_repo/frontend/src/components/ReceiptCard.vue`

Fields accessed from `job` prop:
- `job.status` — controls which card variant renders
- `job.vendor` — header
- `job.total` — header
- `job.receiptDate` — formatted via `formatDate()`
- `job.storeCategory` — badge (underscores replaced with spaces)
- `job.priceCheckWarning` / `job.priceCheckMessage` — warning banner
- `job.items[]` — table rows; accesses `description`, `package_size`, `quantity`, `unit_price`, `discount`, `price`
- `job.jobId` — used in lazy URL fetch and keying
- `job.hasCroppedImage` — shows "Cropped image" button
- `job.debugUrl`, `job.textractDebugUrl`, `job.croppedImageUrl` — lazy-loaded from single-job endpoint on first action click
- `job.reason` — used in FAILED message (not returned by API currently — would always be undefined)

---

## 6. Frontend Composables

### /workspace/active_repo/frontend/src/composables/useApi.js
Single exported function `apiFetch(url, options)`:
- Adds `Authorization: Bearer <id_token>` header to every request
- On 401, attempts a token refresh via `refreshTokens()`, then retries once
- On refresh failure, calls `logout()`
- Not a Vue composable (no reactive state) — it is a plain async utility

### /workspace/active_repo/frontend/src/composables/useAuth.js
Exports:
- `getToken()` — reads `id_token` from `sessionStorage`
- `logout()` — clears sessionStorage, redirects to Cognito logout URL
- `exchangeCode(code)` — trades OAuth2 auth code for tokens, stores all three token types in sessionStorage
- `refreshTokens()` — uses refresh_token to get new id_token + access_token, updates sessionStorage

No Vue reactivity in either composable — both are plain JS module exports.

---

## Key Observations for the Main Agent

1. **vue-router is NOT installed.** `package.json` only has `vue`, `vite`, `@vitejs/plugin-vue`, and `vite-plugin-wasm`. Any routing/navigation work would require installing `vue-router` first.

2. **No sort or filter exists yet.** `HistorySection.vue` renders the raw API array. The API itself only supports one page of 20 COMPLETE records sorted by `created_at` descending (GSI `ScanIndexForward: false`). There is no query-string support for filtering by vendor/date/category.

3. **storeCategory** and **receiptDate** are the most natural filter fields available in the list response — they come through for every COMPLETE record.

4. **item-level fields** (`item_category`, `nova_group`, `package_size`) are stored in the `line_items` table but are NOT returned by `GET /receipts` or `GET /jobs/{jobId}` — they are only in the `items` JSON blob if Bedrock extracted them.

5. **URL fields are null in list responses** — `ReceiptCard` already handles this correctly with its lazy-fetch pattern (`fetchUrls()` on first action click).

6. **`apiFetch` is provided via Vue `inject`** in both `HistorySection` and `ReceiptCard` — the provider is in a parent component (likely `App.vue`), not imported directly.
