# Flutter App Exploration — Receipt Scanner (mobile_new/)

## Project Root

All Flutter/Dart code lives under `/workspace/active_repo/mobile_new/`.

---

## 1. Project Structure

```
mobile_new/
  pubspec.yaml
  lib/
    main.dart
    core/
      config/app_config.dart          # Static constants (API URL, Cognito, limits)
      network/api_client.dart         # Dio instance with auth interceptor
      router/app_router.dart          # GoRouter config + bottom-nav shell
      theme/app_theme.dart            # Material3 theme
    features/
      auth/
        data/
          models/auth_tokens.dart
          repositories/auth_repository.dart
          services/auth_service.dart
        presentation/
          screens/login_screen.dart
          view_models/auth_view_model.dart
      upload/
        data/
          models/upload_job.dart
          services/upload_service.dart
        presentation/
          screens/upload_screen.dart
          view_models/upload_view_model.dart
      receipts/
        data/
          models/receipt.dart
          services/receipts_service.dart
        presentation/
          screens/receipts_screen.dart
          view_models/receipts_view_model.dart
          widgets/receipt_card.dart
  test/
    widget_test.dart
```

---

## 2. Key Dependencies (pubspec.yaml)

- State management: `flutter_riverpod ^2.5.1`
- Navigation: `go_router ^14.2.7`
- HTTP: `dio ^5.4.3+1`
- Image picking: `image_picker ^1.1.2`
- Secure storage: `flutter_secure_storage ^9.2.2`
- No camera package is present.

---

## 3. Image Picking — Current Implementation

File: `/workspace/active_repo/mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart`

The `pickPhotos()` method on `UploadNotifier`:

```dart
final picker = ImagePicker();
final files = await picker.pickMultiImage(imageQuality: 90);
```

- Uses `image_picker` only — specifically `pickMultiImage()` with `imageQuality: 90`.
- This opens the OS photo gallery picker (no camera option).
- After picking, each file's bytes are read to enforce the 20 MB limit (`AppConfig.maxFileSizeBytes`). Files over the limit are collected in `_oversizedFiles` and surfaced to the UI as a snackbar.
- Passing files are added to state as `PhotoUpload` objects with `status = UploadStatus.idle`.

There is NO camera capture code anywhere in the codebase. No `ImageSource.camera` call exists.

---

## 4. Upload Flow (end-to-end)

1. User taps "Pick photos" -> `UploadNotifier.pickPhotos()` -> `image_picker.pickMultiImage()`.
2. Each picked file becomes a `PhotoUpload(status: idle)` entry in the list.
3. User taps "Upload" -> `UploadNotifier.uploadAll()` -> iterates idle items -> `_uploadOne(id)`.
4. Inside `_uploadOne`:
   a. Status -> `uploading`.
   b. Read file bytes from disk (`dart:io File.readAsBytes()`).
   c. Determine content type from extension (jpeg vs png) via `UploadService.contentTypeFor()`.
   d. POST `{apiBaseUrl}/upload-url` with `{contentType}` -> receive `{jobId, uploadUrl}`.
   e. PUT bytes to the S3 presigned URL via a separate `Dio` instance (no `Authorization` header).
   f. Status -> `processing`.
   g. Poll `GET {apiBaseUrl}/jobs/{jobId}` every 3 s, up to 60 attempts (3 min timeout).
   h. On `COMPLETE` or `FAILED`, update status accordingly with `ReceiptJob` result or error.

The S3 PUT uses a dedicated `_s3Dio` instance to avoid sending the Bearer token to S3.

---

## 5. Screens and Navigation

Router: `/workspace/active_repo/mobile_new/lib/core/router/app_router.dart`

- `/login` -> `LoginScreen` (shown when not authenticated)
- `/` -> `UploadScreen` (tab 0, "Upload")
- `/receipts` -> `ReceiptsScreen` (tab 1, "History")

Navigation uses `StatefulShellRoute.indexedStack` for a persistent bottom `NavigationBar`. Auth state is bridged to `GoRouter` via a `ChangeNotifier` (`_RouterNotifier`) that listens to `authProvider` and triggers a redirect check on every auth state change.

---

## 6. State Management

Riverpod is used throughout. Pattern is consistent: `NotifierProvider` / `AsyncNotifierProvider` with Notifier subclasses.

- `authProvider` (`NotifierProvider<AuthNotifier, AuthState>`) — sealed state: `AuthLoading`, `Unauthenticated`, `Authenticated`.
- `uploadProvider` (`NotifierProvider<UploadNotifier, List<PhotoUpload>>`) — list of in-progress uploads.
- `receiptsProvider` (`AsyncNotifierProvider<ReceiptsNotifier, List<ReceiptJob>>`) — async fetch with manual `refresh()`.
- `apiClientProvider` (`Provider<Dio>`) — shared Dio with auth interceptor; 401 triggers auto sign-out.

---

## 7. Auth Implementation

- Sign-in calls Cognito `InitiateAuth` (USER_PASSWORD_AUTH flow) directly via Dio — no OAuth browser redirect despite `AppConfig` containing OAuth endpoints (those constants appear unused in the current code).
- Tokens stored in `FlutterSecureStorage` (Android: EncryptedSharedPreferences).
- Token expiry is checked with a 5-minute buffer; refresh uses `REFRESH_TOKEN_AUTH`.
- Email is decoded from the JWT payload client-side (no verification — the Lambda does that).

---

## 8. No Camera Code

Confirmed: there is no `ImageSource.camera`, no `camera` package, no `CameraController`, and no camera permission declaration referenced in any Dart file. The only image-sourcing code is `picker.pickMultiImage()` (gallery only).

---

## Files Read

- `/workspace/active_repo/mobile_new/pubspec.yaml`
- `/workspace/active_repo/mobile_new/lib/main.dart`
- `/workspace/active_repo/mobile_new/lib/core/router/app_router.dart`
- `/workspace/active_repo/mobile_new/lib/core/config/app_config.dart`
- `/workspace/active_repo/mobile_new/lib/core/network/api_client.dart`
- `/workspace/active_repo/mobile_new/lib/core/theme/app_theme.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/presentation/screens/upload_screen.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/presentation/view_models/upload_view_model.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/data/models/upload_job.dart`
- `/workspace/active_repo/mobile_new/lib/features/upload/data/services/upload_service.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/screens/receipts_screen.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/view_models/receipts_view_model.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/presentation/widgets/receipt_card.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/data/models/receipt.dart`
- `/workspace/active_repo/mobile_new/lib/features/receipts/data/services/receipts_service.dart`
- `/workspace/active_repo/mobile_new/lib/features/auth/presentation/screens/login_screen.dart`
- `/workspace/active_repo/mobile_new/lib/features/auth/presentation/view_models/auth_view_model.dart`
- `/workspace/active_repo/mobile_new/lib/features/auth/data/models/auth_tokens.dart`
- `/workspace/active_repo/mobile_new/lib/features/auth/data/repositories/auth_repository.dart`
- `/workspace/active_repo/mobile_new/lib/features/auth/data/services/auth_service.dart`
