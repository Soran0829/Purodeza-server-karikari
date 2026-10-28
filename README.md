# Mimamori Test

M5StickC Plus2 の子機、Python (FastAPI) サーバー、Flutter アプリ、シミュレーターを統合した見守りGPS試作システムです。
実機GPS・LTE-M は未接続のため、仮データで一連の処理をテストできます。

## ディレクトリ構成

```text
Mimamori-test/
├── MimamoriTest.ino      # M5StickC Plus2 ファームウェア
├── protocol.md           # 共通データ仕様
├── server/               # FastAPI + SQLite
├── simulator/            # 仮GPS送信シミュレーター
├── app/                  # Flutter アプリ
├── tests/                # サーバーテスト
└── README.md
```

## 共通データ仕様

`protocol.md` を参照してください。主要フィールド:

- `device_id`
- `latitude`
- `longitude`
- `timestamp`（端末時刻、Unix ms、null 可）
- `received_at`（サーバー受信時刻、Unix ms）
- `accuracy_m`（null 可、捏造しない）
- `fix_valid`
- `data_source`（`simulated` または `gps`）

## 必要環境

- Python 3.10 以上
- （Flutter アプリを使う場合）Flutter SDK 3.x
- （Android をビルドする場合）JDK 21 と Android SDK（`flutter doctor` がすべて緑になること）
- （M5 実機を使う場合）Arduino IDE または PlatformIO

## サーバーのセットアップと起動

```powershell
cd C:\Users\free\Desktop\purodeza\Mimamori-test
pip install -r server\requirements.txt
$env:DEVICE_API_KEY="dev-device-key-change-me"
$env:APP_API_KEY="dev-app-key-change-me"
$env:DATABASE_PATH="mimamori.db"
$env:PYTHONPATH="."
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

ヘルスチェック:

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

## シミュレーターの起動

別ターミナルで:

```powershell
cd C:\Users\free\Desktop\purodeza\Mimamori-test
$env:PYTHONPATH="."
$env:SERVER_URL="http://127.0.0.1:8000"
$env:DEVICE_ID="M5STICK-SIM-001"
$env:DEVICE_API_KEY="dev-device-key-change-me"
pip install -r simulator\requirements.txt
python simulator\simulate.py
```

5秒ごとに仮の移動座標を送信します。

## Flutter アプリの起動

Flutter SDK 3.x が必要です。`app/android/` は生成済みです。

```powershell
cd C:\Users\free\Desktop\purodeza\Mimamori-test\app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=APP_API_KEY=dev-app-key-change-me
```

APK を作る場合:

```powershell
flutter build apk --debug
# 成果物: app\build\app\outputs\flutter-apk\app-debug.apk
```

Android エミュレーターでは `10.0.2.2` を使用してください。実機では PC の LAN IP を指定します（デスクトップ向けプラットフォームは未生成です）。

アプリは 5 秒ごとに最新位置と履歴を取得し、30 秒以上更新がない場合は `STALE` と表示します。

## M5StickC Plus2 ファームウェア

`MimamoriTest.ino` を Arduino IDE / PlatformIO でビルドします。

- デフォルトは仮データモード（`USE_SIMULATED_GPS=1`）
- 画面に状態、緯度、経度、測位状態、バッテリー、データソースを表示
- 実GPS・LTE-M は未接続です
- RTC が無いため、ネットワーク送信を実装する際の `timestamp` は **null** にします（起動経過時間 `millis()` は絶対に送らない。サーバーは 24 時間より古い値を拒否します）
- `STALE` は最後の有効測位から `STALE_THRESHOLD_MS`（既定 30 秒）経過で表示します

## テストの実行

```powershell
cd C:\Users\free\Desktop\purodeza\Mimamori-test
pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
```

`pyproject.toml` が `pythonpath` を設定するため、`PYTHONPATH` の指定は不要です。

テスト内容:
- 正常系の位置情報登録（`id` / `received_at` の採番含む）
- 無効座標（範囲外、(0,0) センチネル）、`device_id` の長さ・文字種・空白、負の精度
- 不正な `data_source`、数値項目への文字列/bool 混入
- 認証失敗（キーなし/不正/種別取り違え/非ASCII）
- タイムスタンプ未来・過去 24 時間超の拒否、`null` の受理
- 最新位置取得、履歴取得、404
- 履歴の新しい順、`since` の絞り込み、`limit` 境界
- 旧バージョンが書いた不正行・未知の `data_source` を読んでも500にならないこと

Flutter 側:

```powershell
cd app
flutter analyze
flutter test
```

## CI

`.github/workflows/ci.yml` により、push / pull request 時に以下を実行します。

- `ruff check .` と `pytest -q`（Python 3.10）
- `flutter analyze` と `flutter test`（Flutter 3.38.5）

## 各コンポーネントの接続方法

1. サーバーを起動します。
2. シミュレーターまたは M5 実機が `POST /api/v1/locations` に送信します。
3. Flutter アプリが `GET /api/v1/devices/{device_id}/latest` と `history` を取得します。
4. 認証は `X-API-Key` ヘッダーで行います。キーは環境変数で設定し、ソースコードに直書きしません。未設定時は開発用の既定値が使われ、起動時に警告ログが出ます。

## 未実装・制約

- HTTPS / MQTT / LTE-M 通信: 未実装（HTTP のみ）。Flutter 側は試作のため平文 HTTP を許可しています
- ネットワーク再接続: 未実装
- 実GPS解析: フラグの背後でのみ実装、ハードウェア未接続
- RTC なしのため timestamp は null（起動経過時間は送らない）
- 精度は捏造せず、取得できない場合は null / N/A
- 位置情報は認証なしで公開しないでください
- 端末キーは全端末共通です（試作品の制約）。端末ごとのキーや失効機構は未実装で、`device_id` の詐称を防げません
- DB は暗号化されておらず、保持期間・自動削除も未実装です（個人情報の取り扱いに注意）
- Flutter は Android のみ生成済み。`flutter analyze` / `flutter test` / `flutter build apk --debug` まで検証済みで、実機/エミュレーターでの画面確認は未実施です
- M5 実機での GPS/LTE-M 動作は未検証です
