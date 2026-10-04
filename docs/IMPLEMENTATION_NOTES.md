# Implementation notes

This document records the decisions that are easiest to miss when reading the
source. General Python syntax is left to the Python documentation; these notes
focus on behaviour specific to LagScope.

## Windows command boundary

LagScope calls the Windows `route` and `ping` programs through
`subprocess.run()`. Their output is treated as external input rather than as a
stable Python API.

`extract_default_gateway()` looks for the first IPv4 route whose destination and
netmask are both `0.0.0.0`. `extract_latency_ms()` accepts both `time=6ms` and
`time<1ms`. Known failure messages are checked even when `ping.exe` returns a
zero exit status because Windows can report an unreachable destination that way.

The parsing functions are kept separate from process execution so representative
command output can be tested without depending on the machine running the tests.

## Dependency checks

Startup checks run from the nearest dependency to the furthest:

```text
default gateway -> public target -> DNS -> TCP -> TLS/HTTPS
```

The configured `--target` is used by both the startup public-IP check and paired
monitoring. This keeps the two sets of evidence comparable.

TCP and HTTPS are separate checks. A completed TCP handshake proves transport
reachability to the selected port; it does not prove that TLS negotiation or the
HTTP application succeeds.

## Evidence model

`ProbeResult` represents one ICMP attempt. `PathObservation` groups a gateway
probe and a public probe under one observation timestamp and classification.
Keeping the pair together prevents later reporting from losing the relationship
between the local and wider-path measurements.

Classifications use names such as `LOCAL_PATH_SUSPECTED` deliberately. Two ICMP
probes can narrow a failure domain, but they cannot prove a physical root cause.

## Persistence

The session CSV is created before monitoring. Every completed observation is
appended and flushed immediately. A later crash or power loss may interrupt the
current probe, but it will not remove rows that were already completed.

The same observations remain in memory to calculate the final packet-loss,
latency, jitter, and session summaries.

## Tests

Network calls, HTTPS connections, time, and interruptions are mocked so the test
suite is deterministic. Windows route and ping samples exercise the text-parsing
boundary directly. Integration tests verify that an interrupted session retains
both its in-memory results and its completed CSV rows.
