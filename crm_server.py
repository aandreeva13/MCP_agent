"""MCP CRM Server

Exposes CRM-related tools over the Model Context Protocol (MCP).

Tool(s):
- get_customer_email(order_id: str) -> str

This implementation uses the standard MCP stdio "wall socket" pattern so
clients can connect via a subprocess and communicate over stdin/stdout.
"""

from __future__ import annotations

import re

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crm")


@mcp.tool()
def get_customer_email(order_id: str) -> str:
    """Return a mock customer email for a given order id."""

    # Keep it deterministic-ish so demos are stable.
    safe = re.sub(r"[^A-Za-z0-9]+", "-", (order_id or "").strip()).strip("-")
    if not safe:
        safe = "unknown"
    return f"customer+{safe.lower()}@example.com"


if __name__ == "__main__":
    mcp.run()
