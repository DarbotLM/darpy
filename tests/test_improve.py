import json
import unittest
from dataclasses import FrozenInstanceError, replace

from darpy.improve import CheckResult, EvaluationEvidence, EvaluationSpec, ImprovementGate


class ImprovementTests(unittest.TestCase):
    def setUp(self):
        self.spec = EvaluationSpec(
            "evaluator:sha256:abc", "heldout:sha256:def", "accuracy", required_checks=("correctness", "regressions")
        )
        self.baseline = EvaluationEvidence(
            "skill:planner",
            "v1",
            self.spec.evaluator_id,
            self.spec.dataset_id,
            "accuracy",
            0.75,
            100,
            (CheckResult("correctness", True), CheckResult("regressions", True)),
        )
        self.candidate = replace(self.baseline, artifact_version="v2", score=0.8)
        self.gate = ImprovementGate(self.spec)

    def test_strict_improvement_promotes_and_records_evidence(self):
        record = self.gate.evaluate(self.baseline, self.candidate)
        self.assertTrue(record.promoted)
        self.assertEqual(record.selected_version, "v2")
        self.assertAlmostEqual(record.improvement, 0.05)
        saved = json.loads(record.to_json())
        self.assertEqual(saved["schema_version"], "1.0")
        self.assertEqual(saved["baseline"]["artifact_version"], "v1")
        self.assertEqual(saved["candidate"]["score"], 0.8)
        self.assertEqual(saved["spec"]["dataset_id"], self.spec.dataset_id)

    def test_tie_and_regression_retain_baseline(self):
        for score in [0.75, 0.74]:
            record = self.gate.evaluate(self.baseline, replace(self.candidate, score=score))
            self.assertFalse(record.promoted)
            self.assertEqual(record.selected_version, "v1")
            self.assertEqual(record.reason, "no_strict_improvement")

    def test_minimize_metric(self):
        gate = ImprovementGate(replace(self.spec, direction="minimize"))
        self.assertTrue(gate.evaluate(self.baseline, replace(self.candidate, score=0.7)).promoted)
        self.assertFalse(gate.evaluate(self.baseline, self.candidate).promoted)

    def test_required_correctness_cannot_be_overridden_by_score(self):
        for checks in [
            (),
            (CheckResult("correctness", True),),
            (CheckResult("correctness", False), CheckResult("regressions", True)),
        ]:
            record = self.gate.evaluate(self.baseline, replace(self.candidate, checks=checks, score=1.0))
            self.assertEqual(record.reason, "candidate_correctness_failed")
            self.assertFalse(record.promoted)

    def test_invalid_baseline_is_not_a_valid_reference(self):
        record = self.gate.evaluate(replace(self.baseline, checks=()), self.candidate)
        self.assertEqual(record.reason, "baseline_correctness_failed")

    def test_evaluator_dataset_metric_and_samples_fixed(self):
        for changes in [{"evaluator_id": "other"}, {"dataset_id": "train"}, {"metric": "other"}, {"sample_count": 99}]:
            with self.subTest(changes=changes):
                record = self.gate.evaluate(self.baseline, replace(self.candidate, **changes))
                self.assertFalse(record.promoted)
                self.assertEqual(record.reason, "incomparable_evidence")

    def test_artifact_identity_and_versions_must_be_distinct(self):
        record = self.gate.evaluate(self.baseline, replace(self.candidate, artifact_id="other"))
        self.assertEqual(record.reason, "different_artifact")
        record = self.gate.evaluate(self.baseline, replace(self.candidate, artifact_version="v1"))
        self.assertEqual(record.reason, "same_artifact_version")

    def test_improvement_threshold_is_strict(self):
        gate = ImprovementGate(replace(self.spec, min_improvement=0.25))
        self.assertFalse(gate.evaluate(self.baseline, replace(self.candidate, score=1.0)).promoted)
        self.assertTrue(gate.evaluate(self.baseline, replace(self.candidate, score=1.1)).promoted)

    def test_nonfinite_input_or_derived_metrics_never_promote(self):
        for value in [float("nan"), float("inf"), True]:
            with self.assertRaises((TypeError, ValueError)):
                replace(self.candidate, score=value)
        record = self.gate.evaluate(replace(self.baseline, score=-1e308), replace(self.candidate, score=1e308))
        self.assertFalse(record.promoted)
        self.assertEqual(record.reason, "nonfinite_improvement")
        json.loads(record.to_json())

    def test_duplicate_checks_and_invalid_sample_count_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.candidate, checks=(CheckResult("x", True), CheckResult("x", False)))
        for count in (0, -1, True, 2.5):
            with self.assertRaises((TypeError, ValueError)):
                replace(self.candidate, sample_count=count)

    def test_evidence_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.candidate.score = 1.0
        with self.assertRaises(FrozenInstanceError):
            self.spec.dataset_id = "new"


if __name__ == "__main__":
    unittest.main()
