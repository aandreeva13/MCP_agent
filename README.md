# Autonomous Operations Agent (MCP)

This project demonstrates a **decoupled** host/agent that processes customer orders by coordinating between **two MCP servers** using the standard MCP stdio **"wall socket"** pattern.

## Files

- [`crm_server.py`](crm_server.py) — MCP server exposing [`get_customer_email()`](crm_server.py:1)
- [`email_server.py`](email_server.py) — MCP server exposing [`send_shipping_confirmation()`](email_server.py:1)
- [`main.py`](main.py) — Host/agent using the OpenAI SDK and MCP client sessions
- [`.env.example`](.env.example) — environment variable template

## Architecture

- The Host in [`main.py`](main.py) has **no hardcoded API logic** for CRM or email.
- It only:
  1. connects to MCP servers via stdio wall sockets,
  2. lists tools from each server,
  3. lets the model decide which tools to call,
  4. executes tool calls and returns results back to the model.

Servers can be swapped by changing the wall-socket descriptors (command/args) in [`run_agent()`](main.py:126) without changing tool invocation logic.

## Setup

### 1) Install dependencies

Create and activate a virtual environment (recommended), then:

```bash
pip install "mcp" "openai"
```

### 2) Provide your OpenAI API key

You can do this in one of two ways:

#### Option A: Set an environment variable (quick)

**Windows (cmd.exe):**

```bat
set OPENAI_API_KEY=YOUR_KEY
```

Optionally set a model:

```bat
set OPENAI_MODEL=gpt-4.1-mini
```

#### Option B: Use a local `.env` file (recommended)

If you are using an **OpenAI-compatible gateway** (not OpenAI directly), also set:

- `OPENAI_BASE_URL=https://...`

The host reads this in [`run_agent()`](main.py:126) and passes it to [`AsyncOpenAI()`](main.py:1) via `base_url`.

1. Copy the template:
   - cmd.exe: `copy .env.example .env`
   - PowerShell: `Copy-Item .env.example .env`
2. Edit `.env` and set `OPENAI_API_KEY=...` (or `OPENAI_KEY=...`).

Simplest Windows approach: **do not load `.env`**; just set the variable in the same command you run:

**cmd.exe:**

```bat
set OPENAI_API_KEY=YOUR_KEY && python main.py "Process new order #XYZ-789"
```

If you do want to load `.env` into your current shell session, note that Windows `cmd.exe` requires double-percent in batch files.

**cmd.exe (interactive):**

```bat
for /f "usebackq tokens=1,* delims==" %A in (".env") do set "%A=%B"
```

**cmd.exe (in a .bat file):**

```bat
for /f "usebackq tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
```

**PowerShell:**

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^(\w+)\s*=\s*(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
```

## Run

Run the host/agent (it will spawn both MCP servers as subprocesses):

```bash
python main.py "Process new order #XYZ-789"
```

Expected behavior:

1. The agent calls [`get_customer_email()`](crm_server.py:1) on the CRM server.
2. Then it calls [`send_shipping_confirmation()`](email_server.py:1) on the Email server.
3. The Email server logs a confirmation line to stdout.
