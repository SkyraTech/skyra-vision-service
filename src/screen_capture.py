# ── skyra-vision-service: In-Memory Screen Capture Pipeline ──────────────────
# Captures the primary display screen using mss (zero-copy screenshot) and
# encodes it into an in-memory JPEG byte buffer using Pillow.
#
# CRITICAL: Zero disk writes - all operations are performed in-memory via
# io.BytesIO. No .png or .jpg files are ever written to the filesystem.

import io
from loguru import logger

try:
    import mss
    import mss.tools
    from PIL import Image
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False
    logger.warning("⚠️  mss or Pillow not installed. Screen capture will be unavailable.")


def capture_screen_to_bytes(quality: int = 75) -> bytes:
    """
    Captures the primary display monitor and returns JPEG-encoded bytes.

    All operations are in-memory (io.BytesIO). Nothing is written to disk.

    Args:
        quality: JPEG compression quality 1-95. Lower = smaller payload.
                 Default 75 balances LLM readability vs. network cost.

    Returns:
        bytes: Raw JPEG image bytes ready for base64 encoding and Gemini dispatch.

    Raises:
        RuntimeError: If mss or Pillow is not installed.
        Exception: If screen capture fails at the OS level.
    """
    if not _DEPS_AVAILABLE:
        raise RuntimeError("mss and Pillow are required for screen capture. Run: pip install mss pillow")

    try:
        with mss.mss() as sct:
            # Grab the primary monitor (index 1 = primary display, 0 = all monitors combined)
            monitor = sct.monitors[1]
            raw_screenshot = sct.grab(monitor)

            # Convert mss ScreenShot to Pillow Image (in-memory, no disk I/O)
            pil_image = Image.frombytes(
                mode="RGB",
                size=(raw_screenshot.width, raw_screenshot.height),
                data=raw_screenshot.rgb,
            )

            # Encode to JPEG bytes using an in-memory BytesIO buffer
            buffer = io.BytesIO()
            pil_image.save(buffer, format="JPEG", quality=quality, optimize=True)
            buffer.seek(0)
            image_bytes = buffer.read()

            logger.debug(
                f"📷 Screen captured: {raw_screenshot.width}x{raw_screenshot.height}px "
                f"→ {len(image_bytes) // 1024}KB JPEG (quality={quality})"
            )
            return image_bytes

    except Exception as e:
        logger.error(f"❌ Screen capture failed: {e}")
        raise
