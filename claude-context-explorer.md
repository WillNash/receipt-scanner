# Codebase Structural Hotspot Analysis

_Generated: 2026-08-24. Branch: next-steps._

---

## Files Surveyed

| File | Lines | Role |
|---|---|---|
| `lambda/processor/handler.py` | 878 | Receipt processing Lambda |
| `lambda/api/handler.py` | 566 | REST API Lambda |
| `frontend/app.js.template` | 884 | Vanilla JS SPA (source of truth) |
| `lambda/processor/line_grouping.py` | 89 | Textract row-grouping algorithm |
| `scripts/visualize_textract.py` | 722 | Dev-tool: Textract block graph |
| `scripts/export_receipts.py` | 126 | Dev-tool: DynamoDB CSV export |
| `scripts/inject_config.py` | 123 | Build-step: config injection + S3 sync |
| `mobile_new/lib/features/receipts/presentation/screens/receipts_screen.dart` | 484 | Flutter receipts screen + edit sheet |
| `mobile_new/lib/features/upload/presentation/screens/upload_screen.dart` | 413 | Flutter upload screen |
| `mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart` | 236 | Flutter upload state/logic |
| `mobile_new/lib/features/receipts/presentation/view_models/receipts_view_model.dart` | 92 | Flutter receipts state |
| `mobile_new/lib/core/network/api_client.dart` | 33 | Dio HTTP client with auth interceptor |
| `mobile_new/lib/features/auth/data/repositories/auth_repository.dart` | 93 | Token storage + refresh |
| `mobile_new/lib/features/upload/data/services/upload_service.dart` | 76 | Upload HTTP service |
| `mobile_new/lib/features/receipts/data/models/receipt.dart` | 75 | ReceiptJob + LineItem models |

---

## Hotspot Rankings

### 1. `lambda/processor/handler.py` — HIGHEST COMPLEXITY

**What it does:** SQS consumer that orchestrates the full receipt pipeline — image download, SHA-256 dedup check, JPEG normalisation, OpenCV cropping (three detection methods), skew detection and correction, Textract OCR, Bedrock/Claude LLM extraction, price validation and correction, debug artefact upload to S3, and DynamoDB writes across three tables.

**Concerns (mixed responsibility — at least 8 distinct concerns):**
1. SQS event parsing and per-record error handling (`lambda_handler`, `process_record`)
2. Image format normalisation (`_to_jpeg`)
3. Image cropping with three ranked detection strategies (`crop_receipt`, `_find_receipt`, `_bright_region`, `_edge_contour`, `_mser_density`)
4. Skew/deskew pipeline (`_compute_skew_angle`, `_deskew_correction`, `_deskew_image`)
5. Textract orchestration and row grouping (`_textract_lines`, delegating to `line_grouping.py`)
6. Bedrock/Claude prompt construction and tool-call extraction — the prompt string in `analyze_receipt` is 60+ lines of inline text
7. Post-extraction validation and price correction (`_validate_classification`, `_fix_weighted_item_prices`, `_verify_price_sum`)
8. Debug artefact serialisation and S3 upload (`save_debug`, `_debug_block_list`)
9. DynamoDB writes for jobs, image hashes, and line items (`update_job`, `store_image_hash`, `write_line_items`)

**Coupling:** Directly calls boto3 clients for S3, DynamoDB, Textract, and Bedrock. Imports `line_grouping.group_blocks` as the only external module. The `to_n()` helper (DynamoDB numeric value formatter) is defined twice: once inside `_replace_line_items` in api/handler.py, and once inside `write_line_items` here — exact duplication.

