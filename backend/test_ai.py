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


def _records(frame):
    return frame.to_dict(orient="records")


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


def main() -> int:
    questions = [
        "What is our open pipeline?",
        "How much is receivable from work orders?",
        "For Mining, compare open deals with work orders.",
    ]

    planner = QueryPlanner()
    plans = []
    for question in questions:
        plan = planner.plan(question)
        plans.append((question, plan))
        print(f"Question: {question}")
        print(f"Structured plan: {plan.model_dump(mode='json')}")

    try:
        client = MondayClient()
        deals_board = client.get_board_with_items(DEALS_BOARD_ID)
        work_orders_board = client.get_board_with_items(WORK_ORDERS_BOARD_ID)
    except MondayClientError as exc:
        print("AI test: failure")
        print(f"Technical error: {exc}")
        return 1

    normalized = normalize_boards(deals_board, work_orders_board)
    answer_plan = plans[0][1]
    verified_result = _run_verified_analytics(answer_plan, normalized)

    answer = AnswerGenerator().generate(plans[0][0], verified_result)
    print("Generated answer:")
    print(answer.answer)
    print("AI test: success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
