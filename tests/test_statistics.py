"""Automated tests for LagScope's probe summary calculations."""

import unittest

from src.lagscope import ProbeResult, calculate_summary


class CalculateSummaryTests(unittest.TestCase):
    """Verify packet-loss, latency, and simplified-jitter calculations."""

    def test_mixed_probe_results_produce_expected_statistics(self) -> None:
        results = [
            ProbeResult(
                target="test-target",
                timestamp="time-1",
                success=True,
                latency_ms=8,
                error=None,
            ),
            ProbeResult(
                target="test-target",
                timestamp="time-2",
                success=True,
                latency_ms=10,
                error=None,
            ),
            ProbeResult(
                target="test-target",
                timestamp="time-3",
                success=False,
                latency_ms=None,
                error="Request timed out",
            ),
            ProbeResult(
                target="test-target",
                timestamp="time-4",
                success=True,
                latency_ms=14,
                error=None,
            ),
        ]

        summary = calculate_summary(results)

        self.assertEqual(summary.sent_count, 4)
        self.assertEqual(summary.received_count, 3)
        self.assertEqual(summary.lost_count, 1)
        self.assertEqual(summary.packet_loss_percent, 25.0)
        self.assertEqual(summary.minimum_latency_ms, 8)
        self.assertAlmostEqual(summary.average_latency_ms, 32 / 3)
        self.assertEqual(summary.maximum_latency_ms, 14)
        self.assertEqual(summary.average_jitter_ms, 3.0)

    def test_all_failed_probes_have_no_latency_statistics(self) -> None:
        results = [
            ProbeResult(
                target="test-target",
                timestamp="time-1",
                success=False,
                latency_ms=None,
                error="Request timed out",
            ),
            ProbeResult(
                target="test-target",
                timestamp="time-2",
                success=False,
                latency_ms=None,
                error="Destination unreachable",
            ),
        ]

        summary = calculate_summary(results)

        self.assertEqual(summary.sent_count, 2)
        self.assertEqual(summary.received_count, 0)
        self.assertEqual(summary.lost_count, 2)
        self.assertEqual(summary.packet_loss_percent, 100.0)
        self.assertIsNone(summary.minimum_latency_ms)
        self.assertIsNone(summary.average_latency_ms)
        self.assertIsNone(summary.maximum_latency_ms)
        self.assertIsNone(summary.average_jitter_ms)

    def test_one_successful_probe_has_no_jitter_measurement(self) -> None:
        results = [
            ProbeResult(
                target="test-target",
                timestamp="time-1",
                success=True,
                latency_ms=8,
                error=None,
            )
        ]

        summary = calculate_summary(results)

        self.assertEqual(summary.sent_count, 1)
        self.assertEqual(summary.received_count, 1)
        self.assertEqual(summary.packet_loss_percent, 0.0)
        self.assertEqual(summary.minimum_latency_ms, 8)
        self.assertEqual(summary.average_latency_ms, 8.0)
        self.assertEqual(summary.maximum_latency_ms, 8)
        self.assertIsNone(summary.average_jitter_ms)

    def test_successful_reply_without_parsed_latency_is_still_received(self) -> None:
        results = [
            ProbeResult(
                target="test-target",
                timestamp="time-1",
                success=True,
                latency_ms=None,
                error=None,
            )
        ]

        summary = calculate_summary(results)

        self.assertEqual(summary.sent_count, 1)
        self.assertEqual(summary.received_count, 1)
        self.assertEqual(summary.lost_count, 0)
        self.assertEqual(summary.packet_loss_percent, 0.0)
        self.assertIsNone(summary.minimum_latency_ms)
        self.assertIsNone(summary.average_latency_ms)
        self.assertIsNone(summary.maximum_latency_ms)
        self.assertIsNone(summary.average_jitter_ms)


if __name__ == "__main__":
    unittest.main()
