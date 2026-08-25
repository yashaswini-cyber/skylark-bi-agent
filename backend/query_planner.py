import json
import re

from google import genai
from google.genai import types

from config import GEMINI_API_KEY
from models import AnalyticsIntent, AnalyticsRequest


PLANNER_MODEL = "gemini-3.6-flash"


class QueryPlanner:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = PLANNER_MODEL) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def plan(self, question: str) -> AnalyticsRequest:
        prompt = (
            "Map the user's BI question to one supported analytics intent. "
            "Supported intents: open_pipeline, won_business, sector_pipeline, "
            "deal_stage_analysis, work_order_status, billing_summary, "
            "sector_operations, cross_board_sector_analysis, data_quality. "
            "Extract sector, deal_stage, or status only when explicitly present. "
            "If a required parameter is missing or the question is ambiguous, use intent clarification "
            "and ask one short clarification_question. Do not calculate metrics.\n\n"
            f"Question: {question}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                response_mime_type="application/json",
                response_json_schema=AnalyticsRequest.model_json_schema(),
            ),
        )

        if response.parsed:
            return AnalyticsRequest.model_validate(response.parsed)

        return AnalyticsRequest.model_validate(json.loads(response.text))


def plan_query(question: str) -> AnalyticsRequest:
    return QueryPlanner().plan(question)


def _has_phrase(text: str, phrases: list[str]) -> bool:
    for phrase in phrases:
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return True
    return False


def _match_sector(text: str, sectors: list[str] | None) -> str | None:
    for sector in sectors or []:
        cleaned = str(sector).strip()
        if cleaned and cleaned.lower() in text:
            return cleaned
    return None


def heuristic_plan(question: str, sectors: list[str] | None = None) -> AnalyticsRequest:
    """Map a question to an intent without calling Gemini. Does not calculate metrics."""
    text = question.strip().lower()
    sector = _match_sector(text, sectors)

    if _has_phrase(text, ["data quality", "missing value", "missing data", "data completeness"]):
        return AnalyticsRequest(intent=AnalyticsIntent.DATA_QUALITY)

    if _has_phrase(text, ["receivable", "billed", "collected", "billing"]):
        return AnalyticsRequest(intent=AnalyticsIntent.BILLING_SUMMARY)

    if _has_phrase(text, ["execution status", "work order status", "work-order status"]):
        return AnalyticsRequest(intent=AnalyticsIntent.WORK_ORDER_STATUS)

    if _has_phrase(text, ["won business", "won deal", "closed won", "awarded"]):
        return AnalyticsRequest(intent=AnalyticsIntent.WON_BUSINESS)

    if _has_phrase(text, ["deal stage", "by stage", "pipeline stage"]):
        return AnalyticsRequest(intent=AnalyticsIntent.DEAL_STAGE_ANALYSIS)

    if _has_phrase(text, ["sector operation", "work orders by sector"]):
        return AnalyticsRequest(intent=AnalyticsIntent.SECTOR_OPERATIONS)

    if sector:
        return AnalyticsRequest(
            intent=AnalyticsIntent.CROSS_BOARD_SECTOR_ANALYSIS,
            sector=sector,
        )

    if _has_phrase(text, ["by sector", "sector pipeline", "pipeline by sector"]):
        return AnalyticsRequest(intent=AnalyticsIntent.SECTOR_PIPELINE)

    if _has_phrase(text, ["open pipeline", "open deal", "pipeline"]):
        return AnalyticsRequest(intent=AnalyticsIntent.OPEN_PIPELINE)

    if _has_phrase(text, ["work order"]):
        return AnalyticsRequest(intent=AnalyticsIntent.WORK_ORDER_STATUS)

    return AnalyticsRequest(
        intent=AnalyticsIntent.CLARIFICATION,
        clarification_question=(
            "Which metric should I analyze: open pipeline, won business, billing, "
            "work orders, or a specific sector?"
        ),
    )
