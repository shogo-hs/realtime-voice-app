# AGENTS.md

## プロジェクト概要
- **名前**: Realtime Voice Assistant
- **説明**: `openai-agents` の `RealtimeAgent`/`RealtimeRunner` を使って音声入出力をリアルタイムで処理し、簡易な Web UI から制御できる Python 3.12 アプリ。
- **ランタイム**: Python 3.12 (`uv` で管理)
- **主要モジュール**: `realtime_voice` パッケージ（`audio.py`, `assistant.py`, `controller.py`, `webserver.py`）

## セットアップ
- 依存関係の同期:
  ```bash
  uv sync
  ```
- 追加パッケージは `uv add <package>` を使用すること（`pip install` は禁止）。
- `.env` に以下を設定し、機密情報はコミットしないこと。
  ```env
  OPENAI_API_KEY=sk-...
  ```
- サンプルとして `.env.example` を用意しているため、新しい変数を追加したら併せて更新。
- アプリ設定は `config/settings.yaml` に記載し、変更時は設定値のバリデーション結果を確認すること。
- 音声デバイスを固定する場合は `.env` に `AUDIO_INPUT_DEVICE` / `AUDIO_OUTPUT_DEVICE` を設定する（ID もしくは名称を指定）。

## 実行方法
- Web ダッシュボードを起動:
  ```bash
  uv run python -m realtime_voice --host 127.0.0.1 --port 8000
  ```
- ブラウザで `http://127.0.0.1:8000/` を開いてセッションの開始/停止やログ確認を行う。
- オーディオデバイスの確認:
  ```bash
  uv run python -m sounddevice
  ```

## テスト
- 推奨フレームワーク: `pytest`（`tests/` 配下にモジュール単位で追加）。
- 実行:
  ```bash
  uv run pytest -q
  ```
- 実装変更時は可能な限りユニットテストまたは回帰テストを追加。音声 I/O は実機テストで補う。

## コードスタイル
- PEP 8 / 4 スペースインデント、型ヒント必須。
- ログは `controller` 経由のメッセージに統一し、絵文字を使った短いフィードバックを継続。
- 音声リソースは `AudioHandler` を介して操作し、直接 `sounddevice` を触る場合は影響範囲をコメントで明記。
- 関数・メソッドには簡潔な **日本語** の docstring を必ず記述すること（Ruff が D10* で検知）。

## 作業ルール
- まとまった変更は小さなコミットに分割し、件名は命令形・72文字以内（例: `Add web dashboard polling`）。
- PR では概要、テスト結果、影響範囲（新しい env, ポート、ハードウェア要件など）を記載し、必要に応じてスクリーンショットやログを添付。
- ランタイム設定や手順を変更したら本ファイルを更新すること。
- コミット前に以下を必ず実行し、フォーマット/ lint チェックを通過させること。
  ```bash
  uv run pre-commit install
  uv run pre-commit run
  ```

## リポジトリ構成
- `realtime_voice/audio.py`: 入出力ストリーム管理。
- `realtime_voice/assistant.py`: Realtime API とのセッション制御。
- `realtime_voice/controller.py`: バックグラウンド実行とログ管理。
- `realtime_voice/webserver.py`: API + 静的アセット配信。
- `realtime_voice/config.py`: 設定オブジェクトと YAML ロード処理。
- `realtime_voice/logging_utils.py`: ログ設定を初期化。
- `realtime_voice/web/`: `index.html`, `styles.css`, `app.js` の Web UI。
- `pyproject.toml`, `uv.lock`: 依存関係定義。
- `tests/`: 追加予定の pytest スイート。
- `AGENTS.md`: 当ファイル。

## セキュリティ & プライバシー
- API キーは `.env` のみに保存し、レビュー時も伏せ字を徹底。
- ログに個人情報や音声内容を残さない。必要に応じてログを適宜 truncate する。

## トラブルシューティング
- **API キー未設定**: Web UI にエラーが表示されたら `.env` の値を確認。
- **音声が入らない/出ない**: `sounddevice` でデバイス ID を確認し、OS 権限を付与。
- **セッションが停止しない**: Web UI の停止ボタンで応答がなければサーバープロセスを終了し、`realtime_voice/controller.py` のログを参照。

---

## コミュニケーション
- エージェント間の連絡は日本語で行うこと。
