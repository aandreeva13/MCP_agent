"""MCP Email Server

Exposes email/notification tools over the Model Context Protocol (MCP).

Tool(s):
- send_shipping_confirmation(email: str, order_details: str) -> str

This implementation uses the standard MCP stdio "wall socket" pattern so
clients can connect via a subprocess and communicate over stdin/stdout.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="[email_server] %(message)s")
logger = logging.getLogger("email_server")

mcp = FastMCP("email")


@mcp.tool()
def send_shipping_confirmation(email: str, order_details: str) -> str:
    """Log a shipping confirmation message."""

    payload = {"email": email, "order_details": order_details}
    logger.info("Shipping confirmation sent: %s", json.dumps(payload, ensure_ascii=False))
    return "ok"


if __name__ == "__main__":
    mcp.run()
