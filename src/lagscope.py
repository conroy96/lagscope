"""LagScope Day 1 proof of concept.

Run one Windows ping probe and report the result in a predictable format.
"""

# Comment key used throughout this file:
# PROJECT CODE: written specifically for LagScope.
# PYTHON BUILT-IN: available without importing a module.
# STANDARD LIBRARY: supplied with Python, but imported from a module.
# PYTHON SYNTAX: part of the Python language rather than a callable function.
# Detailed references: docs/PYTHON_CODE_GUIDE.md

# STANDARD LIBRARY: argparse reads and validates command-line options.
import argparse
# STANDARD LIBRARY: re searches text using regular-expression patterns.
import re
# STANDARD LIBRARY: subprocess starts another program and captures its result.
import subprocess
# STANDARD LIBRARY: time provides sleep(), which pauses the current program.
import time
# STANDARD LIBRARY: dataclass generates data-storage methods for a class.
from dataclasses import dataclass
# STANDARD LIBRARY: datetime and timezone create a UTC timestamp.
from datetime import datetime, timezone


# STANDARD LIBRARY: @dataclass generates ProbeResult.__init__ for us.
# PROJECT CODE: ProbeResult defines the five values LagScope records.
@dataclass
class ProbeResult:
    """The evidence collected from one network probe."""

    target: str
    timestamp: str
    success: bool
    latency_ms: int | None
    error: str | None


# PROJECT CODE: ProbeSummary stores statistics calculated from several probes.
@dataclass
class ProbeSummary:
    """Aggregate measurements calculated from a collection of probes."""

    sent_count: int
    received_count: int
    lost_count: int
    packet_loss_percent: float
    minimum_latency_ms: int | None
    average_latency_ms: float | None
    maximum_latency_ms: int | None
    average_jitter_ms: float | None


# PROJECT FUNCTION: inspect Windows ping text for known failure phrases.
def output_contains_failure(ping_output: str) -> bool:
    """Return True when Windows ping reports a known failure message."""

    failure_messages = [
        "unreachable",
        "request timed out",
        "could not find host",
        "general failure",
    ]

    # BUILT-IN str METHOD: .lower() returns a lowercase copy of the string.
    # This makes the search ignore capitalisation differences.
    lowercase_output = ping_output.lower()

    # PYTHON SYNTAX: for examines each item in the list one at a time.
    # PYTHON SYNTAX: "in" checks whether text occurs inside other text.
    for failure_message in failure_messages:
        if failure_message in lowercase_output:
            return True

    return False


# PROJECT FUNCTION: choose useful error text to show to the user.
def find_failure_message(ping_output: str, error_output: str) -> str:
    """Choose the most useful error message produced by Windows ping."""

    # BUILT-IN str METHOD: .strip() removes whitespace and newlines from
    # the beginning and end of a string.
    cleaned_error_output = error_output.strip()
    if cleaned_error_output:
        return cleaned_error_output

    failure_messages = [
        "unreachable",
        "request timed out",
        "could not find host",
        "general failure",
    ]

    # BUILT-IN str METHOD: .splitlines() turns one multiline string into
    # separate strings so that each output line can be inspected.
    for line in ping_output.splitlines():
        lowercase_line = line.lower()

        for failure_message in failure_messages:
            if failure_message in lowercase_line:
                return line.strip()

    return "no ICMP echo reply received"


# PROJECT FUNCTION: extract the numerical latency from successful ping text.
def extract_latency_ms(ping_output: str) -> int | None:
    """Extract the latency number from text such as 'time=6ms'."""

    # STANDARD LIBRARY: re.search(pattern, text, option) scans ping_output
    # until it finds text matching the regular-expression pattern.
    #
    # r"..." is a raw string, so Python leaves the backslash in \d unchanged.
    # Pattern breakdown:
    #   time    = match the literal word "time"
    #   [=<]    = match one character: either "=" or "<"
    #   (\d+)   = capture one or more digits; for example, capture "6"
    #   ms      = match the literal unit "ms"
    # re.IGNORECASE allows "time", "Time", or "TIME" to match.
    latency_pattern = r"time[=<](\d+)ms"
    latency_match = re.search(latency_pattern, ping_output, re.IGNORECASE)

    if latency_match is None:
        return None

    # STANDARD LIBRARY: a successful re.search returns a Match object.
    # .group(1) returns the text captured by the first (...) group.
    latency_text = latency_match.group(1)

    # PYTHON BUILT-IN: int("6") converts the text "6" to the number 6.
    latency_ms = int(latency_text)
    return latency_ms


