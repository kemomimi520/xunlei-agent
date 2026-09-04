"""
Xunlei Cloud Agent - A lightweight, full-featured Xunlei Drive CLI & Agent Tool for Linux
"""

from .core.auth import XunleiAuth
from .core.pan import XunleiPanClient
from .core.downloader import Downloader
from .core.webdav import XunleiWebDAVServer, run_webdav_server
from .agent_tool import XunleiAgentTool

__version__ = "1.0.0"

__all__ = [
    "XunleiAuth",
    "XunleiPanClient",
    "Downloader",
    "XunleiWebDAVServer",
    "run_webdav_server",
    "XunleiAgentTool",
]

