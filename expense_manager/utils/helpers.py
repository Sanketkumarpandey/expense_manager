"""Shared utility helpers for the expense_manager app."""


def escape_like(text: str) -> str:
    """Escape special LIKE characters so user input is matched literally.

    MariaDB/MySQL LIKE syntax treats ``%``, ``_``, and ``\\`` as
    wildcards/escape characters.  This function escapes them so a
    user-supplied search string is matched literally, not as a pattern.
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
