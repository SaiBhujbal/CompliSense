"""Mutability-Conditioned Arbitration for regulatory RAG (MCA-Reg).

APPLIED contribution (not a field-beating paradigm — the arbitration space is
crowded: TrustMargin, ArbGraph, DynaRAG, write-time gating). The honest, narrow
bet: in the RBI-compliance domain, fact MUTABILITY is unusually well-signaled
(volatile: rates/thresholds/dates/"revised"; stable: statutory definitions), so
routing the parametric-vs-retrieved TRUST decision by mutability class should
beat any single global policy on knowledge-conflict — recovering both failure
modes the literature names (over-confidence AND incorrect-match).
"""

from .mca import classify_mutability, decide, POLICIES

__all__ = ["classify_mutability", "decide", "POLICIES"]
