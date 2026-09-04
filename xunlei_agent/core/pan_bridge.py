import json
import os
import re
import sys
import time
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright
from .downloader import Downloader, get_default_download_dir

STATE_PATH = os.path.expanduser("~/.config/xunlei/state.json")
CONFIG_PATH = os.path.expanduser("~/.config/xunlei/config.json")
DEFAULT_DOWNLOAD_DIR = get_default_download_dir()

class XunleiWebBridge:
    def __init__(self, state_path: str = STATE_PATH, default_download_dir: Optional[str] = None):
        self.state_path = state_path
        self.download_dir = default_download_dir or DEFAULT_DOWNLOAD_DIR
        self.downloader = Downloader(default_download_dir=self.download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)

    def _get_context(self, p):
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        if os.path.exists(self.state_path):
            context = browser.new_context(
                storage_state=self.state_path,
                user_agent=ua
            )
        else:
            context = browser.new_context(
                user_agent=ua
            )
        return browser, context

    def _ensure_authenticated_page(self, page, wait_time: int = 3) -> Optional[Dict[str, Any]]:
        """
        Check if page is unauthenticated or redirected to login.
        Returns error dict if unauthenticated, None if OK.
        """
        time.sleep(wait_time)
        url = page.url.lower()
        if "/login" in url or "pan.xunlei.com/login" in url:
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }
        return None

    def get_space(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()

            captured = {"about": None}
            def on_response(response):
                if "/drive/v1/about" in response.url and response.status == 200:
                    try: captured["about"] = response.json()
                    except Exception: pass

            page.on("response", on_response)
            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=30000)
            except Exception:
                pass
            
            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            if captured["about"]:
                browser.close()
                return {"status": "success", "data": captured["about"]}

            try:
                about = page.evaluate("() => window.$nuxt?.$store?.state?.drive?.about")
                if about:
                    browser.close()
                    return {"status": "success", "data": about}
            except Exception:
                pass

            browser.close()
            return {"status": "error", "message": "未获取到网盘空间信息"}

    def list_files(self, parent_id: str = "", limit: int = 50) -> Dict[str, Any]:
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()

            captured = {"files": None}
            def on_response(response):
                if "/drive/v1/files" in response.url and response.status == 200:
                    try:
                        data = response.json()
                        if isinstance(data, dict) and "files" in data:
                            captured["files"] = data
                    except Exception:
                        pass

            page.on("response", on_response)
            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=30000)
            except Exception:
                pass
            
            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            if captured["files"]:
                browser.close()
                return {"status": "success", "data": captured["files"]}

            try:
                res = page.evaluate(f"""async () => {{
                    const store = window.$nuxt?.$store;
                    if (!store) return null;
                    await store.dispatch('drive/getFiles', {{ parent_id: {json.dumps(parent_id)}, limit: {limit} }});
                    const all = Object.values(store.state.drive?.all || {{}});
                    return {{ files: all.filter(x => x.id && x.name) }};
                }}""")
                if res and res.get("files"):
                    browser.close()
                    return {"status": "success", "data": res}
            except Exception:
                pass

            browser.close()
            return {"status": "error", "message": "未获取到文件列表"}

    def save_share(self, share_url: str, passcode: str = "") -> Dict[str, Any]:
        """
        Save a Xunlei share link to user's cloud drive.
        """
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()

            full_url = share_url
            if passcode and "pwd=" not in full_url:
                full_url += f"?pwd={passcode}"

            page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)

            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            if passcode:
                pwd_input = page.query_selector("input[placeholder*='提取码'], input.passcode-input")
                if pwd_input:
                    pwd_input.fill(passcode)
                    btn = page.query_selector("button:has-text('提取'), button:has-text('确定')")
                    if btn:
                        btn.click()
                        time.sleep(3)

            chk_all = page.query_selector(".select-all, input[type='checkbox']")
            if chk_all and not chk_all.is_checked():
                try: chk_all.check(force=True)
                except Exception: pass

            save_btn = page.query_selector("button:has-text('保存到云盘'), button:has-text('转存'), .save-to-pan, button:has-text('转存到网盘')")
            if not save_btn:
                browser.close()
                return {"status": "error", "message": "未找到'保存到云盘'按钮，可能是链接失效或无文件"}

            save_btn.click()
            time.sleep(2)

            modal_btn = page.query_selector(".modal button:has-text('确定'), button:has-text('确定保存'), button.pan-btn-primary")
            if modal_btn:
                modal_btn.click()
                time.sleep(3)

            browser.close()
            return {"status": "success", "message": "分享内容已成功转存至网盘"}

    def delete_files(self, file_ids: List[str]) -> Dict[str, Any]:
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()
            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=20000)
            except Exception:
                pass
            
            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            try:
                res = page.evaluate(f"""async () => {{
                    const store = window.$nuxt?.$store;
                    if (!store) return {{ status: 'error', error: 'Nuxt store not loaded' }};
                    try {{
                        const r = await store.dispatch('drive/batchDeleteFile', {json.dumps(file_ids)});
                        return {{ status: 'success', data: r }};
                    }} catch(e) {{
                        return {{ status: 'error', error: e.toString() }};
                    }}
                }}""")
            except Exception as e:
                auth_err = self._ensure_authenticated_page(page, wait_time=0)
                if auth_err:
                    browser.close()
                    return auth_err
                res = {"status": "error", "error": str(e)}

            browser.close()
            return res

    def empty_trash(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()
            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=20000)
            except Exception:
                pass
            
            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            try:
                res = page.evaluate("""async () => {
                    const store = window.$nuxt?.$store;
                    if (!store) return { status: 'error', error: 'Nuxt store not loaded' };
                    try {
                        const actions = Object.keys(store._actions || {});
                        const trashAction = actions.find(a => /clearTrash|emptyTrash|deleteTrash/i.test(a));
                        if (trashAction) {
                            const r = await store.dispatch(trashAction);
                            return { status: 'success', message: '回收站已成功清空', data: r };
                        }
                        const cred = JSON.parse(localStorage.getItem('credentials') || '{}');
                        const r = await fetch('https://api-pan.xunlei.com/drive/v1/trash', {
                            method: 'DELETE',
                            headers: { 'Authorization': 'Bearer ' + cred.access_token }
                        });
                        return { status: 'success', message: '回收站已成功清空', api_status: r.status };
                    } catch(e) {
                        return { status: 'error', error: e.toString() };
                    }
                }""")
            except Exception as e:
                auth_err = self._ensure_authenticated_page(page, wait_time=0)
                if auth_err:
                    browser.close()
                    return auth_err
                res = {"status": "error", "error": str(e)}

            browser.close()
            return res

    def fetch_and_download(
        self,
        share_url: str,
        passcode: str = "",
        download_to: Optional[str] = None,
        auto_clean_drive: bool = True
    ) -> Dict[str, Any]:
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        out_dir = download_to or self.download_dir
        os.makedirs(out_dir, exist_ok=True)

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()

            # 0. 记录转存前网盘已有文件 ID，确保后续仅下载与清理本次新转存的文件
            initial_file_ids = []
            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=20000)
                init_res = page.evaluate("""async () => {
                    try {
                        const store = window.$nuxt ? window.$nuxt.$store : null;
                        if (!store) return [];
                        const r = await store.dispatch('drive/getFiles', { parent_id: '', limit: 100 });
                        return (r?.files || []).map(x => x.id).filter(Boolean);
                    } catch(e) { return []; }
                }""")
                if isinstance(init_res, list):
                    initial_file_ids = init_res
            except Exception:
                pass

            # 1. 转存分享链接
            full_url = share_url
            if passcode and "pwd=" not in full_url:
                full_url += f"?pwd={passcode}"

            page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)

            auth_err = self._ensure_authenticated_page(page, wait_time=2)
            if auth_err:
                browser.close()
                return auth_err

            if passcode:
                pwd_input = page.query_selector("input[placeholder*='提取码'], input.passcode-input")
                if pwd_input:
                    pwd_input.fill(passcode)
                    btn = page.query_selector("button:has-text('提取'), button:has-text('确定')")
                    if btn:
                        btn.click()
                        time.sleep(3)

            chk_all = page.query_selector(".select-all, input[type='checkbox']")
            if chk_all and not chk_all.is_checked():
                try: chk_all.check(force=True)
                except Exception: pass

            save_btn = page.query_selector("button:has-text('保存到云盘'), button:has-text('转存'), .save-to-pan, button:has-text('转存到网盘')")
            if save_btn:
                save_btn.click()
                time.sleep(2)
                modal_btn = page.query_selector(".modal button:has-text('确定'), button:has-text('确定保存'), button.pan-btn-primary")
                if modal_btn:
                    modal_btn.click()
                    time.sleep(3)

            # 2. 进入网盘获取转存文件与真实直链
            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=20000)
            except Exception:
                pass

            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            try:
                drive_data = page.evaluate("""async () => {
                    const store = window.$nuxt?.$store;
                    if (!store) return { items: [], results: [] };
                    
                    let fileList = [];
                    try {
                        const res = await store.dispatch('drive/getFiles', { parent_id: '', limit: 50 });
                        fileList = res?.files || [];
                    } catch(e) {
                        const elements = Array.from(document.querySelectorAll('li[data-file-id]'));
                        fileList = elements.map(el => ({
                            id: el.getAttribute('data-file-id'),
                            name: el.querySelector('.SourceListItem__name--y6dVw, .highlight-text, a')?.innerText?.trim(),
                        }));
                    }

                    const initSet = new Set({json.dumps(initial_file_ids)});
                    let items = fileList.filter(x => x.id && x.name && !initSet.has(x.id) && !['超级保险箱', '我的转存', '我的资源'].includes(x.name));
                    if (items.length === 0) {
                        items = fileList.filter(x => x.id && x.name && !['超级保险箱', '我的转存', '我的资源'].includes(x.name));
                    }
                    const results = [];
                    for (const it of items) {
                        try {
                            const batch = await store.dispatch('drive/batchGetFileInfo', {{ ids: [it.id] }});
                            const fileObj = batch?.files?.[0];
                            const link = fileObj?.web_content_link || fileObj?.links?.['application/octet-stream']?.url;
                            if (link) {
                                results.push({{
                                    id: it.id,
                                    name: it.name,
                                    link: link
                                }});
                            }
                        } catch(e) {{}}
                    }
                    return {{ items, results }};
                }}""")
            except Exception as e:
                auth_err = self._ensure_authenticated_page(page, wait_time=0)
                if auth_err:
                    browser.close()
                    return auth_err
                browser.close()
                return {"status": "error", "message": f"获取网盘文件列表失败: {e}"}

            download_results = []
            files_to_clean = []

            for f in drive_data.get("results", []):
                name = f.get("name")
                f_id = f.get("id")
                link = f.get("link")
                
                if link and name:
                    files_to_clean.append(f_id)
                    res_dl = self.downloader.download(
                        url=link,
                        filename=name,
                        out_dir=out_dir
                    )
                    download_results.append(res_dl)

            # 3. 自动清理转存文件释放空间
            if auto_clean_drive and files_to_clean:
                page.evaluate(f"""async () => {{
                    try {{
                        await window.$nuxt?.$store.dispatch('drive/batchDeleteFile', {json.dumps(files_to_clean)});
                    }} catch(e) {{}}
                }}""")

            browser.close()

            return {
                "status": "success",
                "message": f"成功下载 {len(download_results)} 个文件到本地",
                "downloaded_files": download_results,
                "cleaned_from_pan": auto_clean_drive
            }

    def download_file(
        self,
        file_id: str,
        filename: Optional[str] = None,
        download_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Directly download an existing file from Xunlei Cloud Drive by file_id.
        """
        if not os.path.exists(self.state_path) and not os.path.exists(CONFIG_PATH):
            return {
                "status": "error",
                "code": "UNAUTHORIZED",
                "message": "迅雷账号未登录或会话已过期，请先运行 'xunlei-agent login' 进行扫码登录。"
            }

        out_dir = download_to or self.download_dir
        os.makedirs(out_dir, exist_ok=True)

        with sync_playwright() as p:
            browser, context = self._get_context(p)
            page = context.new_page()

            try:
                page.goto("https://pan.xunlei.com/", wait_until="networkidle", timeout=30000)
            except Exception:
                pass

            auth_err = self._ensure_authenticated_page(page, wait_time=1)
            if auth_err:
                browser.close()
                return auth_err

            try:
                batch_info = page.evaluate(f"""async () => {{
                    const store = window.$nuxt ? window.$nuxt.$store : null;
                    if (!store) return null;
                    try {{
                        await store.dispatch('drive/getFiles', {{ parent_id: '', limit: 50 }});
                    }} catch(e) {{}}
                    try {{
                        const batch = await store.dispatch('drive/batchGetFileInfo', {{ ids: [{json.dumps(file_id)}] }});
                        return batch;
                    }} catch(e) {{
                        return {{ error: e.toString() }};
                    }}
                }}""")
            except Exception as e:
                browser.close()
                return {"status": "error", "message": f"调用网盘直链接口失败: {e}"}

            browser.close()

            if not batch_info or not isinstance(batch_info, dict) or "files" not in batch_info:
                return {
                    "status": "error",
                    "message": f"未能获取文件直链或文件不存在 (ID: {file_id})",
                    "detail": batch_info
                }

            files = batch_info.get("files", [])
            if not files:
                return {
                    "status": "error",
                    "message": f"未找到对应文件 (ID: {file_id})"
                }

            file_obj = files[0]
            actual_name = filename or file_obj.get("name") or f"file_{file_id}.bin"
            links = file_obj.get("links", {})
            direct_link = file_obj.get("web_content_link") or (links.get("application/octet-stream") or {}).get("url")

            if not direct_link:
                return {
                    "status": "error",
                    "message": f"文件暂无可用高速下载直链 (ID: {file_id})",
                    "file_info": file_obj
                }

            res = self.downloader.download(
                url=direct_link,
                filename=actual_name,
                out_dir=out_dir
            )
            return {
                "status": "success",
                "file_id": file_id,
                "file_info": {
                    "id": file_obj.get("id"),
                    "name": actual_name,
                    "size": file_obj.get("size"),
                    "mime_type": file_obj.get("mime_type")
                },
                "download": res
            }

