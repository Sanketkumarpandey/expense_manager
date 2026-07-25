"""Reply text for the Telegram /unlink command."""


def handle_unlink(update: dict[str, object]) -> str:
	"""Return an unlink placeholder without modifying records or checking account state."""
	return "Unlinking is not available yet. Please try again in a later phase."
