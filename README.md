# skyra-vision-service

> **"The Eye of J.A.R.V.I.S."** — Silent screen capture, multimodal AI analysis, and out-of-band Telegram delivery.

---

## Overview

`skyra-vision-service` is a stealth computer vision microservice in the Skyra Tech ecosystem. It captures the primary display in real-time using `mss`, submits the in-memory JPEG frame to **Google Gemini 2.5 Flash Vision** for analysis, and delivers markdown-formatted solutions directly to your configured **Telegram Chat** — with zero visual footprint on screen.

---

## Key Features

- 🔑 **Dual-Trigger**: Silent global hotkey (`Ctrl+Shift+F9`) **and** REST API endpoint (`POST /vision/analyze`)
- 📷 **Zero Disk Footprint**: All screen captures are in-memory `io.BytesIO` buffers — no `.png`/`.jpg` files ever written
- 👁️ **Gemini 2.5 Flash Vision**: Multimodal AI question parsing, option deduction, and concise markdown answers
- 📩 **Telegram Out-of-Band Delivery**: Results sent silently to your private Telegram chat — no screen overlays
- 🕵️ **Headless Operation**: Launches via `run_silent.vbs` with `pythonw.exe` — no terminal, no taskbar icon

---

## Port & Network

| Setting | Value |
| :--- | :--- |
| Bound Interface | `127.0.0.1` (loopback only) |
| Port | `8006` |
| CORS Allowed Origins | `http://127.0.0.1:8000`, `http://localhost:8000` |

---

## Setup

### 1. Create Virtual Environment
```bash
cd apps/skyra-vision-service
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
copy .env.example .env
# Edit .env with your Gemini API keys, Telegram Bot Token, and Chat ID
```

### 3. Run (Development)
```bash
uvicorn src.main:app --host 127.0.0.1 --port 8006 --reload
```

### 4. Run (Silent / Stealth Mode)
Double-click `run_silent.vbs` — runs as a hidden background process with no terminal window.

---

## API Reference

### `GET /health`
Returns service status and adapter configuration states.

### `POST /vision/analyze`
Captures screen, runs Gemini Vision analysis, and optionally delivers to Telegram.

**Request Body:**
```json
{
  "prompt": "Optional custom prompt override",
  "notify_telegram": true
}
```

**Response:**
```json
{
  "success": true,
  "analysis": "**Question detected:** ...\n**Answer:** ...",
  "telegram_delivered": true
}
```

---

## Architecture

See [`PROJECT_ARCHITECTURE.md`](./PROJECT_ARCHITECTURE.md) for the full PAD specification.
