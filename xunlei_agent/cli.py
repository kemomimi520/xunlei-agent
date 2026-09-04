#!/usr/bin/env python3
"""
CLI entrypoint for Xunlei Agent Linux Toolkit.
"""

import argparse
import json
import os
import sys
import time
from .core.auth import XunleiAuth
from .agent_tool import XunleiAgentTool

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--config", "-c", help="配置文件路径 (默认: ~/.config/xunlei/config.json)")
    common_parser.add_argument("--json", action="store_true", help="以结构化 JSON 格式输出结果")

    parser = argparse.ArgumentParser(
        prog="xunlei-agent",
        description="迅雷网盘 Linux 命令行与 Agent 自动化工具 (全权限管理、转存与高速下载)",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 1. login
    p_login = subparsers.add_parser("login", parents=[common_parser], help="登录迅雷账号")
    p_login.add_argument("--token", help="直接指定 access_token")
    p_login.add_argument("--refresh", help="指定 refresh_token")
    p_login.add_argument("--user-id", help="指定 user_id")
    p_login.add_argument("--device-id", help="指定 device_id")

    # 2. space
    p_space = subparsers.add_parser("space", parents=[common_parser], help="查看迅雷云盘容量与使用情况")

    # 3. ls
    p_ls = subparsers.add_parser("ls", parents=[common_parser], help="列出云盘中的文件与文件夹")
    p_ls.add_argument("parent_id", nargs="?", default="", help="目标目录ID (留空为根目录)")
    p_ls.add_argument("--limit", type=int, default=100, help="单页最大条数")

    # 4. fetch (转存并下载)
    p_fetch = subparsers.add_parser("fetch", parents=[common_parser], help="一键全流程：转存分享链接 -> 提取直链 -> 下载到服务器本地")
    p_fetch.add_argument("url", help="迅雷分享链接 (如 https://pan.xunlei.com/s/xxx 或 share_id)")
    p_fetch.add_argument("--pwd", "-p", default="", help="分享提取码")
    p_fetch.add_argument("--out", "-o", default=None, help="本地下载存放目录 (默认: /opt/xunlei-agent/downloads)")
    p_fetch.add_argument("--no-clean", action="store_true", help="下载完成后保留网盘中的临时转存文件")

    # 5. rm (删除文件)
    p_rm = subparsers.add_parser("rm", parents=[common_parser], help="删除网盘中的文件或文件夹")
    p_rm.add_argument("file_ids", nargs="+", help="文件/目录 ID 列表")

    # 6. empty-trash (清空回收站)
    p_trash = subparsers.add_parser("empty-trash", parents=[common_parser], help="清空网盘回收站释放空间")

    # 7. schema (Agent tools definition)
    p_schema = subparsers.add_parser("schema", parents=[common_parser], help="输出 Agent Function Calling 工具定义 JSON")

    # 8. download (直接下载网盘已有文件)
    p_dl = subparsers.add_parser("download", parents=[common_parser], help="根据文件 ID 下载云盘已有文件到本地")
    p_dl.add_argument("file_id", help="云盘文件 ID")
    p_dl.add_argument("--name", "-n", default=None, help="自定义本地保存文件名")
    p_dl.add_argument("--out", "-o", default=None, help="本地下载存放目录")

    # 9. webdav (WebDAV 挂载服务，支持 OpenList / AList / RaiDrive / Infuse)
    p_dav = subparsers.add_parser("webdav", parents=[common_parser], help="启动 WebDAV 挂载服务端 (兼容 OpenList / AList / RaiDrive)")
    p_dav.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    p_dav.add_argument("--port", "-p", type=int, default=8080, help="监听端口 (默认: 8080)")
    p_dav.add_argument("--user", "-u", default=None, help="WebDAV Basic 认证用户名 (可选)")
    p_dav.add_argument("--password", "-P", default=None, help="WebDAV Basic 认证密码 (可选)")
    p_dav.add_argument("--cache-ttl", type=int, default=180, help="目录缓存时间 (秒，默认: 180)")
    p_dav.add_argument("--path", default="/dav", help="WebDAV 访问路径前缀 (默认: /dav)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    auth = XunleiAuth(config_path=args.config)
    tool = XunleiAgentTool(config_path=args.config)

    if args.command == "login":
        if args.token:
            auth.set_tokens(args.token, args.refresh, args.user_id, args.device_id)
            print(f"[OK] Token 已成功保存至 {auth.config_path}")
            return
        # Interactive QR code login with browser
        try:
            print("[*] 正在启动无头浏览器拉取迅雷扫码登录界面...")
            res = auth.login_with_browser_playwright()
            print(f"[OK] 登录成功！凭据与会话已写入 {auth.config_path}")
        except Exception as e:
            print(f"[ERROR] 登录失败: {e}", file=sys.stderr)
            sys.exit(1)
        return

    elif args.command == "space":
        res = tool.check_space()
        if res.get("status") == "error" or res.get("code") == "UNAUTHORIZED":
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[ERROR] {res.get('message', res.get('error', '未知错误'))}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print("=" * 45)
            print("  迅雷网盘存储空间容量报告")
            print("=" * 45)
            print(f"  总空间:   {res.get('total_human')}")
            print(f"  已使用:   {res.get('used_human')}")
            print(f"  剩余可用: {res.get('available_human')}")
            print("=" * 45)

    elif args.command == "ls":
        res = tool.list_files(parent_id=args.parent_id, limit=args.limit)
        if res.get("status") == "error" or res.get("code") == "UNAUTHORIZED":
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[ERROR] {res.get('message', res.get('error', '未知错误'))}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            files = res.get("files", [])
            print(f"共 {len(files)} 个文件/文件夹:")
            for f in files:
                tag = "<DIR>" if f.get("is_folder") else f"{f.get('size_human', '-'):>8}"
                print(f"  [{tag}] {f.get('name')}  (ID: {f.get('id')})")

    elif args.command == "fetch":
        res = tool.fetch_and_download(
            share_url=args.url,
            passcode=args.pwd,
            download_to=args.out,
            auto_clean_drive=not args.no_clean
        )
        if res.get("status") == "error" or res.get("code") == "UNAUTHORIZED":
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[ERROR] {res.get('message', res.get('error', '未知错误'))}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[*] {res.get('message')}")
            for item in res.get("downloaded_files", []):
                print(f"  - 文件: {item.get('name')}")
                print(f"    路径: {item.get('local_path') or item.get('path')}")
                print(f"    大小: {item.get('size_human')}")
                print(f"    SHA256: {item.get('sha256')}")

    elif args.command == "rm":
        res = tool.delete_files(file_ids=args.file_ids)
        if res.get("status") == "error" or res.get("code") == "UNAUTHORIZED":
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[ERROR] {res.get('message', res.get('error', '未知错误'))}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[OK] 已删除 {len(args.file_ids)} 个文件/文件夹")

    elif args.command == "empty-trash":
        res = tool.empty_trash()
        if res.get("status") == "error" or res.get("code") == "UNAUTHORIZED":
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[ERROR] {res.get('message', res.get('error', '未知错误'))}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[OK] {res.get('message', '回收站已清空')}")

    elif args.command == "schema":
        schema = tool.get_tool_schema()
        print(json.dumps(schema, indent=2, ensure_ascii=False))

    elif args.command == "download":
        res = tool.download_file(file_id=args.file_id, filename=args.name, download_to=args.out)
        if res.get("status") == "error" or res.get("code") == "UNAUTHORIZED":
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[ERROR] {res.get('message', res.get('error', '未知错误'))}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            dl_info = res.get("download", {})
            print(f"[OK] 文件下载成功！")
            print(f"  - 文件名:   {dl_info.get('filename')}")
            print(f"  - 本地路径: {dl_info.get('local_path')}")
            print(f"  - 大小:     {dl_info.get('size_human')} ({dl_info.get('size_bytes')} 字节)")
            print(f"  - 下载耗时: {dl_info.get('duration_seconds')} 秒")
            print(f"  - 平均速度: {dl_info.get('avg_speed')}")
            print(f"  - SHA256:   {dl_info.get('sha256')}")

    elif args.command == "webdav":
        from .core.webdav import run_webdav_server
        run_webdav_server(
            host=args.host,
            port=args.port,
            auth_user=args.user,
            auth_pass=args.password,
            cache_ttl=args.cache_ttl,
            url_prefix=args.path
        )

if __name__ == "__main__":
    main()
