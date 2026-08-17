# ── skyra-vision-service: Gemini 2.5 Flash Vision Analyzer ───────────────────
# Async client querying the Gemini multimodal REST API.
# Encodes captured JPEG bytes as base64 inline image data and returns
# a concise, markdown-formatted analysis string.

import base64
import asyncio
from typing import Optional

import httpx
from loguru import logger

from .config import settings

# Gemini 2.5 Flash Vision model endpoint
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# System prompt optimized for question detection, option deduction, and concise solutions
_SYSTEM_PROMPT = """You are J.A.R.V.I.S. Vision — an expert AI analyst.

Your task is to analyze the provided screenshot image and:
1. Identify any visible QUESTION, MCQ, problem statement, or task on screen.
2. Determine the CORRECT ANSWER or best response using logical deduction.
3. Format your response in **clear, concise Markdown**.

Response format:
**Question detected:** [Restate the question briefly]
**Answer:** [Direct, correct answer]
**Reasoning:** [1–2 sentence justification]

If no question is visible, describe what is on screen in 2 sentences.
Keep total response under 300 words."""


async def analyze_image_payload(
    image_bytes: bytes,
    user_prompt: Optional[str] = None,
) -> str:
    """
    Sends a JPEG image byte payload to Gemini 2.5 Flash Vision and returns
    the text analysis response.

    Args:
        image_bytes: Raw JPEG bytes from screen_capture.
        user_prompt: Optional custom prompt override. Falls back to system prompt.

    Returns:
        str: Markdown-formatted analysis from Gemini Vision.

    Raises:
        RuntimeError: If Gemini API key is not configured.
        httpx.HTTPStatusError: On non-2xx Gemini API responses.
    """
    if not settings.gemini_configured:
        raise RuntimeError("❌ Gemini API key not configured. Set GEMINI_API_KEY_1 in .env")

    api_key = settings.active_gemini_key
    url = f"{_GEMINI_BASE_URL}?key={api_key}"

    # Encode raw bytes as base64 inline image data for Gemini multimodal schema
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt_text = user_prompt or _SYSTEM_PROMPT

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt_text
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "maxOutputTokens": 512,
        }
    }

    logger.info(f"🔍 Sending {len(image_bytes) // 1024}KB screenshot to Gemini Vision...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            candidates = data.get("candidates", [])

            if not candidates:
                return "⚠️ Gemini returned no candidates. The image may be unclear or empty."

            # Extract text content from first candidate
            parts = candidates[0].get("content", {}).get("parts", [])
            analysis_text = " ".join(p.get("text", "") for p in parts if "text" in p).strip()

            if not analysis_text:
                return "⚠️ Gemini Vision returned an empty analysis."

            logger.success(f"✅ Gemini Vision analysis complete ({len(analysis_text)} chars)")
            return analysis_text

    except httpx.TimeoutException:
        logger.error("❌ Gemini Vision request timed out after 30s")
        raise RuntimeError("Gemini Vision API timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Gemini API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
        raise RuntimeError(f"Gemini API error {e.response.status_code}: {e.response.text[:150]}")
    except Exception as e:
        logger.error(f"❌ Unexpected error in vision analyzer: {e}")
        raise
