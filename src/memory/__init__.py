"""Human-memory-inspired RAG memory ("back of the mind").

DT-CAM = Dual-Trace Consolidative Associative Memory. Motivated by
Complementary Learning Systems (hippocampus keeps crisp episodes; neocortex
extracts a gist; BOTH coexist, episode cue-recoverable). The contribution is
NOT the architecture (recombines MemGPT tiering + HippoRAG associative recall +
reflection-style consolidation) but the INVARIANT: consolidation may demote a
conditional/normative span to a dormant tier but must NEVER delete it, and it
stays cue-recoverable — so the "X is not required BUT may be used as an extra"
nuance that lossy summarization drops is preserved at ~zero standing token cost.
"""

from .dtcam import DualTraceMemory, LossyReflectionMemory, classify_span

__all__ = ["DualTraceMemory", "LossyReflectionMemory", "classify_span"]
