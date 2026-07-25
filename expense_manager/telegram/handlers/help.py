"""Reply text for the Telegram /help command."""


def handle_help(update: dict[str, object]) -> str:
	"""Return the supported command list without accessing identity or application data."""
	return (
		"Available commands:\n"
		"/start — welcome message\n"
		"/help — show this help\n"
		"/link — link your account (coming soon)\n"
		"/unlink — unlink your account (coming soon)"
	)
