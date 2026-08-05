"""Groq LLM adapter: transcribed text -> structured expense dict.
Does NOT write to the database."""

from __future__ import annotations

import difflib
import json

import os
import certifi
import httpx
from groq import Groq
from frappe.utils import getdate, today
from dateutil.relativedelta import relativedelta

from expense_manager.telegram.config import get_groq_api_key, get_groq_model, get_use_mock_ai_apis
from expense_manager.ai.exceptions import ExpenseParsingError
from expense_manager.constants.ai import ExpenseParsingConfig
from expense_manager.constants.default_categories import CATEGORY_ALIASES
from expense_manager.utils.logger import logger


def _get_httpx_client() -> httpx.Client:
    ca_bundle = "/etc/ssl/certs/ca-certificates.crt"
    if os.path.exists(ca_bundle):
        return httpx.Client(verify=ca_bundle)
    return httpx.Client(verify=certifi.where())


def parse_expense(text: str, known_categories: list[str]) -> dict:
    if get_use_mock_ai_apis():
        logger.info("groq_parse status=mocked transcript=%.200s", text)
        fallback = known_categories[0] if known_categories else ExpenseParsingConfig.FALLBACK_CATEGORY
        return {
            "amount": 200.0,
            "category": fallback,
            "description": text[:100],
            "expense_date": today(),
            "transaction_type": "expense",
        }

    client = Groq(api_key=get_groq_api_key(), http_client=_get_httpx_client())

    for attempt in range(ExpenseParsingConfig.MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=get_groq_model(),
                response_format={"type": "json_object"},
                messages=_build_prompt(text, known_categories),
                timeout=ExpenseParsingConfig.TIMEOUT_SECONDS,
            )
            raw = response.choices[0].message.content
            result = _validate_expense_json(raw, known_categories)
            logger.info(
                "groq_parse status=success transcript=%.200s category=%s amount=%s",
                text, result["category"], result["amount"],
            )
            return result

        except ExpenseParsingError:
            if attempt < ExpenseParsingConfig.MAX_RETRIES:
                logger.info("groq_parse status=retry attempt=%d", attempt + 1)
                continue
            raise

        except Exception as exc:
            logger.info(
                "groq_parse status=error attempt=%d exc_type=%s exc=%s",
                attempt + 1,
                type(exc).__name__,
                exc,
            )
            if attempt < ExpenseParsingConfig.MAX_RETRIES:
                continue
            raise ExpenseParsingError(
                f"Groq expense parsing failed: {type(exc).__name__}: {exc}"
            ) from exc

    raise ExpenseParsingError("Groq expense parsing failed after retries.")


def _build_prompt(text: str, known_categories: list[str]) -> list[dict]:
    categories_list = ", ".join(known_categories) if known_categories else ExpenseParsingConfig.FALLBACK_CATEGORY
    today_str = today()

    system_prompt = (
        "You extract structured expense data from a short spoken description. "
        "Respond ONLY with a JSON object with exactly these keys: "
        "amount (positive number), category (must be one of the known "
        "categories below, or the literal string 'Uncategorized' if none match), "
        "description (short string), date (ISO date string 'YYYY-MM-DD', or null "
        "if no date was mentioned), "
        "transaction_type (must be the string 'expense' if the user is paying "
        "or spending money, or 'income' if they are receiving, getting back, "
        "or being credited money). "
        f"Today is {today_str}. If the user says 'today' use that date. "
        "Choose the best matching known category even if the item is a brand "
        "(e.g. Zomato -> Food Delivery, Swiggy -> Food Delivery, "
        "Netflix -> Entertainment, Uber -> Transport, Gym -> Fitness). "
        "Never invent a category that is not listed. "
        f"Known categories: {categories_list}."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]


def _find_closest_category(raw: str, known_categories: list[str]) -> str | None:
    """Return the known category most similar to ``raw`` (difflib ratio),
    or None when nothing clears the confidence threshold. Used so an LLM
    label like "Food & Dining" still resolves to a canonical live category
    ("Food") instead of falling back to Uncategorized."""
    if not raw or not known_categories:
        return None

    best_name: str | None = None
    best_ratio = 0.0
    for known in known_categories:
        ratio = difflib.SequenceMatcher(None, raw.lower(), known.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_name = known

    if best_name and best_ratio >= ExpenseParsingConfig.CLOSEST_CATEGORY_THRESHOLD:
        logger.info(
            "category_resolve status=closest_match input=%s resolved=%s ratio=%.2f",
            raw, best_name, best_ratio,
        )
        return best_name
    return None


def _resolve_category_name(raw_category: str | None, known_categories: list[str]) -> str:
    """Match a model-returned category against known categories with case-insensitive,
    alias-aware, and closest-match fallback. Returns the exact known category name
    (the canonical live name) or the custom Uncategorized category."""
    raw = (raw_category or "").strip()
    if not raw:
        logger.info("category_resolve status=empty_input fallback=%s", ExpenseParsingConfig.FALLBACK_CATEGORY)
        return ExpenseParsingConfig.FALLBACK_CATEGORY

    if raw == ExpenseParsingConfig.FALLBACK_CATEGORY:
        return raw

    raw_lower = raw.lower()
    for known in known_categories:
        if known.lower() == raw_lower:
            logger.info("category_resolve status=exact_match input=%s resolved=%s", raw, known)
            return known

    alias_target = CATEGORY_ALIASES.get(raw_lower)
    if alias_target:
        for known in known_categories:
            if known.lower() == alias_target.lower():
                logger.info("category_resolve status=alias_match input=%s via_alias=%s resolved=%s", raw, alias_target, known)
                return known
        closest = _find_closest_category(alias_target, known_categories)
        if closest:
            logger.info(
                "category_resolve status=alias_closest_match input=%s via_alias=%s resolved=%s",
                raw, alias_target, closest,
            )
            return closest
        logger.info("category_resolve status=alias_no_target input=%s alias_target=%s known_categories=%s", raw, alias_target, known_categories)

    closest = _find_closest_category(raw, known_categories)
    if closest:
        return closest

    logger.info("category_resolve status=fallback input=%s known_categories=%s", raw, known_categories)
    return ExpenseParsingConfig.FALLBACK_CATEGORY


def _validate_expense_json(raw: str | None, known_categories: list[str]) -> dict:
    if not raw:
        raise ExpenseParsingError("Groq returned an empty response.")

    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ExpenseParsingError("Groq returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise ExpenseParsingError("Groq response was not a JSON object.")

    missing = [key for key in ExpenseParsingConfig.REQUIRED_KEYS if key not in data]
    if missing:
        raise ExpenseParsingError(f"Groq response missing keys: {missing}.")

    amount = data.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ExpenseParsingError("Groq returned an invalid amount.")

    category = _resolve_category_name(data.get("category"), known_categories)

    raw_date = data.get("date")
    if raw_date:
        expense_date = getdate(raw_date)
        today_date = getdate(today())
        if expense_date > today_date:
            expense_date = today_date
        elif expense_date < today_date - relativedelta(days=30):
            raise ExpenseParsingError(
                f"Groq returned a date ({raw_date}) more than 30 days in the past."
            )
    else:
        expense_date = today()

    return {
        "amount": float(amount),
        "category": category,
        "description": (data.get("description") or "").strip(),
        "expense_date": expense_date,
        "transaction_type": (data.get("transaction_type") or "expense").strip().lower(),
    }