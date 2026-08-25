from enum import Enum

from pydantic import BaseModel, Field


class AnalyticsIntent(str, Enum):
    OPEN_PIPELINE = "open_pipeline"
    WON_BUSINESS = "won_business"
    SECTOR_PIPELINE = "sector_pipeline"
    DEAL_STAGE_ANALYSIS = "deal_stage_analysis"
    WORK_ORDER_STATUS = "work_order_status"
    BILLING_SUMMARY = "billing_summary"
    SECTOR_OPERATIONS = "sector_operations"
    CROSS_BOARD_SECTOR_ANALYSIS = "cross_board_sector_analysis"
    DATA_QUALITY = "data_quality"
    CLARIFICATION = "clarification"


class AnalyticsRequest(BaseModel):
    intent: AnalyticsIntent
    sector: str | None = None
    deal_stage: str | None = None
    status: str | None = None
    clarification_question: str | None = None
    reasoning: str | None = Field(
        default=None,
        description="Short explanation of why this intent and parameters were selected.",
    )


class VerifiedAnalyticsResult(BaseModel):
    intent: AnalyticsIntent
    result: dict | list
    sector: str | None = None
    deal_stage: str | None = None
    status: str | None = None


class BusinessAnswer(BaseModel):
    answer: str