**Structural issues:**
- `analyze_receipt` is ~145 lines and mixes OCR, LLM, validation, and S3 debug writes in one function. It is the single most tangled function in the codebase.
- The 60-line Bedrock prompt is an inline string literal with no abstraction layer.
- `RECEIPT_TOOL` (the Bedrock tool schema) is a 115-line module-level dict — essentially a config artefact embedded in code.
- `process_record` does the full dedup check, status transitions, and final DynamoDB writes inline; it is 80 lines long.
- `_to_float` is defined at module scope but `to_n()` (its DynamoDB-writing counterpart) is redefined as a nested function inside both `write_line_items` and (in api/handler.py) `_replace_line_items`.

---

### 2. `lambda/api/handler.py` — HIGH COMPLEXITY

**What it does:** REST API Lambda routing five HTTP routes (`POST /upload-url`, `GET /receipts`, `GET /jobs/{id}`, `DELETE /receipts/{id}`, `PATCH /receipts/{id}`). Also handles JWT validation, rate limiting, duplicate detection, presigned URL generation, line-item sync on edit, and price-check recalculation.

**Concerns (mixed responsibility — 7 distinct concerns):**
1. HTTP routing (`lambda_handler`)
2. JWT validation and JWKS caching (`get_user_id`, `get_jwks`)
3. Rate limiting via DynamoDB counter items (`check_and_increment_global_count`, `check_and_increment_daily_count`)
4. Upload orchestration — presigned URL, job record creation, dedup check (`handle_upload_url`)
5. Receipt list/get (`handle_list_receipts`, `handle_get_job`)
6. Receipt deletion with cascading deletes across three tables (`handle_delete_receipt`)
7. Receipt editing with full line-item replacement, price-check recalculation (`handle_edit_receipt`, `_validate_edit_body`, `_recheck_prices`, `_replace_line_items`)

**Coupling:** boto3 S3 + DynamoDB; `python-jose` for JWT. The module owns all three DynamoDB table names as globals. `format_receipt` generates three separate S3 presigned URLs per receipt.

**Structural issues:**
- `_replace_line_items` (68 lines) duplicates the DynamoDB line-item write logic that also exists in `processor/handler.py::write_line_items`. They differ only in whether `package_size` is handled.
- `_validate_edit_body` uses an `import re` inside the function body — a deferred import that signals the function grew after the module was written.
- `handle_delete_receipt` performs three sequential DynamoDB operations with no transaction — a partial failure leaves orphaned hash or line-item records.
- `check_and_increment_global_count` and `check_and_increment_daily_count` are structurally identical (same DynamoDB call pattern, differ only in key prefix and limit constant) — a clear candidate for parameterisation.
- Rate limiting increments the counter before checking the global limit, and vice versa for per-user — the order means a user can consume their daily quota even when the global limit is already exceeded.

---

### 3. `frontend/app.js.template` — HIGH COMPLEXITY

**What it does:** Single-file vanilla JS SPA. Handles OAuth2 code exchange, token refresh, auto-retry on 401, file selection with HEIC conversion, multi-file upload flow (presign -> S3 PUT -> poll), result rendering, history rendering, the full edit modal (with live price sum, add/delete/reorder items), the OCR debug panel (block table + merged lines + test fixture download), and all DOM event wiring.

**Concerns (mixed responsibility — 9 distinct concerns):**
1. Auth (token storage, code exchange, refresh, logout)
2. API fetch abstraction with 401 retry (`apiFetch`)
3. File validation and HEIC conversion (`selectFiles`, `isHeic`)
4. Upload + polling flow (`handleUpload`, `pollUntilDone`)
5. New-scan result rendering (`renderResults`, `buildReceiptCard`)
6. History rendering (`loadHistory`, `renderHistory`, `buildHistoryCard`)
7. Edit modal — full inline UI construction with live price check (`showEditModal`, `renderItems`, `updatePriceSum`, `makeInput`)
8. OCR debug panel with block table, merged-lines list, deskew row, row-grouping row (`toggleOcrDebug`)
9. Test fixture download (`downloadTestFixture`)

