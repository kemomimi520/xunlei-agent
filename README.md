# 迅雷网盘转存、下载与 WebDAV 挂载服务

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/WebDAV-302_Redirect-blue.svg" alt="WebDAV 302">
  <img src="https://img.shields.io/badge/Mount-OpenList%20%7C%20AList-orange.svg" alt="OpenList/AList">
  <img src="https://img.shields.io/badge/Model_Skill-Ready-purple.svg" alt="Model Skill Ready">
</p>

> **当前为测试版本，版本号 [1.0.0-beta](https://github.com/kemomimi520/xunlei-agent)，且并未大规模验证。**

本项目专为**大模型 Skill 调度**、**资源转存下载**与 **OpenList / AList 等主流平台挂载**而设计。

提供**标准 WebDAV 挂载服务（完美支持 OpenList / AList / RaiDrive / Infuse 等）**、**全自动分享链接转存与高速下载**、**Aria2 / 多线程 Range 分片下载引擎**，并原生提供标准模型 Skill 接入能力。

---

## 核心特性

- **OpenList / AList 极速挂载 (WebDAV 302 重定向)**：
  - 内置标准 WebDAV 服务端（`xunlei-agent webdav`），一键提供挂载接口。
  - **彻底解决痛点**：无需每次手动打开 F12 抓取易失效的 `x-captcha-token`，后台自动维护持久化会话与续期。
  - **302 直链高速重定向**：媒体播放与文件下载直连迅雷官方全国 CDN 高速节点，**零中转带宽消耗、零 CPU 占用**！
  - **多级内存元数据缓存**：目录快速秒开，杜绝重复调用浏览器的等待延迟。
- **分享链接一键转存与高速下载 (`fetch`)**：
  - 自动解析分享链接（支持提取码）。
  - 云端秒级转存 -> 提取真实 CDN 直链 -> 16 线程并发高速下载。
  - **差异化精准清理防护**：下载后可自动清理临时文件释放空间，且**仅清理本次转存的新文件**，绝不误伤网盘原有数据。
- **双引擎自适应高速下载器 (`downloader`)**：
  - 优先调用 `aria2c` 16 线程高速下载；
  - 环境无 `aria2c` 时，自动平滑切入**原生 Python HTTP Range 多线程分片并发**，全速跑满带宽。
- **大模型 Skill 原生支持**：
  - 自带标准 `SKILL.md`，可直接复制或导入至 Cursor / Claude Code / Antigravity 等 AI 编程助手。
  - 让模型能够自主理解自然语言并驱动迅雷网盘执行查询、转存与下载。
  - 所有 CLI 命令均支持 `--json` 机器格式输出，内置标准 OpenAI Function Calling Schema。

---

## 快速上手

### 1. 安装环境

```bash
# 克隆仓库并安装
git clone https://github.com/kemomimi520/xunlei-agent.git
cd xunlei-agent
pip install -e .

# 安装无头浏览器驱动
playwright install chromium
```

### 2. 账号登录

```bash
# 终端扫码登录（自动生成二维码图片）
xunlei-agent login

# 或直接通过 Token 登录
xunlei-agent login --token "<your_access_token>" --refresh "<your_refresh_token>"
```

---

## 命令行使用指南

### 1. 启动 WebDAV 服务（挂载到 OpenList / AList / 影视播放器）

```bash
# 默认启动于 0.0.0.0:8080/dav（免密访问）
xunlei-agent webdav

# 自定义端口、挂载前缀与 Basic 认证账号密码
xunlei-agent webdav --port 8080 --user admin --password mypassword --path /dav
```

#### OpenList / AList 挂载配置步骤：
1. 打开 OpenList / AList 管理后台 -> 点击 **【存储】** -> **【添加】**。
2. **驱动**：选择 `WebDAV`。
3. **挂载路径**：填写 `/迅雷云盘`。
4. **WebDAV 地址**：`http://127.0.0.1:8080/dav`（若远程访问填服务器 IP）。
5. **用户名 / 密码**：填写启动时配置的凭据（若未设则留空）。
6. **WebDAV 策略**：推荐选择 **【302 重定向】**（直连迅雷 CDN，速度最快）。

---

### 2. 网盘文件管理与下载

```bash
# 查询云盘容量
xunlei-agent space
xunlei-agent space --json

# 列出文件列表
xunlei-agent ls
xunlei-agent ls <folder_id> --limit 50 --json

# 下载云盘中已有文件（按文件 ID，支持多线程并发）
xunlei-agent download <file_id> --out "/data/downloads"

# 删除文件与清空回收站
xunlei-agent rm <file_id_1> <file_id_2>
xunlei-agent empty-trash
```

---

### 3. 一键转存分享链接并下载到本地

```bash
# 转存分享链接并高速下载（下载后自动清理网盘空间）
xunlei-agent fetch "https://pan.xunlei.com/s/xxxx" --pwd "myjp"

# 指定本地下载目录，且保留云盘文件（不自动清理）
xunlei-agent fetch "https://pan.xunlei.com/s/xxxx" --pwd "myjp" --out "/data/downloads" --no-clean
```

---

## 模型 Skill 与 Python 调用

### 1. 接入 AI 模型（Cursor / Claude Code / Antigravity 等）
仓库根目录下包含标准的 [`SKILL.md`](SKILL.md) 与 [`skills/xunlei-agent/`](skills/xunlei-agent/) 目录。
- **Claude Code / Cursor / Antigravity**：将 `skills/xunlei-agent` 放入您的技能目录中，AI 模型即可在对话中自主识别并调用 `xunlei-agent` 帮助您转存和拉取外部资源。

### 2. Python SDK 调用示例
```python
from xunlei_agent import XunleiAgentTool

tool = XunleiAgentTool()

# 1. 查询容量
space = tool.check_space()
print(f"剩余可用: {space.get('available_human')}")

# 2. 转存并高速下载
result = tool.fetch_and_download(
    share_url="https://pan.xunlei.com/s/xxxx",
    passcode="1234",
    download_to="./downloads",
    auto_clean_drive=True
)

# 3. 获取 OpenAI Function Calling Schema（供大模型工具注册）
schema = tool.get_tool_schema()
```

---

## 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。
