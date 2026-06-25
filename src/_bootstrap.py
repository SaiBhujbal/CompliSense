"""Native-library bootstrap — IMPORT THIS FIRST in any module that loads chromadb.

On this CPU, importing chromadb/onnxruntime (via langchain_chroma) BEFORE
torch/sentence-transformers causes an OpenMP/native segfault. Importing this
module first initializes torch threading and sentence-transformers up front,
which avoids the clash. Safe no-op if torch/ST aren't installed.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

try:  # pragma: no cover - environment-dependent
    import torch

    torch.set_num_threads(1)
    import sentence_transformers  # noqa: F401
except Exception:
    pass
