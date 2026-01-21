from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Simple in-memory run registry.
# For a single-user local tool this is enough.
_runs: Dict[str, "Run"] = {}
_active_run_id: Optional[str] = None


@dataclass
class Run:
    run_id: str
    command: str
    queue: "asyncio.Queue[dict]"
    task: "asyncio.Task[None]"


app = FastAPI(title="MCP Agent UI", version="0.1.0")


def _index_html() -> str:
    return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Logistics Assistant</title>
    <style>
      :root {
        --bg: #0b1020;
        --panel: rgba(255,255,255,0.06);
        --panel2: rgba(255,255,255,0.08);
        --text: #e8ecff;
        --muted: rgba(232,236,255,0.7);
        --border: rgba(255,255,255,0.12);
        --good: #22c55e;
        --warn: #f59e0b;
        --bad: #ef4444;
      }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
        color: var(--text);
        background: radial-gradient(1200px 800px at 20% 10%, rgba(99,102,241,0.25), transparent 60%),
                    radial-gradient(900px 600px at 80% 30%, rgba(34,197,94,0.18), transparent 55%),
                    var(--bg);
      }
      .wrap { max-width: 980px; margin: 22px auto; padding: 0 16px; }
      .header { display:flex; align-items:center; justify-content: space-between; gap: 12px; }
      .title { font-size: 20px; font-weight: 650; letter-spacing: 0.2px; }
      .subtitle { color: var(--muted); font-size: 13px; }
      .card {
        margin-top: 14px;
        padding: 14px;
        border: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.04));
        border-radius: 14px;
        box-shadow: 0 14px 34px rgba(0,0,0,0.35);
      }
      .row { display:flex; gap: 10px; flex-wrap: wrap; }
      .row input[type=text] {
        flex: 1;
        min-width: 300px;
        padding: 12px 12px;
        font-size: 16px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(0,0,0,0.35);
        color: var(--text);
        outline: none;
      }
      button {
        padding: 12px 14px;
        font-size: 15px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(255,255,255,0.10);
        color: var(--text);
        cursor: pointer;
      }
      button:disabled { opacity: 0.55; cursor: not-allowed; }
      .status { margin-top: 10px; color: var(--muted); font-size: 13px; }

      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-top: 12px;
      }
      @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }

      .panel {
        border: 1px solid var(--border);
        background: rgba(0,0,0,0.25);
        border-radius: 14px;
        padding: 12px;
      }
      .panel h3 { margin: 0 0 8px 0; font-size: 14px; color: var(--muted); font-weight: 650; }

      .kvs { display:grid; grid-template-columns: 160px 1fr; gap: 8px 10px; }
      .k { color: rgba(232,236,255,0.65); font-size: 13px; }
      .v { font-size: 14px; white-space: pre-wrap; word-break: break-word; }
      .badge { display:inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,0.10); font-size: 12px; }
      .badge.good { border-color: rgba(34,197,94,0.55); background: rgba(34,197,94,0.18); }
      .badge.warn { border-color: rgba(245,158,11,0.55); background: rgba(245,158,11,0.18); }
      .badge.bad  { border-color: rgba(239,68,68,0.55);  background: rgba(239,68,68,0.18); }

      details { margin-top: 12px; }
      summary { cursor: pointer; color: var(--muted); }
      pre {
        margin-top: 10px;
        background: rgba(0,0,0,0.45);
        border: 1px solid var(--border);
        color: var(--text);
        padding: 10px;
        border-radius: 12px;
        height: 280px;
        overflow: auto;
      }
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"header\">
        <div>
          <div class=\"title\">Logistics Assistant</div>
          <div class=\"subtitle\">Runs the agent and shows a clean order summary + optional debug logs.</div>
        </div>
      </div>

      <div class=\"card\">
        <div class=\"row\">
          <input id=\"cmd\" type=\"text\" placeholder=\"Ship order ORD-1001\" />
          <button id=\"run\">Run</button>
          <button id=\"stop\" disabled>Stop</button>
        </div>
        <div class=\"status\" id=\"status\">Ready.</div>

        <div class=\"grid\">
          <div class=\"panel\">
            <h3>Order summary</h3>
            <div class=\"kvs\">
              <div class=\"k\">order_id</div><div class=\"v\" id=\"order_id\">—</div>
              <div class=\"k\">status</div><div class=\"v\" id=\"status_badge\">—</div>
              <div class=\"k\">customer_email</div><div class=\"v\" id=\"customer_email\">—</div>
              <div class=\"k\">customer_name</div><div class=\"v\" id=\"customer_name\">—</div>
              <div class=\"k\">product</div><div class=\"v\" id=\"product\">—</div>
              <div class=\"k\">price</div><div class=\"v\" id=\"price\">—</div>
              <div class=\"k\">shipping_address</div><div class=\"v\" id=\"shipping_address\">—</div>
              <div class=\"k\">notes</div><div class=\"v\" id=\"notes\">—</div>
            </div>
          </div>

          <div class=\"panel\">
            <h3>Assistant</h3>
            <div class=\"v\" id=\"assistant_says\">—</div>
            <div class=\"subtitle\" style=\"margin-top:10px\">Tip: try “Where should we deliver order ORD-3007?” or “Ship order ORD-1001”.</div>
          </div>
        </div>

        <details>
          <summary>Debug logs (raw stdout/stderr)</summary>
          <pre id=\"debug\"></pre>
        </details>
      </div>
    </div>

    <script>
      const cmdEl = document.getElementById('cmd');
      const runEl = document.getElementById('run');
      const stopEl = document.getElementById('stop');
      const statusEl = document.getElementById('status');
      const debugEl = document.getElementById('debug');

      const orderEls = {
        order_id: document.getElementById('order_id'),
        status_badge: document.getElementById('status_badge'),
        customer_email: document.getElementById('customer_email'),
        customer_name: document.getElementById('customer_name'),
        product: document.getElementById('product'),
        price: document.getElementById('price'),
        shipping_address: document.getElementById('shipping_address'),
        notes: document.getElementById('notes'),
      };
      const assistantSaysEl = document.getElementById('assistant_says');

      let es = null;
      let currentRunId = null;

      function setBadge(status) {
        const s = (status || '').toLowerCase();
        let cls = 'badge';
        if (['shipped','delivered'].includes(s)) cls += ' good';
        else if (['pending','processing'].includes(s)) cls += ' warn';
        else if (['cancelled'].includes(s)) cls += ' bad';
        orderEls.status_badge.innerHTML = status ? `<span class=\"${cls}\">${status}</span>` : '—';
      }

      function resetPanels() {
        for (const k of Object.keys(orderEls)) orderEls[k].textContent = '—';
        assistantSaysEl.textContent = '—';
        debugEl.textContent = '';
      }

      function addDebug(stream, text) {
        const tag = stream === 'stderr' ? '[stderr]' : '[stdout]';
        debugEl.textContent += `${tag} ${text}\n`;
        debugEl.scrollTop = debugEl.scrollHeight;
      }

      function tryParseOrderFromLine(text) {
        // Extract order_id from: [crm_server] Normalized order id: 'ORD-1001'
        const m = text.match(/Normalized order id:\\s*'([^']+)'/);
        if (m) orderEls.order_id.textContent = m[1];

        // Extract tool_result JSON from: [host] tool_result -> {...}
        const t = text.match(/\\[host\\]\\s+tool_result\\s+->\\s+(\\{.*\\})\\s*$/);
        if (!t) return;

        try {
          const obj = JSON.parse(t[1]);
          if (obj && typeof obj === 'object') {
            if (obj.order_id) orderEls.order_id.textContent = obj.order_id;
            if (obj.customer_email) orderEls.customer_email.textContent = obj.customer_email;
            if (obj.customer_name) orderEls.customer_name.textContent = obj.customer_name;
            if (obj.product) orderEls.product.textContent = obj.product;
            if (obj.price != null) orderEls.price.textContent = String(obj.price);
            if (obj.shipping_address) orderEls.shipping_address.textContent = obj.shipping_address;
            if (obj.notes != null) orderEls.notes.textContent = obj.notes;
            if (obj.status) setBadge(obj.status);
          }
        } catch (e) {
          // ignore parse errors
        }
      }

      function tryParseAssistantSentence(stream, text) {
        // Only treat plain Host/model output as the assistant response.
        // Filter out internal log prefixes.
        if (stream !== 'stdout') return;
        if (!text) return;
        if (
          text.startsWith('[host]') ||
          text.startsWith('[crm_server]') ||
          text.startsWith('[email_server]') ||
          text.startsWith('[') // timestamps / other logs
        ) {
          return;
        }

        // Show the last meaningful line as the assistant sentence.
        assistantSaysEl.textContent = text;
      }

      async function startRun() {
        const cmd = (cmdEl.value || '').trim();
        if (!cmd) return;

        resetPanels();
        statusEl.textContent = 'Starting...';

        const resp = await fetch('/run', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ command: cmd })
        });
        const data = await resp.json();
        if (!resp.ok) {
          statusEl.textContent = `Error: ${data.detail || resp.status}`;
          return;
        }

        currentRunId = data.run_id;
        stopEl.disabled = false;
        runEl.disabled = true;
        statusEl.textContent = `Running: ${cmd}`;

        es = new EventSource(`/events/${currentRunId}`);
        es.addEventListener('line', (evt) => {
          const msg = JSON.parse(evt.data);
          addDebug(msg.stream, msg.text);
          tryParseOrderFromLine(msg.text);
          tryParseAssistantSentence(msg.stream, msg.text);
        });
        es.addEventListener('done', (evt) => {
          const msg = JSON.parse(evt.data);
          addDebug('stdout', `DONE (exit_code=${msg.exit_code})`);
          statusEl.textContent = 'Ready.';
          cleanup();
        });
        es.addEventListener('error', () => {
          addDebug('stderr', 'SSE connection error');
          statusEl.textContent = 'Ready.';
          cleanup();
        });
      }

      async function stopRun() {
        if (!currentRunId) return;
        await fetch(`/stop/${currentRunId}`, { method: 'POST' });
      }

      function cleanup() {
        if (es) { es.close(); es = null; }
        runEl.disabled = false;
        stopEl.disabled = true;
        currentRunId = null;
      }

      runEl.addEventListener('click', startRun);
      stopEl.addEventListener('click', stopRun);
      cmdEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startRun();
      });

      // initial
      resetPanels();
    </script>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _index_html()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
