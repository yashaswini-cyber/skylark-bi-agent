import json
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class NormalizedDataset:
    deals: pd.DataFrame
    work_orders: pd.DataFrame
    quality: dict[str, dict[str, int]]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return re.sub(r"\s+", " ", text)


def _clean_category(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    return text.title()


def _key(value: Any) -> str:
    text = _clean_text(value) or ""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _parse_json(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _parse_money(text: Any, raw_value: Any = None) -> float | None:
    raw = _parse_json(raw_value)
    if isinstance(raw, dict):
        for key in ("amount", "number", "value"):
            parsed = _parse_money(raw.get(key))
            if parsed is not None:
                return parsed

    cleaned = _clean_text(text)
    if cleaned is None:
        return None

    cleaned = cleaned.replace(",", "")
    match = re.search(r"-?\d+(\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_percent(text: Any, raw_value: Any = None) -> float | None:
    raw = _parse_json(raw_value)
    if isinstance(raw, dict):
        for key in ("percent", "number", "value"):
            parsed = _parse_percent(raw.get(key))
            if parsed is not None:
                return parsed

    cleaned = _clean_text(text)
    if cleaned is None:
        return None

    match = re.search(r"-?\d+(\.\d+)?", cleaned.replace(",", ""))
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None

    if number > 1:
        number = number / 100
    return number if 0 <= number <= 1 else None


def _parse_date(text: Any, raw_value: Any = None) -> Any:
    raw = _parse_json(raw_value)
    candidates: list[Any] = [text]
    if isinstance(raw, dict):
        candidates.extend(raw.get(key) for key in ("date", "from", "to", "changed_at"))

    for candidate in candidates:
        cleaned = _clean_text(candidate)
        if cleaned is None:
            continue
        parsed = pd.to_datetime(cleaned, errors="coerce")
        if not pd.isna(parsed):
            return parsed
    return pd.NaT


def _column_lookup(board: dict) -> dict[str, str]:
    lookup = {}
    for column in board.get("columns") or []:
        column_id = column.get("id")
        title = column.get("title")
        if column_id:
            lookup[_key(column_id)] = column_id
        if title and column_id:
            lookup[_key(title)] = column_id
    return lookup


def _find_column_id(lookup: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        candidate_key = _key(candidate)
        if candidate_key in lookup:
            return lookup[candidate_key]

    for lookup_key, column_id in lookup.items():
        for candidate in candidates:
            candidate_key = _key(candidate)
            if candidate_key and candidate_key in lookup_key:
                return column_id
    return None


def _item_columns(item: dict, columns_by_id: dict[str, str]) -> dict[str, dict[str, Any]]:
    values = {}
    for column_value in item.get("column_values") or []:
        column_id = column_value.get("id")
        title = columns_by_id.get(column_id, column_id)
        values[_key(title)] = column_value
        values[_key(column_id)] = column_value
    return values


def _column_text(values: dict[str, dict[str, Any]], column_id: str | None) -> str | None:
    if not column_id:
        return None
    value = values.get(_key(column_id))
    return _clean_text(value.get("text")) if value else None


def _column_raw(values: dict[str, dict[str, Any]], column_id: str | None) -> Any:
    if not column_id:
        return None
    value = values.get(_key(column_id))
    return value.get("value") if value else None


def _flatten_board(board: dict) -> pd.DataFrame:
    columns_by_id = {
        column.get("id"): column.get("title")
        for column in board.get("columns") or []
        if column.get("id")
    }
    rows = []
    for item in board.get("items") or []:
        row = {"item_id": item.get("id"), "item_name": _clean_text(item.get("name"))}
        for value in item.get("column_values") or []:
            title = columns_by_id.get(value.get("id"), value.get("id"))
            row[_key(title)] = _clean_text(value.get("text"))
        rows.append(row)
    return pd.DataFrame(rows)


def normalize_deals(board: dict) -> tuple[pd.DataFrame, dict[str, int]]:
    lookup = _column_lookup(board)
    columns_by_id = {
        column.get("id"): column.get("title")
        for column in board.get("columns") or []
        if column.get("id")
    }

    deal_value_id = _find_column_id(
        lookup, ["deal value", "pipeline value", "value", "amount", "project value", "contract value"]
    )
    probability_id = _find_column_id(
        lookup, ["closure probability", "close probability", "win probability", "probability"]
    )
    date_id = _find_column_id(lookup, ["closure date", "close date", "expected close date", "date", "timeline"])
    sector_id = _find_column_id(lookup, ["sector", "industry"])
    stage_id = _find_column_id(lookup, ["deal stage", "stage", "deal status", "status"])

    rows = []
    for item in board.get("items") or []:
        values = _item_columns(item, columns_by_id)
        value_text = _column_text(values, deal_value_id)
        probability_text = _column_text(values, probability_id)
        date_text = _column_text(values, date_id)

        rows.append(
            {
                "item_id": item.get("id"),
                "deal_name": _clean_text(item.get("name")),
                "deal_value": _parse_money(value_text, _column_raw(values, deal_value_id)),
                "closure_probability": _parse_percent(probability_text, _column_raw(values, probability_id)),
                "expected_close_date": _parse_date(date_text, _column_raw(values, date_id)),
                "sector": _clean_category(_column_text(values, sector_id)),
                "deal_stage": _clean_category(_column_text(values, stage_id)),
            }
        )

    deals = pd.DataFrame(rows)
    if deals.empty:
        deals = pd.DataFrame(
            columns=[
                "item_id",
                "deal_name",
                "deal_value",
                "closure_probability",
                "expected_close_date",
                "sector",
                "deal_stage",
            ]
        )

    quality = {
        "total_deals": int(len(deals)),
        "missing_deal_values": int(deals["deal_value"].isna().sum()),
        "missing_closure_probabilities": int(deals["closure_probability"].isna().sum()),
        "missing_dates": int(deals["expected_close_date"].isna().sum()),
        "missing_sectors": int(deals["sector"].isna().sum()),
        "missing_deal_stages": int(deals["deal_stage"].isna().sum()),
    }
    return deals, quality


def normalize_work_orders(board: dict) -> tuple[pd.DataFrame, dict[str, int]]:
    lookup = _column_lookup(board)
    columns_by_id = {
        column.get("id"): column.get("title")
        for column in board.get("columns") or []
        if column.get("id")
    }

    sector_id = _find_column_id(lookup, ["sector", "industry"])
    status_id = _find_column_id(lookup, ["execution status", "work order status", "status"])
    billed_id = _find_column_id(lookup, ["billed value", "total billed", "billed", "billing", "invoice amount"])
    collected_id = _find_column_id(
        lookup, ["collected amount", "total collected", "collected", "paid", "received"]
    )
    receivable_id = _find_column_id(
        lookup, ["amount receivable", "total receivable", "receivable", "outstanding", "balance"]
    )

    rows = []
    for item in board.get("items") or []:
        values = _item_columns(item, columns_by_id)
        rows.append(
            {
                "item_id": item.get("id"),
                "work_order_name": _clean_text(item.get("name")),
                "sector": _clean_category(_column_text(values, sector_id)),
                "execution_status": _clean_category(_column_text(values, status_id)),
                "billed_value": _parse_money(_column_text(values, billed_id), _column_raw(values, billed_id)),
                "collected_amount": _parse_money(
                    _column_text(values, collected_id), _column_raw(values, collected_id)
                ),
                "amount_receivable": _parse_money(
                    _column_text(values, receivable_id), _column_raw(values, receivable_id)
                ),
            }
        )

    work_orders = pd.DataFrame(rows)
    if work_orders.empty:
        work_orders = pd.DataFrame(
            columns=[
                "item_id",
                "work_order_name",
                "sector",
                "execution_status",
                "billed_value",
                "collected_amount",
                "amount_receivable",
            ]
        )

    quality = {
        "total_work_orders": int(len(work_orders)),
        "missing_sectors": int(work_orders["sector"].isna().sum()),
        "missing_execution_statuses": int(work_orders["execution_status"].isna().sum()),
        "missing_billed_values": int(work_orders["billed_value"].isna().sum()),
        "missing_collected_amounts": int(work_orders["collected_amount"].isna().sum()),
        "missing_amount_receivable": int(work_orders["amount_receivable"].isna().sum()),
    }
    return work_orders, quality


def normalize_boards(deals_board: dict, work_orders_board: dict) -> NormalizedDataset:
    deals, deals_quality = normalize_deals(deals_board)
    work_orders, work_orders_quality = normalize_work_orders(work_orders_board)
    return NormalizedDataset(
        deals=deals,
        work_orders=work_orders,
        quality={"deals": deals_quality, "work_orders": work_orders_quality},
    )
