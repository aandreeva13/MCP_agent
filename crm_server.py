"""MCP CRM Server

Exposes CRM-related tools over the Model Context Protocol (MCP).

Tool(s):
- get_order_details(order_id: str) -> str

Reads from the local JSON file database [`data.json`](data.json:1).

This implementation uses the standard MCP stdio "wall socket" pattern so
clients can connect via a subprocess and communicate over stdin/stdout.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crm")
print("[crm_server] started", file=sys.stderr)


def _load_db() -> Dict[str, Any]:
    # 1. Find EXACTLY where this crm_server.py file is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 2. Join it with the data.json filename
    db_path = os.path.join(base_dir, "data.json")

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # stderr only so stdout remains reserved for MCP protocol messages.
        print(
            f"CRITICAL ERROR: CRM Server cannot find data.json at {db_path}",
            file=sys.stderr,
        )
        return {"orders": {}}


@mcp.tool()
def get_order_details(order_id: str) -> str:
    """Lookup and return order details for an order id.

    Expected DB shape for reliable lookup:
    {
      "orders": {
        "GHI-101": { ...order object... }
      }
    }

    The tool returns a string (JSON) representation of the order object so the LLM can read it.
    """

    try:
        # Keep the raw value visible for debugging.
        print(f"[crm_server] Server looking for: {order_id!r}", file=sys.stderr)

        # Normalize common formatting issues (leading '#', accidental whitespace).
        normalized_id = str(order_id or "").strip().lstrip("#").strip()
        print(
            f"[crm_server] Normalized order id: {normalized_id!r}",
            file=sys.stderr,
        )

        data = _load_db()

        # Requested lookup behavior: data.get('orders', {}).get(order_id)
        orders = data.get("orders", {})
        print(f"[crm_server] orders type: {type(orders).__name__}", file=sys.stderr)

        if not isinstance(orders, dict):
            raise ValueError(
                "data.json must have an 'orders' dictionary for O(1) lookup, e.g. { 'orders': { 'GHI-101': {...} } }"
            )

        order = orders.get(normalized_id)
        if order is None:
            # Print available keys for debugging (bounded).
            keys = list(orders.keys())
            print(
                f"[crm_server] Available order ids (sample): {keys[:50]!r}",
                file=sys.stderr,
            )
            raise ValueError(f"Order {normalized_id} not found in data.json")

        # Include the order id in the returned payload so UIs/clients can display it.
        payload = dict(order) if isinstance(order, dict) else {"order": order}
        payload.setdefault("order_id", normalized_id)

        # Ensure a string representation (stable JSON).
        return json.dumps(payload, ensure_ascii=False)

    except Exception as e:
        # stderr only so stdout remains reserved for MCP protocol messages.
        print(
            f"[crm_server] ERROR in get_order_details: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        raise


@mcp.tool()
def get_order(order_id: str) -> str:
    """Return the full order payload as a JSON string.

    This is equivalent to [`get_order_details()`](crm_server.py:46) and includes `order_id`.
    """

    return get_order_details(order_id)


@mcp.tool()
def get_email(order_id: str) -> str:
    """Return only the customer_email for the given order id."""

    order_json = get_order_details(order_id)
    order = json.loads(order_json)
    email = str(order.get("customer_email", "")).strip()
    if not email:
        raise ValueError(f"Order {order.get('order_id', order_id)} has no customer_email")
    return email


if __name__ == "__main__":
    mcp.run()
