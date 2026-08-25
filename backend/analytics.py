from typing import Any

import pandas as pd

from models import AnalyticsIntent, AnalyticsRequest


WON_STAGES = {"won", "closed won", "awarded"}
NOT_OPEN_STAGES = WON_STAGES | {"lost", "closed lost", "dead", "cancelled", "canceled"}
ONGOING_STATUSES = {
    "ongoing",
    "in progress",
    "in-progress",
    "executing",
    "active",
    "started",
    "in execution",
}


def _empty_series() -> pd.Series:
    return pd.Series(dtype="float64")


def _as_float(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    return float(value)


def _status_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def open_deals(deals: pd.DataFrame) -> pd.DataFrame:
    if deals.empty:
        return deals.copy()
    stages = deals["deal_stage"].map(_status_key)
    return deals[~stages.isin(NOT_OPEN_STAGES)].copy()


def won_deals(deals: pd.DataFrame) -> pd.DataFrame:
    if deals.empty:
        return deals.copy()
    stages = deals["deal_stage"].map(_status_key)
    return deals[stages.isin(WON_STAGES)].copy()


def open_pipeline(deals: pd.DataFrame) -> dict[str, float | int]:
    open_df = open_deals(deals)
    return {
        "open_deal_count": int(len(open_df)),
        "open_pipeline_value": _as_float(open_df["deal_value"].dropna().sum()),
    }


def won_business(deals: pd.DataFrame) -> dict[str, float | int]:
    won_df = won_deals(deals)
    return {
        "won_deal_count": int(len(won_df)),
        "won_deal_value": _as_float(won_df["deal_value"].dropna().sum()),
    }


def sector_pipeline(deals: pd.DataFrame) -> pd.DataFrame:
    open_df = open_deals(deals)
    if open_df.empty:
        return pd.DataFrame(columns=["sector", "open_pipeline_value", "open_deal_count"])

    grouped = (
        open_df.groupby("sector", dropna=False)
        .agg(open_pipeline_value=("deal_value", "sum"), open_deal_count=("item_id", "count"))
        .reset_index()
    )
    grouped["sector"] = grouped["sector"].fillna("Unknown")
    return grouped.sort_values(["open_pipeline_value", "open_deal_count"], ascending=False)


def deal_stage_analysis(deals: pd.DataFrame) -> pd.DataFrame:
    open_df = open_deals(deals)
    if open_df.empty:
        return pd.DataFrame(columns=["deal_stage", "open_pipeline_value", "open_deal_count"])

    grouped = (
        open_df.groupby("deal_stage", dropna=False)
        .agg(open_pipeline_value=("deal_value", "sum"), open_deal_count=("item_id", "count"))
        .reset_index()
    )
    grouped["deal_stage"] = grouped["deal_stage"].fillna("Unknown")
    return grouped.sort_values(["open_pipeline_value", "open_deal_count"], ascending=False)


def work_order_status_counts(work_orders: pd.DataFrame) -> pd.DataFrame:
    if work_orders.empty:
        return pd.DataFrame(columns=["execution_status", "work_order_count"])

    counts = (
        work_orders.groupby("execution_status", dropna=False)
        .agg(work_order_count=("item_id", "count"))
        .reset_index()
    )
    counts["execution_status"] = counts["execution_status"].fillna("Unknown")
    return counts.sort_values("work_order_count", ascending=False)


def billing_summary(work_orders: pd.DataFrame) -> dict[str, float]:
    if work_orders.empty:
        return {
            "total_billed_value": 0.0,
            "total_collected_amount": 0.0,
            "total_amount_receivable": 0.0,
        }

    return {
        "total_billed_value": _as_float(work_orders["billed_value"].dropna().sum()),
        "total_collected_amount": _as_float(work_orders["collected_amount"].dropna().sum()),
        "total_amount_receivable": _as_float(work_orders["amount_receivable"].dropna().sum()),
    }


def sector_operational_analysis(work_orders: pd.DataFrame) -> pd.DataFrame:
    if work_orders.empty:
        return pd.DataFrame(columns=["sector", "execution_status", "work_order_count"])

    grouped = (
        work_orders.groupby(["sector", "execution_status"], dropna=False)
        .agg(work_order_count=("item_id", "count"))
        .reset_index()
    )
    grouped["sector"] = grouped["sector"].fillna("Unknown")
    grouped["execution_status"] = grouped["execution_status"].fillna("Unknown")
    return grouped.sort_values(["sector", "work_order_count"], ascending=[True, False])


def cross_board_sector_analysis(deals: pd.DataFrame, work_orders: pd.DataFrame, sector: str) -> dict[str, float | int | str]:
    sector_key = sector.strip().lower()
    open_df = open_deals(deals)

    sector_deals = open_df[open_df["sector"].fillna("").str.lower() == sector_key]
    sector_work_orders = work_orders[work_orders["sector"].fillna("").str.lower() == sector_key]
    ongoing = sector_work_orders[
        sector_work_orders["execution_status"].map(_status_key).isin(ONGOING_STATUSES)
    ]

    return {
        "sector": sector,
        "open_deal_count": int(len(sector_deals)),
        "open_pipeline_value": _as_float(sector_deals["deal_value"].dropna().sum()),
        "work_order_count": int(len(sector_work_orders)),
        "ongoing_work_order_count": int(len(ongoing)),
    }


def data_quality_summary(quality: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return quality


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.to_dict(orient="records")


def execute_plan(plan: AnalyticsRequest, normalized) -> dict[str, Any] | list[dict[str, Any]]:
    """Dispatch a structured plan to the matching deterministic analytics function."""
    if plan.intent == AnalyticsIntent.OPEN_PIPELINE:
        return open_pipeline(normalized.deals)
    if plan.intent == AnalyticsIntent.WON_BUSINESS:
        return won_business(normalized.deals)
    if plan.intent == AnalyticsIntent.SECTOR_PIPELINE:
        return _records(sector_pipeline(normalized.deals))
    if plan.intent == AnalyticsIntent.DEAL_STAGE_ANALYSIS:
        return _records(deal_stage_analysis(normalized.deals))
    if plan.intent == AnalyticsIntent.WORK_ORDER_STATUS:
        return _records(work_order_status_counts(normalized.work_orders))
    if plan.intent == AnalyticsIntent.BILLING_SUMMARY:
        return billing_summary(normalized.work_orders)
    if plan.intent == AnalyticsIntent.SECTOR_OPERATIONS:
        return _records(sector_operational_analysis(normalized.work_orders))
    if plan.intent == AnalyticsIntent.CROSS_BOARD_SECTOR_ANALYSIS:
        if not plan.sector:
            raise ValueError("cross_board_sector_analysis requires a sector")
        return cross_board_sector_analysis(normalized.deals, normalized.work_orders, plan.sector)
    if plan.intent == AnalyticsIntent.DATA_QUALITY:
        return data_quality_summary(normalized.quality)
    raise ValueError(f"Unsupported analytics intent: {plan.intent}")
