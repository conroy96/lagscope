"""LagScope V2 network-path monitor and layered diagnostic tool."""

import argparse
import csv
import http.client
import re
import socket
import ssl
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VERSION = "2.0.0"

@dataclass
class ProbeResult:
    """The evidence collected from one network probe."""

    target: str
    timestamp: str
    success: bool
    latency_ms: int | None
    error: str | None

@dataclass
class PathObservation:
    """A paired snapshot of the local and Internet paths."""

    timestamp: str
    gateway_result: ProbeResult
    public_result: ProbeResult
    diagnosis: str


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

@dataclass
class DiagnosticCheck:
    """The result of checking one network dependency."""

    name: str
    success: bool
    detail: str


@dataclass
class SessionAssessment:
    """A session-level summary of path classifications."""

    total_observations: int
    healthy_observations: int
    degraded_observations: int
    diagnosis_counts: dict[str, int]
    dominant_diagnosis: str | None
    conclusion: str


# Keep output deterministic and prefer stronger failure evidence when counts tie.
PATH_DIAGNOSIS_ORDER = (
    "LOCAL_PATH_SUSPECTED",
    "UPSTREAM_PATH_SUSPECTED",
    "LOCAL_LATENCY_SUSPECTED",
    "UPSTREAM_LATENCY_SUSPECTED",
    "GATEWAY_ICMP_UNAVAILABLE",
    "GATEWAY_ICMP_SLOW",
    "LATENCY_UNAVAILABLE",
    "HEALTHY",
)

PATH_OBSERVATION_HEADER = (
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
)

def output_contains_failure(ping_output: str) -> bool:
    """Return True when Windows ping reports a known failure message."""

    failure_messages = [
        "unreachable",
        "request timed out",
        "could not find host",
        "general failure",
    ]

    lowercase_output = ping_output.lower()

    for failure_message in failure_messages:
        if failure_message in lowercase_output:
            return True

    return False


def find_failure_message(ping_output: str, error_output: str) -> str:
    """Choose the most useful error message produced by Windows ping."""

    cleaned_error_output = error_output.strip()
    if cleaned_error_output:
        return cleaned_error_output

    failure_messages = [
        "unreachable",
        "request timed out",
        "could not find host",
        "general failure",
    ]

    for line in ping_output.splitlines():
        lowercase_line = line.lower()

        for failure_message in failure_messages:
            if failure_message in lowercase_line:
                return line.strip()

    return "no ICMP echo reply received"



def extract_default_gateway(route_output: str) -> str | None:
    """Return the gateway from the first IPv4 default-route row."""

    for line in route_output.splitlines():
        fields = line.split()

        # Header and blank lines do not contain five route fields.
        if len(fields) < 5:
            continue

        destination_is_default = fields[0] == "0.0.0.0"
        netmask_is_default = fields[1] == "0.0.0.0"

        if destination_is_default:
            if netmask_is_default:
                gateway = fields[2]
                return gateway
    return None


def discover_default_gateway() -> str | None:
    """Run route.exe and return the active IPv4 default gateway."""

    command = ["route", "print", "-4", "0.0.0.0"]

    try:
        route_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return None

    if route_process.returncode != 0:
        return None

    route_output = route_process.stdout
    gateway = extract_default_gateway(route_output)
    return gateway


def extract_latency_ms(ping_output: str) -> int | None:
    """Extract the latency number from text such as 'time=6ms'."""

    latency_pattern = r"time[=<](\d+)ms"
    latency_match = re.search(latency_pattern, ping_output, re.IGNORECASE)

    if latency_match is None:
        return None

    latency_text = latency_match.group(1)
    return int(latency_text)


def ping_once(target: str, timeout_ms: int) -> ProbeResult:
    """Send one ICMP echo request using the Windows ping command."""

    timestamp = datetime.now(timezone.utc).isoformat()
    command = ["ping", "-n", "1", "-w", str(timeout_ms), target]

    try:
        ping_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=(timeout_ms / 1000) + 2,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(
            target=target,
            timestamp=timestamp,
            success=False,
            latency_ms=None,
            error="command timed out",
        )
    except OSError as operating_system_error:
        return ProbeResult(
            target=target,
            timestamp=timestamp,
            success=False,
            latency_ms=None,
            error=str(operating_system_error),
        )

    ping_output = ping_process.stdout
    error_output = ping_process.stderr
    windows_reported_failure = output_contains_failure(ping_output)

    # Windows ping can report an unreachable destination with a zero return code.
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

    latency_ms = extract_latency_ms(ping_output)
    return ProbeResult(
        target=target,
        timestamp=timestamp,
        success=True,
        latency_ms=latency_ms,
        error=None,
    )

