"""Local web panel for a Huawei USB modem: python3 server.py, then open the printed URL."""

import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import modem

HOST, PORT = "127.0.0.1", 18352
PAGE = Path(__file__).with_name("index.html").read_bytes()
# USB access is single-client: serialize every modem call.
lock = threading.Lock()


def with_modem(action):
    with lock:
        m = modem.Modem()
        try:
            return action(m)
        finally:
            m.close()


def device_state():
    with lock:
        _, mode = modem.find_device()
    return {"mode": mode}


def switch():
    with lock:
        modem.switch_with_admin_prompt()
    return {"mode": "modem"}


ROUTES = {
    ("GET", "/api/device"): lambda body: device_state(),
    ("POST", "/api/switch"): lambda body: switch(),
    ("GET", "/api/info"): lambda body: with_modem(lambda m: m.info()),
    ("GET", "/api/status"): lambda body: with_modem(lambda m: m.status()),
    ("POST", "/api/ussd"): lambda body: {"answer": with_modem(lambda m: m.ussd(body["code"]))},
    ("GET", "/api/sms"): lambda body: with_modem(lambda m: m.list_sms()),
    ("POST", "/api/sms"): lambda body: with_modem(lambda m: m.send_sms(body["number"], body["text"])) or {"sent": True},
    ("POST", "/api/sms/delete"): lambda body: with_modem(lambda m: m.delete_sms(body["index"])) or {"deleted": True},
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload, content_type="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        if method == "GET" and self.path == "/":
            return self._send(200, PAGE, "text/html")
        route = ROUTES.get((method, self.path))
        if route is None:
            return self._send(404, {"error": "not found"})
        # Only the page itself may call the API, not other sites in the browser.
        origin = self.headers.get("Origin")
        if method == "POST" and origin not in (None, f"http://{HOST}:{PORT}"):
            return self._send(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, route(body))
        except modem.ModemError as e:
            self._send(409, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}/"
    print(f"Modem Panel: {url}  (Ctrl+C — выход)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
