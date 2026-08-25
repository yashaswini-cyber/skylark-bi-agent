from config import DEALS_BOARD_ID, WORK_ORDERS_BOARD_ID
from monday_client import MondayClient, MondayClientError


def _test_board(client: MondayClient, label: str, board_id: str) -> dict:
    board = client.get_board_with_items(board_id)
    items = board["items"]

    print(f"{label} connection: success")
    print(f"{label} board name: {board['name']}")
    print(f"{label} item count: {len(items)}")
    if items:
        print(f"{label} first item name: {items[0].get('name')}")

    return board


def main() -> int:
    client = MondayClient()

    try:
        _test_board(client, "Deals", DEALS_BOARD_ID)
        _test_board(client, "Work Orders", WORK_ORDERS_BOARD_ID)
    except MondayClientError as exc:
        print("Read-only monday.com connection: failure")
        print(f"Technical error: {exc}")
        return 1

    print("Read-only monday.com connection: success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