def check_default_gateway(
    gateway: str | None,
    timeout_ms: int,
) -> DiagnosticCheck:
    """Return a diagnostic result for the supplied default gateway."""

    if gateway is None:
        return DiagnosticCheck(
            name="Default gateway",
            success=False,
            detail="No IPv4 default route was found",
        )

    probe_result = ping_once(gateway, timeout_ms)

    if probe_result.success:
        if probe_result.latency_ms is not None:
            detail = f"{gateway} replied in {probe_result.latency_ms} ms"
        else:
            detail = f"{gateway} replied; latency was unavailable"

        return DiagnosticCheck(
            name="Default gateway",
            success=True,
            detail=detail,
        )

    if probe_result.error is not None:
        failure_reason = probe_result.error
    else:
        failure_reason = "no ICMP echo reply was received"

    detail = f"{gateway} failed: {failure_reason}"

    return DiagnosticCheck(
        name="Default gateway",
        success=False,
        detail=detail,
    )
def check_public_ip(target: str, timeout_ms: int) -> DiagnosticCheck:
    """Test routed Internet connectivity using a known public IP address."""

    public_ip_result = ping_once(target, timeout_ms)

    if public_ip_result.success:
        if public_ip_result.latency_ms is not None:
            detail = f"{target} replied in {public_ip_result.latency_ms} ms"
        else:
            detail = f"{target} replied; latency was unavailable"

        return DiagnosticCheck(
            name="Public IP",
            success=True,
            detail=detail,
        )

    if public_ip_result.error is not None:
        failure_reason = public_ip_result.error
    else:
        failure_reason = "no ICMP echo reply was received"

    detail = f"{target} failed: {failure_reason}"

    return DiagnosticCheck(
        name="Public IP",
        success=False,
        detail=detail,
    )

def check_dns(hostname: str) -> DiagnosticCheck:
    """Test whether Windows can resolve a hostname into an IP address."""

    try:
        resolved_ip = socket.gethostbyname(hostname)
    except socket.gaierror as error:
        detail = f"{hostname} could not be resolved: {error}"

        return DiagnosticCheck(
            name="DNS resolution",
            success=False,
            detail=detail,
        )

    detail = f"{hostname} resolved to {resolved_ip}"

    return DiagnosticCheck(
        name="DNS resolution",
        success=True,
        detail=detail,
    )


def check_tcp_service(
    hostname: str,
    port: int,
    timeout_ms: int,
) -> DiagnosticCheck:
    """Test whether a TCP connection can be established to a service port."""

    # The socket API accepts seconds; the CLI accepts milliseconds.
    timeout_seconds = timeout_ms / 1000

    try:
        connection = socket.create_connection(
            (hostname, port),
            timeout=timeout_seconds,
        )
    except OSError as error:
        detail = f"{hostname}:{port} could not establish TCP: {error}"

        return DiagnosticCheck(
            name="TCP service",
            success=False,
            detail=detail,
        )
    connection.close()

    detail = f"{hostname}:{port} accepted a TCP connection"

    return DiagnosticCheck(
        name="TCP service",
        success=True,
        detail=detail,
    )

def check_https_application(
    hostname: str,
    port: int,
    timeout_ms: int,
) -> DiagnosticCheck:
    """Test whether an HTTPS service completes TLS and returns an HTTP response."""

    timeout_seconds = timeout_ms / 1000

    connection = http.client.HTTPSConnection(
        hostname,
        port=port,
        timeout=timeout_seconds,
    )

    try:
        connection.request("HEAD", "/")
        response = connection.getresponse()

    except ssl.SSLError as error:
        return DiagnosticCheck(
            name="HTTPS application",
            success=False,
            detail=f"{hostname}:{port} failed TLS: {error}",
        )
    except (OSError, http.client.HTTPException) as error:
        return DiagnosticCheck(
            name="HTTPS application",
            success=False,
            detail=f"{hostname}:{port} failed HTTPS: {error}",
        )
    finally:
        connection.close()

    status_code = response.status
    reason = response.reason
    # 2xx and 3xx responses indicate a successful request or redirect. A 4xx or
    # 5xx response still proves that HTTP replied, but it indicates that the
    # requested application path was not successful.
    http_succeeded = 200 <= status_code < 400

    return DiagnosticCheck(
        name="HTTPS application",
        success=http_succeeded,
        detail=f"{hostname}:{port} returned HTTP {status_code} {reason}",
    )



