# skyra-vision-service — Project Architecture & Design Specification (PAD)

## 1. Executive Summary & Core Responsibilities
`skyra-vision-service` (codename: **"The Eye of J.A.R.V.I.S."**) is a specialized stealth computer vision microservice in the Skyra Tech ecosystem. It captures the primary display in real-time, submits the frame to Google Gemini 2.5 Flash Vision for multimodal AI analysis, and delivers concise markdown-formatted solutions **out-of-band via Telegram** — with zero visual presence on the active screen during operation.

### Design Philosophy
The service is built around three non-negotiable operating principles:
1. **Zero Disk Footprint**: All frame captures occur in-memory via `io.BytesIO` buffers. No `.png`, `.jpg`, or `.tmp` files are ever written to the filesystem.
2. **Zero Screen Presence**: The service runs headlessly via `pythonw.exe`, produces no overlays or toast notifications, and delivers results exclusively through the Telegram Bot API.
3. **Zero Event Loop Blocking**: All synchronous blocking operations (screenshot capture, pynput keyboard listener) run in isolated daemon threads or `asyncio.to_thread`, keeping FastAPI's async loop responsive.

### Service SLAs
* **Screen Capture → Analysis Dispatch**: End-to-end pipeline under 12.0 seconds (hotkey trigger → Telegram delivery).
* **REST API Response**: `/vision/analyze` JSON response returned within 15.0 seconds.
* **Health Check**: `/health` responds under 100ms.

---

## 2. High-Level Architecture & Lifecycle Diagrams

### Dual-Trigger Analysis Workflow
```text
 ┌──────────────────────────────────────────────────┐
 │              TRIGGER SOURCES                       │
 │                                                    │
 │  [Ctrl+Shift+F9] ──────────► HotkeyListener       │
 │  (Global pynput hook)         (Daemon Thread)      │
 │                                    │               │
 │  skyra-jarvis ────────────► POST /vision/analyze   │
 │  (httpx.AsyncClient)          (FastAPI Route)      │
 └────────────────────────┬───────────────────────────┘
                          │
                          ▼ asyncio.to_thread()
                  ┌───────────────────┐
                  │  screen_capture   │
                  │  mss + Pillow     │
                  │  (in-memory JPEG) │
                  └────────┬──────────┘
                           │
                           ▼ async HTTP POST
                  ┌───────────────────┐
                  │  vision_analyzer  │
                  │  Gemini 2.5 Flash │
                  │  (base64 inline)  │
                  └────────┬──────────┘
                           │
                           ▼ async HTTP POST
                  ┌───────────────────┐
                  │ telegram_notifier │
                  │ Bot API sendMsg   │
                  └───────────────────┘
```

### Component Interaction Matrix

| Source | Target | Protocol | Description |
| :--- | :--- | :--- | :--- |
| `skyra-jarvis` | `POST /vision/analyze` | HTTP REST | Remote trigger to capture and analyze current screen |
| `Global Hotkey` | `HotkeyListener` | pynput daemon thread | Silent keyboard trigger for immediate capture |
| `screen_capture` | Pillow BytesIO | In-memory | JPEG-encode screenshot pixels without disk writes |
| `vision_analyzer` | Gemini 2.5 Flash API | HTTPS | Multimodal AI analysis with base64 inline image data |
| `telegram_notifier` | Telegram Bot API | HTTPS | Out-of-band markdown solution delivery |

---

## 3. Directory Structure & Code Taxonomy
```text
apps/skyra-vision-service/
├── PROJECT_ARCHITECTURE.md   ← This document
├── requirements.txt          ← Python package specifications
├── .env.example              ← Sample configuration file
├── run_silent.vbs            ← Stealth pythonw.exe launcher (no terminal)
└── src/
    ├── __init__.py
    ├── config.py             ← Pydantic-Settings environment loader
    ├── screen_capture.py     ← In-memory capture pipeline (mss + Pillow)
    ├── vision_analyzer.py    ← Async Gemini 2.5 Flash Vision REST client
    ├── telegram_notifier.py  ← Async Telegram Bot API dispatcher
    ├── hotkey_listener.py    ← pynput daemon thread with asyncio bridge
    └── main.py               ← FastAPI app, CORS, lifespan manager
```

### Component Lifecycle Scopes
| Component | Lifecycle | Notes |
| :--- | :--- | :--- |
| `FastAPI App` | Process lifetime | Uvicorn event loop on `127.0.0.1:8006` |
| `HotkeyListener` | Process lifetime (daemon thread) | Stops on app shutdown via lifespan hook |
| `screen_capture` | Per-request | Captures and returns in-memory bytes, then terminates |
| `vision_analyzer` | Per-request | Async httpx client session per call |
| `telegram_notifier` | Per-request | Async httpx client session per call |

---

## 4. Technical Specs & Feature Deep-Dive

### 4A. In-Memory Screen Capture Pipeline (`screen_capture.py`)
1. **`mss.mss().grab(monitor[1])`**: Captures the primary monitor as raw pixel data.
2. **`PIL.Image.frombytes()`**: Converts raw pixel memory to a Pillow Image object.
3. **`image.save(buffer, format='JPEG', quality=75)`**: Encodes to JPEG in an `io.BytesIO` buffer.
4. **Result**: Returns raw `bytes` — zero disk writes at any stage.