async def run_agent_endpoint(request: Request) -> JSONResponse:
    global _active_run_id

    body = await request.json()
    command = str(body.get("command", "")).strip()
    if not command:
        return JSONResponse({"detail": "command is required"}, status_code=400)
    if len(command) > 500:
        return JSONResponse({"detail": "command too long"}, status_code=400)

    # Single active run guard (keeps data.json writes sane).
    if _active_run_id is not None:
        return JSONResponse({"detail": "A run is already in progress"}, status_code=409)

    run_id = uuid.uuid4().hex
    q: asyncio.Queue[dict] = asyncio.Queue()

    task = asyncio.create_task(_run_subprocess(run_id=run_id, command=command, queue=q))
    _runs[run_id] = Run(run_id=run_id, command=command, queue=q, task=task)
    _active_run_id = run_id

    return JSONResponse({"run_id": run_id})


@app.post("/stop/{run_id}")
async def stop_run(run_id: str) -> JSONResponse:
    run = _runs.get(run_id)
    if run is None:
        return JSONResponse({"detail": "run_id not found"}, status_code=404)

    # Mark stop request by putting a control message; subprocess task checks it.
    await run.queue.put({"type": "control", "action": "stop"})
    return JSONResponse({"status": "stopping"})


@app.get("/events/{run_id}")
async def events(run_id: str) -> StreamingResponse:
    run = _runs.get(run_id)
    if run is None:
        return StreamingResponse(_sse_error("run_id not found"), media_type="text/event-stream")

    async def gen() -> AsyncIterator[bytes]:
        # Initial comment to open stream.
        yield b": ok\n\n"

        while True:
            msg = await run.queue.get()
            mtype = msg.get("type")

            if mtype == "line":
                payload = json.dumps({"stream": msg["stream"], "text": msg["text"]}, ensure_ascii=False)
                yield f"event: line\ndata: {payload}\n\n".encode("utf-8")
                continue

            if mtype == "done":
                payload = json.dumps({"exit_code": msg.get("exit_code", 0)})
                yield f"event: done\ndata: {payload}\n\n".encode("utf-8")
                break

            # ignore control messages here

    return StreamingResponse(gen(), media_type="text/event-stream")


