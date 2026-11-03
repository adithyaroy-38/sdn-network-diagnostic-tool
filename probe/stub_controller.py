import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send(400, {"error": "bad json"})
            return
        if self.path == "/diag/report":
            if body.get("status") in ("degraded", "failed"):
                resp = {"action": "rerouted", "new_path": "s1-s3-s4"}
            else:
                resp = {"action": "none"}
            print(f"REPORT {body.get('src')}->{body.get('dst')} "
                  f"status={body.get('status')} loss={body.get('loss_pct')}% "
                  f"-> {resp['action']}", flush=True)
            self._send(200, resp)
        elif self.path == "/diag/mode":
            self._send(200, {"mode": body.get("mode", "dynamic")})
        else:
            self._send(404, {"error": "not found"})

    def do_GET(self):
        if self.path.startswith("/diag/paths"):
            self._send(200, {"src": "h1", "dst": "h2",
                             "active_path": ["s1", "s2", "s4"],
                             "alternative_paths": [["s1", "s3", "s4"]]})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Stub controller listening on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
