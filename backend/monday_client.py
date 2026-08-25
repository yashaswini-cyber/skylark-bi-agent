import requests

from config import MONDAY_API_TOKEN


class MondayClientError(RuntimeError):
    """Base error for monday.com client failures."""


class MondayHTTPError(MondayClientError):
    """Raised when monday.com returns a non-success HTTP response."""


class MondayGraphQLError(MondayClientError):
    """Raised when monday.com returns GraphQL errors."""


class MondayClient:
    API_URL = "https://api.monday.com/v2"

    def __init__(self, token: str = MONDAY_API_TOKEN, timeout: int = 30) -> None:
        self.timeout = timeout
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    def _execute(self, query: str, variables: dict) -> dict:
        try:
            response = requests.post(
                self.API_URL,
                json={"query": query, "variables": variables},
                headers=self.headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MondayHTTPError(f"Failed to reach monday.com API: {exc}") from exc

        if not response.ok:
            message = f"monday.com API returned HTTP {response.status_code}"
            try:
                body = response.json()
                error_message = body.get("error_message") or body.get("message")
                if error_message:
                    message = f"{message}: {error_message}"
            except ValueError:
                pass
            raise MondayHTTPError(message)

        payload = response.json()
        errors = payload.get("errors")
        if errors:
            messages = []
            for error in errors:
                if isinstance(error, dict) and error.get("message"):
                    messages.append(error["message"])
            detail = "; ".join(messages) if messages else "Unknown GraphQL error"
            raise MondayGraphQLError(f"monday.com GraphQL error: {detail}")

        return payload.get("data", {})

    def get_board_with_items(self, board_id: str, page_limit: int = 100) -> dict:
        if page_limit < 1 or page_limit > 500:
            raise ValueError("page_limit must be between 1 and 500")

        board_query = """
        query GetBoardItems($board_ids: [ID!], $limit: Int!) {
          boards(ids: $board_ids) {
            id
            name
            columns {
              id
              title
              type
            }
            items_page(limit: $limit) {
              cursor
              items {
                id
                name
                column_values {
                  id
                  text
                  value
                  type
                }
              }
            }
          }
        }
        """

        data = self._execute(
            board_query,
            {"board_ids": [str(board_id)], "limit": page_limit},
        )
        boards = data.get("boards") or []
        if not boards:
            raise MondayGraphQLError(f"No board found for board ID {board_id}")

        board = boards[0]
        items_page = board.get("items_page") or {}
        items = list(items_page.get("items") or [])
        cursor = items_page.get("cursor")

        while cursor:
            page = self._get_next_items_page(cursor, page_limit)
            items.extend(page.get("items") or [])
            cursor = page.get("cursor")

        return {
            "id": board.get("id"),
            "name": board.get("name"),
            "columns": board.get("columns") or [],
            "items": items,
        }

    def _get_next_items_page(self, cursor: str, page_limit: int) -> dict:
        next_query = """
        query GetNextItemsPage($cursor: String!, $limit: Int!) {
          next_items_page(cursor: $cursor, limit: $limit) {
            cursor
            items {
              id
              name
              column_values {
                id
                text
                value
                type
              }
            }
          }
        }
        """

        data = self._execute(next_query, {"cursor": cursor, "limit": page_limit})
        return data.get("next_items_page") or {}
