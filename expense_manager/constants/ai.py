class SpeechToTextConfig:
    ENDPOINT = "https://api.sarvam.ai/speech-to-text"
    MODEL = "saaras:v3"
    MODE = "transcribe"
    DEFAULT_LANGUAGE_CODE = "unknown"
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 2


class ExpenseParsingConfig:
    TIMEOUT_SECONDS = 20
    MAX_RETRIES = 1
    FALLBACK_CATEGORY = "Uncategorized"
    REQUIRED_KEYS = ("amount", "category", "description", "date", "transaction_type")
    CLOSEST_CATEGORY_THRESHOLD = 0.45