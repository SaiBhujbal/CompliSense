"""
CompliSense web server. Lightweight on purpose: it imports NO ML libraries, so
uvicorn never loads torch/chromadb (which segfaults on this CPU). Each /api/stream
request spawns agent_runner.py as an isolated subprocess and forwards its JSON
lines to the browser as Server-Sent Events.

Run:  uvicorn server:app --host 0.0.0.0 --port 8000
      (or: docker compose up)
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="CompliSense")
_HERE = os.path.dirname(os.path.abspath(__file__))


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Force the browser to revalidate static assets so edits show immediately."""

    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        if not request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp


app.add_middleware(NoCacheMiddleware)


@app.on_event("startup")
def _startup():
    """Best-effort: start Slack Socket Mode if tokens are already configured."""
    try:
        from src.slack_integration import try_start_socket_mode

        try_start_socket_mode()
    except Exception:  # noqa: BLE001
        pass


@app.get("/api/health")
def health():
    """Liveness + light readiness for Docker HEALTHCHECK / compose."""
    chroma = Path(os.getenv("CHROMA_DB_PATH", os.path.join(_HERE, "data", "chroma_db")))
    chroma_ok = (chroma / "chroma.sqlite3").exists()
    slack = {}
    try:
        from src.slack_integration import status as slack_status

        slack = slack_status()
    except Exception as e:  # noqa: BLE001
        slack = {"error": str(e)[:120]}
    return {
        "ok": True,
        "service": "complisense",
        "chroma_ready": chroma_ok,
        "chroma_path": str(chroma),
        "slack": slack,
    }


@app.get("/api/watchtower")
def watchtower(profile: str = "all", limit: int = 40):
    from src.watchtower import check
    try:
        return check(profile=profile, limit=limit)
    except Exception as e:  # noqa: BLE001
        return {"alerts": [], "new_count": 0, "error": str(e)[:200]}


@app.get("/api/news")
def news(q: str, limit: int = 20, tier3: bool = False):
    from src.newsfeed import get_news
    try:
        return get_news(q, limit=limit, include_tier3=tier3)
    except Exception as e:  # noqa: BLE001
        return {"query": q, "items": [], "error": str(e)[:200]}


@app.get("/api/slack/preview")
def slack_preview(kind: str = "watchtower", sector: str = ""):
    from src.slack_integration import preview
    try:
        return preview(kind, sector)
    except Exception as e:  # noqa: BLE001
        return {"kind": kind, "blocks": [], "error": str(e)[:200]}


@app.get("/api/slack/status")
def slack_status():
    from src.slack_integration import status
    try:
        return status()
    except Exception as e:  # noqa: BLE001
        return {"connected": False, "error": str(e)[:200]}


class _SlackConnect(BaseModel):
    webhook_url: str


@app.post("/api/slack/connect")
def slack_connect(body: _SlackConnect):
    from src.slack_integration import save_webhook
    return save_webhook(body.webhook_url)


@app.post("/api/slack/disconnect")
def slack_disconnect():
    from src.slack_integration import clear_webhook
    return clear_webhook()


class _SlackAskConnect(BaseModel):
    bot_token: str = ""
    app_token: str = ""
    signing_secret: str = ""


@app.post("/api/slack/ask/connect")
def slack_ask_connect(body: _SlackAskConnect):
    """Enable inbound Ask AI (Bot Token + optional Socket Mode App Token)."""
    from src.slack_integration import save_ask_tokens
    return save_ask_tokens(body.bot_token, body.app_token, body.signing_secret)


@app.post("/api/slack/ask/disconnect")
def slack_ask_disconnect():
    from src.slack_integration import clear_ask_tokens
    return clear_ask_tokens()


@app.post("/api/slack/ask/socket/start")
def slack_socket_start():
    from src.slack_integration import try_start_socket_mode
    return try_start_socket_mode()


class _SlackSend(BaseModel):
    kind: str = "watchtower"
    sector: str = ""
    blocks: list | None = None