def diagnose_dependencies(
    gateway_check: DiagnosticCheck,
    public_ip_check: DiagnosticCheck,
    dns_check: DiagnosticCheck,
    tcp_check: DiagnosticCheck,
    https_check: DiagnosticCheck,
) -> str:
    """Identify the earliest failed dependency in the network path."""

    if not gateway_check.success:
        return "Likely local network problem: the default gateway was unreachable."

    if not public_ip_check.success:
        return "Likely Internet path problem: the gateway worked but the public IP failed."

    if not dns_check.success:
        return "Likely DNS problem: Internet routing worked but name resolution failed."

    if not tcp_check.success:
        return "Likely service-path problem: DNS worked but the TCP connection failed."

    if not https_check.success:
        return f"Likely HTTPS application-layer problem: {https_check.detail}"

    return "No dependency failure detected."


def display_diagnostic_check(check: DiagnosticCheck) -> None:
    """Display one dependency check in a consistent format."""

    if check.success:
        status = "PASS"
    else:
        status = "FAIL"

    print(f"[{status}] {check.name}: {check.detail}")


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


def format_probe_measurement(result: ProbeResult) -> str:
    """Return a compact success, latency, or failure description."""

    if not result.success:
        return f"FAILED ({result.error})"

    if result.latency_ms is None:
        return "OK (latency unavailable)"

    return f"OK ({result.latency_ms} ms)"


def display_path_observation(
    observation_number: int,
    total_observations: int | None,
    observation: PathObservation,
) -> None:
    """Display gateway and public-path evidence beside each other."""

    gateway_measurement = format_probe_measurement(observation.gateway_result)
    public_measurement = format_probe_measurement(observation.public_result)

    if total_observations is None:
        print(f"\nObservation {observation_number}")
    else:
        print(f"\nObservation {observation_number} of {total_observations}")

    print(f"Timestamp: {observation.timestamp}")
    print(f"Gateway:  {gateway_measurement}")
    print(f"Public:   {public_measurement}")
    print(f"Diagnosis: {observation.diagnosis}")


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


def create_unavailable_gateway_result(timestamp: str) -> ProbeResult:
    """Return failed probe evidence when no default gateway was discovered."""

    return ProbeResult(
        target="default gateway",
        timestamp=timestamp,
        success=False,
        latency_ms=None,
        error="No IPv4 default route was found",
    )


def classify_path_observation(
    gateway_result: ProbeResult,
    public_result: ProbeResult,
    latency_threshold_ms: int,
) -> str:
    """Classify reachability and latency evidence from one pair."""

    if not gateway_result.success and not public_result.success:
        return "LOCAL_PATH_SUSPECTED"

    if gateway_result.success and not public_result.success:
        return "UPSTREAM_PATH_SUSPECTED"

    if not gateway_result.success and public_result.success:
        return "GATEWAY_ICMP_UNAVAILABLE"

    if gateway_result.latency_ms is None:
        return "LATENCY_UNAVAILABLE"

    if public_result.latency_ms is None:
        return "LATENCY_UNAVAILABLE"

    gateway_latency_high = gateway_result.latency_ms >= latency_threshold_ms
    public_latency_high = public_result.latency_ms >= latency_threshold_ms

    if gateway_latency_high and public_latency_high:
        return "LOCAL_LATENCY_SUSPECTED"

    if not gateway_latency_high and public_latency_high:
        return "UPSTREAM_LATENCY_SUSPECTED"

    if gateway_latency_high and not public_latency_high:
        return "GATEWAY_ICMP_SLOW"

    return "HEALTHY"


