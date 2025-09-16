# Realtime Voice Assistant

音声入出力をローカルで制御しながら、OpenAI Realtime API と会話できる簡易 Web アプリです。Python 3.12 と音声デバイス（マイク・スピーカー）を備えた環境で動作します。

## 必要条件
- Python 3.12
- [uv](https://github.com/astral-sh/uv)（依存関係と実行環境の管理に使用）
- OpenAI API キー（Realtime API が利用可能なもの）
- マイク・スピーカーが使用可能な OS 権限

## セットアップ
1. 依存関係を同期します。
   ```bash
   uv sync
   ```
2. プロジェクト直下に `.env` を作成し、API キーを設定します。
   ```env
   OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
   ```
3. 初回のみ、OS からマイク入力の許可を求められた場合は許可してください。
4. 入出力デバイスを固定したい場合は環境変数に名称または ID を設定します。
   ```env
   AUDIO_INPUT_DEVICE=Built-in Microphone
   AUDIO_OUTPUT_DEVICE=Built-in Output
   ```
5. `config/settings.yaml` にアプリ全体の設定（エージェントの指示文、ログ出力先、音声パラメータ）が
   まとまっています。値を変更すると、起動時に自動でバリデーションが行われます。

## 起動方法
1. Web サーバーを起動します。
   ```bash
   uv run python -m realtime_voice --host 127.0.0.1 --port 8000
   ```
2. ブラウザで `http://127.0.0.1:8000/` を開き、ダッシュボードにアクセスします。
3. 「接続開始」を押すと音声ストリームが開始され、ログ欄にステータスが流れます。
4. 会話を終了する際は「停止」を押すか、サーバープロセスを終了します。

## ディレクトリ構成（主要）
- `realtime_voice/audio.py`: サウンドデバイスを扱う入出力ハンドラー。
- `realtime_voice/assistant.py`: Realtime API セッションの制御ロジック。
- `realtime_voice/controller.py`: バックグラウンドスレッドの管理とログ蓄積。
- `realtime_voice/webserver.py`: HTTP API と静的ファイルの配信。
- `realtime_voice/web/`: `index.html`, `styles.css`, `app.js` からなる Web UI。
- `realtime_voice/config.py`: YAML + 環境変数から設定を読み込み、バリデーションする。
- `realtime_voice/logging_utils.py`: ファイル / コンソールへのロギングを初期化。
- `config/settings.yaml`: アプリ全体の設定ファイル。
- `AGENTS.md`: コントリビューター向けガイド。

## よくある質問
- **音声が聞こえない / 入らない**: `uv run python -m sounddevice` でデバイス一覧を確認し、OS の入出力設定が正しいか、マイクアクセスの権限があるか確認してください。
- **API キー関連エラー**: `.env` の `OPENAI_API_KEY` が正しく設定されているか、Realtime API が有効なキーか確認してください。
- **停止できない**: UI の停止ボタンで反応しない場合はターミナルで `Ctrl+C` を押し、ログに表示される最終メッセージを確認してください。

## WSL で音声入出力を有効化する
このアプリは PortAudio（`sounddevice`）を利用するため、WSL では追加設定が必要です。以下の手順で PulseAudio ブリッジを構成すると、WSL 上でもマイク・スピーカーを利用できます。

Note: WSL では物理マイクが直接 ALSA に見えないため、Windows 側の PulseAudio サーバーを経由してデバイスを認識させる必要があります。この設定を行わないと `sounddevice` から「利用可能な入力デバイスが見つかりませんでした」というエラーになります。

1. 依存パッケージを導入します。
   ```bash
   sudo apt update
   sudo apt install -y libportaudio2 portaudio19-dev pulseaudio-utils alsa-utils libasound2 libasound2-plugins
   ```
2. ALSA を PulseAudio 経由にするため、`~/.asoundrc` を作成します。
   ```
   pcm.!default pulse
   ctl.!default pulse
   ```
3. PulseAudio を再起動します。
   ```bash
   pulseaudio -k || true
   pulseaudio --start
   ```
4. WSLg を利用している場合は、PulseAudio サーバーを指す環境変数を `~/.profile` に追記して永続化します。
   ```bash
   export PULSE_SERVER=unix:/mnt/wslg/PulseServer
   ```
5. 以下のコマンドで接続状態とデバイス列挙を確認します。
   ```bash
   pactl info | head
   arecord -L
   uv run python -c "import sounddevice as sd; print(sd.query_devices())"
   ```

   成功していれば、`pulse` / `default` デバイスが表示されます（例: `0 pulse, ALSA (32 in, 32 out)`）。

## 開発メモ
- 依存パッケージの追加は `uv add <package>` を使用してください。
- テストは `pytest` を想定しています（`uv run pytest -q`）。
- 変更を加えた際は `AGENTS.md` も併せて更新し、開発ルールを最新に保ってください。
- コミット前に以下を実行し、Ruff によるフォーマットと lint を自動適用します。
  ```bash
  uv run pre-commit install
  uv run pre-commit run --all-files
  ```
- Docstring（簡潔な **日本語** で可）と型ヒントを欠かしたコードは Ruff により弾かれるため、追加実装では必ず両方を記述してください。
