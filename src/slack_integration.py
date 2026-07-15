"""Slack integration — outbound alerts + inbound Ask AI.

Outbound (existing): Incoming Webhook → Block Kit alerts (Watchtower / Gap / Compliance).

Inbound Ask AI (new): user messages CompliSense in Slack → agent_runner answers
back in the thread. Two workable paths for Docker:

1. **Socket Mode** (recommended for local Docker — no public URL):
   paste Bot Token (xoxb-) + App-Level Token (xapp-… with connections:write).
2. **HTTP Events / Slash** (when you have a public URL or tunnel):
   POST /api/slack/events  and  POST /api/slack/commands
   with Signing Secret verification.

Pure stdlib for webhooks + signing. Socket Mode uses official `slack_sdk` when
tokens are configured (optional dependency — Ask UI still works without it).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

_SEV_EMOJI = {"amendment": "🔴", "new_direction": "🟠", "enforcement": "🟡",
              "draft": "🔵", "info": "⚪"}

_ROOT = Path(__file__).parent.parent
_CONFIG = _ROOT / "data" / "slack_config.json"
_HERE = str(_ROOT)

_socket_started = False
_socket_lock = threading.Lock()


def _load_cfg() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_cfg(data: dict) -> None:
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    cur = _load_cfg()
    cur.update({k: v for k, v in data.items() if v is not None})
    # Allow explicit clears
    for k, v in data.items():
        if v == "":
            cur.pop(k, None)
    _CONFIG.write_text(json.dumps(cur, indent=2), encoding="utf-8")


def _valid_webhook(url: str) -> bool:
    return isinstance(url, str) and url.startswith("https://hooks.slack.com/")


def get_webhook() -> str | None:
    u = _load_cfg().get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL")
    return u or None


def get_bot_token() -> str | None:
    return _load_cfg().get("bot_token") or os.getenv("SLACK_BOT_TOKEN") or None


def get_app_token() -> str | None:
    return _load_cfg().get("app_token") or os.getenv("SLACK_APP_TOKEN") or None


def get_signing_secret() -> str | None:
    return _load_cfg().get("signing_secret") or os.getenv("SLACK_SIGNING_SECRET") or None


def save_webhook(url: str) -> dict:
    if not _valid_webhook(url):
        return {"ok": False, "error": "That is not a Slack incoming-webhook URL "
                "(it must start with https://hooks.slack.com/services/…)."}
    _save_cfg({"webhook_url": url})
    return {"ok": True}


def save_ask_tokens(
    bot_token: str = "",
    app_token: str = "",
    signing_secret: str = "",
) -> dict:
    """Persist Bot / App / Signing tokens for inbound Ask AI (clicks, not .env)."""
    bot_token = (bot_token or "").strip()
    app_token = (app_token or "").strip()
    signing_secret = (signing_secret or "").strip()
    if bot_token and not bot_token.startswith("xoxb-"):
        return {"ok": False, "error": "Bot Token must start with xoxb-."}
    if app_token and not app_token.startswith("xapp-"):
        return {"ok": False, "error": "App-Level Token must start with xapp-."}
    patch = {}
    if bot_token:
        patch["bot_token"] = bot_token
    if app_token:
        patch["app_token"] = app_token
    if signing_secret:
        patch["signing_secret"] = signing_secret
    if not patch:
        return {"ok": False, "error": "Paste at least a Bot Token (xoxb-)."}
    _save_cfg(patch)
    # Kick Socket Mode if we now have both tokens
    try_start_socket_mode()
    return {"ok": True, **status()}


def clear_webhook() -> dict:
    cfg = _load_cfg()
    cfg.pop("webhook_url", None)
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"ok": True}


def clear_ask_tokens() -> dict:
    cfg = _load_cfg()
    for k in ("bot_token", "app_token", "signing_secret"):
        cfg.pop(k, None)
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"ok": True, **status()}


def status() -> dict:
    u = get_webhook()
    masked = (u[:34] + "…") if u and len(u) > 34 else u
    bot = get_bot_token()
    app = get_app_token()
    return {
        "connected": bool(u),
        "target": masked,
        "ask_enabled": bool(bot),
        "socket_mode": bool(bot and app),
        "socket_running": _socket_started,
        "has_signing_secret": bool(get_signing_secret()),
        "bot_token_set": bool(bot),
        "app_token_set": bool(app),
    }


# ── Block Kit builders (outbound) ─────────────────────────────────────────── #

def watchtower_blocks(alert: dict) -> list:
    sev = (alert.get("severity") or "info").lower()
    emoji = _SEV_EMOJI.get(sev, "⚪")
    title = alert.get("title", "RBI update")
    link = alert.get("link", "")
    profiles = ", ".join(alert.get("profiles", []) or []) or "general"
    matched = ", ".join(alert.get("matched", []) or [])
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} Watchtower — {sev.replace('_', ' ')}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*"}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"Affects: *{profiles}*" + (f"  ·  matched: {matched}" if matched else "")}]},
    ]
    if link:
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Open the circular ↗"},
             "url": link, "style": "primary"}]})
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "CompliSense · informational only — verify against the primary source."}]})
    return blocks


def gap_blocks(gap: dict) -> list:
    wg = gap.get("wedge", {})
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"◎ Gap Finder — {gap.get('competitor', '')}"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Top opening:* {wg.get('theme', '')}\n{wg.get('sub', '')}"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Segment*\n{wg.get('market', '—')}"},
            {"type": "mrkdwn", "text": f"*Fix cost*\n{wg.get('fixcost', '—')}"},
            {"type": "mrkdwn", "text": f"*Copy-back risk*\n{wg.get('copyback', '—')}"},
            {"type": "mrkdwn", "text": f"*Positioning*\n{wg.get('line', '—')}"}]},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": "CompliSense Gap Finder · grounded in cited public reviews."}]},
    ]


_COMPLY_SUMMARY = {
    "boat": ("Consumer electronics", ["BIS CRS (safety)", "WPC ETA (wireless)", "CPCB e-waste EPR", "Legal Metrology"], "BIS CRS registration before sale"),
    "himalaya": ("Beauty & personal care", ["CDSCO Cosmetics Rules 2020", "BIS standards", "Legal Metrology", "D&C Act (claims)"], "CDSCO registration/licence before sale"),
    "kreditbee": ("Consumer fintech / lending", ["RBI SBR 2023", "RBI Digital Lending", "RBI KYC MD", "DPDP 2023"], "NBFC registration + NOF glide path"),
    "yogabar": ("Packaged food / FMCG", ["FSSAI licence", "FSSAI labelling 2020", "Legal Metrology", "FSSAI claims"], "FSSAI licence before sale"),
    "zoho": ("B2B SaaS", ["DPDP Act 2023", "CERT-In Directions 2022", "IT Act / SPDI", "GST"], "CERT-In 6-hour incident reporting"),
    "other": ("General business", ["GST", "Shops & Establishments", "DPDP 2023", "Legal Metrology"], "GST registration + your sector licence"),
}


def compliance_blocks(sector_key: str) -> list:
    label, regs, top = _COMPLY_SUMMARY.get(sector_key or "other", _COMPLY_SUMMARY["other"])
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"⬡ Compliance — {label}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Top blocker before you sell:* {top}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Regulators that apply:*\n• " + "\n• ".join(regs)}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": "CompliSense · informational only — verify against each regulator's primary source."}]},
    ]


def post(blocks: list, webhook_url: str | None = None, text: str = "CompliSense alert") -> dict:
    url = webhook_url or get_webhook()
    if not url:
        return {"ok": False, "status": None, "error": "Slack is not connected — open Slack in the app and paste your Incoming Webhook URL."}
    payload = json.dumps({"text": text, "blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {"ok": r.status == 200, "status": r.status, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "error": str(e)[:200]}


def preview(kind: str = "watchtower", sector: str = "") -> dict:
    if kind == "compliance":
        return {"kind": "compliance", "posted": False, "blocks": compliance_blocks(sector),
                "note": "Preview only. Connect Slack in the app (paste an Incoming Webhook URL) to send."}
    if kind == "gap":
        sample = {"competitor": "boAt Airdopes 141", "wedge": {
            "theme": "Call quality", "sub": "Keep the bass and 40h battery buyers love; win on the mic.",
            "market": "Large & vocal (est.)", "fixcost": "+₹ modest BOM (est.)",
            "copyback": "Medium", "line": "The bass and 40-hour battery you love — with calls you're not embarrassed to take."}}
        return {"kind": "gap", "posted": False, "blocks": gap_blocks(sample),
                "note": "Preview only. Connect Slack in the app (paste an Incoming Webhook URL) to send."}

    alert = None
    try:
        from .watchtower import check
        alerts = (check(profile="all", limit=5) or {}).get("alerts") or []
        alert = alerts[0] if alerts else None
    except Exception:  # noqa: BLE001
        alert = None
    if not alert:
        alert = {"title": "Payments Banks Responsible Business Conduct (Second Amendment) Directions, 2026",
                 "severity": "amendment", "profiles": ["payments"], "matched": ["amendment"],
                 "link": "https://www.rbi.org.in/"}
    return {"kind": "watchtower", "posted": False, "blocks": watchtower_blocks(alert),
            "note": "Preview only. Connect Slack in the app (paste an Incoming Webhook URL) to send."}


def send(kind: str = "watchtower", sector: str = "", blocks: list | None = None) -> dict:
    wh = get_webhook()
    if not wh:
        return {"ok": False, "error": "Slack is not connected."}
    if blocks is None:
        blocks = preview(kind, sector).get("blocks", [])
    return {**post(blocks, wh, text=f"CompliSense · {kind}"), "kind": kind}


# ── Inbound Ask AI ────────────────────────────────────────────────────────── #

def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    secret = get_signing_secret()
    if not secret:
        # No secret configured — allow only when explicitly opted in for local dev
        return os.getenv("SLACK_SKIP_VERIFY", "").lower() in ("1", "true", "yes")
    if abs(time.time() - int(timestamp or "0")) > 60 * 5:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    digest = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature or "")


def _api(method: str, payload: dict) -> dict:
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "Bot Token not configured"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": str(e)[:200]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


def post_message(channel: str, text: str, thread_ts: str | None = None) -> dict:
    payload = {"channel": channel, "text": text[:3900]}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return _api("chat.postMessage", payload)


def run_agent_query(question: str, timeout_s: int = 600) -> dict:
    """Spawn agent_runner.py (same isolation as /api/stream) and collect the answer."""
    env = dict(
        os.environ,
        KMP_DUPLICATE_LIB_OK="TRUE",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        CS_JSON="1",
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-u", os.path.join(_HERE, "agent_runner.py"), "--json", question],
            cwd=_HERE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "response": "Timed out waiting for the agents. Try a narrower question.", "sources": []}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "response": f"Could not start agents: {e}"[:300], "sources": []}

    done = None
    last_err = None
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("error"):
            last_err = obj["error"]
        if obj.get("done"):
            done = obj
    if done:
        return {
            "ok": True,
            "response": done.get("response") or last_err or "No answer returned.",
            "sources": done.get("sources") or [],
        }
    err = last_err or (proc.stderr or "")[-400:] or f"exit {proc.returncode}"
    return {"ok": False, "response": f"Agent run failed: {err}"[:500], "sources": []}


def _format_answer(result: dict) -> str:
    text = (result.get("response") or "").strip()
    if not text:
        text = "No answer returned."
    # Slack mrkdwn: keep it readable; truncate hard
    if len(text) > 3500:
        text = text[:3490] + "…"
    srcs = result.get("sources") or []
    if srcs:
        lines = []
        seen = set()
        for s in srcs[:6]:
            title = (s.get("title") or s.get("ref") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            ref = s.get("ref") or ""
            if ref.startswith("http"):
                lines.append(f"• <{ref}|{title}>")
            else:
                lines.append(f"• {title}" + (f" — {ref}" if ref and ref != title else ""))
        if lines:
            text += "\n\n*Sources*\n" + "\n".join(lines)
    text += "\n\n_CompliSense · informational only — verify against primary sources._"
    return text


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[^>]+>\s*", "", text or "").strip()


def handle_ask_async(channel: str, question: str, thread_ts: str | None = None) -> None:
    """Background: run agents and reply in-thread."""

    def _job():
        q = _strip_mention(question)
        if not q:
            post_message(channel, "Ask me a business / market / compliance question.", thread_ts)
            return
        post_message(channel, f"_Working on:_ {q[:200]}\n(~30–90s while specialists run…)", thread_ts)
        result = run_agent_query(q)
        post_message(channel, _format_answer(result), thread_ts)

    threading.Thread(target=_job, daemon=True).start()


def handle_slash_command(form: dict) -> dict:
    """Immediate Slack slash-command response + async agent reply."""
    text = (form.get("text") or "").strip()
    channel = form.get("channel_id") or ""
    # Prefer responding in a new thread rooted at the slash ack — use response_url later if needed
    if not text:
        return {
            "response_type": "ephemeral",
            "text": "Usage: `/complisense <your question>` — e.g. `/complisense What is my top competitor weakness?`",
        }
    # Kick async via bot token if available; also return an in_channel ack
    if get_bot_token() and channel:
        handle_ask_async(channel, text, thread_ts=None)
        return {
            "response_type": "in_channel",
            "text": f"CompliSense is analysing: *{text[:180]}* — answer incoming…",
        }
    # Fallback: run sync is too slow for Slack's 3s window — refuse honestly
    return {
        "response_type": "ephemeral",
        "text": "Inbound Ask needs a Bot Token. Open CompliSense → Slack → enable Ask AI (paste xoxb- token).",
    }


def handle_event_callback(payload: dict) -> dict:
    """Handle Events API callbacks (url_verification already handled by server)."""
    event = payload.get("event") or {}
    etype = event.get("type")
    # Ignore bot echoes / message_changed
    if event.get("bot_id") or event.get("subtype"):
        return {"ok": True}
    if etype == "app_mention":
        channel = event.get("channel")
        text = event.get("text") or ""
        ts = event.get("ts")
        if channel and text:
            handle_ask_async(channel, text, thread_ts=ts)
    elif etype == "message" and event.get("channel_type") == "im":
        # DM to the bot
        channel = event.get("channel")
        text = event.get("text") or ""
        ts = event.get("ts")
        if channel and text:
            handle_ask_async(channel, text, thread_ts=ts)
    return {"ok": True}


def try_start_socket_mode() -> dict:
    """Start Slack Socket Mode in a daemon thread (no public URL needed)."""
    global _socket_started
    bot = get_bot_token()
    app = get_app_token()
    if not (bot and app):
        return {"ok": False, "error": "Need both Bot Token (xoxb-) and App Token (xapp-)."}
    with _socket_lock:
        if _socket_started:
            return {"ok": True, "already": True}
        try:
            from slack_sdk.socket_mode import SocketModeClient
            from slack_sdk.socket_mode.request import SocketModeRequest
            from slack_sdk.socket_mode.response import SocketModeResponse
            from slack_sdk.web import WebClient
        except ImportError:
            return {
                "ok": False,
                "error": "slack-sdk not installed. Rebuild the Docker image or pip install slack-sdk.",
            }

        client = SocketModeClient(app_token=app, web_client=WebClient(token=bot))

        def _process(cli: SocketModeClient, req: SocketModeRequest):
            try:
                cli.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
                if req.type == "events_api":
                    handle_event_callback(req.payload)
                elif req.type == "slash_commands":
                    form = req.payload or {}
                    # Socket Mode slash: reply via response_url or chat.postMessage
                    text = (form.get("text") or "").strip()
                    channel = form.get("channel_id") or ""
                    if channel and text:
                        handle_ask_async(channel, text)
            except Exception:  # noqa: BLE001
                pass

        client.socket_mode_request_listeners.append(_process)

        def _run():
            try:
                client.connect()
            except Exception:  # noqa: BLE001
                global _socket_started
                _socket_started = False

        threading.Thread(target=_run, daemon=True, name="slack-socket-mode").start()
        _socket_started = True
        return {"ok": True, "socket_mode": True}
