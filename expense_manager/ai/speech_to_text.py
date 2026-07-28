"""Sarvam AI speech-to-text adapter: audio file path -> plain transcribed text.
Does NOT do any expense parsing."""

from __future__ import annotations

import mimetypes
import os
import time

import requests

from expense_manager.telegram.config import get_sarvam_api_key, get_use_mock_ai_apis
from expense_manager.ai.exceptions import SpeechTranscriptionError
from expense_manager.constants.ai import SpeechToTextConfig
from expense_manager.utils.logger import logger


def transcribe(file_path: str, language_hint: str | None = None) -> str:
    if get_use_mock_ai_apis():
        logger.info("sarvam_transcribe status=mocked")
        return "I spent 200 on Zomato"

    last_exc: Exception | None = None

    for attempt in range(SpeechToTextConfig.MAX_RETRIES + 1):
        started_at = time.monotonic()
        try:
            filename = os.path.basename(file_path)
            content_type = mimetypes.guess_type(filename)[0] or "audio/ogg"
            with open(file_path, "rb") as audio_file:
                response = requests.post(
                    SpeechToTextConfig.ENDPOINT,
                    headers={"api-subscription-key": get_sarvam_api_key()},
                    files={"file": (filename, audio_file, content_type)},
                    data={
                        "model": SpeechToTextConfig.MODEL,
                        "mode": SpeechToTextConfig.MODE,
                        "language_code": language_hint or SpeechToTextConfig.DEFAULT_LANGUAGE_CODE,
                    },
                    timeout=SpeechToTextConfig.TIMEOUT_SECONDS,
                )

            if 400 <= response.status_code < 500:
                error_body = response.text[:500]
                logger.info(
                    "sarvam_transcribe status=client_error code=%s body=%s latency_ms=%d",
                    response.status_code,
                    error_body,
                    int((time.monotonic() - started_at) * 1000),
                )
                raise SpeechTranscriptionError(
                    f"Sarvam AI rejected the audio (status {response.status_code}): {error_body}"
                )

            response.raise_for_status()
            data = response.json()
            transcript = data.get("transcript")

            if not transcript or not transcript.strip():
                raise SpeechTranscriptionError("Sarvam AI returned an empty transcript.")

            logger.info(
                "sarvam_transcribe status=success latency_ms=%d",
                int((time.monotonic() - started_at) * 1000),
            )
            return transcript.strip()

        except SpeechTranscriptionError:
            raise

        except requests.exceptions.RequestException as exc:
            last_exc = exc
            logger.info(
                "sarvam_transcribe status=network_error attempt=%d latency_ms=%d",
                attempt + 1,
                int((time.monotonic() - started_at) * 1000),
            )
            if attempt < SpeechToTextConfig.MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue

    raise SpeechTranscriptionError("Sarvam AI transcription failed after retries.") from last_exc