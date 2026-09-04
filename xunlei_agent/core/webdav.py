import base64
import datetime
import html
import http.server
import json
import os
import posixpath
import sys
import threading
import time
import urllib.parse
from typing import Dict, Any, List, Optional
from .pan_bridge import XunleiWebBridge

class WebDAVCache:
    def __init__(self, ttl: int = 180):
        self.ttl = ttl
        self._folders: Dict[str, Dict[str, Any]] = {}
        self._path_map: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_folder(self, folder_id: str) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            cached = self._folders.get(folder_id)
            if cached and time.time() - cached["time"] < self.ttl:
                return cached["items"]
        return None

    def set_folder(self, folder_id: str, items: List[Dict[str, Any]], base_path: str = "/"):
        with self._lock:
            self._folders[folder_id] = {
                "time": time.time(),
                "items": items
            }
            for item in items:
                name = item.get("name", "")
                p = posixpath.join(base_path, name)
                self._path_map[p] = item

    def get_item_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._path_map.get(path)

    def clear(self):
        with self._lock:
            self._folders.clear()
            self._path_map.clear()

class XunleiWebDAVHandler(http.server.BaseHTTPRequestHandler):
    server_version = "XunleiWebDAV/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def bridge(self) -> XunleiWebBridge:
        return self.server.bridge

    @property
    def cache(self) -> WebDAVCache:
        return self.server.cache

    def _check_auth(self) -> bool:
        if not self.server.auth_user or not self.server.auth_pass:
            return True
        auth_hdr = self.headers.get("Authorization")
        if not auth_hdr or not auth_hdr.startswith("Basic "):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Xunlei Agent WebDAV"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return False
        try:
            raw = base64.b64decode(auth_hdr[6:]).decode("utf-8")
            u, p = raw.split(":", 1)
            if u == self.server.auth_user and p == self.server.auth_pass:
                return True
        except Exception:
            pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Xunlei Agent WebDAV"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Invalid credentials")
        return False

    def _clean_path(self) -> str:
        raw_path = urllib.parse.unquote(self.path.split("?")[0])
        clean = posixpath.normpath(raw_path)
        prefix = self.server.url_prefix
        if prefix and clean.startswith(prefix):
            clean = clean[len(prefix):]
        if not clean or clean == ".":
            clean = "/"
        if not clean.startswith("/"):
            clean = "/" + clean
        return clean

    def do_OPTIONS(self):
        if not self._check_auth():
            return
        self.send_response(200)
        self.send_header("DAV", "1, 2")
        self.send_header("Allow", "OPTIONS, GET, HEAD, PROPFIND")
        self.send_header("MS-Author-Via", "DAV")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PROPFIND(self):
        if not self._check_auth():
            return
        depth = self.headers.get("Depth", "1")
        clean_path = self._clean_path()

        # Resolve files
        items = []
        if clean_path == "/":
            cached = self.cache.get_folder("")
            if cached is not None:
                items = cached
            else:
                res = self.bridge.list_files(parent_id="", limit=200)
                if res.get("status") == "success" and "data" in res:
                    raw_files = res["data"].get("files", [])
                    items = [f for f in raw_files if f.get("id") and f.get("name")]
                    self.cache.set_folder("", items, base_path="/")
        else:
            # Look up path in cache
            target_item = self.cache.get_item_by_path(clean_path)
            if not target_item:
                # Refresh root first to populate cache
                res = self.bridge.list_files(parent_id="", limit=200)
                if res.get("status") == "success" and "data" in res:
                    raw_files = res["data"].get("files", [])
                    items = [f for f in raw_files if f.get("id") and f.get("name")]
                    self.cache.set_folder("", items, base_path="/")
                    target_item = self.cache.get_item_by_path(clean_path)

            if not target_item:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Path not found")
                return

            is_folder = target_item.get("kind") == "drive#folder" or "folder" in target_item.get("mime_type", "")
            if is_folder and depth == "1":
                folder_id = target_item.get("id", "")
                cached = self.cache.get_folder(folder_id)
                if cached is not None:
                    items = cached
                else:
                    res = self.bridge.list_files(parent_id=folder_id, limit=200)
                    if res.get("status") == "success" and "data" in res:
                        raw_files = res["data"].get("files", [])
                        items = [f for f in raw_files if f.get("id") and f.get("name")]
                        self.cache.set_folder(folder_id, items, base_path=clean_path)
            else:
                items = [target_item]

        # Generate WebDAV multistatus XML
        prefix = self.server.url_prefix.rstrip("/")
        xml_chunks = [
            '<?xml version="1.0" encoding="utf-8" ?>',
            '<D:multistatus xmlns:D="DAV:">'
        ]

        # Self element
        self_href = urllib.parse.quote(posixpath.join(prefix, clean_path.lstrip("/")))
        if clean_path == "/" and not self_href.endswith("/"):
            self_href += "/"
        xml_chunks.append(f"""
  <D:response>
    <D:href>{self_href}</D:href>
    <D:propstat>
      <D:prop>
        <D:displayname>{html.escape(posixpath.basename(clean_path.rstrip("/")) or "root")}</D:displayname>
        <D:resourcetype><D:collection/></D:resourcetype>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>""")

        if depth != "0":
            for item in items:
                name = item.get("name", "")
                item_path = posixpath.join(prefix, clean_path.lstrip("/"), name)
                is_dir = item.get("kind") == "drive#folder" or "folder" in item.get("mime_type", "")
                href = urllib.parse.quote(item_path)
                if is_dir and not href.endswith("/"):
                    href += "/"

                size = int(item.get("size", 0))
                mtime_str = item.get("modified_time") or item.get("created_time")
                rfc_date = "Thu, 01 Jan 1970 00:00:00 GMT"
                if mtime_str:
                    try:
                        # parse ISO 8601 date
                        dt = datetime.datetime.fromisoformat(mtime_str)
                        rfc_date = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                    except Exception:
                        pass

                resourcetype = "<D:collection/>" if is_dir else ""
                mime = item.get("mime_type") or ("httpd/unix-directory" if is_dir else "application/octet-stream")

                xml_chunks.append(f"""
  <D:response>
    <D:href>{href}</D:href>
    <D:propstat>
      <D:prop>
        <D:displayname>{html.escape(name)}</D:displayname>
        <D:getcontentlength>{size}</D:getcontentlength>
        <D:resourcetype>{resourcetype}</D:resourcetype>
        <D:getlastmodified>{rfc_date}</D:getlastmodified>
        <D:getcontenttype>{html.escape(mime)}</D:getcontenttype>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>""")

        xml_chunks.append("</D:multistatus>")
        body = "".join(xml_chunks).encode("utf-8")

        self.send_response(207)
        self.send_header("Content-Type", 'application/xml; charset="utf-8"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self._handle_get_or_head(is_head=True)

    def do_GET(self):
        self._handle_get_or_head(is_head=False)

    def _handle_get_or_head(self, is_head: bool):
        if not self._check_auth():
            return
        clean_path = self._clean_path()
        if clean_path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if not is_head:
                self.wfile.write(b"<h1>Xunlei Agent WebDAV Service Running</h1><p>Compatible with OpenList, AList, RaiDrive, Infuse.</p>")
            return

        target_item = self.cache.get_item_by_path(clean_path)
        if not target_item:
            # Refresh directory
            res = self.bridge.list_files(parent_id="", limit=200)
            if res.get("status") == "success" and "data" in res:
                raw_files = res["data"].get("files", [])
                items = [f for f in raw_files if f.get("id") and f.get("name")]
                self.cache.set_folder("", items, base_path="/")
                target_item = self.cache.get_item_by_path(clean_path)

        if not target_item:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if not is_head:
                self.wfile.write(b"File not found")
            return

        file_id = target_item.get("id")
        links = target_item.get("links", {})
        direct_link = target_item.get("web_content_link") or (links.get("application/octet-stream") or {}).get("url")

        if not direct_link:
            # Retrieve fresh batchGetFileInfo
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    b, ctx = self.bridge._get_context(p)
                    page = ctx.new_page()
                    page.goto("https://pan.xunlei.com/", wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    batch = page.evaluate(f"""async () => {{
                        const store = window.$nuxt ? window.$nuxt.$store : null;
                        if (!store) return null;
                        return await store.dispatch('drive/batchGetFileInfo', {{ ids: [{json.dumps(file_id)}] }});
                    }}""")
                    b.close()
                    if batch and isinstance(batch, dict) and "files" in batch and batch["files"]:
                        fobj = batch["files"][0]
                        flinks = fobj.get("links", {})
                        direct_link = fobj.get("web_content_link") or (flinks.get("application/octet-stream") or {}).get("url")
            except Exception as e:
                sys.stderr.write(f"[WebDAV] Error querying direct link for {file_id}: {e}\n")

        if not direct_link:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if not is_head:
                self.wfile.write(b"Failed to acquire direct CDN download link")
            return

        # 302 Redirect directly to Xunlei CDN link (Zero proxy bandwidth, maximum speed!)
        self.send_response(302)
        self.send_header("Location", direct_link)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

class XunleiWebDAVServer(http.server.ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        auth_user: Optional[str] = None,
        auth_pass: Optional[str] = None,
        cache_ttl: int = 180,
        url_prefix: str = "/dav",
        bridge: Optional[XunleiWebBridge] = None
    ):
        self.auth_user = auth_user
        self.auth_pass = auth_pass
        self.url_prefix = url_prefix or "/dav"
        self.cache = WebDAVCache(ttl=cache_ttl)
        self.bridge = bridge or XunleiWebBridge()
        super().__init__(server_address, XunleiWebDAVHandler)

def run_webdav_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    auth_user: Optional[str] = None,
    auth_pass: Optional[str] = None,
    cache_ttl: int = 180,
    url_prefix: str = "/dav"
):
    addr = (host, port)
    server = XunleiWebDAVServer(
        addr,
        auth_user=auth_user,
        auth_pass=auth_pass,
        cache_ttl=cache_ttl,
        url_prefix=url_prefix
    )
    print("=" * 60)
    print("  迅雷网盘 WebDAV 挂载服务 (Xunlei Agent WebDAV)")
    print("=" * 60)
    print(f"  服务监听:  http://{host}:{port}{url_prefix}")
    print(f"  缓存 TTL:  {cache_ttl} 秒")
    if auth_user:
        print(f"  认证账号:  {auth_user}")
    else:
        print(f"  访问认证:  无 (免密)")
    print(f"  直链模式:  302 Redirect (客户端直连迅雷全国 CDN 高速流)")
    print("=" * 60)
    print("  [OpenList / AList 挂载配置指南]")
    print(f"  1. 在 OpenList 管理后台中点击 [添加存储] -> 驱动选择 [WebDAV]")
    print(f"  2. 挂载路径填写: /迅雷云盘")
    print(f"  3. 地址填写:     http://<IP>:{port}{url_prefix}")
    if auth_user:
        print(f"  4. 用户名/密码:  {auth_user} / {auth_pass}")
    print("  4. WebDAV 策略选择: [302 重定向] 或 [本地代理]")
    print("=" * 60)
    print("按 Ctrl+C 停止服务...\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] WebDAV 服务已安全停止。")
        server.server_close()
