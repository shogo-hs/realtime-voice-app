"""ロギング初期化ユーティリティ。"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from .config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """設定に従ってロギングを初期化する。"""
    log_path = Path(config.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": config.level,
                "formatter": "default",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": config.level,
                "formatter": "default",
                "filename": str(log_path),
                "maxBytes": config.max_bytes,
                "backupCount": config.backup_count,
                "encoding": "utf-8",
            },
        },
        "root": {"level": config.level, "handlers": ["console", "file"]},
    }

    logging.config.dictConfig(logging_config)
