"""
Runs ONE query through the multi-agent graph and streams per-agent updates as
human-readable markdown to stdout. Invoked as an isolated subprocess by
server.py so the heavy ML stack (torch/chromadb/sentence-transformers) never
loads inside the web server — which was causing the native OpenMP segfault
under uvicorn.

Usage:  python agent_runner.py "<question>"
        python agent_runner.py --json "<question>"
"""

import json
import os
import sys
import traceback

# Reports contain ₹, →, — etc. Force UTF-8 stdout so the Windows cp1252 console
# (and the web SSE pipe) never crash on a non-ASCII character.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

_JSON = ("--json" in sys.argv) or bool(os.getenv("CS_JSON"))


def emit(text: str = ""):
    sys.stdout.write(text.rstrip() + "\n")
    sys.stdout.flush()


def emit_json(obj: dict):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _fail(msg: str):
    if _JSON:
        emit_json({"error": msg[:400]})
        emit_json({"done": True, "response": msg[:800], "sources": []})
    else:
        emit(f"**Error:** {msg[:400]}")
    sys.exit(0)  # exit 0 so SSE still delivered the JSON error/done events


try:
    import src._bootstrap  # noqa: F401  -- init torch/ST before chromadb
except Exception as e:  # noqa: BLE001
    _fail(f"Native ML bootstrap failed: {type(e).__name__}: {e}")

from langchain_core.messages import HumanMessage  # noqa: E402

from src.graph.workflow import create_workflow  # noqa: E402

AGENTS = {
    "orchestrator": "Orchestrator", "rbi": "RBI compliance", "pestel": "PESTEL",
    "competitor": "Competitor", "trend": "Trend", "faithfulness": "Faithfulness",
    "crossexam": "Cross-examination", "swot": "SWOT", "analysis": "Synthesis",
    "responder": "Response",
}
_REPORT_KEYS = ["rbi_report", "pestel_report", "competitor_report", "trend_report",
                "swot_report", "final_analysis", "final_response"]
_SPECIALISTS = frozenset({"rbi", "pestel", "competitor", "trend"})


def _report_of(u: dict) -> str:
    for k in _REPORT_KEYS:
        if u.get(k):
            return str(u[k])
    return ""


def _is_empty_update(u) -> bool:
    return not u or (isinstance(u, dict) and not any(u.values()))


def _snippet(u: dict) -> str:
    if _is_empty_update(u):
        return "skipped — not needed for this question"
    for k in _REPORT_KEYS:
        if u.get(k):
            return str(u[k])[:220].replace("\n", " ")
    if "faithfulness_status" in u:
        return f"verdict: {u['faithfulness_status']}"
    if "route_flags" in u:
        active = [a for a, v in (u["route_flags"] or {}).items() if v]
        return "routing to: " + (", ".join(active) if active else "none (orchestrator only)")
    return "working..."


def emit_markdown_event(agent, node, body, sources=None, debate=None):
    emit(f"### {agent}")
    emit(f"- Node: {node}")
    emit("")
    emit(body)
    if debate:
        emit("")
        emit(f"**Cross-examination — {len(debate)} exchange(s):**")
        for m in debate:
            s = m.get("source_label", m.get("source", ""))
            t = m.get("target_label", m.get("target", ""))
            emit(f"  - **{s}** {m.get('kind', 'addresses')} **{t}**: {m.get('text', '')}")
    if sources:
        emit("")
        emit("- Sources:")
        for src in sources:
            emit(f"  - {src.get('title', '')} — {src.get('ref', '')}")
    emit("")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    q = args[0] if args else sys.stdin.readline().strip()
    if not q:
        _fail("No question provided.")

    try:
        graph = create_workflow()
    except Exception as e:  # noqa: BLE001
        _fail(f"Could not start the agent graph: {type(e).__name__}: {e}")

    state = {"user_query": q, "messages": [HumanMessage(content=q)]}
    cfg = {"configurable": {"thread_id": f"run-{os.getpid()}"}}
    final, sources = {}, {}
    if not _JSON:
        emit("# CompliSense multi-agent run")
        emit(f"- Question: {q}")
        emit("")
    try:
        for chunk in graph.stream(state, cfg, stream_mode="updates"):
            for node, upd in chunk.items():
                if node == "dispatch":
                    continue
                node_srcs = []
                if upd and isinstance(upd.get("sources"), dict):
                    sources.update(upd["sources"])
                    node_srcs = [s for lst in upd["sources"].values() for s in (lst or [])]
                final.update(upd or {})
                debate = (upd or {}).get("cross_messages") or []
                srcs = [{"id": s.get("id", ""), "title": s.get("title", ""),
                         "ref": s.get("ref", "")} for s in node_srcs[:6]]
                if _JSON:
                    skipped = node in _SPECIALISTS and _is_empty_update(upd)
                    evt = {
                        "agent": AGENTS.get(node, node),
                        "node": node,
                        "snippet": _snippet(upd),
                        "skipped": skipped,
                    }
                    if isinstance(upd, dict) and upd.get("route_flags") is not None:
                        evt["route_flags"] = upd["route_flags"]
                    if isinstance(upd, dict) and upd.get("analysis_lens"):
                        evt["analysis_lens"] = upd["analysis_lens"]
                    if srcs:
                        evt["sources"] = srcs
                    if node == "crossexam":
                        evt["debate"] = debate
                        evt["snippet"] = (f"{len(debate)} cross-agent exchange(s)"
                                          if debate else "no contested claims")
                        evt["skipped"] = False
                    emit_json(evt)
                else:
                    report = _report_of(upd)
                    if node == "crossexam":
                        body = (f"{len(debate)} cross-agent exchange(s)."
                                if debate else "No contested claims.")
                    elif report:
                        body = report
                    elif "faithfulness_status" in (upd or {}):
                        body = f"verdict: {upd['faithfulness_status']}"
                    elif "route_flags" in (upd or {}):
                        body = ("Routing to: "
                                + ", ".join(a for a, v in (upd["route_flags"] or {}).items() if v))
                    else:
                        body = "working..."
                    emit_markdown_event(AGENTS.get(node, node), node, body,
                                        sources=srcs, debate=debate if node == "crossexam" else None)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        if _JSON:
            emit_json({"error": err[:400]})
        else:
            emit(f"**Error:** {err[:400]}")
            traceback.print_exc(file=sys.stderr)

    flat = [s for lst in sources.values() for s in (lst or [])]
    amb = final.get("is_ambiguous") or not final.get("in_scope", True)
    ans = final.get("clarification_question") if amb else final.get("final_response", "")
    if not ans:
        ans = (
            "I couldn't complete a full multi-agent answer for this question. "
            "Try again, or narrow the question (competitor / regulatory / strategy)."
        )
    if _JSON:
        emit_json({"done": True, "response": ans or "", "sources": flat})
    else:
        emit("---")
        emit("## Final Response")
        emit(ans or "")
        if flat:
            emit("")
            emit("### Final Sources")
            for src in flat:
                emit(f"- {src.get('title', '')} — {src.get('ref', '')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        _fail(f"Fatal runner error: {type(e).__name__}: {e}")
