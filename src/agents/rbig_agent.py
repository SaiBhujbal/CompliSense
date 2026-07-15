"""RBI Compliance agent — CAG-first, retrieval fallback, citation-grounded.

If the corpus fits the model window (and CAG is enabled), preload it and answer
without retrieval (cheap under prompt caching). Otherwise retrieve the strongest
grounded chunks; if nothing clears the threshold, REFUSE rather than hallucinate.
Every claim must cite a provided [S#] source.

Retrieval / embedding / sentence-transformers failures never crash the graph —
they return an honest refusal so Ask AI keeps working on other lenses.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm
from ..llm.structured import safe_invoke
from ..rag.embeddings import RagUnavailable

SYSTEM_PROMPT = """You are an expert on RBI (Reserve Bank of India) and Indian financial regulation as it applies to BUSINESSES IN ANY SECTOR — not only FinTech. Your job: surface the financial-regulatory points that actually TOUCH the user's business, mapped to what they do. Common touch-points for non-finance businesses:
- Collecting online payments → Payment Aggregator / gateway rules, settlement timelines (cash-flow impact), merchant KYC.
- Offering EMI / BNPL / credit at checkout → digital-lending, co-lending and default-guarantee (DLG) rules.
- Borrowing working capital / inventory finance → NBFC & bank lending norms, MSME / priority-sector credit (Mudra, CGTMSE).
- Cross-border sales / payments → FEMA basics.

Answer ONLY from the provided context. Rules:
- Every substantive claim MUST cite its source with the [S#] tag.
- If the context does not contain a rule relevant to THIS business, say so explicitly — do NOT use outside knowledge or guess.
- Quote exact obligations (thresholds, dates, "shall", settlement windows) verbatim where they matter.
- Map the rules to the user's actual activity; do NOT dump unrelated regulation. If the business clearly touches none of the above, say the regulatory load is light and name what little applies."""

REFUSAL = (
    "I could not find a relevant RBI source in the knowledge base for this "
    "question, so I won't guess. Please rephrase, or consult the RBI directly."
)


def _rag_refusal(detail: str) -> dict:
    msg = (
        "RBI / compliance retrieval is unavailable for this run, so I will not "
        f"guess at regulation. ({detail}) "
        "Other specialist agents (competitor, PESTEL, trend) can still answer. "
        "To restore the RBI corpus: ensure `sentence-transformers` + `torch` are "
        "installed, then run `docker compose --profile ingest run --rm ingest` "
        "(or `python ingest_data.py`)."
    )
    return {"rbi_report": msg, "sources": {"rbi": []}}


def rbig_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("rbi"):
        return {}

    try:
        return _rbig_run(state)
    except RagUnavailable as e:
        return _rag_refusal(str(e)[:240])
    except Exception as e:  # noqa: BLE001 — never take down Ask AI
        return _rag_refusal(f"{type(e).__name__}: {e}"[:240])


def _rbig_run(state: dict) -> dict:
    llm = get_llm("reasoning")
    intent = state.get("analysis_intent") or state["user_query"]

    if config.CAG_ENABLED:
        try:
            from ..rag.cag import corpus_fits_window, preloaded_corpus

            if corpus_fits_window():
                context, src_tuple = preloaded_corpus()
                sources = [dict(t) for t in src_tuple]
                return _answer(llm, intent, context, sources)
        except Exception:  # noqa: BLE001 — fall through to retrieval
            pass

    from ..rag.retriever import retrieve

    chunks = retrieve(intent)
    if not chunks:
        return {"rbi_report": REFUSAL, "sources": {"rbi": []}}

    def _body(text: str) -> str:
        if config.NRPC_ENABLED:
            from ..rag.compression import compress_context

            return compress_context(text, keep_ratio=config.NRPC_KEEP_RATIO)[0]
        return text

    context = "\n\n".join(
        f"[S{i}] ({c.source} p.{c.page})\n{_body(c.document.page_content)}"
        for i, c in enumerate(chunks, start=1)
    )
    sources = [
        {"id": f"S{i}", "title": c.source, "ref": f"{c.source} p.{c.page}"}
        for i, c in enumerate(chunks, start=1)
    ]
    return _answer(llm, intent, context, sources)


def _answer(llm, intent: str, context: str, sources: list) -> dict:
    human = (
        f"User's question / intent: {intent}\n\n"
        f"Context from RBI documents:\n---\n{context}\n---\n\n"
        "Answer the question, citing [S#] tags. If unanswerable from the context, say so."
    )
    content = safe_invoke(
        llm, [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)],
        fallback="RBI financial-regulation read was rate-limited this run; rely on the other reports for now.",
    )
    return {"rbi_report": content, "sources": {"rbi": sources}}
