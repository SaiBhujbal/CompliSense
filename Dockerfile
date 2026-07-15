# CompliSense — multi-stage hardened image (FastAPI + agent_runner)
# Build:  docker compose build --no-cache
# Run:    docker compose up
#
# Security notes (2026-07-15):
# - PyPI: setuptools>=83 / wheel>=0.46.2 / jaraco.context>=6.1.0 (CVE-2026-59890,
#   CVE-2026-24049, CVE-2026-23949).
# - chromadb: no fixed PyPI release past 1.5.9 for CVE-2026-45829 yet; we use
#   local PersistentClient only (no Chroma HTTP/FastAPI server exposed). Attack
#   surface for ChromaToast is the HTTP collection API — not used here.
# - OS: apt full upgrade on Bookworm; runtime has no build-essential/curl;
#   healthcheck uses Python stdlib. Many deb perl/tar/glibc scanner hits are
#   unfixed/disputed upstream — see residual risk in the remediations note.

# ── builder ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Patch build tooling first, then app deps; re-pin after in case transitive pins regress.
RUN pip install --upgrade \
        "pip>=25" \
        "setuptools>=83.0.0" \
        "wheel>=0.46.2" \
        "jaraco.context>=6.1.0" \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2" \
    && pip install -r requirements.txt \
    && pip install --upgrade \
        "setuptools>=83.0.0" \
        "wheel>=0.46.2" \
        "jaraco.context>=6.1.0" \
    && python -c "from importlib.metadata import version as v; \
import sentence_transformers, torch, fastapi, slack_sdk, chromadb; \
print('deps_ok', torch.__version__, 'chroma', v('chromadb'), \
'setuptools', v('setuptools'), 'wheel', v('wheel'), \
'jaraco.context', v('jaraco.context'))"

# ── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KMP_DUPLICATE_LIB_OK=TRUE \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface \
    PATH="/opt/venv/bin:$PATH" \
    # Chroma: never start the Python FastAPI server (CVE-2026-45829 surface).
    CHROMA_SERVER_NOFILE=1 \
    ANONYMIZED_TELEMETRY=False

WORKDIR /app

# OS security updates + minimal runtime libs only (no curl — healthcheck uses Python).
# Do NOT purge perl-base: apt itself depends on it on Debian.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && apt-get autoremove -y --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache

COPY --from=builder /opt/venv /opt/venv
COPY . .

# Stay root so named-volume mounts at /app/data are writable (local compose).
RUN mkdir -p /app/data /app/data/chroma_db /app/.cache/huggingface \
    && chmod +x /app/entrypoint.sh \
    && sed -i 's/\r$//' /app/entrypoint.sh \
    && python -c "import fastapi, chromadb, torch; print('runtime_ok', chromadb.__version__)"

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
