"""Minimal runnable check for the UI Run handler guard.

Run (from repo root):
  python frontend\test_guard_run.py

This script calls the same `/run` handler used by the UI and asserts that
"tell me a joke" is blocked with the refusal text.

Note: this uses FastAPI's TestClient (provided by Starlette/FastAPI).
"""

from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

# Ensure repo root is on sys.path when running as a script.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from frontend.app import app


def main() -> None:
    client = TestClient(app)

    # Regression: Order-status query containing an order id must proceed to normal order flow
    # (i.e., the /run endpoint should NOT return blocked/clarify).
    resp0 = client.post("/run", json={"command": "status of ORD-1004"})
    assert resp0.status_code == 200, resp0.text
    data0 = resp0.json()
    assert data0.get("blocked") is False, data0
    assert "run_id" in data0, data0

    # Regression: Out-of-scope content must be blocked.
    resp = client.post("/run", json={"command": "tell me a joke"})
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data.get("blocked") is True, data
    assert data.get("decision") == "BLOCK", data

    assistant = (data.get("assistant") or "").strip()
    assert assistant.startswith("I can’t help with jokes or unrelated requests."), assistant

    # Optional sanity check: support-related but missing required info should CLARIFY.
    resp2 = client.post("/run", json={"command": "what’s my order status?"})
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2.get("blocked") is True, data2
    assert data2.get("decision") == "CLARIFY", data2

    print("ok")


if __name__ == "__main__":
    main()
