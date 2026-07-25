"""Reply text for the Telegram /link command."""


def handle_link(update: dict[str, object]) -> str:
	"""Return an account-linking placeholder without generating an OTP or touching the database."""
	return "Account linking is not available yet. Please try again in a later phase."
