"""One-off live SSE audit helper. Not for production."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request


def run_stream(q: str, label: str, timeout: float = 300.0) -> list[dict]:
    print("=" * 60, flush=True)
    print(f"TEST: {label}", flush=True)
    print(f"Q: {q}", flush=True)
    print("=" * 60, flush=True)
    url = "http://127.0.0.1:8000/api/stream?q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    events: list[dict] = []
    start = time.time()
    pings = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            buf = ""
            while True:
                chunk = r.read(512)
                if not chunk:
                    print("(EOF from server)", flush=True)
                    break
                buf += chunk.decode("utf-8", "replace")
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    lines = block.splitlines()
                    # comment/keepalive
                    if any(ln.startswith(":") for ln in lines) and not any(
                        ln.startswith("data:") for ln in lines
                    ):
                        pings += 1
                        if pings <= 3 or pings % 6 == 0:
                            print(f"  keepalive #{pings} t={time.time()-start:.0f}s", flush=True)
                        continue
                    data_lines = [ln[5:].lstrip() for ln in lines if ln.startswith("data:")]
                    if not data_lines:
                        continue
                    raw = "\n".join(data_lines)
                    try:
                        evt = json.loads(raw)
                    except Exception:
                        print(f"  RAW: {raw[:240]}", flush=True)
                        continue
                    events.append(evt)
                    summary = {
                        k: evt[k]
                        for k in (
                            "agent",
                            "node",
                            "skipped",
                            "analysis_lens",
                            "route_flags",
                            "error",
                            "done",
                            "snippet",
                        )
                        if k in evt
                    }
                    if isinstance(summary.get("snippet"), str) and len(summary["snippet"]) > 140:
                        summary["snippet"] = summary["snippet"][:140] + "..."
                    print(f"  EVT[{len(events):02d}] {json.dumps(summary, ensure_ascii=False)[:500]}", flush=True)
                    if evt.get("done") or evt.get("error"):
                        resp = evt.get("response") or ""
                        if resp:
                            print(
                                f"  FINAL len={len(resp)} preview={resp[:280]!r}",
                                flush=True,
                            )
                        # keep reading briefly if error precedes done
                        if evt.get("done"):
                            return events
                if time.time() - start > timeout:
                    print("TIMEOUT", flush=True)
                    break
    except Exception as e:
        print(f"STREAM_ERR: {type(e).__name__}: {e}", flush=True)
    print(f"elapsed={time.time()-start:.1f}s events={len(events)} keepalives={pings}", flush=True)
    for e in events:
        if e.get("route_flags"):
            print("ROUTE_FLAGS:", json.dumps(e["route_flags"]), flush=True)
        if e.get("analysis_lens"):
            print("LENS:", e["analysis_lens"], flush=True)
        if e.get("agent") and "skipped" in e:
            print(f"  mesh: agent={e.get('agent')} node={e.get('node')} skipped={e.get('skipped')}", flush=True)
    return events


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "glow"
    if which == "glow":
        run_stream(
            "How does GlowLeaf Organic Skincare compare to The Ordinary and Minimalist "
            "on pricing, reviews, and competitive positioning? Focus on customer "
            "sentiment and market gaps — no RBI needed.",
            "GlowLeaf competitor (RBI should skip)",
            timeout=360,
        )
    elif which == "rbi":
        run_stream(
            "I am setting up a digital lending NBFC in India. Do I need RBI approval "
            "for a 28% foreign investor stake, and which KYC / digital-lending "
            "circular obligations apply?",
            "Regulatory (RBI should activate)",
            timeout=360,
        )
    else:
        run_stream(which, "custom", timeout=360)
