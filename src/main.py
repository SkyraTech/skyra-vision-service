# ── skyra-vision-service: FastAPI Application Entry Point ────────────────────
# Exposes GET /health and POST /vision/analyze.
# Manages the background hotkey listener via FastAPI lifespan context.
# Binds strictly to 127.0.0.1:8006 with CORS locked to Jarvis dashboard.

import asyncio
import sys
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# ── Internal Imports ──────────────────────────────────────────────────────────
from .config import settings
from .screen_capture import capture_screen_to_bytes
from .vision_analyzer import analyze_image_payload
from .telegram_notifier import send_telegram_markdown, send_error_alert
from .hotkey_listener import HotkeyListener


# ── Loguru Configuration ──────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


# ── Pydantic Request / Response Schemas ──────────────────────────────────────
class AnalyzeRequest(BaseModel):
    prompt: Optional[str] = None
    notify_telegram: bool = True


class AnalyzeResponse(BaseModel):
    success: bool
    analysis: Optional[str] = None
    telegram_delivered: bool = False
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    gemini_configured: bool
    telegram_configured: bool
    hotkey: str
    port: int


# ── FastAPI Lifespan (Start / Stop Hooks) ────────────────────────────────────
_hotkey_listener: Optional[HotkeyListener] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan manager:
    - On startup: Register and start the global hotkey listener daemon thread.
    - On shutdown: Gracefully stop the hotkey listener.
    """
    global _hotkey_listener
    event_loop = asyncio.get_event_loop()

    logger.info("🚀 Skyra Vision Service starting up...")
    logger.info(f"   Port      : {settings.PORT}")
    logger.info(f"   Gemini    : {'✅ Configured' if settings.gemini_configured else '⚠️  Not configured'}")
    logger.info(f"   Telegram  : {'✅ Configured' if settings.telegram_configured else '⚠️  Not configured'}")
    logger.info(f"   Hotkey    : {settings.HOTKEY_COMBINATION}")

    # Initialize and start the hotkey listener daemon
    _hotkey_listener = HotkeyListener(event_loop)
    _hotkey_listener.start()

    yield  # Application is running here

    # Shutdown cleanup
    logger.info("🛑 Skyra Vision Service shutting down...")
    if _hotkey_listener:
        _hotkey_listener.stop()


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Skyra Vision Service",
    description="The Eye of J.A.R.V.I.S. — Silent screen capture and multimodal AI analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
# Locked strictly to the Jarvis dashboard port. Wildcard (*) is FORBIDDEN.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Status"])
async def health_check() -> HealthResponse:
    """Returns service health and adapter configuration statuses."""
    return HealthResponse(
        status="OK",
        service="skyra-vision-service",
        version="1.0.0",
        gemini_configured=settings.gemini_configured,
        telegram_configured=settings.telegram_configured,
        hotkey=settings.HOTKEY_COMBINATION,
        port=settings.PORT,
    )


@app.post("/vision/analyze", response_model=AnalyzeResponse, tags=["Vision"])
async def vision_analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Captures the current screen and runs Gemini Vision analysis.

    - Captures primary display in-memory (no file writes).
    - Sends to Gemini 2.5 Flash Vision for analysis.
    - Optionally delivers the result to Telegram.

    Returns markdown-formatted analysis in the JSON response.
    """
    try:
        logger.info("📥 Received /vision/analyze request via REST API")

        # Run blocking screen capture in a thread pool to avoid blocking the event loop
        image_bytes = await asyncio.to_thread(capture_screen_to_bytes)

        # Run the Gemini Vision analysis
        analysis = await analyze_image_payload(image_bytes, user_prompt=body.prompt)

        # Optionally deliver to Telegram out-of-band
        telegram_delivered = False
        if body.notify_telegram and settings.telegram_configured:
            message = f"👁️ *J.A.R.V.I.S. Vision Analysis*\n\n{analysis}"
            telegram_delivered = await send_telegram_markdown(message)

        return AnalyzeResponse(
            success=True,
            analysis=analysis,
            telegram_delivered=telegram_delivered,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ /vision/analyze error: {error_msg}")

        # Attempt to notify Telegram of the failure
        try:
            await send_error_alert(error_msg)
        except Exception:
            pass

        return AnalyzeResponse(
            success=False,
            error=error_msg,
        )


# ── Entry Point (for pythonw.exe / run_silent.vbs) ────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=settings.PORT,
        log_level="info",
        access_log=False,  # Suppress access logs when running headlessly
    )
