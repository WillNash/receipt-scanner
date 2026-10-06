# Receipt Scanner — Mobile

Flutter app for scanning and uploading receipts to AWS.

## Installing on Android over Wi-Fi (ADB)

Requires Android 11+ and both your phone and computer on the same Wi-Fi network.

### First-time pairing (do this once per computer)

1. Enable **Developer Options**: Settings → About phone → tap Build number 7 times
2. Enable **Wireless debugging**: Settings → Developer options → Wireless debugging → toggle on
3. Tap **Pair device with pairing code** — note the IP address, port, and 6-digit code shown
4. On your computer:

```bash
adb pair <ip>:<port>
# Enter the 6-digit code when prompted
# e.g. adb pair 192.168.1.42:37491
```

### Connecting (each session)

After pairing, use the main IP/port shown on the Wireless debugging screen (different from the pairing port):

```bash
adb connect <ip>:<port>
# e.g. adb connect 192.168.1.42:5555

adb devices  # confirm it shows up
```

The IP and port can change between sessions — check the Wireless debugging screen each time.

### Building and installing the app

```bash
# Debug build with hot reload
flutter run

# Release build
flutter build apk && adb install build/app/outputs/flutter-apk/app-release.apk
```

### Disconnecting

```bash
adb disconnect
```
