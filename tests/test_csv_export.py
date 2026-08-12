"""Automated tests for LagScope's CSV evidence export."""

import csv
import tempfile
import unittest
from pathlib import Path

from src.lagscope import ProbeResult, save_results_to_csv


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

        # STANDARD LIBRARY: TemporaryDirectory creates an isolated folder for
        # this test and automatically removes it when the with block finishes.
        with tempfile.TemporaryDirectory() as temporary_folder:
            output_path = Path(temporary_folder) / "nested" / "session.csv"

            save_results_to_csv(str(output_path), results)

            # Open the saved evidence and parse it using the standard CSV reader.
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


if __name__ == "__main__":
    unittest.main()
