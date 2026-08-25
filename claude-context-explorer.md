# Codebase Audit Findings

## Files Examined

### Lambda
- `/workspace/active_repo/lambda/api/handler.py`
- `/workspace/active_repo/lambda/processor/handler.py`
- `/workspace/active_repo/lambda/processor/bedrock_extraction.py`
- `/workspace/active_repo/lambda/processor/image_processing.py`
- `/workspace/active_repo/lambda/processor/textract_pipeline.py`
- `/workspace/active_repo/lambda/processor/line_grouping.py`
- `/workspace/active_repo/lambda/shared/dynamo.py`
- `/workspace/active_repo/lambda/shared/line_items.py`
- `/workspace/active_repo/lambda/shared/pricing.py`
- `/workspace/active_repo/lambda/shared/constants.py`

### Flutter
- All files under `/workspace/active_repo/mobile_new/lib/`

### Vue 3 Frontend
- All files under `/workspace/active_repo/frontend/src/`

### Terraform
- All `.tf` files under `/workspace/active_repo/terraform/`

---

## Findings by Severity

### HIGH

**1. Mobile auth flow not enabled in Cognito — login always fails**
- `/workspace/active_repo/mobile_new/lib/features/auth/data/services/auth_service.dart` line 26
- `/workspace/active_repo/terraform/cognito.tf` line 49
- `AuthService.signIn()` calls `USER_PASSWORD_AUTH`. The Cognito user pool client only enables `ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`. `ALLOW_USER_PASSWORD_AUTH` is absent. Every mobile login attempt receives a Cognito `NotAuthorizedException`.
- Fix: add `ALLOW_USER_PASSWORD_AUTH` to `explicit_auth_flows` in `cognito.tf`, or rewrite `AuthService` to use SRP flow.

**2. Job permanently stuck in PROCESSING after processor exhausts SQS retries**
- `/workspace/active_repo/lambda/processor/handler.py` lines 62-70, 95-98
- `process_record()` sets status to `PROCESSING` then calls `analyze_receipt()`. If that throws, the exception is caught, the message ID is added to `batchItemFailures`, and SQS redelivers up to `maxReceiveCount=5` times. After the 5th failure the message goes to the DLQ and processing stops. The job remains in `PROCESSING` status indefinitely — no `FAILED` write ever happens. Users polling `GET /jobs/{jobId}` will see it processing forever.
- Fix: write status `FAILED` to DynamoDB in the exception handler in `lambda_handler`, or inside `process_record` before re-raising.

**3. Rate-limit counters not rolled back — global rejection burns the user's daily quota**
- `/workspace/active_repo/lambda/api/handler.py` lines 192-202
- `check_and_increment_daily_count` is called first (line 192); if it passes, `check_and_increment_global_count` is called (line 198). If the global limit is already hit, the function returns 429, but the user counter has already been permanently incremented and cannot be undone. The user's daily quota is consumed even though no upload was allowed.
- Fix: check both counters without incrementing first, then increment only if both pass (use a conditional expression or read-then-conditionally-update pattern).

**4. S3 objects never deleted when a receipt is deleted**
- `/workspace/active_repo/lambda/api/handler.py` lines 306-335
- `handle_delete_receipt` removes the DynamoDB job record, image-hash record, and line items, but never calls `s3.delete_object` on `job.s3_key`, `job.debug_s3_key`, `job.textract_debug_s3_key`, or `job.cropped_s3_key`. These objects accumulate in S3 indefinitely, incurring storage cost and leaving user data on disk after the user explicitly deleted it.
- Fix: add `s3:DeleteObject` to the api Lambda IAM policy and delete all four S3 keys (null-checked) in `handle_delete_receipt`.

