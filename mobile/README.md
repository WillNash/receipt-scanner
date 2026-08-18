# Receipt Scanner — Android App

Flutter app for uploading receipt photos from your Android gallery to the existing AWS backend.

## Prerequisites

- [Flutter SDK](https://docs.flutter.dev/get-started/install/linux/android) (stable channel, 3.22+)
- Android SDK / Android Studio (for `adb` and build tools)
- The AWS backend deployed (`make deploy` from repo root)

## 1. Fill in config

After running `make deploy`, run `terraform output` in the `terraform/` directory. Then edit:

```
mobile/lib/core/config/app_config.dart
```

Replace the two placeholder values:
- `apiBaseUrl` → value of `api_invoke_url`
- `cognitoClientId` → value of `cognito_client_id`

If your Cognito domain prefix is different from `bedrock-image-ai-025423`, update `_cognitoBaseUrl` too.

## 2. Redeploy Terraform

The Cognito app client now includes the Android redirect URI. If you haven't redeployed since this file was added:

```bash
cd terraform && terraform apply
```

## 3. Build and install

```bash
cd mobile
flutter pub get
flutter build apk --release
```

Copy the APK to your phone and install it:

```bash
adb install build/app/outputs/flutter-apk/app-release.apk
```

Or just copy `app-release.apk` to your phone via USB/Google Drive, tap it, and allow "Install unknown apps" when prompted.

## Development

```bash
flutter run          # run on connected Android device / emulator
flutter analyze      # lint check
flutter test         # unit tests
```

## How the app works

1. **Login** — taps open the Cognito hosted UI in the system browser. After sign-in you're redirected back automatically.
2. **Upload tab** — pick one or more receipt photos from your gallery, then tap Upload. Progress is shown per photo. Results (vendor, total, line items) appear inline when Textract finishes.
3. **History tab** — shows your 20 most recent receipts. Pull to refresh.

Tokens are stored encrypted in Android's `EncryptedSharedPreferences`. The id_token is refreshed automatically 5 minutes before expiry.
