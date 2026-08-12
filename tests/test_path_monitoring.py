"""Automated tests for LagScope's paired path monitoring."""

import unittest
from unittest.mock import patch

from src.lagscope import (
    PathObservation,
    ProbeResult,
    collect_path_observation,
    run_path_monitoring,
)


def make_successful_probe(target: str, latency_ms: int) -> ProbeResult:
    """Create predictable successful probe evidence for these tests."""

    return ProbeResult(
        target=target,
        timestamp="test-time",
        success=True,
        latency_ms=latency_ms,
        error=None,
    )


class CollectPathObservationTests(unittest.TestCase):
    """Verify that one local/public measurement pair is collected correctly."""

    def test_gateway_and_public_results_are_kept_together(self) -> None:
        gateway_result = make_successful_probe("192.168.1.1", 2)
        public_result = make_successful_probe("8.8.8.8", 20)

        with patch(
            "src.lagscope.ping_once",
            side_effect=[gateway_result, public_result],
        ):
            observation = collect_path_observation(
                gateway="192.168.1.1",
                public_target="8.8.8.8",
                timeout_ms=1000,
            )

        self.assertEqual(observation.gateway_result, gateway_result)
        self.assertEqual(observation.public_result, public_result)

    def test_missing_gateway_still_collects_public_result(self) -> None:
        public_result = make_successful_probe("8.8.8.8", 20)

        with patch(
            "src.lagscope.ping_once",
            return_value=public_result,
        ) as mocked_ping:
            observation = collect_path_observation(
                gateway=None,
                public_target="8.8.8.8",
                timeout_ms=1000,
            )

        self.assertFalse(observation.gateway_result.success)
        self.assertEqual(observation.public_result, public_result)
        mocked_ping.assert_called_once_with("8.8.8.8", 1000)


class RunPathMonitoringTests(unittest.TestCase):
    """Verify that paired collection repeats at the requested interval."""

    def test_requested_observations_are_collected(self) -> None:
        first_observation = PathObservation(
            timestamp="time-1",
            gateway_result=make_successful_probe("gateway", 1),
            public_result=make_successful_probe("public", 10),
        )
        second_observation = PathObservation(
            timestamp="time-2",
            gateway_result=make_successful_probe("gateway", 2),
            public_result=make_successful_probe("public", 12),
        )

        with patch(
            "src.lagscope.collect_path_observation",
            side_effect=[first_observation, second_observation],
        ):
            with patch("src.lagscope.display_path_observation"):
                with patch("src.lagscope.time.sleep") as mocked_sleep:
                    observations = run_path_monitoring(
                        gateway="192.168.1.1",
                        public_target="8.8.8.8",
                        timeout_ms=1000,
                        count=2,
                        interval=0.5,
                    )

        self.assertEqual(
            observations,
            [first_observation, second_observation],
        )
        mocked_sleep.assert_called_once_with(0.5)


if __name__ == "__main__":
    unittest.main()
