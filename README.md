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

## 起動方法
1. Web サーバーを起動します。
   ```bash
   uv run python -m realtime_voice.webserver
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
- `AGENTS.md`: コントリビューター向けガイド。

## よくある質問
- **音声が聞こえない / 入らない**: `uv run python -m sounddevice` でデバイス一覧を確認し、OS の入出力設定が正しいか、マイクアクセスの権限があるか確認してください。
- **API キー関連エラー**: `.env` の `OPENAI_API_KEY` が正しく設定されているか、Realtime API が有効なキーか確認してください。
- **停止できない**: UI の停止ボタンで反応しない場合はターミナルで `Ctrl+C` を押し、ログに表示される最終メッセージを確認してください。

## 開発メモ
- 依存パッケージの追加は `uv add <package>` を使用してください。
- テストは `pytest` を想定しています（`uv run pytest -q`）。
- 変更を加えた際は `AGENTS.md` も併せて更新し、開発ルールを最新に保ってください。
- コミット前に以下を実行し、Ruff によるフォーマットと lint を自動適用します。
  ```bash
  uv run pre-commit install
  uv run pre-commit run --all-files
  ```