# PROJECT FUNCTION: perform one Windows ping and return structured evidence.
def ping_once(target: str, timeout_ms: int) -> ProbeResult:
    """Send one ICMP echo request using the Windows ping command."""

    # STANDARD LIBRARY: now(timezone.utc) gets the current UTC time.
    # datetime METHOD: .isoformat() converts it to consistent timestamp text.
    timestamp = datetime.now(timezone.utc).isoformat()

    # PYTHON BUILT-IN: str() converts the timeout number to command-line text.
    # This list represents: ping -n 1 -w <timeout_ms> <target>
    command = ["ping", "-n", "1", "-w", str(timeout_ms), target]

    # PYTHON SYNTAX: try/except lets us handle expected execution errors.
    try:
        # STANDARD LIBRARY: subprocess.run starts ping.exe as a child process
        # and waits for it to finish.
        #   command: the program is item 0; later items are its arguments.
        #   capture_output=True: save stdout and stderr for our code to inspect.
        #   text=True: return captured output as strings instead of bytes.
        #   timeout=...: stop waiting if the whole ping process hangs.
        #   check=False: return the result instead of raising an exception when
        #                ping.exe uses a non-zero return code.
        ping_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=(timeout_ms / 1000) + 2,
            check=False,
        )
    # STANDARD LIBRARY EXCEPTION: raised if subprocess.run exceeds its timeout.
    except subprocess.TimeoutExpired:
        return ProbeResult(
            target=target,
            timestamp=timestamp,
            success=False,
            latency_ms=None,
            error="command timed out",
        )
    # PYTHON BUILT-IN EXCEPTION: raised for OS problems such as being unable
    # to start ping.exe. "as" stores the exception in our named variable.
    except OSError as operating_system_error:
        return ProbeResult(
            target=target,
            timestamp=timestamp,
            success=False,
            latency_ms=None,
            error=str(operating_system_error),
        )

    # STANDARD LIBRARY: subprocess.run returns a CompletedProcess object.
    # .stdout is normal captured output; .stderr is captured error output.
    ping_output = ping_process.stdout
    error_output = ping_process.stderr

    # PROJECT FUNCTION CALL: inspect stdout for Windows failure messages.
    windows_reported_failure = output_contains_failure(ping_output)

    # .returncode is supplied by CompletedProcess. Zero usually means the
    # program ran successfully, but Windows ping may still print "unreachable".
    # PYTHON SYNTAX: "or" makes probe_failed True if either check is True.
    probe_failed = ping_process.returncode != 0 or windows_reported_failure

    if probe_failed:
        error_message = find_failure_message(ping_output, error_output)
        return ProbeResult(
            target=target,
            timestamp=timestamp,
            success=False,
            latency_ms=None,
            error=error_message,
        )

    # PROJECT FUNCTION CALL: obtain latency only after ruling out failure.
    latency_ms = extract_latency_ms(ping_output)
    return ProbeResult(
        target=target,
        timestamp=timestamp,
        success=True,
        latency_ms=latency_ms,
        error=None,
    )


def display_probe_result(
    probe_number: int,
    total_probes: int,
    result: ProbeResult,
) -> None:
    """Display the evidence collected from one probe."""

    if result.success:
        status = "OK"
    else:
        status = "FAILED"

    if result.latency_ms is not None:
        latency = f"{result.latency_ms} ms"
    else:
        latency = "unknown"

    print(f"\nProbe {probe_number} of {total_probes}")
    print(f"Target:    {result.target}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Status:    {status}")
    print(f"Latency:   {latency}")

    if result.error:
        print(f"Error:     {result.error}")


def run_probes(
    target: str,
    timeout_ms: int,
    count: int,
    interval: float,
) -> list[ProbeResult]:
    """Run the requested probes and return every collected result."""

    results: list[ProbeResult] = []

    for probe_number in range(1, count + 1):
        result = ping_once(target, timeout_ms)
        results.append(result)
        display_probe_result(probe_number, count, result)

        # Wait between probes, but do not wait after the final probe.
        if probe_number < count:
            time.sleep(interval)

    return results


