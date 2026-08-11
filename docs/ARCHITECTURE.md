# LagScope architecture

LagScope will diagnose connectivity in dependency order:

```text
Local adapter
    -> default gateway
    -> public Internet IP
    -> DNS resolution
    -> remote TCP service
    -> application response
```

The current milestone implements a reusable Windows ICMP probe, repeats it at a
configurable interval, preserves each structured `ProbeResult`, and calculates
an aggregate `ProbeSummary` containing packet loss, latency, and simplified
jitter statistics.

## Current execution flow

```text
read_command_line_settings
    -> run_probes
        -> ping_once
        -> display_probe_result
    -> calculate_summary
    -> display_summary
```

`ProbeResult` represents one observation. `ProbeSummary` represents statistics
calculated from all observations. Separating collection, calculation, and
display keeps the calculation logic testable without running a live network
probe.

## Planned components

1. **Discovery** - identifies adapters, addresses, routes, gateway, and DNS.
2. **Probes** - performs ICMP, DNS, TCP, and HTTP tests.
3. **Metrics** - calculates latency, packet loss, and simplified jitter.
4. **Storage** - writes timestamped structured evidence.
5. **Classifier** - identifies the most likely failure domain.
6. **Reporter** - produces console and incident-report output.

The current milestone implements the ICMP portion of **Probes**, the initial
**Metrics** component, and console output from **Reporter**. The other
components remain planned work.