### 4B. Gemini 2.5 Flash Multimodal Vision (`vision_analyzer.py`)
* **Endpoint**: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
* **Image Encoding**: Inline base64 `inlineData.data` with `mimeType: image/jpeg`.
* **System Prompt Strategy**: Tailored instruction set for question detection, option deduction, and concise Markdown output ≤300 words.
* **Response Parsing**: Extracts `candidates[0].content.parts[].text` from the Gemini API JSON response.

### 4C. Telegram Out-of-Band Delivery (`telegram_notifier.py`)
* **Endpoint**: `POST https://api.telegram.org/bot<token>/sendMessage`
* **Parse Mode**: `Markdown` for formatted output.
* **Error Alerts**: Separate `send_error_alert()` function for runtime failure notifications.

### 4D. Silent Hotkey Hook (`hotkey_listener.py`)
* **Library**: `pynput.keyboard.GlobalHotKeys`
* **Thread Model**: Runs in a dedicated Python daemon thread (auto-terminates with main process).
* **Asyncio Bridge**: Uses `asyncio.run_coroutine_threadsafe()` to submit async coroutines to the FastAPI event loop from the synchronous thread context.

### 4E. Stealth Launcher (`run_silent.vbs`)
* **Mechanism**: Windows VBScript calling `WshShell.Run` with window style `0` (hidden).
* **Process**: Spawns `pythonw.exe src/main.py` — no console window, no taskbar entry.

### 4F. API Endpoint Schemas

#### `GET /health`
Returns service adapter status.
```json
{
  "status": "OK",
  "service": "skyra-vision-service",
  "version": "1.0.0",
  "gemini_configured": true,
  "telegram_configured": true,
  "hotkey": "ctrl+shift+f9",
  "port": 8006
}
```

#### `POST /vision/analyze`
Triggers a screen capture and Gemini analysis.
* **Request Schema**:
```json
{
  "prompt": "Optional custom analysis prompt override",
  "notify_telegram": true
}
```
* **Response Schema (success)**:
```json
{
  "success": true,
  "analysis": "**Question detected:** ...\n**Answer:** ...\n**Reasoning:** ...",
  "telegram_delivered": true,
  "error": null
}
```
* **Response Schema (error)**:
```json
{
  "success": false,
  "analysis": null,
  "telegram_delivered": false,
  "error": "Gemini API timed out after 30s"
}
```

---

## 5. Security, Environment & Configuration

### Port & Binding
* **Port**: `8006`. Binds **strictly** to `127.0.0.1` (localhost loopback only).
* **Public interfaces** (`0.0.0.0`) are **FORBIDDEN**.

### CORS Configuration
* **Allowed Origins**: `http://127.0.0.1:8000` and `http://localhost:8000` only (Jarvis Dashboard).
* **Wildcard CORS `*`** is **FORBIDDEN**.

### Environment Variables
| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | No | `8006` | FastAPI server port |
| `GEMINI_API_KEY_1` | Yes | — | Primary Gemini Vision API key |
| `GEMINI_API_KEY_2` | No | — | Fallback Gemini Vision API key |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot API token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Yes | — | Target Telegram Chat ID for results |
| `HOTKEY_COMBINATION` | No | `ctrl+shift+f9` | Global hotkey trigger combination |

### Secrets Management
* `.env` and all API keys must be listed in `.gitignore` — **NEVER committed to version control**.

---

## 6. Resilience, Error Handling & Recovery Strategies

* **Gemini Timeout Guard**: `httpx.AsyncClient` enforces a 30-second timeout on all Gemini API calls.
* **Telegram Timeout Guard**: `httpx.AsyncClient` enforces a 10-second timeout on Telegram dispatches.
* **Hotkey Pipeline Isolation**: Exceptions inside the hotkey pipeline are caught locally; failures are forwarded to `send_error_alert()` via Telegram.
* **REST API Error Boundaries**: All `/vision/analyze` errors are caught in a top-level try/except and returned as structured JSON payloads.
* **Standardized Error Payloads**:
```json
{
  "success": false,
  "error": "Descriptive error message here"
}
```
* **Dependency Graceful Degradation**: If `mss`, `pynput`, or `Pillow` is not installed, the service initializes in a degraded state with informative warnings rather than crashing.

---

## 7. Ecosystem Integration & Dependencies

### Upstream Callers
* `skyra-jarvis` dispatches `POST /vision/analyze` via `apps/skyra-jarvis/tools/vision_tools.py` using `httpx.AsyncClient` with a 15-second timeout on port `8000`.

### Outbound Destinations
* **Gemini AI API**: `https://generativelanguage.googleapis.com` — multimodal vision analysis.
* **Telegram Bot API**: `https://api.telegram.org` — out-of-band result delivery.

### Dependencies
| Package | Purpose |
| :--- | :--- |
| `fastapi` | HTTP REST API framework |
| `uvicorn` | ASGI server |
| `mss` | Cross-platform screen capture |
| `Pillow` | In-memory JPEG encoding |
| `pynput` | Global keyboard hotkey hook |
| `httpx` | Async HTTP client for Gemini & Telegram |
| `pydantic-settings` | Environment configuration loader |
| `loguru` | Structured logging |
| `python-dotenv` | `.env` file loader |
