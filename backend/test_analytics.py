from analytics import (
    billing_summary,
    cross_board_sector_analysis,
    data_quality_summary,
    open_pipeline,
    sector_operational_analysis,
    won_business,
    work_order_status_counts,
)
from config import DEALS_BOARD_ID, WORK_ORDERS_BOARD_ID
from data_normalizer import normalize_boards
from monday_client import MondayClient, MondayClientError


def _pick_sector(normalized) -> str:
    sectors = normalized.deals["sector"].dropna()
    if not sectors.empty:
        return sectors.iloc[0]

    sectors = normalized.work_orders["sector"].dropna()
    if not sectors.empty:
        return sectors.iloc[0]

    return "Unknown"


def main() -> int:
    client = MondayClient()

    try:
        deals_board = client.get_board_with_items(DEALS_BOARD_ID)
        work_orders_board = client.get_board_with_items(WORK_ORDERS_BOARD_ID)
    except MondayClientError as exc:
        print("Analytics test: failure")
        print(f"Technical error: {exc}")
        return 1

    normalized = normalize_boards(deals_board, work_orders_board)

    pipeline = open_pipeline(normalized.deals)
    won = won_business(normalized.deals)
    billing = billing_summary(normalized.work_orders)
    status_counts = work_order_status_counts(normalized.work_orders)
    sector = _pick_sector(normalized)
    sector_analysis = cross_board_sector_analysis(normalized.deals, normalized.work_orders, sector)
    sector_ops = sector_operational_analysis(normalized.work_orders)
    quality = data_quality_summary(normalized.quality)

    print("Analytics test: success")
    print(f"Open deal count: {pipeline['open_deal_count']}")
    print(f"Open pipeline value: {pipeline['open_pipeline_value']}")
    print(f"Won deal count: {won['won_deal_count']}")
    print(f"Total receivable: {billing['total_amount_receivable']}")
    print("Work-order status counts:")
    print(status_counts.to_string(index=False))
    print(f"Sector analysis for: {sector}")
    print(sector_analysis)
    print("Sector operational rows:", len(sector_ops))
    print("Data-quality summary:")
    print(quality)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
