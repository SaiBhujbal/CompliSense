"""
Hardened RBI document ingestion.

Fixes the silent-corpus-corruption failure mode: RBI ``.aspx`` URLs return HTML,
which the old pipeline saved as ``.pdf`` and then failed to parse inside a bare
``except`` — silently shrinking the corpus. Here we:

  * verify each download is actually a PDF (Content-Type + ``%PDF`` magic bytes),
  * fall back to the ``alt_pdf`` URL when the primary is HTML,
  * stamp source metadata onto every chunk (so citations are real, not invented),
  * record a manifest of what succeeded/failed,
  * assert a minimum chunk count so a broken corpus fails loudly.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import requests
import yaml
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .. import config
from .embeddings import get_embeddings

DATA_DIR = Path(config.RBI_DATA_PATH)
CHROMA_DB_PATH = Path(config.CHROMA_DB_PATH)
DATA_SOURCES_FILE = Path(config.DATA_SOURCES_FILE)

_PDF_MAGIC = b"%PDF-"


@dataclass
class IngestManifest:
    downloaded: list[str] = field(default_factory=list)
    skipped_not_pdf: list[str] = field(default_factory=list)
    download_failed: list[str] = field(default_factory=list)
    parse_failed: list[str] = field(default_factory=list)
    chunk_count: int = 0

    def summary(self) -> str:
        return (
            f"  downloaded (valid PDF): {len(self.downloaded)}\n"
            f"  skipped (not a PDF):    {len(self.skipped_not_pdf)} {self.skipped_not_pdf}\n"
            f"  download failed:        {len(self.download_failed)} {self.download_failed}\n"
            f"  parse failed:           {len(self.parse_failed)} {self.parse_failed}\n"
            f"  total chunks:           {self.chunk_count}"
        )


def _looks_like_pdf(content_type: str, head: bytes) -> bool:
    if "application/pdf" in (content_type or "").lower():
        return True
    return head[:5] == _PDF_MAGIC


def _try_download(url: str, dest: Path) -> bool:
    """Download ``url`` to ``dest`` only if it is genuinely a PDF."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    first_chunk = next(resp.iter_content(chunk_size=8192), b"")
    if not _looks_like_pdf(content_type, first_chunk):
        return False
    with open(dest, "wb") as f:
        f.write(first_chunk)
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


def download_documents(manifest: IngestManifest) -> None:
    # Never wipe the whole data dir — it also holds chroma_db, slack_config,
    # caches, and briefs when CHROMA_DB_PATH lives under RBI_DATA_PATH (Docker).
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for stale in DATA_DIR.glob("*.pdf"):
        try:
            stale.unlink()
        except OSError:
            pass

    with open(DATA_SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = yaml.safe_load(f) or {}

    for doc in sources.get("documents", []):
        name = doc.get("name", "<unnamed>")
        dest = DATA_DIR / doc["file_name"]
        urls = [u for u in (doc.get("url"), doc.get("alt_pdf")) if u]
        for url in urls:
            try:
                if _try_download(url, dest):
                    manifest.downloaded.append(doc["file_name"])
                    print(f"OK  {name} <- {url}")
                    break
                print(f"NOT-PDF  {name} <- {url} (trying fallback if any)")
            except requests.RequestException as e:
                print(f"FAIL {name} <- {url}: {e}")
        else:
            # No URL yielded a valid PDF.
            if urls:
                manifest.skipped_not_pdf.append(name)
            else:
                manifest.download_failed.append(name)


def build_vector_store(manifest: IngestManifest) -> None:
    all_docs = []
    for pdf_file in sorted(DATA_DIR.glob("*.pdf")):
        try:
            loaded = PyPDFLoader(str(pdf_file)).load()
            # Stamp a clean source name so retrieval can cite it.
            for d in loaded:
                d.metadata["source"] = pdf_file.name
            all_docs.extend(loaded)
        except Exception as e:  # noqa: BLE001 - record, don't swallow
            manifest.parse_failed.append(pdf_file.name)
            print(f"PARSE-FAIL {pdf_file.name}: {e}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(all_docs)
    manifest.chunk_count = len(chunks)

    if CHROMA_DB_PATH.exists():
        shutil.rmtree(CHROMA_DB_PATH)
    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)

    Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        persist_directory=str(CHROMA_DB_PATH),
        collection_name=config.CHROMA_COLLECTION,
    )


def ingest() -> IngestManifest:
    manifest = IngestManifest()
    download_documents(manifest)
    build_vector_store(manifest)

    print("\n=== Ingestion manifest ===")
    print(manifest.summary())

    if manifest.chunk_count < config.MIN_EXPECTED_CHUNKS:
        raise RuntimeError(
            f"Ingestion produced only {manifest.chunk_count} chunks, below the "
            f"MIN_EXPECTED_CHUNKS={config.MIN_EXPECTED_CHUNKS} floor. The corpus is "
            "broken or incomplete — refusing to ship a knowledge base that would "
            "force the model to hallucinate. Check the manifest above."
        )
    return manifest


if __name__ == "__main__":
    ingest()
    print("\nData ingestion and vectorization complete.")
