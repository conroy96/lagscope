"""Automated tests for LagScope's dependency diagnosis logic."""

import unittest

from src.lagscope import DiagnosticCheck, diagnose_dependencies


class DiagnoseDependenciesTests(unittest.TestCase):
    """Verify the diagnosis returned for each possible failure boundary."""

    def test_gateway_failure_reports_local_network_problem(self) -> None:
        gateway_check = DiagnosticCheck("Gateway", False, "failed")
        public_ip_check = DiagnosticCheck("Public IP", True, "passed")
        dns_check = DiagnosticCheck("DNS", True, "passed")
        tcp_check = DiagnosticCheck("TCP", True, "passed")

        diagnosis = diagnose_dependencies(
            gateway_check,
            public_ip_check,
            dns_check,
            tcp_check,
        )

        self.assertEqual(
            diagnosis,
            "Likely local network problem: the default gateway was unreachable.",
        )

    def test_public_ip_failure_reports_internet_path_problem(self) -> None:
        gateway_check = DiagnosticCheck("Gateway", True, "passed")
        public_ip_check = DiagnosticCheck("Public IP", False, "failed")
        dns_check = DiagnosticCheck("DNS", True, "passed")
        tcp_check = DiagnosticCheck("TCP", True, "passed")

        diagnosis = diagnose_dependencies(
            gateway_check,
            public_ip_check,
            dns_check,
            tcp_check,
        )

        self.assertEqual(
            diagnosis,
            "Likely Internet path problem: the gateway worked but the public IP failed.",
        )

    def test_dns_failure_reports_name_resolution_problem(self) -> None:
        gateway_check = DiagnosticCheck("Gateway", True, "passed")
        public_ip_check = DiagnosticCheck("Public IP", True, "passed")
        dns_check = DiagnosticCheck("DNS", False, "failed")
        tcp_check = DiagnosticCheck("TCP", True, "passed")

        diagnosis = diagnose_dependencies(
            gateway_check,
            public_ip_check,
            dns_check,
            tcp_check,
        )

        self.assertEqual(
            diagnosis,
            "Likely DNS problem: Internet routing worked but name resolution failed.",
        )

    def test_tcp_failure_reports_service_path_problem(self) -> None:
        gateway_check = DiagnosticCheck("Gateway", True, "passed")
        public_ip_check = DiagnosticCheck("Public IP", True, "passed")
        dns_check = DiagnosticCheck("DNS", True, "passed")
        tcp_check = DiagnosticCheck("TCP", False, "failed")

        diagnosis = diagnose_dependencies(
            gateway_check,
            public_ip_check,
            dns_check,
            tcp_check,
        )

        self.assertEqual(
            diagnosis,
            "Likely service-path problem: DNS worked but the TCP connection failed.",
        )

    def test_all_successful_checks_report_no_failure(self) -> None:
        gateway_check = DiagnosticCheck("Gateway", True, "passed")
        public_ip_check = DiagnosticCheck("Public IP", True, "passed")
        dns_check = DiagnosticCheck("DNS", True, "passed")
        tcp_check = DiagnosticCheck("TCP", True, "passed")

        diagnosis = diagnose_dependencies(
            gateway_check,
            public_ip_check,
            dns_check,
            tcp_check,
        )

        self.assertEqual(diagnosis, "No dependency failure detected.")


# PYTHON RUNTIME CONVENTION: allow this test file to be run directly as well as
# discovered by "python -m unittest discover".
if __name__ == "__main__":
    unittest.main()
