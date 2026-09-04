import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from xunlei_agent.core.auth import XunleiAuth

class TestLoginQRCapture(unittest.TestCase):
    def test_qr_capture(self):
        auth = XunleiAuth()
        qr_path = os.path.join(os.path.dirname(auth.config_path), "login_qr.png")
        if os.path.exists(qr_path):
            os.remove(qr_path)
            
        print("[Test] Launching headless browser to capture Xunlei QR code (5s test)...")
        try:
            auth.login_with_browser_playwright(timeout_sec=5)
        except Exception as e:
            print(f"[Test] Caught expected wait exception: {e}")

        self.assertTrue(os.path.exists(qr_path), f"QR screenshot {qr_path} should exist")
        file_size = os.path.getsize(qr_path)
        print(f"[Test] QR screenshot file size: {file_size} bytes")
        self.assertGreater(file_size, 1000, "QR screenshot should be a valid non-empty image")

if __name__ == "__main__":
    unittest.main()