def calculate_summary(results: list[ProbeResult]) -> ProbeSummary:
    """Calculate packet loss, latency, and simplified jitter statistics."""

    successful_latencies: list[int] = []

    for probe_result in results:
        if probe_result.success and probe_result.latency_ms is not None:
            successful_latencies.append(probe_result.latency_ms)

    sent_count = len(results)
    received_count = len(successful_latencies)
    lost_count = sent_count - received_count
    packet_loss_percent = (lost_count / sent_count) * 100

    if successful_latencies:
        minimum_latency_ms = min(successful_latencies)
        maximum_latency_ms = max(successful_latencies)
        average_latency_ms = sum(successful_latencies) / len(successful_latencies)
    else:
        minimum_latency_ms = None
        maximum_latency_ms = None
        average_latency_ms = None

    # Simplified jitter: mean absolute difference between consecutive
    # successful round-trip latency measurements.
    latency_differences: list[int] = []

    for index in range(1, len(successful_latencies)):
        previous_latency = successful_latencies[index - 1]
        current_latency = successful_latencies[index]
        difference = abs(current_latency - previous_latency)
        latency_differences.append(difference)

    if latency_differences:
        average_jitter_ms = sum(latency_differences) / len(latency_differences)
    else:
        average_jitter_ms = None

    return ProbeSummary(
        sent_count=sent_count,
        received_count=received_count,
        lost_count=lost_count,
        packet_loss_percent=packet_loss_percent,
        minimum_latency_ms=minimum_latency_ms,
        average_latency_ms=average_latency_ms,
        maximum_latency_ms=maximum_latency_ms,
        average_jitter_ms=average_jitter_ms,
    )


def display_summary(summary: ProbeSummary) -> None:
    """Display aggregate statistics calculated from all probes."""

    print("\nSummary")
    print(f"Sent:        {summary.sent_count}")
    print(f"Received:    {summary.received_count}")
    print(f"Lost:        {summary.lost_count}")
    print(f"Packet loss: {summary.packet_loss_percent:.1f}%")

    if summary.average_latency_ms is not None:
        print(f"Minimum:     {summary.minimum_latency_ms} ms")
        print(f"Average:     {summary.average_latency_ms:.1f} ms")
        print(f"Maximum:     {summary.maximum_latency_ms} ms")
    else:
        print("Latency:     No successful replies")

    if summary.average_jitter_ms is not None:
        print(f"Jitter:      {summary.average_jitter_ms:.1f} ms")
    else:
        print("Jitter:      Not enough successful replies")


# PROJECT FUNCTION: define, read, and validate LagScope's command-line options.
def read_command_line_settings() -> argparse.Namespace:
    # STANDARD LIBRARY: ArgumentParser creates the command-line parser.
    parser = argparse.ArgumentParser(
        description="Run the LagScope Day 1 network probe."
    )

    # STANDARD LIBRARY METHOD: .add_argument defines an accepted option,
    # its default value, conversion type, and --help description.
    parser.add_argument(
        "--target",
        default="8.8.8.8",
        help="IP address or hostname to probe (default: 8.8.8.8)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=1000,
        help="Maximum ping wait in milliseconds (default: 1000)",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of probes to run (default is set to 5)",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds to wait between probes (default:1.0)",

    )

    # STANDARD LIBRARY METHOD: .parse_args() reads the arguments supplied in
    # PowerShell and returns an argparse.Namespace containing their values.
    settings = parser.parse_args()

    if settings.timeout_ms <= 0:
        # STANDARD LIBRARY METHOD: .error() displays the message and stops the
        # program with command-line usage information.
        parser.error("--timeout-ms must be greater than zero")

    if settings.count <= 0:
        parser.error("--count must be greater than zero")

    if settings.interval < 0:
        parser.error("--interval must be 0 or greater")

   

    return settings




# PROJECT FUNCTION: coordinate the program's steps and display the result.
def main() -> None:
    settings = read_command_line_settings()

    results = run_probes(
        target=settings.target,
        timeout_ms=settings.timeout_ms,
        count=settings.count,
        interval=settings.interval,
    )
    summary = calculate_summary(results)
    display_summary(summary)

# PYTHON RUNTIME CONVENTION: when this file is run directly, Python sets
# __name__ to "__main__". This prevents main() running if another file imports
# lagscope as a module.
if __name__ == "__main__":
    main()
