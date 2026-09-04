import os
import sys
import time
import threading
import unittest
import urllib.request
import urllib.error

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from xunlei_agent.core.webdav import XunleiWebDAVServer, WebDAVCache

class DummyBridge:
    def list_files(self, parent_id="", limit=50):
        return {
            "status": "success",
            "data": {
                "files": [
                    {
                        "id": "file_1",
                        "name": "sample_video.mp4",
                        "size": 1048576,
                        "kind": "drive#file",
                        "mime_type": "video/mp4",
                        "modified_time": "2026-09-04T12:00:00+08:00",
                        "web_content_link": "https://vod.example.com/sample_video.mp4"
                    },
                    {
                        "id": "folder_1",
                        "name": "MyFolder",
                        "size": 0,
                        "kind": "drive#folder",
                        "mime_type": "application/vnd.xunlei.folder",
                        "modified_time": "2026-09-04T12:00:00+08:00"
                    }
                ]
            }
        }

class TestWebDAVServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 19876
        cls.server = XunleiWebDAVServer(
            ("127.0.0.1", cls.port),
            auth_user="admin",
            auth_pass="123456",
            cache_ttl=60,
            url_prefix="/dav",
            bridge=DummyBridge()
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_unauthorized(self):
        url = f"http://127.0.0.1:{self.port}/dav"
        req = urllib.request.Request(url, method="OPTIONS")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 401)

    def test_02_options(self):
        url = f"http://127.0.0.1:{self.port}/dav"
        req = urllib.request.Request(url, method="OPTIONS")
        # Basic auth admin:123456 -> YWRtaW46MTIzNDU2
        req.add_header("Authorization", "Basic YWRtaW46MTIzNDU2")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("1", resp.headers.get("DAV", ""))
            self.assertIn("PROPFIND", resp.headers.get("Allow", ""))

    def test_03_propfind_multistatus(self):
        url = f"http://127.0.0.1:{self.port}/dav"
        req = urllib.request.Request(url, method="PROPFIND")
        req.add_header("Authorization", "Basic YWRtaW46MTIzNDU2")
        req.add_header("Depth", "1")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 207)
            body = resp.read().decode("utf-8")
            self.assertIn("multistatus", body)
            self.assertIn("sample_video.mp4", body)
            self.assertIn("MyFolder", body)
            self.assertIn("<D:collection/>", body)

    def test_04_get_302_redirect(self):
        url = f"http://127.0.0.1:{self.port}/dav/sample_video.mp4"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", "Basic YWRtaW46MTIzNDU2")
        
        # Don't follow redirect automatically so we can assert 302
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def http_error_302(self, req, fp, code, msg, headers):
                return fp

        opener = urllib.request.build_opener(NoRedirectHandler)
        resp = opener.open(req)
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.headers.get("Location"), "https://vod.example.com/sample_video.mp4")

if __name__ == "__main__":
    unittest.main(verbosity=2)
