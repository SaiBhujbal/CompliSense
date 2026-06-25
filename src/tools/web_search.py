"""
URL-grounded web search wrapper (Tavily).

Unlike the original agents, this preserves the source URL/title of every result
and returns numbered ``[S#]`` citation tags, so downstream agents can cite the
exact page a claim came from and the faithfulness gate can verify it.
"""

import os

from .. import config


def tavily_search(
    query: str,
    *,
    max_results: int | None = None,
    include_domains: list[str] | None = None,
    start_index: int = 1,
):
    """Run a Tavily search and return (context_with_citation_tags, sources).

    ``sources`` is a list of {"id": "S<n>", "title": str, "ref": url}.
    Raises on missing key; callers should handle/return a graceful message.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not configured.")

    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    result = client.search(
        query=query,
        search_depth=config.TAVILY_SEARCH_DEPTH,
        max_results=max_results or config.TAVILY_MAX_RESULTS,
        include_domains=include_domains,
    )

    blocks, sources = [], []
    for offset, item in enumerate(result.get("results", [])):
        sid = f"S{start_index + offset}"
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")
        sources.append({"id": sid, "title": title, "ref": url})
        blocks.append(f"[{sid}] {title} — {url}\n{content}")

    return "\n\n".join(blocks), sources
