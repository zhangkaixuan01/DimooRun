from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class SpaHandler(SimpleHTTPRequestHandler):
    root_directory = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(*args, directory=self.root_directory, **kwargs)

    def send_head(self):  # type: ignore[no-untyped-def]
        path = self.translate_path(self.path)
        if not Path(path).exists() and "text/html" in self.headers.get("Accept", ""):
            self.path = "/index.html"
        return super().send_head()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not (directory / "index.html").exists():
        raise SystemExit(f"Missing built Console app: {directory / 'index.html'}")

    SpaHandler.root_directory = str(directory)

    server = ThreadingHTTPServer((args.host, args.port), SpaHandler)
    print(f"Serving Console from {directory} at http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
