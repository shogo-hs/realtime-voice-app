"""アプリケーションのサービス初期化を担うモジュール。"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Tuple

from .config import AppConfig, load_config
from .controller import VoiceSessionController
from .logging_utils import setup_logging


@lru_cache(maxsize=1)
def get_services() -> Tuple[AppConfig, VoiceSessionController]:
    """設定とコントローラを初期化し、シングルトンとして返す。"""
    config = load_config()
    setup_logging(config.logging)

    logger = logging.getLogger("voice.controller")
    controller = VoiceSessionController(logger=logger, config=config)
    return config, controller
