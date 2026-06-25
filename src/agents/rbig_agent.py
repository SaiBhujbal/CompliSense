"""RBI Compliance agent — CAG-first, retrieval fallback, citation-grounded.

If the corpus fits the model window (and CAG is enabled), preload it and answer
without retrieval (cheap under prompt caching). Otherwise retrieve the strongest
grounded chunks; if nothing clears the threshold, REFUSE rather than hallucinate.
Every claim must cite a provided [S#] source.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm
from ..rag.cag import corpus_fits_window, preloaded_corpus
from ..rag.retriever import retrieve

SYSTEM_PROMPT = """You are an expert on RBI (Reserve Bank of India) regulations for FinTech, NBFCs, and digital lending.

Answer ONLY from the provided context. Rules:
- Every substantive claim MUST cite the source it came from using its [S#] tag.
- If the context does not contain the answer, say so explicitly — do NOT use outside knowledge or guess.
- Quote exact obligations (e.g. "shall", thresholds, dates, section numbers) verbatim where they matter.
- Be precise and structured; this guidance must be verifiable against the cited sources.
- If a source is marked DRAFT / not-in-force, say so explicitly; do not present it as binding law.
- For LICENSING / REGISTRATION questions ("which licence/approval do I need"), structure the answer:
  (a) applicable licence/registration, (b) minimum Net Owned Fund / net-worth threshold,
  (c) key registration steps, (d) core ongoing obligations (KYC/AML, reporting) — each line [S#]-cited."""

REFUSAL = (
    "I could not find a relevant RBI source in the knowledge base for this "
    "question, so I won't guess. Please rephrase, or consult the RBI directly."
)


def rbig_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("rbi"):
        return {}

    llm = get_llm("reasoning")
    intent = state.get("analysis_intent") or state["user_query"]

    if config.CAG_ENABLED and corpus_fits_window():
        context, src_tuple = preloaded_corpus()
        sources = [dict(t) for t in src_tuple]
    else:
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

    human = (
        f"User's question / intent: {intent}\n\n"
        f"Context from RBI documents:\n---\n{context}\n---\n\n"
        "Answer the question, citing [S#] tags. If unanswerable from the context, say so."
    )
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)])
    return {"rbi_report": resp.content, "sources": {"rbi": sources}}