async def _run_subprocess(*, run_id: str, command: str, queue: "asyncio.Queue[dict]") -> None:
    """Run `python main.py <command>` and stream stdout+stderr lines into queue."""
    global _active_run_id

    proc: Optional[asyncio.subprocess.Process] = None

    try:
        python = sys.executable
        main_py = os.path.join(PROJECT_DIR, "main.py")

        proc = await asyncio.create_subprocess_exec(
            python,
            main_py,
            command,
            cwd=PROJECT_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=0 if os.name != "nt" else 0,
        )

        assert proc.stdout is not None
        assert proc.stderr is not None

        stop_requested = asyncio.Event()

        async def pump(stream_name: str, stream: asyncio.StreamReader) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                await queue.put({"type": "line", "stream": stream_name, "text": text})

        async def control_loop() -> None:
            while not stop_requested.is_set():
                msg = await queue.get()
                if msg.get("type") == "control" and msg.get("action") == "stop":
                    stop_requested.set()
                    if proc is not None and proc.returncode is None:
                        if os.name == "nt":
                            proc.terminate()
                        else:
                            proc.send_signal(signal.SIGTERM)
                    return
                # ignore any other message types here

        pump_out = asyncio.create_task(pump("stdout", proc.stdout))
        pump_err = asyncio.create_task(pump("stderr", proc.stderr))
        ctl = asyncio.create_task(control_loop())

        # Wait for process exit (with a timeout) and stream completion.
        try:
            exit_code = await asyncio.wait_for(proc.wait(), timeout=90)
        except asyncio.TimeoutError:
            await queue.put({"type": "line", "stream": "stderr", "text": "[ui] TIMEOUT: killing process"})
            if os.name == "nt":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGKILL)
            exit_code = await proc.wait()

        await pump_out
        await pump_err

        # Stop control loop if still running.
        if not ctl.done():
            ctl.cancel()

        await queue.put({"type": "done", "exit_code": exit_code})

    except Exception as e:
        await queue.put(
            {"type": "line", "stream": "stderr", "text": f"[ui] ERROR: {type(e).__name__}: {e}"}
        )
        await queue.put({"type": "done", "exit_code": 1})

    finally:
        _active_run_id = None
        # keep run record for possible inspection; can be GC'd later.


async def _sse_error(message: str) -> AsyncIterator[bytes]:
    payload = json.dumps({"detail": message})
    yield f"event: done\ndata: {payload}\n\n".encode("utf-8")
