"""Generic, config-driven review collector — independent implementation.

Built from standard, public browser-automation technique (Playwright: load →
incremental scroll → extract → signature-dedup → polite backoff). It is NOT a
port of any existing scraper: the design is purpose-built to emit the exact
`rating,text,date,source,url` CSV that src/reviews_ingest.CSVAdapter consumes,
and it is SITE-AGNOSTIC — every CSS selector is supplied as config, nothing is
hardcoded to a particular retailer.

Fill a target's selectors by inspecting the site's CURRENT public DOM (retail
DOMs change constantly, so there is no durable selector to copy from anyone).

USAGE / RESPONSIBILITY
  - Respect each site's Terms of Service and robots.txt. This tool rate-limits
    by default; keep it that way. Use it for your OWN research data collection.
  - For a product you sell/showcase, prefer a licensed data provider or an
    official/affiliate API — durable and unambiguous. This collector is the
    research path, not the shipped-product backbone.

  Config JSON (list of targets):
  [
    {"url": "https://.../product", "source": "sitename",
     "selectors": {"block": "...", "text": "...", "rating": "...",
                   "date": "...", "author": "..."},
     "max_reviews": 200}
  ]

  Run:  python tools/review_collector.py targets.json out.csv
  Then: python src/reviews_ingest.py out.csv <sector>
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:  # keep the module importable without the optional dep
    async_playwright = None  # type: ignore

CSV_FIELDS = ("rating", "text", "date", "source", "url")


@dataclass
class Target:
    url: str
    source: str
    selectors: dict          # {block, text, rating, date, author}
    max_reviews: int = 200
    scroll_pause_s: float = 1.6
    max_idle_rounds: int = 4  # stop after N scrolls yield no new reviews


@dataclass
class _Stats:
    rows: list = field(default_factory=list)
    seen: set = field(default_factory=set)


def _rating_to_number(raw: str) -> str:
    """Pull a 1-5 rating out of whatever text the rating node holds."""
    if not raw:
        return ""
    m = re.search(r"[1-5](?:\.\d)?", raw)
    return m.group(0) if m else ""


def _signature(text: str, author: str, date: str) -> str:
    return f"{author}|{date}|{text[:80]}".lower()


async def _extract_page(page, sel: dict) -> list[dict]:
    """Run one DOM sweep; return raw review dicts. Selectors are all injected,
    so this function knows nothing about any specific site."""
    js = """(sel) => {
      const pick = (root, q) => { const e = q ? root.querySelector(q) : null; return e ? (e.innerText||'').trim() : ''; };
      return Array.from(document.querySelectorAll(sel.block)).map(b => ({
        text:   pick(b, sel.text),
        rating: pick(b, sel.rating),
        date:   pick(b, sel.date),
        author: pick(b, sel.author),
      }));
    }"""
    return await page.evaluate(js, sel)


async def collect(target: Target, headless: bool = True) -> list[dict]:
    if async_playwright is None:
        raise RuntimeError("Playwright not installed. `pip install playwright` "
                           "then `playwright install chromium`.")
    st = _Stats()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
        )
        page = await ctx.new_page()
        await page.goto(target.url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(target.scroll_pause_s)

        idle = 0
        while len(st.rows) < target.max_reviews and idle < target.max_idle_rounds:
            new = 0
            for r in await _extract_page(page, target.selectors):
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                sig = _signature(text, r.get("author", ""), r.get("date", ""))
                if sig in st.seen:
                    continue
                st.seen.add(sig)
                st.rows.append({
                    "rating": _rating_to_number(r.get("rating", "")),
                    "text": text,
                    "date": (r.get("date") or "").strip(),
                    "source": target.source,
                    "url": target.url,
                })
                new += 1
                if len(st.rows) >= target.max_reviews:
                    break

            idle = idle + 1 if new == 0 else 0
            # incremental scroll to trigger lazy-loaded reviews
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await asyncio.sleep(target.scroll_pause_s + random.uniform(0, 0.6))

        await browser.close()
    return st.rows


def write_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)


async def _run(targets: list[Target], out: str, headless: bool) -> None:
    all_rows: list[dict] = []
    for t in targets:
        print(f"[collect] {t.source}: {t.url}", file=sys.stderr)
        try:
            rows = await collect(t, headless=headless)
            print(f"[collect]   -> {len(rows)} reviews", file=sys.stderr)
            all_rows += rows
        except Exception as e:  # noqa: BLE001
            print(f"[collect]   FAILED: {e}", file=sys.stderr)
        await asyncio.sleep(random.uniform(2, 4))  # polite gap between targets
    write_csv(all_rows, out)
    print(f"[collect] wrote {len(all_rows)} rows -> {out}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Config-driven review collector -> pipeline CSV")
    ap.add_argument("config", help="JSON list of targets (see module docstring)")
    ap.add_argument("out", help="output CSV path (rating,text,date,source,url)")
    ap.add_argument("--headful", action="store_true", help="show the browser")
    args = ap.parse_args()

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    targets = [Target(url=t["url"], source=t.get("source", ""), selectors=t["selectors"],
                      max_reviews=int(t.get("max_reviews", 200))) for t in raw]
    asyncio.run(_run(targets, args.out, headless=not args.headful))


if __name__ == "__main__":
    main()
