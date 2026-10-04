"""Tests for command-line settings and top-level coordination."""

import io
import unittest
from contextlib import ExitStack, redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

from src.lagscope import DiagnosticCheck, main, read_command_line_settings


class ReadCommandLineSettingsTests(unittest.TestCase):
    def test_defaults_to_five_observations(self) -> None:
        settings = read_command_line_settings([])

        self.assertEqual(settings.target, "8.8.8.8")
        self.assertEqual(settings.count, 5)
        self.assertIsNone(settings.duration_minutes)

    def test_accepts_a_configured_public_target(self) -> None:
        settings = read_command_line_settings(
            ["--target", "1.1.1.1", "--count", "2"]
        )

        self.assertEqual(settings.target, "1.1.1.1")
        self.assertEqual(settings.count, 2)

    def test_rejects_an_invalid_service_port(self) -> None:
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                read_command_line_settings(["--service-port", "70000"])


class MainCoordinationTests(unittest.TestCase):
    def test_configured_target_is_used_for_startup_and_monitoring(self) -> None:
        settings = SimpleNamespace(
            target="9.9.9.9",
            service_host="example.com",
            service_port=443,
            timeout_ms=1000,
            latency_threshold_ms=100,
            count=1,
            duration_minutes=None,
            interval=0,
            csv="output/test.csv",
        )
        successful_check = DiagnosticCheck("test", True, "ok")

        with ExitStack() as stack:
            stack.enter_context(
                patch("src.lagscope.read_command_line_settings", return_value=settings)
            )
            stack.enter_context(
                patch("src.lagscope.discover_default_gateway", return_value="gateway")
            )
            stack.enter_context(
                patch("src.lagscope.check_default_gateway", return_value=successful_check)
            )
            public_check = stack.enter_context(
                patch("src.lagscope.check_public_ip", return_value=successful_check)
            )
            stack.enter_context(
                patch("src.lagscope.check_dns", return_value=successful_check)
            )
            stack.enter_context(
                patch("src.lagscope.check_tcp_service", return_value=successful_check)
            )
            stack.enter_context(
                patch(
                    "src.lagscope.check_https_application",
                    return_value=successful_check,
                )
            )
            monitor = stack.enter_context(
                patch("src.lagscope.run_path_monitoring", return_value=[])
            )
            stack.enter_context(patch("builtins.print"))

            main()

        public_check.assert_called_once_with("9.9.9.9", 1000)
        self.assertEqual(monitor.call_args.kwargs["public_target"], "9.9.9.9")


if __name__ == "__main__":
    unittest.main()
