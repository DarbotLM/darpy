"""Evidence-based promotion inspired by SkillOpt's held-out acceptance gate.

This module compares caller-supplied measurements. It neither runs an optimizer
nor attests the measurements, trains weights, or rewrites deployed artifacts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from .schemas import SCHEMA_VERSION, _finite, _positive_int, _string


@dataclass(frozen=True, slots=True)
class EvaluationSpec:
    """Frozen comparison identity and required correctness gates.

    IDs should identify immutable evaluator code, dataset contents, and metric
    definitions. DARPy checks identity equality, not external content hashes.
    """

    evaluator_id: str
    dataset_id: str
    metric: str
    required_checks: tuple[str, ...] = ("correctness",)
    direction: Literal["maximize", "minimize"] = "maximize"
    min_improvement: float = 0.0

    def __post_init__(self) -> None:
        for name in ("evaluator_id", "dataset_id", "metric"):
            _string(getattr(self, name), name)
        if type(self.required_checks) is not tuple or not self.required_checks:
            raise ValueError("required_checks must be a nonempty tuple")
        for check in self.required_checks:
            _string(check, "check name")
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("Required checks must be unique")
        if self.direction not in ("maximize", "minimize"):
            raise ValueError("direction must be 'maximize' or 'minimize'")
        _finite(self.min_improvement, "min_improvement")
        if self.min_improvement < 0:
            raise ValueError("min_improvement must be nonnegative")


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool

    def __post_init__(self) -> None:
        _string(self.name, "check name")
        if type(self.passed) is not bool:
            raise TypeError("passed must be a bool")


@dataclass(frozen=True, slots=True)
class EvaluationEvidence:
    """Immutable measurement for an explicitly versioned candidate artifact."""

    artifact_id: str
    artifact_version: str
    evaluator_id: str
    dataset_id: str
    metric: str
    score: float
    sample_count: int
    checks: tuple[CheckResult, ...]

    def __post_init__(self) -> None:
        for name in ("artifact_id", "artifact_version", "evaluator_id", "dataset_id", "metric"):
            _string(getattr(self, name), name)
        _finite(self.score, "score")
        _positive_int(self.sample_count, "sample_count")
        if type(self.checks) is not tuple or not all(isinstance(item, CheckResult) for item in self.checks):
            raise TypeError("checks must be a tuple of CheckResult objects")
        if len({item.name for item in self.checks}) != len(self.checks):
            raise ValueError("Evidence check names must be unique")


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    """Versioned, serializable decision with the full comparison evidence."""

    record_id: str
    created_at: str
    promoted: bool
    reason: str
    spec: EvaluationSpec
    baseline: EvaluationEvidence
    candidate: EvaluationEvidence
    improvement: float | None

    @property
    def selected_version(self) -> str:
        return (self.candidate if self.promoted else self.baseline).artifact_version

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), allow_nan=False, sort_keys=True, separators=(",", ":"))


class ImprovementGate:
    """Retain a baseline unless comparable evidence passes all required gates
    and improves the selected metric strictly beyond ``min_improvement``.

    Repeated validation can overfit a held-out set. Callers must enforce search
    budgets and a separate final holdout; this gate does not manufacture either.
    """

    def __init__(self, spec: EvaluationSpec) -> None:
        if not isinstance(spec, EvaluationSpec):
            raise TypeError("spec must be an EvaluationSpec")
        self._spec = spec

    @property
    def spec(self) -> EvaluationSpec:
        return self._spec

    def evaluate(self, baseline: EvaluationEvidence, candidate: EvaluationEvidence) -> PromotionRecord:
        if not isinstance(baseline, EvaluationEvidence) or not isinstance(candidate, EvaluationEvidence):
            raise TypeError("baseline and candidate must be EvaluationEvidence")
        spec = self.spec
        identity = (spec.evaluator_id, spec.dataset_id, spec.metric)
        comparable = all(
            (item.evaluator_id, item.dataset_id, item.metric) == identity for item in (baseline, candidate)
        )
        promoted, improvement = False, None
        baseline_checks = {item.name: item.passed for item in baseline.checks}
        candidate_checks = {item.name: item.passed for item in candidate.checks}
        if not comparable or baseline.sample_count != candidate.sample_count:
            reason = "incomparable_evidence"
        elif baseline.artifact_id != candidate.artifact_id:
            reason = "different_artifact"
        elif baseline.artifact_version == candidate.artifact_version:
            reason = "same_artifact_version"
        elif not all(baseline_checks.get(name, False) for name in spec.required_checks):
            reason = "baseline_correctness_failed"
        elif not all(candidate_checks.get(name, False) for name in spec.required_checks):
            reason = "candidate_correctness_failed"
        else:
            improvement = (
                (candidate.score - baseline.score)
                if spec.direction == "maximize"
                else (baseline.score - candidate.score)
            )
            # Subtracting two finite values can still overflow. Never promote
            # from nonfinite derived metrics or produce invalid JSON receipts.
            try:
                _finite(improvement, "improvement")
            except ValueError:
                improvement, reason = None, "nonfinite_improvement"
            else:
                promoted = improvement > spec.min_improvement
                reason = "strict_improvement" if promoted else "no_strict_improvement"
        return PromotionRecord(
            uuid4().hex,
            datetime.now(UTC).isoformat(),
            promoted,
            reason,
            spec,
            baseline,
            candidate,
            improvement,
        )


__all__ = ["CheckResult", "EvaluationEvidence", "EvaluationSpec", "ImprovementGate", "PromotionRecord"]
