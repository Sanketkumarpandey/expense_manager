from __future__ import annotations

from typing import Optional

from frappe.model.document import Document

from expense_manager.services.expense_service import ExpenseService
from expense_manager.services.category_service import CategoryService
from expense_manager.ai import speech_to_text, ai_parser
from expense_manager.constants.ai import ExpenseParsingConfig
from expense_manager.constants.expense import ExpenseSource
from expense_manager.utils.logger import logger


class AIService:

    @staticmethod
    def create_expense_from_audio(
        owner_user: str,
        file_path: str,
        dependent: Optional[str] = None,
        language_hint: Optional[str] = None,
        source: str = ExpenseSource.TELEGRAM,
    ) -> Document:
        transcript = speech_to_text.transcribe(file_path, language_hint=language_hint)

        known_categories = CategoryService.list_categories(owner_user, active_only=True)
        category_names = [row["category_name"] for row in known_categories]

        parsed = ai_parser.parse_expense(transcript, category_names)

        category_id = AIService._resolve_category(
            owner_user, parsed["category"], known_categories
        )

        expense = ExpenseService.create_expense(
            owner_user=owner_user,
            category=category_id,
            amount=parsed["amount"],
            expense_date=parsed["expense_date"],
            dependent=dependent,
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
    def _resolve_category(
        owner_user: str,
        category_name: str,
        known_categories: list[dict],
    ) -> str:
        for row in known_categories:
            if row["category_name"] == category_name:
                return row["name"]

        if CategoryService.category_exists(owner_user, ExpenseParsingConfig.FALLBACK_CATEGORY):
            all_categories = CategoryService.list_categories(owner_user)
            for row in all_categories:
                if row["category_name"] == ExpenseParsingConfig.FALLBACK_CATEGORY:
                    return row["name"]

        created = CategoryService.create_category(
            owner_user, ExpenseParsingConfig.FALLBACK_CATEGORY
        )
        return created.name