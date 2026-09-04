"""Automated tests for LagScope's layered dependency diagnostics."""

import http.client
import ssl
import unittest
from unittest.mock import MagicMock, patch

from src.lagscope import (
    DiagnosticCheck,
    check_https_application,
    diagnose_dependencies,
)


class DiagnoseDependenciesTests(unittest.TestCase):
    """Verify the diagnosis returned for each possible failure boundary."""

    def test_gateway_failure_reports_local_network_problem(self) -> None:
        diagnosis = diagnose_dependencies(
            DiagnosticCheck("Gateway", False, "failed"),
            DiagnosticCheck("Public IP", True, "passed"),
            DiagnosticCheck("DNS", True, "passed"),
            DiagnosticCheck("TCP", True, "passed"),
            DiagnosticCheck("HTTPS", True, "passed"),
        )

        self.assertEqual(
            diagnosis,
            "Likely local network problem: the default gateway was unreachable.",
        )

    def test_public_ip_failure_reports_internet_path_problem(self) -> None:
        diagnosis = diagnose_dependencies(
            DiagnosticCheck("Gateway", True, "passed"),
            DiagnosticCheck("Public IP", False, "failed"),
            DiagnosticCheck("DNS", True, "passed"),
            DiagnosticCheck("TCP", True, "passed"),
            DiagnosticCheck("HTTPS", True, "passed"),
        )

        self.assertEqual(
            diagnosis,
            "Likely Internet path problem: the gateway worked but the public IP failed.",
        )

    def test_dns_failure_reports_name_resolution_problem(self) -> None:
        diagnosis = diagnose_dependencies(
            DiagnosticCheck("Gateway", True, "passed"),
            DiagnosticCheck("Public IP", True, "passed"),
            DiagnosticCheck("DNS", False, "failed"),
            DiagnosticCheck("TCP", True, "passed"),
            DiagnosticCheck("HTTPS", True, "passed"),
        )

        self.assertEqual(
            diagnosis,
            "Likely DNS problem: Internet routing worked but name resolution failed.",
        )

    def test_tcp_failure_reports_service_path_problem(self) -> None:
        diagnosis = diagnose_dependencies(
            DiagnosticCheck("Gateway", True, "passed"),
            DiagnosticCheck("Public IP", True, "passed"),
            DiagnosticCheck("DNS", True, "passed"),
            DiagnosticCheck("TCP", False, "failed"),
            DiagnosticCheck("HTTPS", True, "passed"),
        )

        self.assertEqual(
            diagnosis,
            "Likely service-path problem: DNS worked but the TCP connection failed.",
        )

    def test_https_failure_reports_application_layer_problem(self) -> None:
        diagnosis = diagnose_dependencies(
            DiagnosticCheck("Gateway", True, "passed"),
            DiagnosticCheck("Public IP", True, "passed"),
            DiagnosticCheck("DNS", True, "passed"),
            DiagnosticCheck("TCP", True, "passed"),
            DiagnosticCheck("HTTPS", False, "certificate invalid"),
        )

        self.assertEqual(
            diagnosis,
            "Likely HTTPS application-layer problem: certificate invalid",
        )

    def test_all_successful_checks_report_no_failure(self) -> None:
        diagnosis = diagnose_dependencies(
            DiagnosticCheck("Gateway", True, "passed"),
            DiagnosticCheck("Public IP", True, "passed"),
            DiagnosticCheck("DNS", True, "passed"),
            DiagnosticCheck("TCP", True, "passed"),
            DiagnosticCheck("HTTPS", True, "passed"),
        )

        self.assertEqual(diagnosis, "No dependency failure detected.")


class CheckHttpsApplicationTests(unittest.TestCase):
    """Verify HTTPS evidence without contacting live Internet services."""

    @patch("src.lagscope.http.client.HTTPSConnection")
    def test_successful_https_response_passes(self, connection_class) -> None:
        connection = connection_class.return_value
        connection.getresponse.return_value = MagicMock(status=200, reason="OK")

        result = check_https_application("example.com", 443, 1500)

        connection_class.assert_called_once_with(
            "example.com",
            port=443,
            timeout=1.5,
        )
        connection.request.assert_called_once_with("HEAD", "/")
        connection.close.assert_called_once_with()
        self.assertTrue(result.success)
        self.assertEqual(result.detail, "example.com:443 returned HTTP 200 OK")

    @patch("src.lagscope.http.client.HTTPSConnection")
    def test_http_error_response_fails(self, connection_class) -> None:
        connection = connection_class.return_value
        connection.getresponse.return_value = MagicMock(
            status=503,
            reason="Service Unavailable",
        )

        result = check_https_application("example.com", 443, 1000)

        connection.close.assert_called_once_with()
        self.assertFalse(result.success)
        self.assertIn("HTTP 503 Service Unavailable", result.detail)

    @patch("src.lagscope.http.client.HTTPSConnection")
    def test_tls_certificate_error_is_reported(self, connection_class) -> None:
        connection = connection_class.return_value
        connection.request.side_effect = ssl.SSLError("certificate verify failed")

        result = check_https_application("example.com", 443, 1000)

        connection.close.assert_called_once_with()
        self.assertFalse(result.success)
        self.assertIn("failed TLS", result.detail)
        self.assertIn("certificate verify failed", result.detail)

    @patch("src.lagscope.http.client.HTTPSConnection")
    def test_connection_error_is_reported(self, connection_class) -> None:
        connection = connection_class.return_value
        connection.request.side_effect = TimeoutError("timed out")

        result = check_https_application("example.com", 443, 1000)

        connection.close.assert_called_once_with()
        self.assertFalse(result.success)
        self.assertIn("failed HTTPS", result.detail)
        self.assertIn("timed out", result.detail)

    @patch("src.lagscope.http.client.HTTPSConnection")
    def test_http_protocol_error_is_reported(self, connection_class) -> None:
        connection = connection_class.return_value
        connection.getresponse.side_effect = http.client.BadStatusLine("bad response")

        result = check_https_application("example.com", 443, 1000)

        connection.close.assert_called_once_with()
        self.assertFalse(result.success)
        self.assertIn("failed HTTPS", result.detail)


# PYTHON RUNTIME CONVENTION: allow this test file to be run directly as well as
# discovered by "python -m unittest discover".
if __name__ == "__main__":
    unittest.main()
