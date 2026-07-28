from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, add_to_date, get_datetime

from expense_manager.services.exceptions import (
    TelegramAlreadyLinkedError,
    TelegramNotLinkedError,
    InvalidTelegramLinkCodeError,
    ExpiredTelegramLinkCodeError,
    TelegramUserNotFoundError,
)
from expense_manager.utils.logger import logger
from expense_manager.utils.helpers import escape_like


# TODO: move to expense_manager.constants.telegram once that module's
# contents are confirmed — kept local here to avoid guessing at names
# that may already exist there.
LINK_TOKEN_EXPIRY_MINUTES = 10

# The Telegram Link DocType has no field to hold a pending token —
# telegram_user_id is required, so a row can't exist until the
# Telegram side is already known. Pending tokens therefore live in
# Frappe's cache, not the database, keyed by the token's hash. The
# cache TTL is padded past the real expiry so our own expiry check
# (below) always fires before Redis silently evicts the key — that
# lets us tell "expired" apart from "never existed" for the user.
_CACHE_PREFIX = "expense_manager:telegram_link_token:"
_CACHE_TTL_BUFFER_MINUTES = 5


class TelegramLinkService:
    """
    Owns Telegram <-> Frappe User account linking, and nothing else.

    Does not create expenses, generate reports, parse AI input, or
    send Telegram messages. Every Telegram handler's first move is
    get_user_by_telegram() — the DocType itself is never touched
    outside this service.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def link_account(user: str) -> dict:
        """
        Desk-initiated step. Generates a short-lived link token for
        `user` and stashes only its hash in cache, mapped to the user
        — nothing is written to the Telegram Link table yet, since
        telegram_user_id is required and isn't known at this point.

        The raw token is returned exactly once here and cannot be
        recovered later, so the caller (Desk UI / REST layer) must
        surface it to the user immediately, e.g. "Send /link <token>
        to the bot".
        """
        TelegramLinkService._validate_user(user)

        if TelegramLinkService.is_linked(user):
            raise TelegramAlreadyLinkedError(
                _("This user already has a linked Telegram account.")
            )

        raw_token, token_hash, expires_at = TelegramLinkService._generate_link_token()

        frappe.cache().set_value(
            TelegramLinkService._cache_key(token_hash),
            {"user": user, "expires_at": expires_at.isoformat()},
            expires_in_sec=(LINK_TOKEN_EXPIRY_MINUTES + _CACHE_TTL_BUFFER_MINUTES) * 60,
        )

        logger.info(
            "Link token generated | user=%s | expires_at=%s",
            user,
            expires_at,
        )

        return {
            "token": raw_token,
            "expires_at": expires_at,
        }

    @staticmethod
    def verify_and_link(
        token: str,
        telegram_user_id: str,
        telegram_username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Document:
        """
        Telegram-side completion step, triggered by `/link <token>`.

        Not in the originally sketched public API — added because the
        two-actor flow (Desk generates, Telegram redeems) needs a
        distinct entry point from link_account(); one signature can't
        do both without overloading it into something confusing.

        This is also the only place a Telegram Link row is ever
        created, since it's the first point both `user` and
        `telegram_user_id` are known together.
        """
        TelegramLinkService._validate_telegram_id(telegram_user_id)

        cache_key = TelegramLinkService._cache_key(
            TelegramLinkService._hash_token(token)
        )
        payload = frappe.cache().get_value(cache_key)

        if not payload:
            logger.info(
                "Invalid link attempt | telegram_id=%s",
                telegram_user_id,
            )
            raise InvalidTelegramLinkCodeError(
                _("This link code is invalid or has already been used.")
            )

        TelegramLinkService._verify_link_token(payload)

        user = payload["user"]

        if TelegramLinkService.is_linked(user):
            frappe.cache().delete_value(cache_key)
            raise TelegramAlreadyLinkedError(
                _("This user already has a linked Telegram account.")
            )

        TelegramLinkService._validate_unique_link(user, telegram_user_id)

        doc = frappe.get_doc(
            {
                "doctype": "Telegram Link",
                "user": user,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
                "is_active": 1,
                "linked_on": now_datetime(),
            },
            ignore_permissions=True,
        )
        doc.insert(ignore_permissions=True)

        frappe.cache().delete_value(cache_key)

        logger.info(
            "Telegram account linked | user=%s | telegram_id=%s | id=%s",
            user,
            telegram_user_id,
            doc.name,
        )

        return doc

    @staticmethod
    def unlink_account(user: str) -> None:
        """
        Idempotent: unlinking a user with no active link is a no-op,
        not an error. Deactivates rather than deletes — telegram_user_id
        is a required field, so it can't be cleared in place, and
        keeping the row (is_active=0) preserves a link history rather
        than losing it.
        """
        name = frappe.db.get_value(
            "Telegram Link",
            {"user": user, "is_active": 1},
            "name",
        )

        if not name:
            return

        doc = frappe.get_doc("Telegram Link", name, ignore_permissions=True)
        doc.is_active = 0
        doc.save(ignore_permissions=True)

        logger.info(
            "Telegram account unlinked | user=%s | id=%s",
            user,
            doc.name,
        )

    @staticmethod
    def get_link(user: str) -> Document:
        return TelegramLinkService._get_link(user)

    @staticmethod
    def get_user_by_telegram(telegram_user_id: str) -> str:
        """
        The single call every Telegram handler makes first. Returns
        the linked Frappe user (owner_user) — never the Telegram Link
        doc — so handlers never touch the DocType directly.
        """
        TelegramLinkService._validate_telegram_id(telegram_user_id)

        user = frappe.db.get_value(
            "Telegram Link",
            {"telegram_user_id": telegram_user_id, "is_active": 1},
            "user",
        )

        if not user:
            raise TelegramNotLinkedError(
                _("This Telegram account is not linked to any user yet.")
            )

        return user

    @staticmethod
    def is_linked(user: str) -> bool:
        return bool(
            frappe.db.exists(
                "Telegram Link",
                {"user": user, "is_active": 1},
            )
        )

    @staticmethod
    def list_links(active_only: bool = False) -> list[dict]:
        filters = {}

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Telegram Link",
            filters=filters,
            fields=[
                "name",
                "user",
                "telegram_user_id",
                "telegram_username",
                "first_name",
                "last_name",
                "language_code",
                "is_active",
                "linked_on",
            ],
            order_by="linked_on desc",
        )

    @staticmethod
    def search_links(
        search_text: Optional[str],
        active_only: bool = True,
    ) -> list[dict]:
        if not search_text:
            return []

        search_text = search_text.strip()
        active_filter = {"is_active": 1} if active_only else {}

        by_user = frappe.get_all(
            "Telegram Link",
            filters={
                "user": ["like", f"%{escape_like(search_text)}%"],
                **active_filter,
            },
            fields=["name", "user", "telegram_user_id", "telegram_username"],
        )

        by_username = frappe.get_all(
            "Telegram Link",
            filters={
                "telegram_username": ["like", f"%{escape_like(search_text)}%"],
                **active_filter,
            },
            fields=["name", "user", "telegram_user_id", "telegram_username"],
        )

        seen = set()
        results = []

        for row in by_user + by_username:
            if row["name"] in seen:
                continue
            seen.add(row["name"])
            results.append(row)

        return results

    @staticmethod
    def refresh_link(
        user: str,
        telegram_username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> None:
        """
        Opportunistic sync, meant to be called from Telegram
        middleware on incoming updates: picks up Telegram profile
        changes (username, name, language) since there's no separate
        "last seen" field on this DocType to maintain. Safe no-op if
        the user isn't linked — get_user_by_telegram() would already
        have raised earlier in the handler chain in that case.
        """
        name = frappe.db.get_value(
            "Telegram Link",
            {"user": user, "is_active": 1},
            "name",
        )

        if not name:
            return

        doc = frappe.get_doc("Telegram Link", name, ignore_permissions=True)
        changed = False

        for field, value in (
            ("telegram_username", telegram_username),
            ("first_name", first_name),
            ("last_name", last_name),
            ("language_code", language_code),
        ):
            if value is not None and getattr(doc, field) != value:
                setattr(doc, field, value)
                changed = True

        if changed:
            doc.save(ignore_permissions=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_link(user: str) -> Document:
        name = frappe.db.get_value(
            "Telegram Link",
            {"user": user, "is_active": 1},
            "name",
        )

        if not name:
            raise TelegramNotLinkedError(
                _("This user does not have a linked Telegram account.")
            )

        return frappe.get_doc("Telegram Link", name, ignore_permissions=True)

    @staticmethod
    def _validate_user(user: str) -> None:
        if not frappe.db.exists("User", user):
            raise TelegramUserNotFoundError(
                _("User '{0}' does not exist.").format(user)
            )

    @staticmethod
    def _validate_telegram_id(telegram_user_id: str) -> None:
        if not telegram_user_id or not str(telegram_user_id).strip():
            raise InvalidTelegramLinkCodeError(
                _("A Telegram account id is required.")
            )

    @staticmethod
    def _validate_unique_link(
        user: str,
        telegram_user_id: str,
    ) -> None:
        """
        Enforces both directions of the 1:1 constraint at the service
        layer, since the DocType itself has no unique constraints on
        `user` or `telegram_user_id`: one Telegram account can't be
        linked to two Frappe users (checked here), and one Frappe user
        can't hold two active links (checked earlier, in
        verify_and_link, via is_linked()).
        """
        conflicting_user = frappe.db.get_value(
            "Telegram Link",
            {"telegram_user_id": telegram_user_id, "is_active": 1},
            "user",
        )

        if conflicting_user and conflicting_user != user:
            logger.info(
                "Duplicate Telegram ID | telegram_id=%s | existing_user=%s | attempted_user=%s",
                telegram_user_id,
                conflicting_user,
                user,
            )
            raise TelegramAlreadyLinkedError(
                _("This Telegram account is already linked to a different user.")
            )

    @staticmethod
    def _generate_link_token() -> tuple[str, str, datetime]:
        raw_token = secrets.token_hex(4).upper()
        token_hash = TelegramLinkService._hash_token(raw_token)
        expires_at = add_to_date(now_datetime(), minutes=LINK_TOKEN_EXPIRY_MINUTES)

        return raw_token, token_hash, expires_at

    @staticmethod
    def _verify_link_token(payload: dict) -> None:
        expires_at = get_datetime(payload["expires_at"])

        if now_datetime() > expires_at:
            logger.info("Expired token | user=%s", payload.get("user"))
            raise ExpiredTelegramLinkCodeError(
                _("This link code has expired. Please generate a new one.")
            )

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_key(token_hash: str) -> str:
        return f"{_CACHE_PREFIX}{token_hash}"