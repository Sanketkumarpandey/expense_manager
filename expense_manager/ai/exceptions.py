class AIError(Exception):
    """Base exception for all AI-related errors."""


class SpeechTranscriptionError(AIError):
    """Raised when speech transcription fails."""


class ExpenseParsingError(AIError):
    """Raised when AI fails to parse an expense."""


class LowConfidencePredictionError(AIError):
    """Raised when AI confidence is below the acceptable threshold.""""""Placeholder for the Sarvam AI speech-to-text adapter."""


def transcribe(file_path: str, language_hint: str | None = None) -> None:
	"""Reserve audio transcription without calling any external provider."""
	# TODO: Implement Sarvam transcription, validation, and retries in Phase 9.
	pass
