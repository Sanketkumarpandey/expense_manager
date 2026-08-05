"""Reply text for the Telegram /help command."""


def handle_help(update: dict[str, object]) -> str:
	"""Return the supported command list without accessing identity or application data."""
	from expense_manager.telegram.router import COMMAND_DESCRIPTIONS

	lines = ["Available commands:"]
	for section, commands in COMMAND_DESCRIPTIONS.items():
		lines.append("")
		lines.append(f"{section}:")
		for cmd, desc in commands:
			prefix = f"/{cmd} " if desc.startswith("<") else f"/{cmd} — "
			lines.append(f"{prefix}{desc}")
	return "\n".join(lines)

