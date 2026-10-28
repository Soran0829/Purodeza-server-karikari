# Mimamori Test - Flutter app

Root の [README](../README.md) を参照してください。

```powershell
flutter pub get
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=APP_API_KEY=dev-app-key-change-me
flutter build apk --debug
```

- APK の成果物は `build\app\outputs\flutter-apk\app-debug.apk` です。
- Android ビルドには JDK 21 と承諾済みの Android SDK ライセンスが必要です。

- `API_BASE_URL`: Android エミュレーターからホストへは `10.0.2.2`、実機からは PC の LAN IP。
- `APP_API_KEY`: `--dart-define` の値は APK から抽出可能です。試作品用であり、本番の秘密情報は入れないでください。
- 平文 HTTP を許可するため `android:usesCleartextTraffic="true"` を設定しています。HTTPS 化の際に削除してください。
