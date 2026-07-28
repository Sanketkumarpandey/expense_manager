"""Reply text for the Telegram /help command."""


def handle_help(update: dict[str, object]) -> str:
	"""Return the supported command list without accessing identity or application data."""
	return (
		"Available commands:\n"
		"\n"
		"Account:\n"
		"/start — welcome message\n"
		"/help — show this help\n"
		"/link <code> — link your account\n"
		"/unlink — unlink your account\n"
		"/profile — view your profile\n"
		"\n"
		"Expenses & Budgets:\n"
		"/expenses — view recent expenses\n"
		"/categories — view your categories\n"
		"/budgets — view your budgets\n"
		"/balance — check your balance\n"
		"/report — spending report chart\n"
		"\n"
		"Dependents:\n"
		"/dependents — manage dependents\n"
		"/pocketmoney — pocket money allocations\n"
		"/savings — view your savings\n"
		"/rollover — roll over pocket money"
	)
