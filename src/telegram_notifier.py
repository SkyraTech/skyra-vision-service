# ── skyra-vision-service: Out-of-Band Telegram Alert Dispatcher ──────────────
# Async HTTP dispatcher delivering vision analysis results directly to the
# configured Telegram Chat ID via the Bot API.
# Results are delivered out-of-band (no screen overlays, no console popups).

import httpx
from loguru import logger

from .config import settings

_TELEGRAM_API_BASE = "https://api.telegram.org"


async def send_telegram_markdown(message: str) -> bool:
    """
    Sends a markdown-formatted message to the configured Telegram Chat ID.

    Args:
        message: The analysis text to deliver (Markdown V2 or plain markdown).

    Returns:
        bool: True if message was delivered successfully, False on failure.
    """
    if not settings.telegram_configured:
        logger.warning("⚠️  Telegram not configured. Skipping alert delivery.")
        return False

    url = f"{_TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        logger.success(f"📩 Telegram alert delivered to chat {settings.TELEGRAM_ADMIN_CHAT_ID}")
        return True

    except httpx.TimeoutException:
        logger.error("❌ Telegram API timed out after 10s")
        return False
    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ Telegram API HTTP error: {e.response.status_code} — {e.response.text[:150]}"
        )
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected Telegram dispatch error: {e}")
        return False


async def send_error_alert(error_message: str) -> bool:
    """
    Delivers a formatted error notification to Telegram.

    Args:
        error_message: The error details to include in the alert.

    Returns:
        bool: True if alert was delivered successfully.
    """
    formatted = (
        f"⚠️ *Skyra Vision Service Error*\n\n"
        f"```\n{error_message[:800]}\n```"
    )
    return await send_telegram_markdown(formatted)
