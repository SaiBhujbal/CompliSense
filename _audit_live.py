"""One-shot live audit runner: hits agent_runner via docker-friendly file I/O."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUT_DIR = os.environ.get("AUDIT_OUT", "/tmp")


def summarize(label: str, events: list, answer: str | None, errors: list, elapsed: float, q: str):
    orch = next((e for e in events if e.get("node") == "orchestrator"), None)
    skips = [e.get("node") for e in events if e.get("skipped")]
    nodes = [e.get("node") for e in events if e.get("node")]
    print(f"--- {label} summary: events={len(events)} elapsed={elapsed:.1f}s done={bool(answer)} ---")
    print("nodes:", nodes)
    print("skipped:", skips)
    if orch:
        print("orch lens=", orch.get("analysis_lens"), "flags=", orch.get("route_flags"))
    if answer:
        print("ANSWER_HEAD:", answer[:500].replace("\n", " | "))
        low = answer.lower()
        markers = [
            m
            for m in (
                "[s",
                "http",
                "source",
                "[no public",
                "[inference",
                "unavailable",
                "will not guess",
                "knowledge base",
                "circular",
            )
            if m in low
        ]
        print("grounding_markers:", markers)
    else:
        print("NO_ANSWER")
    path = os.path.join(OUT_DIR, f"audit_{label.lower()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "label": label,
                "q": q,
                "elapsed": elapsed,
                "events": events,
                "answer": answer,
                "errors": errors,
                "nodes": nodes,
                "skipped": skips,
                "orch": orch,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("wrote", path)
    return bool(answer)


def run_sse(label: str, q: str, timeout: int = 420) -> bool:
    print("=" * 72)
    print(f"[{label}] {q[:140]}")
    print("=" * 72)
    url = "http://127.0.0.1:8000/api/stream?q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    events: list = []
    answer = None
    errors: list = []
    t0 = time.time()
    buf = b""
    finished = False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            while not finished:
                chunk = r.read(256)
                if not chunk:
                    break
                buf += chunk
                while b"\n\n" in buf:
                    block, buf = buf.split(b"\n\n", 1)
                    for line in block.decode("utf-8", "replace").splitlines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        try:
                            d = json.loads(raw)
                        except Exception:
                            continue
                        events.append(d)
                        sys.stdout.write(
                            f"  EVT node={d.get('node')} skipped={d.get('skipped')} "
                            f"done={d.get('done')} err={bool(d.get('error'))}\n"
                        )
                        sys.stdout.flush()
                        if d.get("error") and not d.get("done"):
                            errors.append(str(d.get("error"))[:300])
                        if d.get("done"):
                            answer = d.get("response") or ""
                            finished = True
    except Exception as e:
        print(f"STREAM_ERR {type(e).__name__}: {e}")
        sys.stdout.flush()
    return summarize(label, events, answer, errors, time.time() - t0, q)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    ok_a = ok_b = None
    if mode in ("A", "both"):
        ok_a = run_sse(
            "A",
            "I run GlowLeaf, a clean-beauty brand. Through the customer lens: "
            "which competitor weakness vs Himalaya is the most defensible opening for me, and why?",
        )
        time.sleep(5)
    if mode in ("B", "both"):
        ok_b = run_sse(
            "B",
            "Do I need RBI approval if a foreign investor takes a 28% stake in my NBFC? "
            "Cite the relevant circular or regulation.",
        )
    print("AUDIT_COMPLETE", "A=", ok_a, "B=", ok_b)
    sys.stdout.flush()
