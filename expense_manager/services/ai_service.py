from __future__ import annotations

from typing import Optional

from frappe.model.document import Document

import re

from expense_manager.services.expense_service import ExpenseService
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.ai import speech_to_text, ai_parser
from expense_manager.ai.exceptions import IncomeDetectedError
from expense_manager.constants.ai import ExpenseParsingConfig
from expense_manager.constants.expense import ExpenseSource
from expense_manager.utils.logger import logger


class AIService:

    INCOME_KEYWORDS: list[str] = [
        "refund", "credit", "received", "cashback", "got money",
        "got back", "came back", "money back", "reversal",
    ]

    INCOME_RE: re.Pattern = re.compile(
        "|".join(re.escape(kw) for kw in INCOME_KEYWORDS),
        re.IGNORECASE,
    )

    INCOME_MSG: str = (
        "This looks like money coming in, not an expense \u2014 "
        "this app only tracks spending. If this was actually a "
        "purchase, try rephrasing."
    )

    @staticmethod
    def _raise_if_income(text: str) -> None:
        if AIService.INCOME_RE.search(text):
            raise IncomeDetectedError(AIService.INCOME_MSG)

    @staticmethod
    def _load_known_categories(
        owner_user: str,
        dependent: Optional[str] = None,
        seed_defaults: bool = True,
    ) -> list[dict]:
        """Load the active categories usable by the acting identity.

        Categories are a shared, guardian-owned pool. Guardian identities use
        all guardian-owned active categories. Dependent identities use the
        categories granted by their ``allowed_categories`` child table,
        resolved through ``DependentService.list_allowed_categories`` (the
        single source of truth for the "empty table = all allowed" fallback).
        Defaults are seeded guardian-wide on first use so free-text and voice
        never parse into an empty list (which would otherwise land in
        Uncategorized).
        """
        if dependent:
            known_categories = DependentService.list_allowed_categories(
                owner_user, dependent, active_only=True
            )
        else:
            known_categories = CategoryService.list_categories(owner_user, active_only=True)

        if not known_categories and seed_defaults:
            logger.info("ai_pipeline status=no_categories_seeding_defaults user=%s", owner_user)
            CategoryService.create_default_categories(owner_user)
            if dependent:
                known_categories = DependentService.list_allowed_categories(
                    owner_user, dependent, active_only=True
                )
            else:
                known_categories = CategoryService.list_categories(owner_user, active_only=True)
        return known_categories

    @staticmethod
    def create_expense_from_audio(
        owner_user: str,
        file_path: str,
        dependent: Optional[str] = None,
        language_hint: Optional[str] = None,
        source: str = ExpenseSource.TELEGRAM,
    ) -> Document:
        transcript = speech_to_text.transcribe(file_path, language_hint=language_hint)
        logger.info("ai_pipeline transcript=%.200s", transcript)

        AIService._raise_if_income(transcript)

        known_categories = AIService._load_known_categories(owner_user, dependent=dependent)

        category_names = [row["category_name"] for row in known_categories]
        logger.info("ai_pipeline known_categories=%s", category_names)

        parsed = ai_parser.parse_expense(transcript, category_names)
        logger.info("ai_pipeline parsed_category=%s parsed_amount=%s", parsed["category"], parsed["amount"])

        if parsed.get("transaction_type", "expense") != "expense":
            raise IncomeDetectedError(AIService.INCOME_MSG)

        category_id = AIService._resolve_category(
            owner_user, parsed["category"], known_categories,
        )

        matched_dependent = dependent

        if matched_dependent:
            PocketMoneyService.enforce_available_balance(
                owner_user, matched_dependent, parsed["amount"]
            )

        expense = ExpenseService.create_expense(
            owner_user=owner_user,
            category=category_id,
            amount=parsed["amount"],
            expense_date=parsed["expense_date"],
            dependent=matched_dependent,
            description=parsed["description"],
            source=source,
            voice_transcript=transcript,
        )

        logger.info(
            "ai_expense_created | owner=%s | category=%s | amount=%s | id=%s",
            owner_user,
            category_id,
            parsed["amount"],
            expense.name,
        )

        return expense

    @staticmethod
    def create_expense_from_text(
        owner_user: str,
        text: str,
        dependent: Optional[str] = None,
        source: str = ExpenseSource.TELEGRAM,
    ) -> Document:
        AIService._raise_if_income(text)

        known_categories = AIService._load_known_categories(owner_user, dependent=dependent)
        category_names = [row["category_name"] for row in known_categories]
        logger.info("ai_pipeline_text known_categories=%s", category_names)

        parsed = ai_parser.parse_expense(text, category_names)

        if parsed.get("transaction_type", "expense") != "expense":
            raise IncomeDetectedError(AIService.INCOME_MSG)

        category_id = AIService._resolve_category(
            owner_user, parsed["category"], known_categories,
        )

        matched_dependent = dependent

        if matched_dependent:
            PocketMoneyService.enforce_available_balance(
                owner_user, matched_dependent, parsed["amount"]
            )

        expense = ExpenseService.create_expense(
            owner_user=owner_user,
            category=category_id,
            amount=parsed["amount"],
            expense_date=parsed["expense_date"],
            dependent=matched_dependent,
            description=parsed["description"],
            source=source,
        )

        logger.info(
            "ai_expense_created_from_text | owner=%s | category=%s | amount=%s | id=%s",
            owner_user,
            category_id,
            parsed["amount"],
            expense.name,
        )

        return expense

    @staticmethod
    def _resolve_category(
        owner_user: str,
        category_name: str,
        known_categories: list[dict],
    ) -> str:
        """Resolve an LLM-returned category to a live category id.

        Uses the canonical parser resolver (exact CI match, then brand/word
        aliases, then closest-match against the user's live categories) so
        voice and free-text always resolve identically. Falls back to the
        FALLBACK_CATEGORY, creating it when it does not exist for the owner.
        ``known_categories`` is already filtered to the acting identity's
        allowed categories (guardian: all; dependent: allowed_categories
        child table), so a dependent's free-text/voice can never silently
        resolve to a category it is not allowed to use.
        """
        category_names = [row["category_name"] for row in known_categories]
        resolved_name = ai_parser._resolve_category_name(category_name, category_names)

        for row in known_categories:
            if row["category_name"] == resolved_name:
                logger.info("category_resolve status=canonical input=%s resolved=%s", category_name, resolved_name)
                return row["name"]

        closest = ai_parser._find_closest_category(resolved_name, category_names)
        if closest:
            for row in known_categories:
                if row["category_name"] == closest:
                    logger.info(
                        "category_resolve status=canonical_closest input=%s resolved=%s",
                        category_name, closest,
                    )
                    return row["name"]

        if CategoryService.category_exists(owner_user, ExpenseParsingConfig.FALLBACK_CATEGORY):
            all_categories = CategoryService.list_categories(owner_user)
            for row in all_categories:
                if row["category_name"] == ExpenseParsingConfig.FALLBACK_CATEGORY:
                    logger.info("category_resolve status=fallback_resolved input=%s fallback=%s", category_name, ExpenseParsingConfig.FALLBACK_CATEGORY)
                    return row["name"]

        created = CategoryService.create_category(
            owner_user, ExpenseParsingConfig.FALLBACK_CATEGORY
        )
        logger.info("category_resolve status=fallback_created input=%s fallback=%s", category_name, ExpenseParsingConfig.FALLBACK_CATEGORY)
        return created.name