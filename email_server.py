"""MCP Email Server

Exposes email/notification tools over the Model Context Protocol (MCP).

Tool(s):
- send_email(email: str, order_details: str) -> str

This implementation uses the standard MCP stdio "wall socket" pattern so
clients can connect via a subprocess and communicate over stdin/stdout.
"""

from __future__ import annotations

import json
import logging
import os

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="[email_server] %(message)s")
logger = logging.getLogger("email_server")

mcp = FastMCP("email")


@mcp.tool()
def send_email(email: str, order_details: str) -> str:
    """Log a shipping confirmation message and persist order status as shipped."""

    payload = {"email": email, "order_details": order_details, "type": "shipping_confirmation"}
    logger.info("Email sent: %s", json.dumps(payload, ensure_ascii=False))

    # Persist status update in data.json (best-effort).
    # We locate the order by matching the customer's email.
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "data.json")

        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        orders = data.get("orders", {})
        if isinstance(orders, dict):
            updated = False
            for order_id, order in orders.items():
                if not isinstance(order, dict):
                    continue
                if str(order.get("customer_email", "")).strip().lower() != str(email).strip().lower():
                    continue

                status = str(order.get("status", "")).strip().lower()
                if status == "cancelled":
                    logger.warning(
                        "Not updating status for cancelled order %s (email=%s)",
                        order_id,
                        email,
                    )
                    return "ok"

                order["status"] = "shipped"
                updated = True
                logger.info("Updated order status -> shipped (order_id=%s)", order_id)
                break

            if updated:
                with open(db_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                logger.warning("Could not find order by customer_email=%s; status not updated", email)
        else:
            logger.warning("data.json has invalid 'orders' shape; status not updated")

    except Exception as e:
        logger.warning("Failed to update data.json status: %s: %s", type(e).__name__, e)

    return "ok"


@mcp.tool()
def send_custom(email: str, subject: str, message: str) -> str:
    """Send/log a custom email-like message.

    This tool does NOT change order status in data.json.
    """

    payload = {"email": email, "subject": subject, "message": message, "type": "custom"}
    logger.info("Custom email sent: %s", json.dumps(payload, ensure_ascii=False))
    return "ok"


if __name__ == "__main__":
    mcp.run()
