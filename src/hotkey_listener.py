# ── skyra-vision-service: Silent Global Hotkey Listener ──────────────────────
# Runs a background pynput.keyboard.GlobalHotKeys listener in a daemon thread.
# On hotkey trigger (default: Ctrl+Shift+F9), the listener captures the screen,
# sends it to Gemini Vision, and delivers results to Telegram.
#
# IMPORTANT: Daemon thread is used so it terminates cleanly when the main
# FastAPI process exits. The async pipeline is bridged via asyncio.run_coroutine_threadsafe.

import asyncio
import threading
from typing import Optional

from loguru import logger

from .config import settings

try:
    from pynput import keyboard
    _PYNPUT_AVAILABLE = True
except ImportError:
    _PYNPUT_AVAILABLE = False
    logger.warning("⚠️  pynput not installed. Hotkey listener will be disabled.")


def _parse_hotkey_combination(combo: str) -> str:
    """
    Converts simple hotkey string like 'ctrl+shift+f9' into pynput GlobalHotKeys format.
    E.g.: 'ctrl+shift+f9' -> '<ctrl>+<shift>+<f9>'
    """
    parts = combo.lower().split("+")
    formatted = []
    for part in parts:
        part = part.strip()
        # Modifiers and special keys need angle-bracket wrapping in pynput
        if part in ("ctrl", "shift", "alt", "cmd", "super"):
            formatted.append(f"<{part}>")
        elif len(part) > 1:
            # F-keys (f1, f9, etc.) and named keys
            formatted.append(f"<{part}>")
        else:
            # Single character key
            formatted.append(part)
    return "+".join(formatted)


class HotkeyListener:
    """
    Manages a global hotkey listener running in an isolated daemon thread.
    Bridges synchronous pynput callbacks to the asyncio event loop of FastAPI.
    """

    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = event_loop
        self._thread: Optional[threading.Thread] = None
        self._hotkey_obj = None
        self._running = False

    def _on_hotkey_triggered(self) -> None:
        """
        Callback invoked by pynput in the listener daemon thread.
        Submits the async capture pipeline to the FastAPI event loop safely.
        """
        logger.info(f"🔑 Hotkey triggered: {settings.HOTKEY_COMBINATION}")
        # Submit the coroutine to the asyncio event loop (thread-safe bridge)
        future = asyncio.run_coroutine_threadsafe(
            self._capture_analyze_notify(),
            self._event_loop
        )
        try:
            # Wait up to 60 seconds for the pipeline to complete
            future.result(timeout=60)
        except Exception as e:
            logger.error(f"❌ Hotkey pipeline error: {e}")

    async def _capture_analyze_notify(self) -> None:
        """
        The full async vision pipeline:
        1. Capture screen to in-memory bytes.
        2. Send to Gemini Vision for analysis.
        3. Deliver result to Telegram.
        """
        from .screen_capture import capture_screen_to_bytes
        from .vision_analyzer import analyze_image_payload
        from .telegram_notifier import send_telegram_markdown, send_error_alert

        try:
            logger.info("📷 Capturing screen via hotkey trigger...")
            # Run blocking capture in executor to avoid blocking the event loop
            image_bytes = await asyncio.get_event_loop().run_in_executor(
                None, capture_screen_to_bytes
            )

            logger.info("🔍 Sending to Gemini Vision for analysis...")
            analysis = await analyze_image_payload(image_bytes)

            # Format the Telegram message
            message = f"👁️ *J.A.R.V.I.S. Vision Analysis*\n\n{analysis}"
            await send_telegram_markdown(message)

        except Exception as e:
            logger.error(f"❌ Vision pipeline failed: {e}")
            try:
                await send_error_alert(str(e))
            except Exception as notify_err:
                logger.error(f"❌ Failed to send error alert: {notify_err}")

    def start(self) -> None:
        """Starts the global hotkey listener in a background daemon thread."""
        if not _PYNPUT_AVAILABLE:
            logger.warning("⚠️  Hotkey listener skipped — pynput not installed.")
            return

        pynput_combo = _parse_hotkey_combination(settings.HOTKEY_COMBINATION)
        logger.info(f"⌨️  Registering global hotkey: {settings.HOTKEY_COMBINATION} → pynput: {pynput_combo}")

        try:
            self._hotkey_obj = keyboard.GlobalHotKeys({
                pynput_combo: self._on_hotkey_triggered
            })

            self._thread = threading.Thread(
                target=self._hotkey_obj.start,
                daemon=True,
                name="SkyraVisionHotkeyListener"
            )
            self._thread.start()
            self._running = True
            logger.success(f"✅ Hotkey listener active. Press {settings.HOTKEY_COMBINATION} to trigger analysis.")
        except Exception as e:
            logger.error(f"❌ Failed to start hotkey listener: {e}")

    def stop(self) -> None:
        """Stops the hotkey listener gracefully."""
        if self._hotkey_obj and self._running:
            try:
                self._hotkey_obj.stop()
                self._running = False
                logger.info("⌨️  Hotkey listener stopped.")
            except Exception as e:
                logger.error(f"❌ Error stopping hotkey listener: {e}")
