"""Reply text for the Telegram /start command."""


def handle_start(update: dict[str, object]) -> str:
	"""Return a welcome message without creating records or checking account state."""
	return "Hi! I'm your Expense Manager bot. Send /help to see the available commands."
