"""Automated tests for LagScope's session-level interpretation."""

import unittest

from src.lagscope import PathObservation, ProbeResult, calculate_session_assessment


def make_observation(diagnosis: str) -> PathObservation:
    """Create a minimal paired observation with a chosen classification."""

    gateway_result = ProbeResult("gateway", "test-time", True, 2, None)
    public_result = ProbeResult("public", "test-time", True, 20, None)
    return PathObservation(
        timestamp="test-time",
        gateway_result=gateway_result,
        public_result=public_result,
        diagnosis=diagnosis,
    )


class CalculateSessionAssessmentTests(unittest.TestCase):
    """Verify counts, dominant issues, and cautious conclusions."""

    def test_empty_session_cannot_be_assessed(self) -> None:
        assessment = calculate_session_assessment([])

        self.assertEqual(assessment.total_observations, 0)
        self.assertIsNone(assessment.dominant_diagnosis)
        self.assertIn("could not be assessed", assessment.conclusion)

    def test_all_healthy_session_reports_no_degradation(self) -> None:
        observations = [make_observation("HEALTHY"), make_observation("HEALTHY")]

        assessment = calculate_session_assessment(observations)

        self.assertEqual(assessment.healthy_observations, 2)
        self.assertEqual(assessment.degraded_observations, 0)
        self.assertIsNone(assessment.dominant_diagnosis)
        self.assertIn("does not prove", assessment.conclusion)

    def test_mixed_session_counts_every_classification(self) -> None:
        observations = [
            make_observation("HEALTHY"),
            make_observation("UPSTREAM_LATENCY_SUSPECTED"),
            make_observation("UPSTREAM_LATENCY_SUSPECTED"),
            make_observation("LOCAL_LATENCY_SUSPECTED"),
        ]

        assessment = calculate_session_assessment(observations)

        self.assertEqual(assessment.total_observations, 4)
        self.assertEqual(assessment.healthy_observations, 1)
        self.assertEqual(assessment.degraded_observations, 3)
        self.assertEqual(
            assessment.diagnosis_counts["UPSTREAM_LATENCY_SUSPECTED"],
            2,
        )
        self.assertEqual(
            assessment.dominant_diagnosis,
            "UPSTREAM_LATENCY_SUSPECTED",
        )
        self.assertIn("gateway remained responsive", assessment.conclusion)

    def test_tied_counts_use_deterministic_priority_order(self) -> None:
        observations = [
            make_observation("UPSTREAM_PATH_SUSPECTED"),
            make_observation("LOCAL_PATH_SUSPECTED"),
        ]

        assessment = calculate_session_assessment(observations)

        self.assertEqual(assessment.dominant_diagnosis, "LOCAL_PATH_SUSPECTED")

    def test_gateway_icmp_result_is_not_called_a_proven_local_failure(self) -> None:
        observations = [make_observation("GATEWAY_ICMP_UNAVAILABLE")]

        assessment = calculate_session_assessment(observations)

        self.assertEqual(
            assessment.dominant_diagnosis,
            "GATEWAY_ICMP_UNAVAILABLE",
        )
        self.assertIn("does not prove a local failure", assessment.conclusion)


if __name__ == "__main__":
    unittest.main()
