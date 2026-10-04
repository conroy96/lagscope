"""Automated tests for LagScope's CSV evidence export."""

import csv
import tempfile
import unittest
from pathlib import Path

from src.lagscope import (
    PathObservation,
    ProbeResult,
    create_session_csv_path,
    save_path_observations_to_csv,
    save_results_to_csv,
)


class SaveResultsToCsvTests(unittest.TestCase):
    """Verify that probe evidence is written correctly to a CSV file."""

    def test_csv_contains_header_success_and_failure_rows(self) -> None:
        results = [
            ProbeResult(
                target="8.8.8.8",
                timestamp="2026-08-12T10:00:00+00:00",
                success=True,
                latency_ms=7,
                error=None,
            ),
            ProbeResult(
                target="8.8.8.8",
                timestamp="2026-08-12T10:00:01+00:00",
                success=False,
                latency_ms=None,
                error="Request timed out",
            ),
        ]

        with tempfile.TemporaryDirectory() as temporary_folder:
            output_path = Path(temporary_folder) / "nested" / "session.csv"

            save_results_to_csv(str(output_path), results)

            with output_path.open(
                mode="r",
                newline="",
                encoding="utf-8",
            ) as csv_file:
                rows = list(csv.reader(csv_file))

        expected_rows = [
            ["target", "timestamp_utc", "success", "latency_ms", "error"],
            ["8.8.8.8", "2026-08-12T10:00:00+00:00", "True", "7", ""],
            [
                "8.8.8.8",
                "2026-08-12T10:00:01+00:00",
                "False",
                "",
                "Request timed out",
            ],
        ]

        self.assertEqual(rows, expected_rows)


class SavePathObservationsToCsvTests(unittest.TestCase):
    """Verify paired path evidence is written as one row per observation."""

    def test_csv_contains_both_paths_and_diagnosis(self) -> None:
        gateway_result = ProbeResult(
            target="192.168.1.1",
            timestamp="gateway-time",
            success=True,
            latency_ms=2,
            error=None,
        )
        public_result = ProbeResult(
            target="8.8.8.8",
            timestamp="public-time",
            success=False,
            latency_ms=None,
            error="Request timed out",
        )
        observation = PathObservation(
            timestamp="2026-08-13T00:30:00+00:00",
            gateway_result=gateway_result,
            public_result=public_result,
            diagnosis="UPSTREAM_PATH_SUSPECTED",
        )

        with tempfile.TemporaryDirectory() as temporary_folder:
            output_path = Path(temporary_folder) / "paired.csv"

            save_path_observations_to_csv(str(output_path), [observation])

            with output_path.open(
                mode="r",
                newline="",
                encoding="utf-8",
            ) as csv_file:
                rows = list(csv.reader(csv_file))

        expected_rows = [
            [
                "observation_timestamp_utc",
                "diagnosis",
                "gateway_target",
                "gateway_success",
                "gateway_latency_ms",
                "gateway_error",
                "public_target",
                "public_success",
                "public_latency_ms",
                "public_error",
            ],
            [
                "2026-08-13T00:30:00+00:00",
                "UPSTREAM_PATH_SUSPECTED",
                "192.168.1.1",
                "True",
                "2",
                "",
                "8.8.8.8",
                "False",
                "",
                "Request timed out",
            ],
        ]

        self.assertEqual(rows, expected_rows)

    def test_default_csv_path_uses_output_folder_and_csv_extension(self) -> None:
        generated_path = Path(create_session_csv_path())

        self.assertEqual(generated_path.parent, Path("output"))
        self.assertTrue(generated_path.name.startswith("lagscope-session-"))
        self.assertEqual(generated_path.suffix, ".csv")


if __name__ == "__main__":
    unittest.main()
