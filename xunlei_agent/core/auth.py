import json
import os
import sys
import time
import uuid
from typing import Dict, Any, Optional
import requests

DEFAULT_CONFIG_PATH = os.environ.get("XUNLEI_CONFIG_PATH") or os.path.expanduser("~/.config/xunlei/config.json")
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CLIENT_VERSION = "1.0.0"
CLIENT_ID = "xunlei_agent_linux"

class XunleiAuth:
    """Handles Xunlei authentication, token management, device ID, and auto-refresh."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.device_id: str = uuid.uuid4().hex
        self.expires_at: float = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_UA})
        self.load()

    def load(self) -> bool:
        """Load credentials and device_id from config file."""
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.user_id = data.get("user_id")
                self.device_id = data.get("device_id") or self.device_id
                self.expires_at = data.get("expires_at", 0)
                return bool(self.access_token)
        except Exception as e:
            sys.stderr.write(f"[Auth] Failed to load config: {e}\n")
            return False

    def save(self) -> None:
        """Save credentials and device_id to config file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "expires_at": self.expires_at,
            "updated_at": int(time.time()),
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            os.chmod(self.config_path, 0o600)
        except Exception:
            pass

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None, user_id: Optional[str] = None, device_id: Optional[str] = None, expires_in: int = 86400 * 30):
        """Set credentials directly."""
        self.access_token = access_token.strip()
        self.refresh_token = refresh_token.strip() if refresh_token else None
        self.user_id = user_id
        if device_id:
            self.device_id = device_id.strip()
        self.expires_at = time.time() + expires_in
        self.save()

    def refresh(self) -> bool:
        """Refresh the access token using refresh_token."""
        if not self.refresh_token:
            return False
        url = "https://xluser-ssl.xunlei.com/v1/auth/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": CLIENT_ID,
            "client_version": CLIENT_VERSION,
            "device_id": self.device_id,
        }
        headers = {
            "User-Agent": DEFAULT_UA,
            "x-device-id": self.device_id,
        }
        try:
            resp = self.session.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token", self.refresh_token)
                self.user_id = data.get("user_id", self.user_id)
                expires_in = data.get("expires_in", 86400 * 7)
                self.expires_at = time.time() + expires_in
                self.save()
                return True
        except Exception as e:
            sys.stderr.write(f"[Auth] Token refresh failed: {e}\n")
        return False

    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, auto-refreshing if expired or near expiry."""
        if not self.access_token:
            return None
        if self.expires_at and (self.expires_at - time.time()) < 300:
            if self.refresh():
                return self.access_token
        return self.access_token

    def check_session(self) -> bool:
        """Check if credentials exist and are currently valid."""
        return bool(self.get_valid_token())

    def login_with_browser_playwright(self, timeout_sec: int = 180) -> Dict[str, Any]:
        """
        Use Playwright headless browser to automate login, intercept tokens,
        render QR code for scanning, and persist both config.json and state.json.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("Playwright is not installed. Please install playwright or use `xunlei-agent login --token <token>`")

        captured = {"access_token": None, "refresh_token": None, "user_id": None}
        state_path = os.path.expanduser("~/.config/xunlei/state.json")
        qr_dir = os.path.dirname(self.config_path)
        os.makedirs(qr_dir, exist_ok=True)
        qr_screenshot_path = os.path.join(qr_dir, "login_qr.png")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(user_agent=DEFAULT_UA)
            page = context.new_page()

            def handle_request(req):
                auth_header = req.headers.get("authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.replace("Bearer ", "").strip()
                    if token and not captured["access_token"]:
                        captured["access_token"] = token

            def handle_response(resp):
                if any(k in resp.url.lower() for k in ["signin", "token", "auth"]):
                    try:
                        json_data = resp.json()
                        if isinstance(json_data, dict) and json_data.get("access_token"):
                            captured["access_token"] = json_data.get("access_token")
                            captured["refresh_token"] = json_data.get("refresh_token")
                            captured["user_id"] = json_data.get("user_id")
                    except Exception:
                        pass

            page.on("request", handle_request)
            page.on("response", handle_response)

            print("[*] 正在加载迅雷网盘登录页面...")
            page.goto("https://pan.xunlei.com/login/", wait_until="domcontentloaded", timeout=60000)
            
            try:
                iframe_element = page.wait_for_selector("iframe", timeout=30000)
                frame = iframe_element.content_frame()
                try:
                    frame.locator(".xlucommon-login-icon-code, .xluweb-login-switch__qr").first.click(timeout=3000)
                except Exception:
                    box = iframe_element.bounding_box()
                    if box:
                        page.mouse.click(box['x'] + box['width'] - 25, box['y'] + 25)
                time.sleep(1.5)

                # Take screenshot of the QR frame
                iframe_element.screenshot(path=qr_screenshot_path)
                print(f"[OK] 登录二维码截图已保存至: {qr_screenshot_path}")
            except Exception as e:
                print(f"[Warning] 定位登录二维码异常: {e}，将直接截取整页...")
                page.screenshot(path=qr_screenshot_path)
                print(f"[*] 页面截图已保存至: {qr_screenshot_path}")

            print("\n" + "=" * 50)
            print("[请使用手机迅雷 App 扫描二维码登录]")
            print(f"二维码图片路径: {qr_screenshot_path}")
            print(f"等待扫码超时时间: {timeout_sec} 秒")
            print("=" * 50 + "\n")

            start = time.time()
            login_success = False

            while time.time() - start < timeout_sec:
                if captured["access_token"]:
                    login_success = True
                    break

                if "pan.xunlei.com/#" in page.url or (page.url == "https://pan.xunlei.com/" and "/login" not in page.url):
                    login_success = True
                    break

                try:
                    storage_data = page.evaluate("() => Object.assign({}, window.localStorage)")
                    for k, v in storage_data.items():
                        if "token" in k.lower() or "cred" in k.lower() or "auth" in k.lower():
                            parsed = json.loads(v)
                            if isinstance(parsed, dict) and parsed.get("access_token"):
                                captured["access_token"] = parsed.get("access_token")
                                captured["refresh_token"] = parsed.get("refresh_token")
                                captured["user_id"] = parsed.get("user_id")
                                login_success = True
                                break
                except Exception:
                    pass

                if login_success:
                    break

                time.sleep(1.5)

            if login_success:
                time.sleep(2)
                os.makedirs(os.path.dirname(state_path), exist_ok=True)
                context.storage_state(path=state_path)
                print(f"[*] 浏览器会话已保存至 {state_path}")

            browser.close()

        if login_success and captured["access_token"]:
            self.set_tokens(
                access_token=captured["access_token"],
                refresh_token=captured["refresh_token"],
                user_id=captured["user_id"]
            )
            return {"status": "success", "access_token": self.access_token, "config_path": self.config_path}
        elif login_success:
            return {"status": "success", "message": "扫码成功并已记录会话状态", "config_path": self.config_path}
        else:
            raise TimeoutError(f"登录超时 ({timeout_sec}s) 或未检测到扫码成功")

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)