def collect_path_observation(
    gateway: str | None,
    public_target: str,
    timeout_ms: int,
    latency_threshold_ms: int,
) -> PathObservation:
    """Probe the gateway and public target and keep their results together."""

    # Record when this paired monitoring cycle began. Each individual
    # ProbeResult also retains the exact time at which its own ping began.
    observation_timestamp = datetime.now(timezone.utc).isoformat()

    if gateway is None:
        gateway_result = create_unavailable_gateway_result(observation_timestamp)
    else:
        gateway_result = ping_once(gateway, timeout_ms)

    public_result = ping_once(public_target, timeout_ms)
    diagnosis = classify_path_observation(
        gateway_result,
        public_result,
        latency_threshold_ms,
    )

    return PathObservation(
        timestamp=observation_timestamp,
        gateway_result=gateway_result,
        public_result=public_result,
        diagnosis=diagnosis,
    )


def run_path_monitoring(
    gateway: str | None,
    public_target: str,
    timeout_ms: int,
    latency_threshold_ms: int,
    count: int | None,
    duration_minutes: float | None,
    interval: float,
    csv_path: str | None = None,
) -> list[PathObservation]:
    """Collect paired observations and persist them as they arrive."""

    observations: list[PathObservation] = []

    if csv_path is not None:
        initialize_path_observation_csv(csv_path)

    end_time = None
    if duration_minutes is not None:
        duration_seconds = duration_minutes * 60
        end_time = time.monotonic() + duration_seconds

    try:
        while True:
            if count is not None:
                if len(observations) >= count:
                    break

            if end_time is not None:
                if time.monotonic() >= end_time:
                    break

            observation = collect_path_observation(
                gateway=gateway,
                public_target=public_target,
                timeout_ms=timeout_ms,
                latency_threshold_ms=latency_threshold_ms,
            )
            observations.append(observation)

            if csv_path is not None:
                append_path_observation_to_csv(csv_path, observation)

            observation_number = len(observations)
            display_path_observation(observation_number, count, observation)

            count_finished = count is not None and observation_number >= count
            duration_finished = end_time is not None and time.monotonic() >= end_time

            if count_finished or duration_finished:
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user; preserving collected evidence.")

    return observations


def calculate_session_assessment(
    observations: list[PathObservation],
) -> SessionAssessment:
    """Count classifications and describe the dominant non-healthy pattern."""

    diagnosis_counts: dict[str, int] = {}

    for observation in observations:
        diagnosis = observation.diagnosis
        current_count = diagnosis_counts.get(diagnosis, 0)
        diagnosis_counts[diagnosis] = current_count + 1

    total_observations = len(observations)
    healthy_observations = diagnosis_counts.get("HEALTHY", 0)
    degraded_observations = total_observations - healthy_observations

    if total_observations == 0:
        return SessionAssessment(
            total_observations=0,
            healthy_observations=0,
            degraded_observations=0,
            diagnosis_counts=diagnosis_counts,
            dominant_diagnosis=None,
            conclusion="No observations were collected, so the path could not be assessed.",
        )

    if degraded_observations == 0:
        return SessionAssessment(
            total_observations=total_observations,
            healthy_observations=healthy_observations,
            degraded_observations=0,
            diagnosis_counts=diagnosis_counts,
            dominant_diagnosis=None,
            conclusion=(
                "No degradation was detected during this sample. This does not prove "
                "the connection is always healthy."
            ),
        )

    dominant_diagnosis = None
    dominant_count = 0

    # Iterate through a fixed priority order so equal counts always produce the
    # same result. HEALTHY is excluded because we want the dominant problem.
    for diagnosis in PATH_DIAGNOSIS_ORDER:
        if diagnosis == "HEALTHY":
            continue

        count = diagnosis_counts.get(diagnosis, 0)
        if count > dominant_count:
            dominant_diagnosis = diagnosis
            dominant_count = count

    conclusions = {
        "LOCAL_PATH_SUSPECTED": (
            "Local-path failures were the most frequent issue. Investigate the local "
            "interface, Wi-Fi or Ethernet link, switch path, and default gateway."
        ),
        "UPSTREAM_PATH_SUSPECTED": (
            "The gateway remained reachable while the public target failed. Investigate "
            "the ISP or upstream route, while remembering that the target may block ICMP."
        ),
        "LOCAL_LATENCY_SUSPECTED": (
            "High latency was already visible at the gateway. Investigate local congestion, "
            "Wi-Fi contention, interface errors, or gateway load."
        ),
        "UPSTREAM_LATENCY_SUSPECTED": (
            "The gateway remained responsive while public latency was high. Investigate "
            "the ISP, upstream route, or destination path."
        ),
        "GATEWAY_ICMP_UNAVAILABLE": (
            "The public target replied while the gateway did not. The gateway may block or "
            "deprioritise ICMP, so this alone does not prove a local failure."
        ),
        "GATEWAY_ICMP_SLOW": (
            "Public latency remained normal while gateway ICMP was slow. The gateway may "
            "deprioritise ICMP; corroborate this result with other evidence."
        ),
        "LATENCY_UNAVAILABLE": (
            "Some replies succeeded but their latency could not be parsed, so latency-based "
            "classification was unavailable for those observations."
        ),
    }

    conclusion = conclusions.get(
        dominant_diagnosis,
        "Non-healthy observations were recorded, but no known pattern dominated.",
    )

    return SessionAssessment(
        total_observations=total_observations,
        healthy_observations=healthy_observations,
        degraded_observations=degraded_observations,
        diagnosis_counts=diagnosis_counts,
        dominant_diagnosis=dominant_diagnosis,
        conclusion=conclusion,
    )


