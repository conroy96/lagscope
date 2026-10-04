"""Tests for the Windows command-output boundary."""

import subprocess
import unittest
from unittest.mock import patch

from src.lagscope import (
    extract_default_gateway,
    extract_latency_ms,
    find_failure_message,
    output_contains_failure,
    ping_once,
)


class PingOutputParsingTests(unittest.TestCase):
    def test_extracts_normal_latency(self) -> None:
        output = "Reply from 8.8.8.8: bytes=32 time=17ms TTL=117"

        self.assertEqual(extract_latency_ms(output), 17)

    def test_extracts_less_than_one_millisecond_as_one(self) -> None:
        output = "Reply from 192.168.1.1: bytes=32 time<1ms TTL=64"

        self.assertEqual(extract_latency_ms(output), 1)

    def test_returns_none_when_latency_is_missing(self) -> None:
        self.assertIsNone(extract_latency_ms("Request timed out."))

    def test_detects_known_failure_text_case_insensitively(self) -> None:
        self.assertTrue(output_contains_failure("REQUEST TIMED OUT."))
        self.assertTrue(output_contains_failure("Destination host unreachable."))
        self.assertFalse(output_contains_failure("Reply from 8.8.8.8: time=8ms"))

    def test_stderr_is_preferred_as_the_failure_message(self) -> None:
        message = find_failure_message(
            "Request timed out.",
            " ping could not start ",
        )

        self.assertEqual(message, "ping could not start")

    def test_failure_line_is_extracted_from_stdout(self) -> None:
        output = "Pinging 8.8.8.8\nRequest timed out.\nPing statistics"

        self.assertEqual(
            find_failure_message(output, ""),
            "Request timed out.",
        )


class RouteOutputParsingTests(unittest.TestCase):
    def test_extracts_ipv4_default_gateway(self) -> None:
        route_output = """
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0      192.168.1.1   192.168.1.211     25
        127.0.0.0        255.0.0.0          On-link       127.0.0.1    331
"""

        self.assertEqual(extract_default_gateway(route_output), "192.168.1.1")

    def test_returns_none_when_default_route_is_missing(self) -> None:
        route_output = "10.0.0.0 255.0.0.0 On-link 10.1.2.3 25"

        self.assertIsNone(extract_default_gateway(route_output))

    def test_ignores_malformed_rows(self) -> None:
        route_output = "heading\n0.0.0.0 0.0.0.0\n"

        self.assertIsNone(extract_default_gateway(route_output))


class PingOnceTests(unittest.TestCase):
    def test_successful_ping_returns_structured_evidence(self) -> None:
        completed_process = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Reply from 8.8.8.8: bytes=32 time=9ms TTL=117",
            stderr="",
        )

        with patch("src.lagscope.subprocess.run", return_value=completed_process):
            result = ping_once("8.8.8.8", 1000)

        self.assertTrue(result.success)
        self.assertEqual(result.target, "8.8.8.8")
        self.assertEqual(result.latency_ms, 9)
        self.assertIsNone(result.error)

    def test_unreachable_text_fails_even_with_zero_return_code(self) -> None:
        completed_process = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Reply from 192.168.1.1: Destination host unreachable.",
            stderr="",
        )

        with patch("src.lagscope.subprocess.run", return_value=completed_process):
            result = ping_once("8.8.8.8", 1000)

        self.assertFalse(result.success)
        self.assertIsNone(result.latency_ms)
        self.assertEqual(
            result.error,
            "Reply from 192.168.1.1: Destination host unreachable.",
        )

    def test_command_timeout_becomes_failed_probe_evidence(self) -> None:
        with patch(
            "src.lagscope.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ping", timeout=3),
        ):
            result = ping_once("8.8.8.8", 1000)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "command timed out")


if __name__ == "__main__":
    unittest.main()
