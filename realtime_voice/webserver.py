import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .controller import VoiceSessionController

WEB_ROOT = Path(__file__).resolve().parent / "web"


class AppRequestHandler(SimpleHTTPRequestHandler):
    controller = VoiceSessionController()

    def __init__(self, *args, directory: Optional[str] = None, **kwargs):
        if directory is None:
            directory = str(WEB_ROOT)
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/session/status"):
            self._json_response(AppRequestHandler.controller.status())
            return

        if self.path.startswith("/api/logs"):
            after = 0
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if "after" in params:
                try:
                    after = int(params["after"][0])
                except (ValueError, TypeError):
                    after = 0
            logs = [entry.__dict__ for entry in AppRequestHandler.controller.get_logs(after)]
            self._json_response({"logs": logs})
            return

        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/session/start":
            started = AppRequestHandler.controller.start()
            status = AppRequestHandler.controller.status()
            if not started and status.get("running"):
                self._json_response({"ok": False, "reason": "already_running", "status": status})
            else:
                self._json_response({"ok": True, "status": status})
            return

        if self.path == "/api/session/stop":
            stopped = AppRequestHandler.controller.stop()
            self._json_response({"ok": stopped, "status": AppRequestHandler.controller.status()})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "API endpoint not found")

    def log_message(self, format, *args):  # noqa: A003
        # reduce console noise
        return

    def _json_response(self, payload, status: HTTPStatus = HTTPStatus.OK):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run(host: str = "127.0.0.1", port: int = 8000):
    WEB_ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer((host, port), AppRequestHandler) as httpd:
        print(f"🌐 Serving realtime assistant UI on http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            AppRequestHandler.controller.stop()


if __name__ == "__main__":
    run()
