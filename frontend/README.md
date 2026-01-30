# MCP Agent UI (FastAPI)

A small local web UI for running the agent (the Host in [`main.py`](../main.py:1)) and streaming live output from stdout/stderr via Server-Sent Events (SSE).

## Policy/Safety guard

The UI backend runs a lightweight policy guard on **every** Run submission in [`POST /run`](app.py:495) before starting the agent subprocess.

- If the guard returns `BLOCK` (e.g. “tell me a joke”), the endpoint returns an immediate refusal payload and the UI displays it in the Assistant panel.
- If the guard returns `ALLOW`, the normal subprocess + SSE streaming flow runs unchanged.

To sanity-check the guard without running the UI server:

```bat
python frontend\test_guard_run.py
```

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
