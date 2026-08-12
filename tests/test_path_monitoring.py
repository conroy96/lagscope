"""Automated tests for LagScope's paired path monitoring."""

import unittest
from unittest.mock import patch

from src.lagscope import (
    PathObservation,
    ProbeResult,
    classify_path_observation,
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


def make_failed_probe(target: str) -> ProbeResult:
    """Create predictable failed probe evidence for these tests."""

    return ProbeResult(
        target=target,
        timestamp="test-time",
        success=False,
        latency_ms=None,
        error="test failure",
    )


class ClassifyPathObservationTests(unittest.TestCase):
    """Verify the four reachability classifications."""

    def test_both_fail_suspects_local_path(self) -> None:
        gateway_result = make_failed_probe("gateway")
        public_result = make_failed_probe("public")

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "LOCAL_PATH_SUSPECTED")

    def test_only_public_fails_suspects_upstream_path(self) -> None:
        gateway_result = make_successful_probe("gateway", 2)
        public_result = make_failed_probe("public")

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "UPSTREAM_PATH_SUSPECTED")

    def test_only_gateway_fails_reports_icmp_unavailable(self) -> None:
        gateway_result = make_failed_probe("gateway")
        public_result = make_successful_probe("public", 20)

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "GATEWAY_ICMP_UNAVAILABLE")

    def test_both_succeed_reports_healthy(self) -> None:
        gateway_result = make_successful_probe("gateway", 2)
        public_result = make_successful_probe("public", 20)

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "HEALTHY")

    def test_both_slow_suspects_local_latency(self) -> None:
        gateway_result = make_successful_probe("gateway", 150)
        public_result = make_successful_probe("public", 180)

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "LOCAL_LATENCY_SUSPECTED")

    def test_only_public_slow_suspects_upstream_latency(self) -> None:
        gateway_result = make_successful_probe("gateway", 2)
        public_result = make_successful_probe("public", 180)

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "UPSTREAM_LATENCY_SUSPECTED")

    def test_only_gateway_slow_reports_gateway_icmp_slow(self) -> None:
        gateway_result = make_successful_probe("gateway", 150)
        public_result = make_successful_probe("public", 20)

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "GATEWAY_ICMP_SLOW")

    def test_missing_latency_reports_unavailable_measurement(self) -> None:
        gateway_result = make_successful_probe("gateway", 2)
        public_result = make_successful_probe("public", 20)
        public_result.latency_ms = None

        diagnosis = classify_path_observation(gateway_result, public_result, 100)

        self.assertEqual(diagnosis, "LATENCY_UNAVAILABLE")


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
                latency_threshold_ms=100,
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
                latency_threshold_ms=100,
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
            diagnosis="HEALTHY",
        )
        second_observation = PathObservation(
            timestamp="time-2",
            gateway_result=make_successful_probe("gateway", 2),
            public_result=make_successful_probe("public", 12),
            diagnosis="HEALTHY",
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
                        latency_threshold_ms=100,
                        count=2,
                        duration_minutes=None,
                        interval=0.5,
                    )

        self.assertEqual(
            observations,
            [first_observation, second_observation],
        )
        mocked_sleep.assert_called_once_with(0.5)

    def test_duration_mode_stops_when_end_time_is_reached(self) -> None:
        first_observation = PathObservation(
            timestamp="time-1",
            gateway_result=make_successful_probe("gateway", 1),
            public_result=make_successful_probe("public", 10),
            diagnosis="HEALTHY",
        )
        second_observation = PathObservation(
            timestamp="time-2",
            gateway_result=make_successful_probe("gateway", 1),
            public_result=make_successful_probe("public", 11),
            diagnosis="HEALTHY",
        )

        with patch(
            "src.lagscope.collect_path_observation",
            side_effect=[first_observation, second_observation],
        ):
            with patch("src.lagscope.display_path_observation"):
                with patch("src.lagscope.time.sleep"):
                    with patch(
                        "src.lagscope.time.monotonic",
                        side_effect=[0, 0, 1, 2, 7],
                    ):
                        observations = run_path_monitoring(
                            gateway="192.168.1.1",
                            public_target="8.8.8.8",
                            timeout_ms=1000,
                            latency_threshold_ms=100,
                            count=None,
                            duration_minutes=0.1,
                            interval=0.5,
                        )

        self.assertEqual(
            observations,
            [first_observation, second_observation],
        )

    def test_keyboard_interrupt_preserves_collected_observations(self) -> None:
        first_observation = PathObservation(
            timestamp="time-1",
            gateway_result=make_successful_probe("gateway", 1),
            public_result=make_successful_probe("public", 10),
            diagnosis="HEALTHY",
        )

        with patch(
            "src.lagscope.collect_path_observation",
            side_effect=[first_observation, KeyboardInterrupt()],
        ):
            with patch("src.lagscope.display_path_observation"):
                with patch("src.lagscope.time.sleep"):
                    with patch("builtins.print"):
                        observations = run_path_monitoring(
                            gateway="192.168.1.1",
                            public_target="8.8.8.8",
                            timeout_ms=1000,
                            latency_threshold_ms=100,
                            count=5,
                            duration_minutes=None,
                            interval=0.5,
                        )

        self.assertEqual(observations, [first_observation])


if __name__ == "__main__":
    unittest.main()
