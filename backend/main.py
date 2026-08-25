from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from analytics import (
    billing_summary,
    cross_board_sector_analysis,
    data_quality_summary,
    deal_stage_analysis,
    open_pipeline,
    sector_operational_analysis,
    sector_pipeline,
    won_business,
    work_order_status_counts,
)
from answer_generator import AnswerGenerator, fallback_answer
from config import DEALS_BOARD_ID, WORK_ORDERS_BOARD_ID
from data_normalizer import normalize_boards
from models import AnalyticsIntent, AnalyticsRequest, VerifiedAnalyticsResult
from monday_client import MondayClient, MondayClientError
from query_planner import QueryPlanner, heuristic_plan


app = FastAPI(title="Skylark BI Agent API")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


def _records(frame):
    return frame.to_dict(orient="records")


def _load_normalized_data():
    client = MondayClient()
    deals_board = client.get_board_with_items(DEALS_BOARD_ID)
    work_orders_board = client.get_board_with_items(WORK_ORDERS_BOARD_ID)
    return normalize_boards(deals_board, work_orders_board)


def _run_verified_analytics(
    plan: AnalyticsRequest,
    normalized,
) -> VerifiedAnalyticsResult:

    if plan.intent == AnalyticsIntent.OPEN_PIPELINE:
        result = open_pipeline(normalized.deals)

    elif plan.intent == AnalyticsIntent.WON_BUSINESS:
        result = won_business(normalized.deals)

    elif plan.intent == AnalyticsIntent.SECTOR_PIPELINE:
        result = _records(sector_pipeline(normalized.deals))

    elif plan.intent == AnalyticsIntent.DEAL_STAGE_ANALYSIS:
        result = _records(deal_stage_analysis(normalized.deals))

    elif plan.intent == AnalyticsIntent.WORK_ORDER_STATUS:
        result = _records(work_order_status_counts(normalized.work_orders))

    elif plan.intent == AnalyticsIntent.BILLING_SUMMARY:
        result = billing_summary(normalized.work_orders)

    elif plan.intent == AnalyticsIntent.SECTOR_OPERATIONS:
        result = _records(
            sector_operational_analysis(normalized.work_orders)
        )

    elif plan.intent == AnalyticsIntent.CROSS_BOARD_SECTOR_ANALYSIS:
        if not plan.sector:
            raise ValueError(
                "cross_board_sector_analysis requires a sector"
            )

        result = cross_board_sector_analysis(
            normalized.deals,
            normalized.work_orders,
            plan.sector,
        )

    elif plan.intent == AnalyticsIntent.DATA_QUALITY:
        result = data_quality_summary(normalized.quality)

    elif plan.intent == AnalyticsIntent.CLARIFICATION:
        result = {
            "clarification_question": plan.clarification_question
        }

    else:
        raise ValueError(
            f"Unsupported analytics intent: {plan.intent}"
        )

    return VerifiedAnalyticsResult(
        intent=plan.intent,
        result=result,
        sector=plan.sector,
        deal_stage=plan.deal_stage,
        status=plan.status,
    )


def _is_temporary_ai_error(exc: Exception) -> bool:
    message = str(exc).lower()

    temporary_markers = [
        "429",
        "503",
        "resource_exhausted",
        "quota",
        "rate limit",
        "temporarily unavailable",
        "unavailable",
    ]

    return any(marker in message for marker in temporary_markers)


@app.get("/")
def root():
    return {
        "service": "Skylark BI Agent",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest):

    # 1. Get current live monday.com data
    try:
        normalized = _load_normalized_data()

    except MondayClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"monday.com read failed: {exc}",
        ) from exc

    # 2. Ask Gemini to understand the question.
    #    If Gemini is unavailable, use the deterministic heuristic planner.
    try:
        plan = QueryPlanner().plan(request.message)

    except Exception as exc:
        if _is_temporary_ai_error(exc):
            plan = heuristic_plan(
                request.message,
                sectors=normalized.deals.get("sector", []).dropna().unique().tolist()
                if "sector" in normalized.deals.columns
                else [],
            )
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Query planning failed: {exc}",
            ) from exc

    # 3. Clarification request
    if plan.intent == AnalyticsIntent.CLARIFICATION:
        return {
            "answer": plan.clarification_question
            or "Please clarify your question.",
            "intent": plan.intent.value,
            "analytics_result": {},
        }

    # 4. Run deterministic analytics
    try:
        verified_result = _run_verified_analytics(
            plan,
            normalized,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analytics failed: {exc}",
        ) from exc

    # 5. Generate natural-language answer.
    #    If Gemini is unavailable, use verified analytics directly.
    try:
        answer = AnswerGenerator().generate(
            request.message,
            verified_result,
        )

    except Exception as exc:
        if _is_temporary_ai_error(exc):
            answer = fallback_answer(verified_result)
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Answer generation failed: {exc}",
            ) from exc

    response = {
        "answer": answer.answer,
        "intent": verified_result.intent.value,
        "analytics_result": verified_result.result,
    }

    if plan.intent == AnalyticsIntent.DATA_QUALITY:
        response["data_quality"] = normalized.quality

    return response