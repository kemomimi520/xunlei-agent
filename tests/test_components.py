import hashlib
import json
import os
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from xunlei_agent import XunleiAuth, XunleiPanClient, Downloader, XunleiAgentTool
from xunlei_agent.core.downloader import calculate_sha256, get_default_download_dir
from xunlei_agent.core.pan_bridge import XunleiWebBridge

class TestXunleiAgentComponents(unittest.TestCase):

    def test_01_imports_and_exports(self):
        """Test module imports and package exports."""
        self.assertTrue(hasattr(XunleiAuth, "login_with_browser_playwright"))
        self.assertTrue(hasattr(XunleiPanClient, "save_share"))
        self.assertTrue(hasattr(XunleiPanClient, "empty_trash"))
        self.assertTrue(hasattr(XunleiPanClient, "download_file"))
        self.assertTrue(hasattr(XunleiWebBridge, "save_share"))
        self.assertTrue(hasattr(XunleiWebBridge, "empty_trash"))
        self.assertTrue(hasattr(XunleiWebBridge, "download_file"))
        self.assertTrue(hasattr(XunleiAgentTool, "save_share"))
        self.assertTrue(hasattr(XunleiAgentTool, "download_file"))

    def test_02_downloader_and_sha256(self):
        """Test built-in Downloader and SHA256 calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_data.bin")
            test_content = b"XunleiAgent Python Stream Download and Hash Verification Test\n" * 100
            with open(test_file, "wb") as f:
                f.write(test_content)

            # Test sha256
            expected_sha = hashlib.sha256(test_content).hexdigest()
            calc_sha = calculate_sha256(test_file)
            self.assertEqual(expected_sha, calc_sha)

            # Test Downloader class
            dl = Downloader(default_download_dir=tmpdir)
            self.assertTrue(os.path.exists(dl.download_dir))
            sanitized = dl.sanitize_filename("test:file/name?.bin")
            self.assertNotIn(":", sanitized)
            self.assertNotIn("/", sanitized)
            self.assertNotIn("?", sanitized)

    def test_03_default_download_dir_platform(self):
        """Verify cross-platform download directory resolution."""
        d = get_default_download_dir()
        self.assertTrue(isinstance(d, str))
        self.assertTrue(len(d) > 0)
        if os.name == "nt":
            self.assertIn("Downloads", d)

    def test_04_schema_generation(self):
        """Verify Agent Function Calling schema validity."""
        schema = XunleiAgentTool.get_tool_schema()
        self.assertTrue(isinstance(schema, list))
        self.assertGreaterEqual(len(schema), 5)
        names = [f["function"]["name"] for f in schema]
        self.assertIn("xunlei_fetch_and_download", names)
        self.assertIn("xunlei_check_space", names)
        self.assertIn("xunlei_list_files", names)
        self.assertIn("xunlei_delete_files", names)
        self.assertIn("xunlei_download_file", names)

    def test_05_unauthenticated_guardrails(self):
        """Verify that methods gracefully return UNAUTHORIZED rather than crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_config = os.path.join(tmpdir, "fake_config.json")
            fake_state = os.path.join(tmpdir, "fake_state.json")
            
            tool = XunleiAgentTool(config_path=fake_config)
            tool.bridge.state_path = fake_state
            
            res_space = tool.check_space()
            self.assertIn(res_space.get("code"), ["UNAUTHORIZED", "ERROR", None])
            if res_space.get("status") == "error":
                self.assertTrue("登录" in res_space.get("message", "") or res_space.get("code") == "UNAUTHORIZED")

            res_ls = tool.list_files()
            self.assertIn(res_ls.get("code"), ["UNAUTHORIZED", "ERROR", None])
            if res_ls.get("status") == "error":
                self.assertTrue("登录" in res_ls.get("message", "") or res_ls.get("code") == "UNAUTHORIZED")

if __name__ == "__main__":
    unittest.main(verbosity=2)
