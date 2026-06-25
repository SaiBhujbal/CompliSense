"""Data model for RBI-NormBench items and answers (stdlib-only, runs anywhere)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Obligation:
    """A single normative obligation a correct answer MUST surface."""

    id: str
    summary: str
    # Lowercased substrings whose presence (all of them) marks the obligation as
    # surfaced under deterministic scoring. Keep these to the load-bearing facts
    # (thresholds, %, dates, section numbers) — not prose.
    key_facts: list[str] = field(default_factory=list)
    source_hint: str = ""


@dataclass
class BenchItem:
    id: str
    question: str
    category: str
    expected_behavior: str  # "answer" | "abstain"
    required_obligations: list[Obligation] = field(default_factory=list)
    # For "answer" items, the cited source's title/ref should contain one of these.
    must_cite_source_like: list[str] = field(default_factory=list)
    # "verified_web" | "expert_label_required" | "synthetic_template"
    provenance: str = "expert_label_required"
    notes: str = ""

    @staticmethod
    def from_dict(d: dict) -> "BenchItem":
        return BenchItem(
            id=d["id"],
            question=d["question"],
            category=d.get("category", ""),
            expected_behavior=d.get("expected_behavior", "answer"),
            required_obligations=[Obligation(**o) for o in d.get("required_obligations", [])],
            must_cite_source_like=d.get("must_cite_source_like", []),
            provenance=d.get("provenance", "expert_label_required"),
            notes=d.get("notes", ""),
        )


@dataclass
class AnswerResult:
    """What the system produced for one question."""

    text: str
    sources: list[dict] = field(default_factory=list)  # [{"id","title","ref"}]
    input_tokens: int = 0
    output_tokens: int = 0
    abstained: bool = False
