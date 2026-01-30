"""MCP Email Server

Exposes email/notification tools over the Model Context Protocol (MCP).

Tool(s):
- send_email(email: str, order_details: str) -> str
- send_custom(email: str, subject: str, message: str) -> str

This implementation uses the standard MCP stdio "wall socket" pattern so
clients can connect via a subprocess and communicate over stdin/stdout.

Tracking:
- This server does not send real emails. It logs a "sent" event and persists
  an email event record on the matching order in [`data.json`](data.json:1).
- A provider webhook can later append events (delivered/opened/clicked/bounced)
  via the UI API in [`frontend/app.py`](frontend/app.py:1).
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="[email_server] %(message)s")
logger = logging.getLogger("email_server")

mcp = FastMCP("email")


def _db_path() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data.json")


def _load_db() -> Dict[str, Any]:
    path = _db_path()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(data: Dict[str, Any]) -> None:
    path = _db_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _find_order_by_email(data: Dict[str, Any], email: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    orders = data.get("orders", {})
    if not isinstance(orders, dict):
        return None, None

    norm_email = str(email or "").strip().lower()
    for order_id, order in orders.items():
        if not isinstance(order, dict):
            continue
        if str(order.get("customer_email", "")).strip().lower() == norm_email:
            return str(order_id), order

    return None, None


def _append_email_event(order: Dict[str, Any], event: Dict[str, Any]) -> None:
    # Keep a compact event log on the order.
    events = order.get("email_events")
    if not isinstance(events, list):
        events = []
        order["email_events"] = events

    events.append(event)

    # Maintain a convenient latest status summary.
    order["email_status"] = str(event.get("event", "")).strip() or order.get("email_status")
    if "message_id" in event:
        order["email_message_id"] = event["message_id"]


@mcp.tool()
def send_email(email: str, order_details: str) -> str:
    """Log a shipping confirmation message and persist order status as shipped.

    Also persists a synthetic email event ("sent") on the order:
    - email_message_id
    - email_status
    - email_events[]

    Returns a JSON string with message_id so the host/UI can display/trace it.
    """

    message_id = f"msg_{uuid.uuid4().hex}"
    now = int(time.time())

    payload = {
        "email": email,
        "order_details": order_details,
        "type": "shipping_confirmation",
        "message_id": message_id,
        "ts": now,
    }
    logger.info("Email sent: %s", json.dumps(payload, ensure_ascii=False))

    # Persist status update in data.json (best-effort).
    # We locate the order by matching the customer's email.
    try:
        data = _load_db()
        order_id, order = _find_order_by_email(data, email)

        if order_id is None or order is None:
            logger.warning("Could not find order by customer_email=%s; status not updated", email)
            return json.dumps({"ok": True, "message_id": message_id, "order_id": None}, ensure_ascii=False)

        status = str(order.get("status", "")).strip().lower()
        if status == "cancelled":
            logger.warning(
                "Not updating status for cancelled order %s (email=%s)",
                order_id,
                email,
            )
            # Still record that a send was attempted? No: align with host rule.
            return json.dumps(
                {"ok": True, "message_id": message_id, "order_id": order_id, "skipped": "cancelled"},
                ensure_ascii=False,
            )

        order["status"] = "shipped"
        logger.info("Updated order status -> shipped (order_id=%s)", order_id)

        _append_email_event(
            order,
            {
                "event": "sent",
                "message_id": message_id,
                "to": str(email or "").strip(),
                "type": "shipping_confirmation",
                "ts": now,
            },
        )

        _save_db(data)

    except Exception as e:
        logger.warning("Failed to update data.json status: %s: %s", type(e).__name__, e)

    return json.dumps({"ok": True, "message_id": message_id}, ensure_ascii=False)


@mcp.tool()
def send_custom(email: str, subject: str, message: str) -> str:
    """Send/log a custom email-like message.

    This tool does NOT change order status in data.json.
    """

    message_id = f"msg_{uuid.uuid4().hex}"
    now = int(time.time())

    payload = {
        "email": email,
        "subject": subject,
        "message": message,
        "type": "custom",
        "message_id": message_id,
        "ts": now,
    }
    logger.info("Custom email sent: %s", json.dumps(payload, ensure_ascii=False))

    # Best-effort: append event to a matching order.
    try:
        data = _load_db()
        order_id, order = _find_order_by_email(data, email)
        if order_id is not None and order is not None:
            _append_email_event(
                order,
                {
                    "event": "sent",
                    "message_id": message_id,
                    "to": str(email or "").strip(),
                    "type": "custom",
                    "subject": str(subject or "").strip(),
                    "ts": now,
                },
            )
            _save_db(data)
    except Exception as e:
        logger.warning("Failed to append custom email event: %s: %s", type(e).__name__, e)

    return json.dumps({"ok": True, "message_id": message_id}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
