"""Placeholder module for future Telegram utility helpers."""


def normalize_update_payload(update: dict[str, object]) -> None:
	"""Reserve safe update normalization for a future implementation."""
	# TODO: Add pure helper behavior only when required by a later phase.
	pass


def get_telegram_user_id(update: dict[str, object]) -> str | None:
	"""Extract a stable Telegram user ID from an update payload.

	Returns the ID as a string when found, otherwise None.
	This helper tolerates unexpected payload shapes and avoids raising.
	"""
	message = update.get("message") if isinstance(update, dict) else None
	from_user = message.get("from") if isinstance(message, dict) else None
	user_id = from_user.get("id") if isinstance(from_user, dict) else None
	if isinstance(user_id, (str, int)) and not isinstance(user_id, bool):
		return str(user_id)
	return None
