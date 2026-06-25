"""
Mutability classifier + arbitration policies (stdlib mechanism demo).

The classifier is rule-based here (a production version uses a MuLan-style probe
of the model's own representations; MuLan reports 85-95% mutability accuracy and
shows mutability is NOT explained by frequency). The point of this harness is to
show the *policy* effect, and to report classifier accuracy honestly as the
system's true ceiling (a misclassified conditional/volatile fact breaks the
guarantee — so the number must be surfaced, not assumed).
"""

from __future__ import annotations

import re

# VOLATILE: facts that change (rates, thresholds, %, amounts, dates, "revised").
_VOLATILE_RE = re.compile(
    r"\b(percent|percentage|rate|threshold|limit|cap|revised|revision|current|"
    r"latest|deadline|increased|reduced|crore|lakh|w\.?e\.?f|as on)\b|%|₹|\b(19|20)\d{2}\b",
    re.IGNORECASE,
)
# STABLE: definitional / structural facts that rarely change.
_STABLE_RE = re.compile(
    r"\b(definition|defined|means|meaning|constitut\w*|structure of|what is a|"
    r"category of|classif\w* of|nature of)\b",
    re.IGNORECASE,
)


def classify_mutability(claim: str) -> str:
    """volatile > stable > semi_stable (volatile wins — safest to defer)."""
    if _VOLATILE_RE.search(claim):
        return "volatile"
    if _STABLE_RE.search(claim):
        return "stable"
    return "semi_stable"


# --- Trust policies: each returns "evidence" or "parametric" ----------------- #
def _prefer_context(item) -> str:
    return "evidence"  # the common RAG default -> "incorrect-match" on bad evidence


def _prefer_parametric(item) -> str:
    return "parametric"  # -> "over-confidence" on stale weights


def _mca(item) -> str:
    """Route trust by ESTIMATED mutability of the claim."""
    m = classify_mutability(item["claim"])
    if m == "volatile":
        return "evidence"                       # weights go stale -> defer to source
    if m == "stable":
        # require strong (corroborated) evidence to override a stable belief
        return "evidence" if item.get("evidence_corroborated") else "parametric"
    return "evidence" if item.get("evidence_corroborated") else "parametric"


POLICIES = {
    "prefer-context (global)": _prefer_context,
    "prefer-parametric (global)": _prefer_parametric,
    "MCA (mutability-routed)": _mca,
}


def decide(policy: str, item: dict) -> str:
    """Return the chosen answer string under the given policy."""
    src = POLICIES[policy](item)
    return item["evidence_answer"] if src == "evidence" else item["parametric_answer"]
