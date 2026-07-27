"""OpenAI GPT adapter: transcribed text -> structured expense dict.
Does NOT write to the database."""

from __future__ import annotations

import json

from openai import OpenAI
from frappe.utils import getdate, today

from expense_manager.telegram.config import get_openai_api_key, get_openai_model, get_use_mock_ai_apis
from expense_manager.ai.exceptions import ExpenseParsingError
from expense_manager.constants.ai import ExpenseParsingConfig
from expense_manager.utils.logger import logger


def parse_expense(text: str, known_categories: list[str]) -> dict:
    if get_use_mock_ai_apis():
        logger.info("openai_parse status=mocked")
        fallback = known_categories[0] if known_categories else ExpenseParsingConfig.FALLBACK_CATEGORY
        return {
            "amount": 200.0,
            "category": fallback,
            "description": text[:100],
            "expense_date": today(),
        }

    client = OpenAI(api_key=get_openai_api_key())

    for attempt in range(ExpenseParsingConfig.MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=get_openai_model(),
                response_format={"type": "json_object"},
                messages=_build_prompt(text, known_categories),
                timeout=ExpenseParsingConfig.TIMEOUT_SECONDS,
            )
            raw = response.choices[0].message.content
            return _validate_expense_json(raw, known_categories)

        except ExpenseParsingError:
            if attempt < ExpenseParsingConfig.MAX_RETRIES:
                logger.info("openai_parse status=retry attempt=%d", attempt + 1)
                continue
            raise

        except Exception as exc:
            if attempt < ExpenseParsingConfig.MAX_RETRIES:
                logger.info("openai_parse status=error_retry attempt=%d", attempt + 1)
                continue
            raise ExpenseParsingError("OpenAI expense parsing failed.") from exc

    raise ExpenseParsingError("OpenAI expense parsing failed after retries.")


def _build_prompt(text: str, known_categories: list[str]) -> list[dict]:
    categories_list = ", ".join(known_categories) if known_categories else ExpenseParsingConfig.FALLBACK_CATEGORY

    system_prompt = (
        "You extract structured expense data from a short spoken description. "
        "Respond ONLY with a JSON object with exactly these keys: "
        "amount (positive number), category (must be exactly one of the known "
        "categories below, or the literal string 'Uncategorized'), "
        "description (short string), date (ISO date string 'YYYY-MM-DD', or null "
        "if no date was mentioned). Never invent a category that is not listed. "
        f"Known categories: {categories_list}."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]


def _validate_expense_json(raw: str | None, known_categories: list[str]) -> dict:
    if not raw:
        raise ExpenseParsingError("OpenAI returned an empty response.")

    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ExpenseParsingError("OpenAI returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise ExpenseParsingError("OpenAI response was not a JSON object.")

    missing = [key for key in ExpenseParsingConfig.REQUIRED_KEYS if key not in data]
    if missing:
        raise ExpenseParsingError(f"OpenAI response missing keys: {missing}.")

    amount = data.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ExpenseParsingError("OpenAI returned an invalid amount.")

    category = data.get("category")
    if category not in known_categories and category != ExpenseParsingConfig.FALLBACK_CATEGORY:
        category = ExpenseParsingConfig.FALLBACK_CATEGORY

    raw_date = data.get("date")
    if raw_date:
        expense_date = getdate(raw_date)
        if expense_date > getdate(today()):
            expense_date = today()
    else:
        expense_date = today()

    return {
        "amount": float(amount),
        "category": category,
        "description": (data.get("description") or "").strip(),
        "expense_date": expense_date,
    }