**5. DynamoDB `Limit` is applied before `FilterExpression`, so history page silently truncates**
- `/workspace/active_repo/lambda/api/handler.py` lines 236-248
- The `handle_list_receipts` query uses `Limit=20` plus `FilterExpression="#st <> :dup"`. DynamoDB applies `Limit` to the number of items *scanned*, then filters. Any DUPLICATE-status records in the top 20 scanned rows are filtered out, delivering fewer than 20 results to the caller, even when more COMPLETE records exist on subsequent pages. The Vue frontend (HistorySection.vue line 19) further filters to COMPLETE only, compounding the shortfall.
- Fix: implement a paginated loop that keeps fetching with `ExclusiveStartKey` until the requested page size of COMPLETE results is collected, or use a sparse GSI that only projects COMPLETE records.

---

### MEDIUM

**6. JWKS cache never refreshes — Cognito key rotation causes permanent 401s until cold start**
- `/workspace/active_repo/lambda/api/handler.py` lines 100-117
- `_JwksCache.get()` fetches JWKS once per container and caches it with no TTL. Cognito rotates signing keys periodically. A container that spans a rotation will fail JWT validation for every request (the new key's `kid` will not be found in the cached key set) until the container is recycled by Lambda.
- Fix: add a TTL to `_JwksCache` (e.g. refresh after 12 hours) or catch `jwt.JWTError` with a key-not-found condition and re-fetch once before giving up.

**7. Recursive polling risks stack exhaustion and is harder to reason about than a loop**
- `/workspace/active_repo/frontend/src/components/UploadSection.vue` lines 72-88
- `pollUntilDone` calls itself with `count + 1` up to `MAX_POLLS=60` times. 60 async recursion levels is not dangerous in V8, but recursion with `async/await` is an antipattern: the call stack accumulates suspended frames, and the intent is obscured. If `MAX_POLLS` is ever raised significantly it becomes a real risk.
- Fix: rewrite as a `while (count < MAX_POLLS)` loop with an `await` delay inside.

**8. `format_receipt` generates up to 3 presigned URL calls per item in the list endpoint**
- `/workspace/active_repo/lambda/api/handler.py` lines 440-481, 247
- `handle_list_receipts` maps all 20 receipts through `format_receipt`, which calls `s3.generate_presigned_url` up to 3 times per receipt (debug, textract-debug, cropped). For a full page that is up to 60 SDK signing calls before the response can be sent. These are CPU-only (no network I/O), but they slow the list endpoint noticeably and generate no value — the list UI does not show debug links.
- Fix: omit presigned URLs from the list response; generate them only in `GET /jobs/{jobId}`.

**9. `write_line_items` issues one `put_item` per line item instead of batching**
- `/workspace/active_repo/lambda/shared/line_items.py` line 70
- Each line item triggers a separate `dynamodb.put_item` call. A receipt with 40 items makes 40 round trips. `batch_write_item` accepts 25 per call, so the same 40 items need only 2 calls.
- Fix: accumulate records into 25-item batches and call `dynamodb.batch_write_item`.

**10. Mobile `ReceiptJob` model silently drops price-check and store-category fields from API**
- `/workspace/active_repo/mobile_new/lib/features/receipts/data/models/receipt.dart` lines 60-74
- `ReceiptJob.fromJson` ignores `storeCategory`, `priceCheckWarning`, `priceCheckMessage`, `debugUrl`, `textractDebugUrl`, and `croppedImageUrl`. The server computes the price-check warning to tell users when item prices do not sum to the receipt total. The mobile app silently discards this data.
- Fix: add `storeCategory`, `priceCheckWarning`, and `priceCheckMessage` to `ReceiptJob`.

**11. `_fetch_job_item` returns a dict-or-response union — `statusCode` key presence is a fragile discriminant**
- `/workspace/active_repo/lambda/api/handler.py` lines 251-267, 271-272, 307-308, 378-379
- The function returns either a raw DynamoDB item dict or a `make_response` error dict. Callers distinguish them by checking `"statusCode" in item`. This relies on DynamoDB items never having a `statusCode` attribute. The pattern is both fragile and untyped.
- Fix: raise a custom exception on error so callers use `try/except`, or return a typed `Result` dataclass.

**12. Unused `today` variable in `_check_and_increment_count`**
- `/workspace/active_repo/lambda/api/handler.py` line 153 (and line 166 in its callers)
- `today = datetime.now(timezone.utc).strftime("%Y-%m-%d")` is assigned inside `_check_and_increment_count` but never referenced — `counter_key` is already passed in pre-formatted. Dead code in a function that handles rate limiting.
- Fix: delete the unused assignment on line 153.

**13. `CloudFront CSP` allows `cdn.jsdelivr.net` in `script-src` but no CDN scripts are used**
- `/workspace/active_repo/terraform/cloudfront.tf` line 12
- The CSP contains `script-src 'self' https://cdn.jsdelivr.net`. No file in the frontend loads from jsdelivr — the Vite build is entirely self-contained. The allowlist entry widens the XSS attack surface.
- Fix: remove `https://cdn.jsdelivr.net` from `script-src`.

**14. `app_config.dart` containing live API endpoint is tracked by git**
- `/workspace/active_repo/mobile_new/lib/core/config/app_config.dart` lines 6-7
- Listed in `.gitignore` as a generated file, but `git ls-files` confirms it is tracked. It contains the live API Gateway URL (`https://6o98lyizu6.execute-api.ap-southeast-2.amazonaws.com/v1`) and Cognito client ID. The `.gitignore` entry is ineffective once a file has been committed.
- Fix: `git rm --cached mobile_new/lib/core/config/app_config.dart` and regenerate it as a true generated artefact (not committed). Use a `.template` file like the frontend does.

**15. Concurrent parallel uploads may trigger simultaneous Cognito token refreshes**
- `/workspace/active_repo/mobile_new/lib/core/network/api_client.dart` lines 14-18
- `/workspace/active_repo/mobile_new/lib/features/auth/presentation/view_models/upload_view_model.dart` line 115 (Future.wait)
- When `uploadAll()` issues multiple parallel Dio requests and the token is expired, every concurrent request hits the interceptor and calls `getIdToken()` simultaneously. Each call independently attempts a Cognito `REFRESH_TOKEN_AUTH`. Cognito may reject the second and subsequent refresh attempts with the same refresh token, causing a spurious sign-out.
- Fix: guard the refresh path in `getIdToken()` with a `Completer`-based mutex so only the first refresh runs and subsequent concurrent calls wait for it.

---

### LOW

**16. `AuthService` and S3 `Dio` instances constructed without connection timeouts**
- `/workspace/active_repo/mobile_new/lib/features/auth/data/services/auth_service.dart` line 9
- `/workspace/active_repo/mobile_new/lib/features/upload/data/services/upload_service.dart` line 10
- Both use bare `Dio()` with no `BaseOptions`, giving them infinite connect/receive timeouts. A stalled Cognito or S3 endpoint would hang the app indefinitely. The authenticated API `Dio` in `api_client.dart` correctly sets 15 s / 30 s limits.
- Fix: pass `BaseOptions(connectTimeout: Duration(seconds: 15), receiveTimeout: Duration(seconds: 30))` to both.

**17. Gallery images compressed twice — `imageQuality: 90` in picker, then JPEG at 92% in processor**
- `/workspace/active_repo/mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart` lines 39, 63
- `pickMultiImage(imageQuality: 90)` and `pickImage(imageQuality: 90)` re-encode images before they are even saved. The processor's `_to_jpeg` (image_processing.py line 37) then re-encodes again at quality 92. For a PNG receipt from the gallery this is a double-lossy conversion. OCR accuracy degrades with each re-encode.
- Fix: use `imageQuality: 100` or omit the parameter to pass through the original file; rely solely on the processor's JPEG conversion.

**18. `Color.withOpacity()` deprecated in Flutter 3.27+**
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/sheets/edit_receipt_sheet.dart` line 344
- `color.withOpacity(0.4)` is deprecated; the replacement is `color.withValues(alpha: 0.4)`.
- Fix: change to `color.withValues(alpha: 0.4)`.

**19. `field` and `VALID_ITEM_CATEGORIES` imported but unused in processor `handler.py`**
- `/workspace/active_repo/lambda/processor/handler.py` lines 4, 12
- `field` from `dataclasses` is never used (no `dataclass` uses `field(...)`). `VALID_ITEM_CATEGORIES` from `constants` is never referenced in this file — its use is inside `bedrock_extraction.py` and `line_items.py`.
- Fix: remove both unused imports.

**20. `VALID_ITEM_CATEGORIES` imported but unused in api `handler.py`**
- `/workspace/active_repo/lambda/api/handler.py` line 12
- Same issue: imported but never referenced in this file.
- Fix: remove the import.

**21. `_MSER_DELTA = 0.25` passed to `cv2.MSER_create` which expects an integer**
- `/workspace/active_repo/lambda/processor/image_processing.py` lines 20, 228
- The OpenCV `MSER_create` `delta` parameter is an integer (step size between grey levels, default 5). Passing `0.25` is silently truncated to `0` by the C++ binding, which means MSER explores every possible threshold level — making it extremely slow and producing meaningless region output.
- Fix: change `_MSER_DELTA = 0.25` to `_MSER_DELTA = 5` (OpenCV default).

**22. `EditModal.vue` uses `alert()` for save errors**
- `/workspace/active_repo/frontend/src/components/EditModal.vue` line 91
- `alert('Failed to save: ' + err.message)` is a blocking browser dialog that interrupts keyboard/screen-reader flows and is not styled to match the app. All other error surfaces in this codebase use inline `<p class="error-text">` elements.
- Fix: add a `saveError` ref and render the error message inline within the modal.

**23. `isPending` getter exists on `ReceiptJob` but is never used; `isProcessing` is absent but needed**
- `/workspace/active_repo/mobile_new/lib/features/receipts/data/models/receipt.dart` lines 55-58
- `isPending` is defined but has no callers anywhere. The processor Lambda sets status `PROCESSING`, but there is no `isProcessing` getter. If the app ever needs to show in-flight upload status from the history screen, it will find `isProcessing` missing and `isPending` unused.
- Fix: either remove `isPending` or add `isProcessing` and use both where needed.

**24. `HistorySection` double-loads after an edit save**
- `/workspace/active_repo/frontend/src/App.vue` line 63
- `/workspace/active_repo/frontend/src/components/HistorySection.vue` lines 31-35
- After a successful edit, `EditModal` emits `saved` then `close`. `HistorySection.onSaved` calls `loadHistory()` and then emits its own `saved` up to `App.vue`. `App.vue.onHistoryRefresh` increments `historyKey`, which destroys and remounts `HistorySection`, triggering another `loadHistory()`. The result is two `GET /receipts` calls every time an edit is saved.
- Fix: either do not increment `historyKey` in response to a save (it is only needed for post-upload refresh), or stop using the `:key` remount technique and expose a `refresh()` ref method on `HistorySection`.

**25. SQS `visibility_timeout_seconds` comment references wrong processor timeout**
- `/workspace/active_repo/terraform/sqs.tf` lines 14-16
- Comment says "6 × 60s = 360s" but `lambda_timeout_processor` defaults to 120 s. 6 × 120 = 720 s. The current value of 360 s is only 3× the actual timeout, which is below the AWS-recommended minimum of 6×. An invocation that runs to the full 120 s timeout will have the SQS message become visible again after only 240 s, potentially triggering a spurious redelivery.
- Fix: change `visibility_timeout_seconds` to `720` and correct the comment, or reduce the Lambda timeout default to 60 s.

**26. `_data` (deskewed bytes) return value from `_run_deskew_pipeline` is ignored with `_` prefix**
- `/workspace/active_repo/lambda/processor/handler.py` line 220
- `_run_deskew_pipeline` returns `(final_bytes, tr, ...)` but the caller binds it as `_data, tr, ...`. The Textract result `tr` was already derived from `final_bytes` inside the function, so there is no functional bug. However, the underscore prefix convention signals "intentionally discarded", which is misleading because `final_bytes` is never needed by the caller — it could simply be removed from the return signature to make the API cleaner.
- Fix: remove `final_bytes` from `_run_deskew_pipeline`'s return tuple since no caller uses it.
