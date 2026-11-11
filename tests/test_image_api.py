import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class Handler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Handler.calls.append((self.path, self.headers.get("Authorization"), body))
        # 第一次假装接口忙，第二次才给图，测重试
        if len(Handler.calls) % 2 == 1:
            out = {"error": {"message": "当前请求较多，请稍后重试"}}
        else:
            out = {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class ImageApiTest(unittest.TestCase):
    def setUp(self):
        Handler.calls = []
        self.srv = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, IMAGE_API_KEY="test-key-not-real",
                        IMAGE_API_BASE=f"http://127.0.0.1:{self.srv.server_port}/v1",
                        IMAGE_RETRY_SECONDS="0")

    def tearDown(self):
        self.srv.shutdown()
        self.tmp.cleanup()

    def run_api(self, *extra):
        art = Path(self.tmp.name) / "文章" / "2026-01-01-测试"
        out = art / "配图" / "a.png"
        r = subprocess.run([sys.executable, "-I", str(ROOT / "工具/生图api.py"), str(out), "画一只猫", *extra],
                           env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(out.read_bytes(), PNG)
        log = (art / "提示词" / "api生图记录.txt").read_text(encoding="utf-8")
        self.assertIn("画一只猫", log)
        self.assertNotIn("test-key-not-real", log)
        return log

    def test_generations_retries_when_busy(self):
        self.run_api("--size", "1536x1024")
        self.assertEqual([c[0] for c in Handler.calls], ["/v1/images/generations"] * 2)
        self.assertEqual(json.loads(Handler.calls[-1][2])["size"], "1536x1024")

    def test_refs_go_to_edits(self):
        ref = Path(self.tmp.name) / "身份参考.png"
        ref.write_bytes(PNG)
        log = self.run_api("--ref", str(ref))
        self.assertEqual(Handler.calls[-1][0], "/v1/images/edits")
        self.assertIn(b'name="image[]"', Handler.calls[-1][2])
        self.assertIn(str(ref), log)


if __name__ == "__main__":
    unittest.main()