def display_session_assessment(assessment: SessionAssessment) -> None:
    """Display classification counts and the cautious session conclusion."""

    print("\nSession assessment")
    print(f"Observations: {assessment.total_observations}")
    print(f"Healthy:      {assessment.healthy_observations}")
    print(f"Non-healthy:  {assessment.degraded_observations}")

    print("Classifications:")
    for diagnosis in PATH_DIAGNOSIS_ORDER:
        count = assessment.diagnosis_counts.get(diagnosis, 0)
        if count > 0:
            print(f"  {diagnosis}: {count}")

    if assessment.dominant_diagnosis is not None:
        print(f"Dominant issue: {assessment.dominant_diagnosis}")

    print(f"Conclusion: {assessment.conclusion}")


def calculate_summary(results: list[ProbeResult]) -> ProbeSummary:
    """Calculate packet loss, latency, and simplified jitter statistics."""

    received_count = 0
    successful_latencies: list[int] = []

    for probe_result in results:
        # A successful reply still counts as received even if latency parsing
        # was unavailable for that particular Windows ping output.
        if probe_result.success:
            received_count = received_count + 1

        # Only numeric latency values can participate in latency calculations.
        if probe_result.success and probe_result.latency_ms is not None:
            successful_latencies.append(probe_result.latency_ms)

    sent_count = len(results)
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


def save_results_to_csv(file_path: str, results: list[ProbeResult]) -> None:
    """Save timestamped probe evidence to a CSV file."""

    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        mode="w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            ["target", "timestamp_utc", "success", "latency_ms", "error"]
        )

        for result in results:
            writer.writerow(
                [
                    result.target,
                    result.timestamp,
                    result.success,
                    result.latency_ms,
                    result.error,
                ]
            )