@app.post("/api/slack/send")
def slack_send(body: _SlackSend):
    from src.slack_integration import send
    try:
        return send(body.kind, body.sector, body.blocks)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


@app.post("/api/slack/events")
async def slack_events(request: Request):
    """Slack Events API (URL verification + app_mention / DM). Needs public URL."""
    from src.slack_integration import handle_event_callback, verify_slack_signature

    body = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(body, ts, sig):
        # Still allow url_verification challenge without secret during setup
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return JSONResponse({"error": "invalid signature"}, status_code=401)
        if payload.get("type") != "url_verification":
            return JSONResponse({"error": "invalid signature"}, status_code=401)
    else:
        payload = json.loads(body.decode("utf-8"))

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    if payload.get("type") == "event_callback":
        return handle_event_callback(payload)
    return {"ok": True}


@app.post("/api/slack/commands")
async def slack_commands(request: Request):
    """Slash command `/complisense <question>` — works with public URL or Socket Mode."""
    from urllib.parse import parse_qs

    from src.slack_integration import (
        get_signing_secret,
        handle_slash_command,
        verify_slack_signature,
    )

    body = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    skip = os.getenv("SLACK_SKIP_VERIFY", "").lower() in ("1", "true", "yes")
    if get_signing_secret() and not skip and not verify_slack_signature(body, ts, sig):
        return JSONResponse({"error": "invalid signature"}, status_code=401)

    # Parse form from raw body — request.form() is unreliable after body() was read.
    raw = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    form = {k: (v[0] if isinstance(v, list) and v else "") for k, v in raw.items()}
    return handle_slash_command(form)


@app.get("/api/state")
def state(refresh: bool = False):
    from src.dailybrief import get_brief
    try:
        return get_brief(force_refresh=refresh)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


@app.get("/api/stream")
def stream(q: str):
    """SSE: spawn agent_runner and forward JSON lines. Always ends with done/error."""

    def gen():
        env = dict(
            os.environ,
            KMP_DUPLICATE_LIB_OK="TRUE",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        err_chunks: list[str] = []
        proc = subprocess.Popen(
            [sys.executable, "-u", os.path.join(_HERE, "agent_runner.py"), "--json", q],
            cwd=_HERE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        q_lines: queue.Queue[str | None] = queue.Queue()
        saw_done = False

        def reader():
            nonlocal saw_done
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    if '"done"' in line:
                        saw_done = True
                    q_lines.put(line)
            finally:
                q_lines.put(None)

        def err_reader():
            try:
                assert proc.stderr is not None
                for line in proc.stderr:
                    if line.strip():
                        err_chunks.append(line.strip()[:300])
                        if len(err_chunks) > 20:
                            err_chunks.pop(0)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=err_reader, daemon=True).start()

        def _stop_runner():
            """Client disconnect / generator close must not leave agent_runner hung."""
            if proc.poll() is not None:
                return
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:  # noqa: BLE001
                    pass

        yield ": connected\n\n"
        try:
            while True:
                try:
                    line = q_lines.get(timeout=10)
                except queue.Empty:
                    if proc.poll() is not None and q_lines.empty():
                        break
                    yield ": ping\n\n"
                    continue
                if line is None:
                    break
                yield f"data: {line}\n\n"
        finally:
            _stop_runner()
            if not saw_done:
                detail = " | ".join(err_chunks[-3:]) if err_chunks else f"exit {proc.returncode}"
                err = json.dumps({"error": f"Agent runner stopped early: {detail}"[:400]})
                done = json.dumps({
                    "done": True,
                    "response": (
                        "The analysis run stopped before finishing. "
                        f"({detail[:240]}) Try again — if this persists, check API keys "
                        "and that sentence-transformers is installed in the container."
                    ),
                    "sources": [],
                })
                yield f"data: {err}\n\n"
                yield f"data: {done}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.mount("/", StaticFiles(directory=os.path.join(_HERE, "web"), html=True), name="web")
