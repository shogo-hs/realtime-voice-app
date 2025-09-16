"""アプリ設定のロードとバリデーションを担当するモジュール。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioConfig(BaseModel):
    """音声入出力に関する設定。"""

    sample_rate: int = Field(default=24000, ge=8000, description="サンプリングレート")
    blocksize: int = Field(default=960, ge=120, description="1ブロックのフレーム数")
    input_channels: int = Field(default=1, ge=1, le=2)
    output_channels: int = Field(default=2, ge=1, le=2)
    input_device: Optional[Union[int, str]] = Field(default=None)
    output_device: Optional[Union[int, str]] = Field(default=None)
    max_buffer_seconds: int = Field(default=15, ge=1, le=60)


class VoiceConfig(BaseModel):
    """エージェントの動作やボイス設定。"""

    instructions: str
    voice: str = "alloy"
    interrupt_response: bool = True


class LoggingConfig(BaseModel):
    """ロギング設定。"""

    level: str = "INFO"
    file: str = "logs/app.log"
    max_bytes: int = Field(default=1_048_576, ge=10_000)
    backup_count: int = Field(default=5, ge=1)

    @field_validator("level", mode="before")
    def _upper(cls, value: str) -> str:  # noqa: N805
        return value.upper()


class AppConfig(BaseSettings):
    """アプリ全体の設定。YAML と環境変数をマージする。"""

    audio: AudioConfig = AudioConfig()
    voice: VoiceConfig
    logging: LoggingConfig = LoggingConfig()

    model_config = SettingsConfigDict(env_prefix="VOICE_", env_nested_delimiter="__")


def load_config(path: Optional[Path] = None) -> AppConfig:
    """設定ファイルを読み込み、環境変数で上書きして返す。"""
    settings_path = path or Path("config/settings.yaml")
    if not settings_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {settings_path}")

    with settings_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return AppConfig(**data)
