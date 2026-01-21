# MCP Agent UI (FastAPI)

A small local web UI for running the agent (the Host in [`main.py`](../main.py:1)) and streaming live output from stdout/stderr via Server-Sent Events (SSE).

## Setup

From the repo root:

```bat
python -m venv .venv
.\.venv\Scripts\activate
pip install -r frontend\requirements.txt
```

## Run

```bat
.\.venv\Scripts\activate
uvicorn frontend.app:app --host 127.0.0.1 --port 3000
```

Open:
- http://127.0.0.1:3000

## What you’ll see

- **stdout**: Host prints like [`print(f"[host] tool_result -> {tool_output}")`](../main.py:284)
- **stderr**: server diagnostics like [`print("[crm_server] started", file=sys.stderr)`](../crm_server.py:24)

## Example

Type in the textbox:

- `Ship order ORD-1001`

You should see tool calls/results streamed, and after the email tool runs, the order status will be persisted to [`data.json`](../data.json:1) by [`send_email()`](../email_server.py:27).
