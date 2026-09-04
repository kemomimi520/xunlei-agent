import json
import re
import sys
import time
from typing import Dict, Any, List, Optional
import requests
from .auth import XunleiAuth, DEFAULT_UA
from .pan_bridge import XunleiWebBridge

API_BASE_URLS = [
    "https://api-pan.xunlei.com/drive/v1",
    "https://api-pan.xunleix.com/drive/v1",
]

class XunleiPanClient:
    """Full-featured client for Xunlei Cloud Drive operations with intelligent Web Bridge fallback."""

    def __init__(self, auth: Optional[XunleiAuth] = None):
        self.auth = auth or XunleiAuth()
        self.session = requests.Session()
        self.base_url = API_BASE_URLS[0]
        self.bridge = XunleiWebBridge()

    def _get_headers(self) -> Dict[str, str]:
        token = self.auth.get_valid_token()
        if not token:
            raise PermissionError("迅雷账号未登录，请先执行登录")
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": DEFAULT_UA,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-device-id": self.auth.device_id,
            "x-client-id": "XW5SkOhLDjnOZP7J",
            "x-client-version": "1.0.0",
        }

    # ==================== 1. 云盘容量与基础信息 ====================
    def get_space(self) -> Dict[str, Any]:
        """获取网盘容量与使用情况"""
        res = self.bridge.get_space()
        if res.get("status") == "success" and "data" in res:
            about = res["data"]
            quota = (about.get("quota") or about.get("space") or {}) if isinstance(about, dict) else {}
            total = int(quota.get("limit") or quota.get("total") or 0)
            used = int(quota.get("usage") or quota.get("used") or 0)
            avail = max(0, total - used)
            return {
                "total_bytes": total,
                "used_bytes": used,
                "available_bytes": avail,
                "total_human": self._human_size(total),
                "used_human": self._human_size(used),
                "available_human": self._human_size(avail),
                "raw": about,
            }
        return res

    # ==================== 2. 文件列表与查询 ====================
    def list_files(self, parent_id: str = "", limit: int = 100) -> Dict[str, Any]:
        """列出云盘中的文件和文件夹"""
        res = self.bridge.list_files(parent_id=parent_id, limit=limit)
        if res.get("status") == "success" and "data" in res:
            raw_files = res["data"].get("files", []) if isinstance(res["data"], dict) else []
            files = []
            for item in raw_files:
                is_dir = item.get("kind") == "drive#folder" or item.get("mime_type") == "application/vnd.xunlei.folder"
                size = int(item.get("size", 0))
                files.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "size_bytes": size,
                    "size_human": self._human_size(size),
                    "is_folder": is_dir,
                    "created_time": item.get("created_time"),
                    "modified_time": item.get("modified_time"),
                })
            return {
                "status": "success",
                "count": len(files),
                "files": files
            }
        return res

    # ==================== 3. 转存分享链接 ====================
    def save_share(self, share_url: str, passcode: str = "") -> Dict[str, Any]:
        """将分享链接转存至云盘"""
        return self.bridge.save_share(share_url, passcode=passcode)

    # ==================== 4. 删除文件 ====================
    def delete_files(self, file_ids: List[str], permanent: bool = True) -> Dict[str, Any]:
        """删除文件"""
        return self.bridge.delete_files(file_ids)

    def empty_trash(self) -> Dict[str, Any]:
        """清空回收站"""
        return self.bridge.empty_trash()

    # ==================== 5. 下载网盘文件 ====================
    def download_file(self, file_id: str, filename: Optional[str] = None, download_to: Optional[str] = None) -> Dict[str, Any]:
        """下载云盘指定文件到本地"""
        return self.bridge.download_file(file_id=file_id, filename=filename, download_to=download_to)


    @staticmethod
    def _human_size(num_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:.2f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.2f} PB"
