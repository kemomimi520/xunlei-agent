import json
import os
import sys
from typing import Dict, Any, List, Optional
from .core.auth import XunleiAuth
from .core.pan import XunleiPanClient
from .core.pan_bridge import XunleiWebBridge
from .core.downloader import Downloader

class XunleiAgentTool:
    """
    High-level Agent Tool for AI Models & Automation workflows.
    Provides complete cloud drive management and end-to-end share fetching & downloading.
    """

    def __init__(self, config_path: Optional[str] = None, default_download_dir: Optional[str] = None):
        self.auth = XunleiAuth(config_path=config_path)
        self.pan = XunleiPanClient(auth=self.auth)
        self.bridge = XunleiWebBridge(default_download_dir=default_download_dir)
        self.downloader = Downloader(default_download_dir=default_download_dir)

    def check_space(self) -> Dict[str, Any]:
        """[Agent Action] Check Xunlei Cloud Drive capacity and available space."""
        return self.pan.get_space()

    def list_files(self, parent_id: str = "", limit: int = 100) -> Dict[str, Any]:
        """[Agent Action] List files and directories in Xunlei Cloud Drive."""
        return self.pan.list_files(parent_id=parent_id, limit=limit)

    def save_share(self, share_url: str, passcode: str = "") -> Dict[str, Any]:
        """[Agent Action] Save Xunlei share link to cloud drive."""
        return self.pan.save_share(share_url=share_url, passcode=passcode)

    def delete_files(self, file_ids: List[str], permanent: bool = True) -> Dict[str, Any]:
        """[Agent Action] Delete files or directories from Xunlei Cloud Drive to free up space."""
        return self.pan.delete_files(file_ids=file_ids, permanent=permanent)

    def empty_trash(self) -> Dict[str, Any]:
        """[Agent Action] Empty Xunlei Cloud Drive trash bin."""
        return self.pan.empty_trash()

    def fetch_and_download(
        self,
        share_url: str,
        passcode: str = "",
        download_to: Optional[str] = None,
        auto_clean_drive: bool = True,
    ) -> Dict[str, Any]:
        """
        [Agent Action] End-to-end execution:
        1. Resolve Xunlei share link
        2. Transfer to temporary cloud drive folder
        3. Extract direct CDN download URLs
        4. Download files to local Linux server directory via Aria2 16-connections
        5. (Optional) Auto-clean transferred files from drive to save quota
        """
        return self.bridge.fetch_and_download(
            share_url=share_url,
            passcode=passcode,
            download_to=download_to,
            auto_clean_drive=auto_clean_drive
        )

    def download_file(
        self,
        file_id: str,
        filename: Optional[str] = None,
        download_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        [Agent Action] Directly download an existing file from Xunlei Cloud Drive by file_id.
        """
        return self.pan.download_file(file_id=file_id, filename=filename, download_to=download_to)

    @classmethod

    def get_tool_schema(cls) -> List[Dict[str, Any]]:
        """Return OpenAI / Function Calling JSON schema definitions for Agent integration."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "xunlei_fetch_and_download",
                    "description": "解析迅雷网盘分享链接，秒级转存并高速下载到 Linux 本地磁盘路径，下载后可自动清理网盘空间。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "share_url": {
                                "type": "string",
                                "description": "迅雷网盘分享链接 (如 https://pan.xunlei.com/s/xxx 或短链 key)"
                            },
                            "passcode": {
                                "type": "string",
                                "description": "分享链接提取码 (如 myjp)，若无则为空"
                            },
                            "download_to": {
                                "type": "string",
                                "description": "服务器本地目标下载目录路径，默认为 /opt/xunlei-agent/downloads"
                            },
                            "auto_clean_drive": {
                                "type": "boolean",
                                "description": "下载完成后是否自动删除网盘内的临时转存文件并清空回收站，默认为 true"
                            }
                        },
                        "required": ["share_url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "xunlei_check_space",
                    "description": "查询迅雷云盘的总空间、已用空间和剩余可用空间。",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "xunlei_list_files",
                    "description": "列出迅雷网盘中的文件和文件夹列表。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "parent_id": {
                                "type": "string",
                                "description": "目标文件夹ID，留空表示根目录"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "xunlei_delete_files",
                    "description": "从迅雷网盘中删除指定的文件或文件夹以释放空间。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要删除的文件或文件夹 ID 列表"
                            },
                            "permanent": {
                                "type": "boolean",
                                "description": "是否彻底删除（永久删除并清空回收站），默认为 true"
                            }
                        },
                        "required": ["file_ids"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "xunlei_download_file",
                    "description": "根据文件 ID 直接将网盘已有文件高速下载到本地磁盘路径。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {
                                "type": "string",
                                "description": "要下载的文件 ID"
                            },
                            "filename": {
                                "type": "string",
                                "description": "自定义保存文件名（可选，默认使用网盘中的原始文件名）"
                            },
                            "download_to": {
                                "type": "string",
                                "description": "服务器本地目标下载目录路径（可选）"
                            }
                        },
                        "required": ["file_id"]
                    }
                }
            }
        ]
