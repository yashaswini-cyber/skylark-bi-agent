from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
from answer_generator import AnswerGenerator
from config import DEALS_BOARD_ID, WORK_ORDERS_BOARD_ID
from data_normalizer import normalize_boards
from models import AnalyticsIntent, AnalyticsRequest, VerifiedAnalyticsResult
from monday_client import MondayClient, MondayClientError
from query_planner import QueryPlanner


app = FastAPI(title="Skylark BI Agent API")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


def _records(frame):
    return frame.to_dict(orient="records")


def _load_normalized_data():
    client = MondayClient()
    deals_board = client.get_board_with_items(DEALS_BOARD_ID)
    work_orders_board = client.get_board_with_items(WORK_ORDERS_BOARD_ID)
    return normalize_boards(deals_board, work_orders_board)


def _run_verified_analytics(plan: AnalyticsRequest, normalized) -> VerifiedAnalyticsResult:
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
        result = _records(sector_operational_analysis(normalized.work_orders))
    elif plan.intent == AnalyticsIntent.CROSS_BOARD_SECTOR_ANALYSIS and plan.sector:
        result = cross_board_sector_analysis(normalized.deals, normalized.work_orders, plan.sector)
    elif plan.intent == AnalyticsIntent.DATA_QUALITY:
        result = data_quality_summary(normalized.quality)
    else:
        result = {"clarification_question": plan.clarification_question}

    return VerifiedAnalyticsResult(
        intent=plan.intent,
        result=result,
        sector=plan.sector,
        deal_stage=plan.deal_stage,
        status=plan.status,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        plan = QueryPlanner().plan(request.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Query planning failed: {exc}") from exc

    if plan.intent == AnalyticsIntent.CLARIFICATION:
        return {
            "answer": plan.clarification_question or "Please clarify your question.",
            "intent": plan.intent.value,
            "analytics_result": {},
        }

    try:
        normalized = _load_normalized_data()
        verified_result = _run_verified_analytics(plan, normalized)
    except MondayClientError as exc:
        raise HTTPException(status_code=502, detail=f"monday.com read failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {exc}") from exc

    try:
        answer = AnswerGenerator().generate(request.message, verified_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Answer generation failed: {exc}") from exc

    response = {
        "answer": answer.answer,
        "intent": verified_result.intent.value,
        "analytics_result": verified_result.result,
    }
    if plan.intent == AnalyticsIntent.DATA_QUALITY:
        response["data_quality"] = normalized.quality

    return response
