"""Reply text for unsupported Telegram commands and text input."""


def handle_unknown(update: dict[str, object]) -> str:
	"""Return a friendly fallback without interpreting input or invoking business logic."""
	return "I don't recognise that command. Try /help to see the available commands."
