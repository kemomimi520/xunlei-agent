# Xunlei Pan - Transfer, Download & WebDAV Mount

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/WebDAV-302_Redirect-blue.svg" alt="WebDAV 302">
  <img src="https://img.shields.io/badge/Mount-OpenList%20%7C%20AList-orange.svg" alt="OpenList/AList">
  <img src="https://img.shields.io/badge/Model_Skill-Ready-purple.svg" alt="Model Skill Ready">
</p>

Designed for **AI Model Skills**, **resource transfers & high-speed downloads**, and **OpenList / AList storage mounting**.

Provides a **standard WebDAV mount server (seamlessly compatible with OpenList, AList, RaiDrive, Infuse, and Kodi)**, **zero-intervention share transfer & multi-thread downloader**, and out-of-the-box model skill integration.

---

## 🌟 Key Features

- 🌐 **OpenList / AList Native WebDAV Mounting (302 Redirect)**:
  - Built-in lightweight WebDAV server (`xunlei-agent webdav`).
  - **Zero Captcha Pain**: No need to manually extract short-lived `x-captcha-token` via browser DevTools; sessions are transparently maintained and refreshed.
  - **302 Direct CDN Streaming**: Media playback and downloads redirect directly to official high-speed CDN nodes with zero intermediate bandwidth or CPU overhead.
  - **In-Memory Metadata Cache**: Lightning-fast directory listing and browsing.
- ⚡ **Share Link Auto-Transfer & Download (`fetch`)**:
  - Automatically handles share links and passwords.
  - Cloud transfer -> Extract official CDN links -> 16-connection concurrent download.
  - **Differential Cleanup Guard**: Cleans up ONLY newly transferred files to reclaim cloud quota without touching pre-existing data.
- 🚀 **Dual-Engine Adaptive Downloader**:
  - Automatically prefers `aria2c` with 16 connections.
  - Seamlessly falls back to native Python multi-threaded HTTP Range downloading when `aria2c` is not installed.
- 🧠 **Model Skill Native Integration**:
  - Comes with standard `SKILL.md` ready to plug into Cursor, Claude Code, Antigravity, etc.
  - Every command supports structured `--json` output.
  - Standard OpenAI / Claude Function Calling schemas built-in.

---

## 🚀 Getting Started

```bash
git clone https://github.com/kemomimi520/xunlei-agent.git
cd xunlei-agent
pip install -e .
playwright install chromium
```

### Authentication

```bash
# Interactive QR Code Login
xunlei-agent login

# Direct Token Injection
xunlei-agent login --token "<your_access_token>" --refresh "<your_refresh_token>"
```

---

## 💻 WebDAV Server (Mount to OpenList / AList)

```bash
# Start WebDAV server on 0.0.0.0:8080/dav
xunlei-agent webdav

# Start with custom port, path prefix, and basic authentication
xunlei-agent webdav --port 8080 --user admin --password mypassword --path /dav
```

### OpenList / AList Configuration:
1. Go to OpenList/AList Admin -> **Storage** -> **Add**.
2. **Driver**: Choose `WebDAV`.
3. **Mount Path**: `/Xunlei`.
4. **Address**: `http://127.0.0.1:8080/dav`.
5. **Username / Password**: Enter configured credentials.
6. **WebDAV Policy**: Select **302 Redirect** for maximum CDN performance.

---

## 🤖 Model Skill & Python Usage

### Integrating with AI Coding Models (Cursor / Claude Code / Antigravity)
Copy or link `skills/xunlei-agent` to your assistant's skill directory. The model can automatically execute transfers, space checks, and downloads via natural language.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