def create_session_csv_path() -> str:
    """Create a unique default path for one monitoring session."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    output_path = Path("output") / f"lagscope-session-{timestamp}.csv"
    return str(output_path)


def path_observation_to_row(observation: PathObservation) -> list[object]:
    """Convert one paired observation into its CSV representation."""

    return [
        observation.timestamp,
        observation.diagnosis,
        observation.gateway_result.target,
        observation.gateway_result.success,
        observation.gateway_result.latency_ms,
        observation.gateway_result.error,
        observation.public_result.target,
        observation.public_result.success,
        observation.public_result.latency_ms,
        observation.public_result.error,
    ]


def initialize_path_observation_csv(file_path: str) -> None:
    """Create a paired-observation CSV and write its header."""

    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(mode="w", newline="", encoding="utf-8") as csv_file:
        csv.writer(csv_file).writerow(PATH_OBSERVATION_HEADER)


def append_path_observation_to_csv(
    file_path: str,
    observation: PathObservation,
) -> None:
    """Append and flush one observation so completed evidence survives a crash."""

    output_path = Path(file_path)
    with output_path.open(mode="a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(path_observation_to_row(observation))
        csv_file.flush()


def save_path_observations_to_csv(
    file_path: str,
    observations: list[PathObservation],
) -> None:
    """Save paired gateway/public evidence and diagnoses to a CSV file."""

    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        mode="w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(PATH_OBSERVATION_HEADER)

        for observation in observations:
            writer.writerow(path_observation_to_row(observation))


def display_summary(summary: ProbeSummary, heading: str = "Summary") -> None:
    """Display aggregate statistics calculated from all probes."""

    print(f"\n{heading}")
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


def read_command_line_settings(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    """Parse and validate command-line settings."""

    parser = argparse.ArgumentParser(
        description="Run LagScope V2 network diagnostics and path monitoring."
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"LagScope {VERSION}",
    )

    parser.add_argument(
        "--target",
        default="8.8.8.8",
        help="IP address or hostname to probe (default: 8.8.8.8)",
    )
    parser.add_argument(
        "--service-host",
        default="example.com",
        help="Hostname to test with DNS, TCP, TLS, and HTTP (default: example.com)",
    )

    parser.add_argument(
        "--service-port",
        type=int,
        default=443,
        help="HTTPS service port to test (default: 443)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=1000,
        help="Maximum ping wait in milliseconds (default: 1000)",
    )

    parser.add_argument(
        "--latency-threshold-ms",
        type=int,
        default=100,
        help="Latency at or above which a path is considered slow (default: 100)",
    )

    monitoring_limit = parser.add_mutually_exclusive_group()

    monitoring_limit.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of paired observations to collect (default: 5)",
    )

    monitoring_limit.add_argument(
        "--duration-minutes",
        type=float,
        default=None,
        help="Minutes to monitor instead of using a fixed observation count",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds to wait between probes (default:1.0)",

    )

    parser.add_argument(
        "--csv",
        default=None,
        help="Optional path for saving timestamped probe results as CSV",
    )

    settings = parser.parse_args(arguments)

    if settings.count is None and settings.duration_minutes is None:
        settings.count = 5

    if settings.timeout_ms <= 0:
        parser.error("--timeout-ms must be greater than zero")

    if settings.latency_threshold_ms <= 0:
        parser.error("--latency-threshold-ms must be greater than zero")

    if settings.count is not None and settings.count <= 0:
        parser.error("--count must be greater than zero")

    if settings.duration_minutes is not None:
        if settings.duration_minutes <= 0:
            parser.error("--duration-minutes must be greater than zero")

    if settings.interval < 0:
        parser.error("--interval must be 0 or greater")

    if settings.service_port < 1:
        parser.error("--service-port must be between 1 and 65535")

    if settings.service_port > 65535:
        parser.error("--service-port must be between 1 and 65535")

    return settings




def main() -> None:
    settings = read_command_line_settings()

    print("Dependency checks")
    gateway = discover_default_gateway()
    gateway_check = check_default_gateway(gateway, settings.timeout_ms)
    display_diagnostic_check(gateway_check)

    public_ip_check = check_public_ip(settings.target, settings.timeout_ms)
    display_diagnostic_check(public_ip_check)

    dns_check = check_dns(settings.service_host)
    display_diagnostic_check(dns_check)

    tcp_check = check_tcp_service(
        settings.service_host,
        settings.service_port,
        settings.timeout_ms,
    )
    display_diagnostic_check(tcp_check)

    https_check = check_https_application(
        settings.service_host,
        settings.service_port,
        settings.timeout_ms,
    )
    display_diagnostic_check(https_check)

    diagnosis = diagnose_dependencies(
        gateway_check,
        public_ip_check,
        dns_check,
        tcp_check,
        https_check,
    )

    print("\nDiagnosis")
    print(diagnosis)

    if settings.csv is None:
        csv_path = create_session_csv_path()
    else:
        csv_path = settings.csv

    print("\nPaired path monitoring")
    observations = run_path_monitoring(
        gateway=gateway,
        public_target=settings.target,
        timeout_ms=settings.timeout_ms,
        latency_threshold_ms=settings.latency_threshold_ms,
        count=settings.count,
        duration_minutes=settings.duration_minutes,
        interval=settings.interval,
        csv_path=csv_path,
    )

    if not observations:
        print("\nNo monitoring observations were collected.")
        print(f"CSV saved to: {csv_path}")
        return

    session_assessment = calculate_session_assessment(observations)
    display_session_assessment(session_assessment)

    gateway_results: list[ProbeResult] = []
    public_results: list[ProbeResult] = []

    for observation in observations:
        gateway_results.append(observation.gateway_result)
        public_results.append(observation.public_result)

    gateway_summary = calculate_summary(gateway_results)
    public_summary = calculate_summary(public_results)

    display_summary(gateway_summary, "Gateway summary")
    display_summary(public_summary, "Public target summary")

    print(f"\nCSV saved to: {csv_path}")

if __name__ == "__main__":
    main()
