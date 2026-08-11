# LagScope

LagScope is a Windows-first gaming network diagnostic tool. Its purpose is to
record evidence during lag, ping spikes, and disconnects, then help distinguish
between a local-network problem and a wider connectivity problem.

## Current status

The current milestone performs repeated, configurable ICMP probes and reports:

- successful and failed probe evidence;
- sent, received, and lost probe counts;
- packet-loss percentage;
- minimum, average, and maximum round-trip latency; and
- simplified jitter, defined as the mean absolute change between consecutive
  successful round-trip latency measurements.

## Why I am building it

Games often report only a generic connection warning. That does not reveal
whether the problem is the local gateway, the Internet connection, DNS, or the
remote service. LagScope will test those dependencies separately and preserve
timestamped evidence for later analysis.

## Run LagScope

From PowerShell:

```powershell
.\.venv\Scripts\python.exe .\src\lagscope.py
.\.venv\Scripts\python.exe .\src\lagscope.py --target 8.8.8.8 --count 10 --interval 1.0 --timeout-ms 1500
.\.venv\Scripts\python.exe .\src\lagscope.py --help
```

The defaults are target `8.8.8.8`, five probes, a one-second interval, and a
1,000-millisecond ICMP reply timeout.

The `.venv` directory is a project-local Python environment. It keeps the
runtime and any future packages isolated from unrelated Python projects and is
excluded from Git because it can be recreated.

## Five-day target

- Discover local adapter, gateway, DNS, and routing information.
- Probe the gateway, a public IP, DNS, and configurable remote targets.
- Calculate latency, packet loss, and jitter. **Implemented.**
- Store timestamped results in CSV or JSON.
- Classify likely local, DNS, Internet-path, or remote-target incidents.
- Include automated tests, example output, and an architecture explanation.

## Current limitations

- The probe implementation currently depends on the English output format of
  Windows `ping.exe`.
- ICMP reachability does not prove that a remote application or TCP service is
  healthy.
- Jitter is a deliberately simple diagnostic measure, not an implementation of
  RTP interarrival jitter.
- Gateway discovery, DNS, TCP, incident classification, and report export are
  planned for the next milestones.
