# LagScope architecture

LagScope is organised around two related diagnostic activities:

1. a startup dependency check that identifies the earliest failed layer; and
2. repeated paired monitoring that compares the local and wider network paths.

## Startup dependency flow

```text
discover IPv4 default gateway
        |
        v
gateway ICMP -> public IP ICMP -> DNS resolution -> TCP connection -> TLS/HTTPS
        |
        v
report the earliest failed dependency
```

The order matters. For example, investigating DNS first is not useful if the
machine cannot reach its local gateway.

The TCP check establishes and immediately closes a connection. The separate
HTTPS check then negotiates TLS, validates the certificate using Python's
default trust store, sends `HEAD /`, and records the HTTP status. Keeping these
checks separate distinguishes transport reachability from application-layer
behaviour.

## Paired monitoring flow

```text
run_path_monitoring
        |
        v
collect_path_observation
        |
        +--> ping_once(default gateway) --> ProbeResult
        |
        +--> ping_once(public target) ----> ProbeResult
        |
        v
classify_path_observation
        |
        v
PathObservation
```

`ProbeResult` stores the evidence from one ping:

```text
target, timestamp, success, latency_ms, error
```

`PathObservation` groups the gateway and public `ProbeResult` objects with a
shared observation timestamp and diagnosis. Keeping both paths together makes
the comparison explicit in console and CSV output.

## Session flow

```text
read and validate command-line settings
        |
run startup dependency checks
        |
monitor by count or monotonic duration
        |
extract gateway and public result lists
        |
calculate independent ProbeSummary objects
        |
calculate one SessionAssessment from all classifications
        |
display summaries and save paired CSV evidence
```

Count and duration modes are mutually exclusive. Duration mode uses
`time.monotonic()` so Windows wall-clock corrections cannot make a session end
too early or too late. `KeyboardInterrupt` is caught inside monitoring so
completed observations can still be returned, summarised, and saved.

`SessionAssessment` counts the classifications from every `PathObservation`,
reports the most frequent non-healthy pattern, and maps it to a cautious next
troubleshooting step. It preserves the distinction between evidence and
interpretation: the underlying paired observations remain available in CSV.

## Classification boundary

The classifier produces a likely failure-domain label from reachability and
latency evidence. It uses cautious names such as `LOCAL_PATH_SUSPECTED` because
two consecutive ICMP measurements cannot prove a physical root cause.

Reachability is evaluated before latency. A failed probe has no numerical
latency, so comparing latency before handling failure would be invalid.

## Storage boundary

The paired CSV writer creates one row per `PathObservation`. It stores both
paths, both errors, and the classification in the same record. Files are
automatically named with a UTC timestamp unless the user supplies `--csv`.

The file and header are created before monitoring starts. Each completed
observation is appended and flushed immediately. Results also remain in memory
for the end-of-session assessment, but completed CSV evidence no longer depends
on a clean shutdown.

## Current source layout

The application remains in one `src/lagscope.py` file while behaviour is still
being developed and learned. Once the responsibilities are stable, a dedicated
refactor can separate models, probes, monitoring, diagnosis, reporting, and CLI
coordination without mixing structural work with feature changes.

This progression keeps the Git history clear: validate behaviour first, then
improve maintainability while preserving the tested external behaviour.
