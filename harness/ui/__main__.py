"""Preview the workspace without model credentials: python -m harness.ui."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from harness.ui import STATIC_DIRECTORY


class WorkspaceHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        if self.path.startswith("/ui/"):
            self.path = self.path[3:]
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview the mini-harness workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    handler = partial(WorkspaceHandler, directory=str(STATIC_DIRECTORY))
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f"mini-harness workspace: http://{args.host}:{args.port}", flush=True)
        print("Demo mode. For live runs, use python main.py api.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
