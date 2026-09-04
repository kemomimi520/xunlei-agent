import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Dict, Any, Optional
import requests
from .auth import DEFAULT_UA

def get_default_download_dir() -> str:
    if os.environ.get("XUNLEI_DOWNLOAD_DIR"):
        return os.environ["XUNLEI_DOWNLOAD_DIR"]
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), "Downloads", "xunlei")
    return "/opt/xunlei-agent/downloads"

def calculate_sha256(file_path: str) -> str:
    """Calculate SHA256 hash using Python built-in hashlib."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

class Downloader:
    """Downloader engine with Aria2c multi-thread support and Python streaming fallback."""

    def __init__(self, default_download_dir: Optional[str] = None):
        self.download_dir = default_download_dir or get_default_download_dir()
        os.makedirs(self.download_dir, exist_ok=True)
        self.has_aria2 = shutil.which("aria2c") is not None

    def sanitize_filename(self, filename: str) -> str:
        """Filter dangerous characters from filename."""
        clean = re.sub(r'[\\/*?:"<>|]', "_", filename)
        return clean.strip() or f"download_{int(time.time())}.bin"

    def download(
        self,
        url: str,
        filename: str,
        out_dir: Optional[str] = None,
        user_agent: str = DEFAULT_UA,
        max_connections: int = 16,
    ) -> Dict[str, Any]:
        """
        Download a file to the local Linux filesystem.
        """
        target_dir = out_dir or self.download_dir
        os.makedirs(target_dir, exist_ok=True)
        clean_name = self.sanitize_filename(filename)
        target_file = os.path.join(target_dir, clean_name)

        start_time = time.time()

        if self.has_aria2:
            try:
                res = self._download_aria2(url, clean_name, target_dir, user_agent, max_connections)
                return res
            except Exception as e:
                sys.stderr.write(f"[Downloader] Aria2 failed: {e}, falling back to Python stream...\n")

        # Python fallback download
        return self._download_python(url, target_file, user_agent, start_time)

    def _download_aria2(
        self,
        url: str,
        filename: str,
        target_dir: str,
        user_agent: str,
        max_connections: int,
    ) -> Dict[str, Any]:
        start_time = time.time()
        target_file = os.path.join(target_dir, filename)

        cmd = [
            "aria2c",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            f"--max-connection-per-server={max_connections}",
            f"--split={max_connections}",
            "--min-split-size=1M",
            f"--user-agent={user_agent}",
            f"--dir={target_dir}",
            f"--out={filename}",
            "--summary-interval=5",
            url,
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"aria2c exit code {proc.returncode}: {proc.stderr}")

        if not os.path.exists(target_file):
            raise FileNotFoundError(f"Downloaded file not found at {target_file}")

        file_size = os.path.getsize(target_file)
        duration = time.time() - start_time
        speed = file_size / duration if duration > 0 else 0

        sha = calculate_sha256(target_file)

        return {
            "status": "success",
            "method": "aria2c",
            "filename": filename,
            "local_path": os.path.abspath(target_file),
            "size_bytes": file_size,
            "size_human": self._format_size(file_size),
            "duration_seconds": round(duration, 2),
            "avg_speed": f"{self._format_size(int(speed))}/s",
            "sha256": sha,
        }

    def _download_python(
        self,
        url: str,
        target_file: str,
        user_agent: str,
        start_time: float,
        max_workers: int = 8,
    ) -> Dict[str, Any]:
        headers = {"User-Agent": user_agent}
        total_size = 0
        accept_ranges = False
        try:
            with requests.head(url, headers=headers, timeout=15, allow_redirects=True) as h:
                if h.status_code == 200:
                    total_size = int(h.headers.get("content-length", 0))
                    accept_ranges = "bytes" in h.headers.get("accept-ranges", "").lower()
        except Exception:
            pass

        if accept_ranges and total_size > 2 * 1024 * 1024:
            try:
                return self._download_python_multithread(url, target_file, user_agent, total_size, start_time, max_workers)
            except Exception as e:
                sys.stderr.write(f"[Downloader] Multi-thread range download failed: {e}, falling back to stream...\n")

        return self._download_python_stream(url, target_file, user_agent, start_time)

    def _download_python_multithread(
        self,
        url: str,
        target_file: str,
        user_agent: str,
        total_size: int,
        start_time: float,
        max_workers: int = 8,
    ) -> Dict[str, Any]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with open(target_file, "wb") as f:
            f.truncate(total_size)

        num_workers = min(max_workers, max(1, total_size // (1024 * 1024)))
        chunk_size = (total_size + num_workers - 1) // num_workers

        def download_part(part_idx: int):
            start = part_idx * chunk_size
            end = min(total_size - 1, start + chunk_size - 1)
            if start > end:
                return
            part_headers = {
                "User-Agent": user_agent,
                "Range": f"bytes={start}-{end}"
            }
            with requests.get(url, headers=part_headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(target_file, "r+b") as fp:
                    fp.seek(start)
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if chunk:
                            fp.write(chunk)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(download_part, i) for i in range(num_workers)]
            for fut in as_completed(futures):
                fut.result()

        file_size = os.path.getsize(target_file)
        if file_size != total_size:
            raise RuntimeError(f"Downloaded size mismatch: expected {total_size}, got {file_size}")

        duration = time.time() - start_time
        speed = file_size / duration if duration > 0 else 0
        sha = calculate_sha256(target_file)

        return {
            "status": "success",
            "method": f"python_multithread_{num_workers}w",
            "filename": os.path.basename(target_file),
            "local_path": os.path.abspath(target_file),
            "size_bytes": file_size,
            "size_human": self._format_size(file_size),
            "duration_seconds": round(duration, 2),
            "avg_speed": f"{self._format_size(int(speed))}/s",
            "sha256": sha,
        }

    def _download_python_stream(
        self,
        url: str,
        target_file: str,
        user_agent: str,
        start_time: float,
    ) -> Dict[str, Any]:
        headers = {"User-Agent": user_agent}
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(target_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        file_size = os.path.getsize(target_file)
        duration = time.time() - start_time
        speed = file_size / duration if duration > 0 else 0
        sha = calculate_sha256(target_file)

        return {
            "status": "success",
            "method": "python_stream",
            "filename": os.path.basename(target_file),
            "local_path": os.path.abspath(target_file),
            "size_bytes": file_size,
            "size_human": self._format_size(file_size),
            "duration_seconds": round(duration, 2),
            "avg_speed": f"{self._format_size(int(speed))}/s",
            "sha256": sha,
        }

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        double_size = float(size_bytes)
        while double_size >= 1024 and i < len(units) - 1:
            double_size /= 1024
            i += 1
        return f"{double_size:.2f} {units[i]}"
