# Code Smell Audit — receipts_screen.dart & upload_view_model.dart

_Generated: 2026-08-25. Branch: next-steps._

---

## Files Audited

- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/screens/receipts_screen.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart`

## Related Files Read

- `/workspace/active_repo/mobile_new/lib/features/receipts/data/models/receipt.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/data/services/receipts_service.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/view_models/receipts_view_model.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/widgets/receipt_card.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/data/models/upload_job.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/data/services/upload_service.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/presentation/screens/upload_screen.dart`
- `/workspace/active_repo/mobile_new/lib/core/config/app_config.dart`

---

## HIGH Severity

### 1. God File — edit sheet embedded in list screen
- **File:** receipts_screen.dart, lines 119–484
- `_showEditSheet`, `_EditableItem`, `_EditReceiptSheet`, `_EditReceiptSheetState` all live beside `ReceiptsScreen`. Three separate concerns in one file. Cannot test the sheet independently.
- **Fix:** Extract to `lib/features/receipts/presentation/sheets/edit_receipt_sheet.dart`.

### 2. WidgetRef stored as StatefulWidget field
- **File:** receipts_screen.dart, lines 195–199
- `_EditReceiptSheet` stores `WidgetRef` as `final WidgetRef ref`. The ref can go stale; Riverpod docs explicitly forbid this pattern. `didUpdateWidget` is never overridden, so a parent rebuild never delivers the fresh ref.
- **Fix:** Convert `_EditReceiptSheet` to `ConsumerStatefulWidget`/`ConsumerState` and use `ref` from `ConsumerState`.

### 3. Filesystem I/O inside presentation-layer ReceiptsNotifier
- **File:** receipts_view_model.dart, lines 49–71 (`_restoreProcessedCapture`)
- Raw directory traversal and `File.rename` live in the receipts view model. Path strings (`receipt-scanner-images`, `processed`) are duplicated from upload_view_model.dart lines 27–40 — two sources of truth for the on-disk layout.
- **Fix:** Introduce a `CaptureFileRepository` that owns directory layout constants and exposes `moveToProcessed(jobId, filePath)` / `restoreFromProcessed(jobId)`. Inject into both notifiers.

---

## MEDIUM Severity

### 4. Magic path strings duplicated across two files
- **Files:** upload_view_model.dart line 27; receipts_view_model.dart lines 52, 61
- `'receipt-scanner-images'` and `'processed'` are hardcoded in both notifiers independently.
- **Fix:** Single constant in a shared `CaptureFileRepository` or constants file.

### 5. Oversized-files side-channel outside Riverpod state
- **File:** upload_view_model.dart, lines 129–135
- `_oversizedFiles` is mutable instance state invisible to Riverpod devtools, undo, or replay. The destructive-read `consumeOversizedWarnings()` can silently drop warnings if any of the three call sites in upload_screen.dart races or is skipped.
- **Fix:** Include `oversizedFiles` inside the Riverpod `state` object; clear via a `clearOversizedWarnings()` state mutation.

### 6. `_priceCheck()` recomputed on every build
- **File:** receipts_screen.dart, lines 232–244 and 277
- Iterates all items and parses strings on every `build()` call. `double.parse(sum.toStringAsFixed(2))` is an unnecessary round-trip string serialization.
- **Fix:** Cache result in state; invalidate only when price `onChanged` fires (already triggers `setState` at line 410).

### 7. Serial upload loop — no concurrency
- **File:** upload_view_model.dart, lines 145–150
- Each upload awaits full completion (including poll, up to 3 min) before the next starts. With multi-select this is extremely slow.
- **Fix:** `Future.wait(pending.map((u) => _uploadOne(u.id)))` — individual state updates are already keyed by id, so concurrent calls are safe.

### 8. Synchronous SHA-256 on UI isolate; ViewModel doing I/O
- **File:** upload_view_model.dart, lines 159–161
- `sha256.convert(bytes)` is synchronous and CPU-bound on up to 20 MB; runs on the main isolate inside the ViewModel. I/O + crypto belong in a service layer.
- **Fix:** Move hashing into `UploadService` or a `FileHashService`; run via `compute()` for CPU-intensive work.

---

## LOW Severity

### 9. `_textField`/`_numField` near-duplicate helpers
- **File:** receipts_screen.dart, lines 421–447
- Differ only by `keyboardType`. Identical `InputDecoration`.
- **Fix:** Merge into `_fieldInput(ctrl, label, {TextInputType? keyboardType})`.

### 10. Full file read just for size check (gallery pick)
- **File:** upload_view_model.dart, lines 51–54
- `file.readAsBytes()` loads up to 20 MB into memory just to inspect `.length`, then discards the bytes. `_uploadOne` reads the file again later.
- **Fix:** Use `XFile.length()` or `File(file.path).length()` (a stat call) for the size check.

### 11. Full file read for size check (camera) + storage leak on oversize
- **File:** upload_view_model.dart, lines 80–84
- Same issue as #10. Additionally, if the file is over the limit the copy at line 78 has already been written to permanent storage and is never deleted.
- **Fix:** Check size before copying; skip the copy entirely for oversized files.

### 12. Non-editable AI fields silently preserved in edit payload
- **File:** receipts_screen.dart, lines 189–190
- `itemCategory` and `novaGroup` have no UI controls but are always re-submitted via `toJson()`. Users cannot clear an AI-assigned category; the field persists invisibly. Behaviour is inconsistent with other fields which omit when blank.
- **Fix:** Either expose the fields in the UI, or explicitly exclude them from the PATCH payload and document that they are server-managed.

### 13. Duplicated delete-confirmation dialog; free functions in library scope
- **Files:** receipts_screen.dart lines 85–104; upload_screen.dart lines 222–246
- `_confirmDelete` and `_deleteAndReport` are module-level free functions that pollute the library namespace and cannot be unit-tested without a widget harness. The same red-button confirmation dialog is independently re-implemented in `_SavedCapturesPickerState`.
- **Fix:** Promote to a shared `ConfirmDeleteDialog.show(context, {required String body})` helper under `core/widgets/`.

---

## Summary Table

| # | Severity | File | Lines | Smell |
|---|---|---|---|---|
| 1 | High | receipts_screen.dart | 119–484 | God file — edit sheet embedded in list screen |
| 2 | High | receipts_screen.dart | 195–199 | WidgetRef stored as StatefulWidget field |
| 3 | High | receipts_view_model.dart | 49–71 | Filesystem I/O inside presentation-layer notifier; duplicated path strings |
| 4 | Medium | upload_view_model.dart + receipts_view_model.dart | 27, 52, 61 | Magic path strings duplicated |
| 5 | Medium | upload_view_model.dart | 129–135 | Oversized-files side-channel outside Riverpod state |
| 6 | Medium | receipts_screen.dart | 232–244, 277 | _priceCheck() recomputed on every build |
| 7 | Medium | upload_view_model.dart | 145–150 | Serial upload loop; no concurrency |
| 8 | Medium | upload_view_model.dart | 159–161 | Synchronous SHA-256 on UI isolate; ViewModel doing I/O |
| 9 | Low | receipts_screen.dart | 421–447 | _textField/_numField near-duplicate helpers |
| 10 | Low | upload_view_model.dart | 51–54 | Full file read just for size check (gallery) |
| 11 | Low | upload_view_model.dart | 80–84 | Full file read for size check (camera) + storage leak |
| 12 | Low | receipts_screen.dart | 189–190 | Non-editable AI fields silently preserved in edit payload |
| 13 | Low | receipts_screen.dart + upload_screen.dart | 85–104, 222–246 | Duplicated delete-confirmation dialog; free functions in library scope |