**Structural issues:**
- Everything in one file with no module system — 884 lines with no bundler.
- `buildReceiptCard` is called from both `renderResults` and `buildHistoryCard`, but `buildHistoryCard` adds debug/edit buttons by appending children after the card is returned — the card construction and card decoration are split across two functions.
- `showEditModal` is 150 lines and builds the entire modal DOM imperatively in one function, mixing state management, DOM construction, event wiring, and API calls.
- `toggleOcrDebug` is 130 lines building a complex debug table; it is deep inside the same file as auth code.
- Inline CSS strings throughout `showEditModal` and `buildHistoryCard` (e.g. `style.cssText = "position:fixed;inset:0;..."`) — no stylesheet abstraction.
- Price-check logic is duplicated: `_recheck_prices` in api/handler.py, `_verify_price_sum` in processor/handler.py, `updatePriceSum` in the JS template, and `_priceCheck` in the Flutter screen — four independent implementations of the same sum(item.prices) vs total calculation.

---

### 4. `mobile_new/lib/features/receipts/presentation/screens/receipts_screen.dart` — MODERATE COMPLEXITY

**What it does:** Flutter receipts list screen that also contains the full edit bottom sheet (`_EditReceiptSheet`, `_EditReceiptSheetState`, `_EditableItem`).

**Concerns:**
1. Screen layout and list rendering with swipe-to-delete (`ReceiptsScreen`)
2. Mutable line-item state management during editing (`_EditableItem` with 6 TextEditingControllers)
3. Full edit form — vendor, date, all line-item fields, dynamic add/delete, price bar (`_EditReceiptSheetState.build`, `_buildItemRow`)
4. Live price check calculation (`_priceCheck` — fourth copy of this logic across the codebase)

**Structural issues:**
- `_EditReceiptSheet` is 290 lines in the same file as the list screen; it should be a separate file.
- `_EditableItem` is a hand-rolled mutable model class duplicating what the ViewModel already tracks; lifecycle management (6 `dispose()` calls) is error-prone.
- `_restoreProcessedCapture` in `receipts_view_model.dart` encodes a file-naming convention (`${jobId}_$filename`) that is also encoded in `upload_view_model.dart` — tight implicit coupling through filesystem path strings.

---

### 5. `mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart` — MODERATE COMPLEXITY

**What it does:** Riverpod `Notifier` managing the upload queue. Also owns camera capture, saved-captures file I/O (two directories: `receipt-scanner-images/` and `.../processed/`), file-size validation, SHA-256 hashing, and the post-upload file move.

**Concerns:**
1. Upload queue state
2. Image picker integration (camera + gallery)
3. App-local filesystem management (save, list, move-to-processed)
4. Upload orchestration (request URL -> S3 PUT -> poll -> update state)
5. Oversized-file warning accumulation

**Structural issues:**
- The file system directory constants (`receipt-scanner-images`, `processed`) are duplicated as string literals in both `upload_view_model.dart` and `receipts_view_model.dart` — if the folder name changes, both files must be updated.
- `uploadAll` processes uploads sequentially in a `for` loop despite having an abort-controller-based pattern available on the web side. No parallelism.
- `_getSavedDir` and `_getProcessedDir` are nearly identical one-liners and could be collapsed to one parameterised helper.

---

## Cross-Cutting Issues

### Duplicated price-check logic (4 copies)
The calculation "sum item prices, compare to total, produce a warning string" appears in:
- `/workspace/active_repo/lambda/processor/handler.py` lines 579-618 (`_verify_price_sum`)
- `/workspace/active_repo/lambda/api/handler.py` lines 364-384 (`_recheck_prices`)
- `/workspace/active_repo/frontend/app.js.template` lines 533-547 (`updatePriceSum`)
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/screens/receipts_screen.dart` lines 232-243 (`_priceCheck`)

### Duplicated line-item write logic (2 copies)
- `/workspace/active_repo/lambda/processor/handler.py` lines 800-858 (`write_line_items`)
- `/workspace/active_repo/lambda/api/handler.py` lines 387-457 (`_replace_line_items`)

Both convert item fields to DynamoDB `N` types, build the same `item_sk` key format (`{created_at}#{job_id}#{i:03d}`), and write the same record shape. The processor version additionally handles `package_size`; the api version handles `nova_group` and `item_category` carry-through differently.

