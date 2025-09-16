"""CLI エントリーポイント。Web サーバーの起動を司る。"""

from __future__ import annotations

import argparse
from typing import Optional

from .runtime import get_services
from .webserver import run as run_server


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """コマンドライン引数を解釈する。"""
    parser = argparse.ArgumentParser(description="Realtime Voice Assistant server")
    parser.add_argument(
        "--host", default="127.0.0.1", help="バインドするホスト (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8000, help="バインドするポート (default: 8000)")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    """Web サーバーを起動する。"""
    args = parse_args(argv)
    get_services()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
