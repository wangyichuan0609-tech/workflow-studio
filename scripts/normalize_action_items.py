#!/usr/bin/env python3
"""Normalize extracted meeting action items from JSON on stdin."""

from __future__ import annotations

import json
import sys
from typing import Any


def due_date_key(item: dict[str, Any]) -> tuple[bool, str]:
    due_date = str(item.get("due_date", "")).strip()
    return (not due_date or due_date == "待确认", due_date)


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    action_items = payload.get("action_items", [])
    if not isinstance(action_items, list) or not all(
        isinstance(item, dict) for item in action_items
    ):
        raise ValueError("action_items must be an array of objects")

    normalized_items = []
    for index, item in enumerate(sorted(action_items, key=due_date_key), start=1):
        normalized_items.append({"task_id": f"TASK-{index:03d}", **item})

    return {**payload, "action_items": normalized_items}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        json.dump(normalize(payload), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    except (json.JSONDecodeError, ValueError) as error:
        print(f"normalize_action_items: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
