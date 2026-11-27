"""http_request binary-safe body + multipart upload.

Regression for babypython: the team built a correct symlink zip but the text 'body'
path UTF-8-encoded the high bytes (symlink marker, CRC), corrupting the upload. The
agent needs a channel that delivers raw bytes intact.
"""
import base64
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools.http import new_http_client, run_http  # noqa: E402

RECEIVED: dict[str, bytes] = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        RECEIVED["ctype"] = (self.headers.get("Content-Type") or "").encode()
        RECEIVED["body"] = self.rfile.read(n)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


def make_symlink_zip() -> bytes:
    """A zip whose single entry is a symlink (external_attr marks S_IFLNK); its bytes
    include values >127 that UTF-8 re-encoding would corrupt."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        info = zipfile.ZipInfo("data.pdf")
        info.external_attr = 0xA1ED0000  # symlink + perms
        z.writestr(info, "/proc/self/environ")
    return buf.getvalue()


def serve():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_body_b64_is_byte_exact():
    srv, base = serve()
    raw = make_symlink_zip()
    assert any(b > 127 for b in raw), "fixture should contain high bytes"
    client = new_http_client()
    run_http(base, client, {"method": "POST", "path": "/", "body_b64": base64.b64encode(raw).decode()})
    assert RECEIVED["body"] == raw, "body_b64 must arrive byte-for-byte"
    # and the file is still a valid zip with a symlink entry on the receiving side
    info = zipfile.ZipFile(BytesIO(RECEIVED["body"])).getinfo("data.pdf")
    assert info.external_attr >> 16 & 0xF000 == 0xA000, "symlink marker survived"
    srv.shutdown()


def test_text_body_would_corrupt():
    # Shows WHY body_b64 exists: the same bytes via 'body' (latin-1 str) get UTF-8'd.
    srv, base = serve()
    raw = make_symlink_zip()
    client = new_http_client()
    run_http(base, client, {"method": "POST", "path": "/", "body": raw.decode("latin-1")})
    assert RECEIVED["body"] != raw, "text body is expected to mangle high bytes"
    srv.shutdown()


def test_multipart_file_upload():
    srv, base = serve()
    raw = make_symlink_zip()
    client = new_http_client()
    out = run_http(base, client, {"method": "POST", "path": "/upload",
                   "files": [{"field": "file", "filename": "exp.zip",
                              "content_b64": base64.b64encode(raw).decode()}]})
    assert "multipart/form-data" in RECEIVED["ctype"].decode()
    assert raw in RECEIVED["body"], "raw zip bytes must appear in the multipart body"
    assert b'filename="exp.zip"' in RECEIVED["body"]
    assert "HTTP 200" in out
    srv.shutdown()


def test_bad_base64_is_reported():
    srv, base = serve()
    client = new_http_client()
    out = run_http(base, client, {"method": "POST", "path": "/", "body_b64": "!!!notb64!!!="})
    assert "base64" in out.lower()
    srv.shutdown()


if __name__ == "__main__":
    test_body_b64_is_byte_exact()
    test_text_body_would_corrupt()
    test_multipart_file_upload()
    test_bad_base64_is_reported()
    print("PASS http binary test")