### Duplicated `update_job` (2 copies)
- `/workspace/active_repo/lambda/processor/handler.py` lines 861-874
- `/workspace/active_repo/lambda/api/handler.py` lines 460-476

Nearly identical DynamoDB `update_item` wrappers. The processor version uses `f"#{key} = :{key}"` as expression syntax; the api version uses numbered aliases `#k{i}` / `:v{i}` — functionally equivalent but differently formatted. These Lambdas are separate deployments so sharing code requires a Lambda layer or shared package.

### Duplicated `to_n` / `_to_float` helpers
`_to_float` in processor/handler.py (line 543) and the `to_n` nested functions inside `write_line_items` (processor) and `_replace_line_items` (api) all perform the same `str -> strip $ and , -> float` transformation. The api handler also has a duplicate copy of `to_float` inside `_recheck_prices` (line 365).

### Filesystem path coupling between mobile ViewModels
The string `receipt-scanner-images/processed` and the naming convention `${jobId}_$filename` are independently encoded in:
- `/workspace/active_repo/mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart` (lines 38-41, 209-212)
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/view_models/receipts_view_model.dart` (lines 49-70)

### Prompt as inline string
The 60-line Bedrock prompt in `/workspace/active_repo/lambda/processor/handler.py` lines 414-467 is an inline multi-line f-string with no abstraction. Changes to prompt wording require editing the handler directly, alongside all the other logic.

### `RECEIPT_TOOL` schema embedded in handler
The 115-line Bedrock tool schema (lines 41-157 of processor/handler.py) is a module-level Python dict literal. It is effectively static configuration that would be cleaner as a separate JSON or YAML file, or at minimum a separate module.

### No cascade safety on delete
`handle_delete_receipt` in api/handler.py performs three independent DynamoDB calls (delete job, delete hash, batch-delete line items) with no DynamoDB transaction. A Lambda timeout or network error between steps leaves partial state. The processor has a similar risk in `process_record` where the COMPLETE write and `store_image_hash` are separate calls.

### Rate-limit counter increment before limit check
In `handle_upload_url`, the per-user counter is incremented unconditionally before checking the global limit (lines 139-149 of api/handler.py). This wastes a counter slot when the global cap is hit, and the global counter is incremented even when the user is over their daily limit, skewing global counts.

---

## Refactoring Priority Order

1. **`lambda/processor/handler.py`** — Split into: image pipeline module (JPEG normalisation, crop, deskew), OCR module (Textract + `line_grouping`), extraction module (Bedrock prompt + tool schema), validation module (price check, classification), persistence module (DynamoDB writes). Move prompt and tool schema out of the handler entirely.

2. **`lambda/api/handler.py`** — Extract: a rate-limiter class (deduplicating the two counter functions), a line-items writer (shared with or matching processor), and a `format_receipt` helper that is isolated from S3 presigning concerns.

3. **Shared Lambda utility** — `update_job`, `now_iso`, `_to_float`/`to_n`, and line-item write logic should live in a shared module (Lambda layer or vendored package) to eliminate the four-way duplication across the two handlers.

4. **`frontend/app.js.template`** — The edit modal (`showEditModal`) and OCR debug panel (`toggleOcrDebug`) are each large enough to be extracted into named factory functions or separate JS modules. Inline CSS strings should move to `styles.css`.

5. **Mobile filesystem coupling** — Extract a `CaptureStorage` class in the mobile app that owns both directory paths and the jobId-prefix naming convention, used by both `upload_view_model.dart` and `receipts_view_model.dart`.
