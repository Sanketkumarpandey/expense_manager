class AIError(Exception):
    """Base exception for all AI-related errors."""


class SpeechTranscriptionError(AIError):
    """Raised when speech transcription fails."""


class ExpenseParsingError(AIError):
    """Raised when AI fails to parse an expense."""


class LowConfidencePredictionError(AIError):
    """Raised when AI confidence is below the acceptable threshold."""
