import json
import math
import re
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_API_KEY
from models import BusinessAnswer, VerifiedAnalyticsResult


ANSWER_MODEL = "gemini-3.6-flash"


def _format_indian_number(value: float) -> str:
    """Format a number using Indian-style comma grouping."""
    if not math.isfinite(value):
        return str(value)

    if value == int(value):
        return f"{int(value):,}"

    return f"{value:,.2f}"


def _format_currency(value: float) -> str:
    """
    Format a rupee amount into business-friendly Indian units.

    Examples:
        454838416.884 -> ₹45.48 Cr
        12500000      -> ₹1.25 Cr
        850000        -> ₹8.50 L
        25000         -> ₹25,000
    """
    absolute_value = abs(value)

    sign = "-" if value < 0 else ""

    if absolute_value >= 10_000_000:
        return f"{sign}₹{absolute_value / 10_000_000:.2f} Cr"

    if absolute_value >= 100_000:
        return f"{sign}₹{absolute_value / 100_000:.2f} L"

    return f"{sign}₹{_format_indian_number(absolute_value)}"


def _format_business_value(key: str, value: Any) -> Any:
    """
    Format numeric analytics values based on their field meaning.

    The underlying numeric value is never changed.
    This only affects presentation.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value

    key_lower = key.lower()

    currency_keywords = (
        "amount",
        "value",
        "revenue",
        "pipeline",
        "billed",
        "billing",
        "collected",
        "receivable",
        "receivables",
        "price",
        "cost",
        "payment",
        "contract",
        "sales",
    )

    if any(keyword in key_lower for keyword in currency_keywords):
        return _format_currency(float(value))

    if isinstance(value, float):
        if value.is_integer():
            return int(value)

        return round(value, 2)

    return value


def _format_result_for_display(value: Any) -> Any:
    """Recursively format analytics results for human-readable display."""
    if isinstance(value, dict):
        return {
            key: _format_result_for_display(
                _format_business_value(key, item)
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_format_result_for_display(item) for item in value]

    if isinstance(value, tuple):
        return [_format_result_for_display(item) for item in value]

    return value


def _humanize_key(key: str) -> str:
    """Convert analytics field names into readable labels."""
    text = key.replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.capitalize()


def _format_fallback_result(result: Any) -> str:
    """
    Convert verified analytics into a concise human-readable fallback.

    This function does not calculate new business metrics.
    It only formats values already produced by analytics.py.
    """
    formatted = _format_result_for_display(result)

    if isinstance(formatted, dict):
        parts = []

        for key, value in formatted.items():
            if value is None:
                continue

            if isinstance(value, (dict, list)):
                value_text = json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                )
            else:
                value_text = str(value)

            parts.append(f"{_humanize_key(key)}: {value_text}")

        return ". ".join(parts)

    if isinstance(formatted, list):
        return json.dumps(
            formatted,
            ensure_ascii=False,
            default=str,
        )

    return str(formatted)


class AnswerGenerator:
    def __init__(
        self,
        api_key: str = GEMINI_API_KEY,
        model: str = ANSWER_MODEL,
    ) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(
        self,
        question: str,
        verified_result: VerifiedAnalyticsResult,
    ) -> BusinessAnswer:

        result_json = verified_result.model_dump_json()

        prompt = (
            "Write a concise founder-level business answer. "
            "Use only the verified analytics result below. "
            "Do not invent, estimate, recalculate, or add numbers. "
            "The Python analytics result is the source of truth. "
            "Format monetary values clearly for a business audience. "
            "For Indian rupee amounts, use ₹ and suitable units such as "
            "L (lakh) or Cr (crore) when the underlying value supports it. "
            "For example, 454838416.884 should be presented approximately "
            "as ₹45.48 Cr. "
            "Do not expose raw floating-point precision to the user. "
            "If the result lacks enough information, say what is missing.\n\n"
            f"Question: {question}\n"
            f"Verified analytics result: {result_json}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
                response_mime_type="application/json",
                response_json_schema=BusinessAnswer.model_json_schema(),
            ),
        )

        if response.parsed:
            return BusinessAnswer.model_validate(response.parsed)

        return BusinessAnswer.model_validate(json.loads(response.text))


def generate_answer(
    question: str,
    verified_result: VerifiedAnalyticsResult,
) -> BusinessAnswer:
    return AnswerGenerator().generate(question, verified_result)


def fallback_answer(
    verified_result: VerifiedAnalyticsResult,
) -> BusinessAnswer:
    """
    Build an answer from verified analytics only.

    No Gemini call is made here.
    No business numbers are calculated here.
    Values are only formatted for presentation.
    """
    formatted_result = _format_fallback_result(
        verified_result.result
    )

    return BusinessAnswer(
        answer=(
            "Based on the latest verified monday.com data: "
            f"{formatted_result}."
        )
    )