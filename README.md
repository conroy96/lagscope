# LagScope 2.0

LagScope is a Windows-first command-line tool for collecting evidence during
gaming lag, latency spikes, and disconnects. It compares the local path to the
default gateway with a public Internet path so that a vague report such as
"the game lagged" becomes a more useful failure-domain hypothesis.

## What it does

Before monitoring, LagScope checks dependencies in order:

```text
default gateway -> public IP -> DNS resolution -> TCP service -> TLS/HTTPS
```

During monitoring, every observation contains two consecutive ICMP probes:

- the Windows IPv4 default gateway, representing the local LAN/Wi-Fi path;
- a configurable public target, representing the local path plus the wider
  Internet path.

LagScope then:

- records success, failure, latency, timestamp, and error evidence;
- classifies likely local-path, upstream-path, or ICMP-specific degradation;
- produces a session-level assessment from the frequency of those classifications;
- calculates separate gateway and public packet-loss, latency, and simplified
  jitter summaries;
- supports a fixed observation count or a timed gaming session;
- preserves completed observations when stopped with `Ctrl+C`;
- saves every paired observation to an automatically named CSV file; and
- includes deterministic automated tests that do not depend on a live network.

## LagScope and Wireshark

LagScope is not a packet-capture replacement. Wireshark captures and dissects
individual frames and packets from an interface. LagScope instead runs a small,
controlled set of active checks and interprets their results as a likely failure
domain.

The tools complement one another:

1. use LagScope during a gaming session to timestamp a problem and decide whether
   the evidence points toward the local path, upstream path, DNS, TCP, or HTTPS;
2. use Wireshark when packet-level evidence is needed to investigate that narrowed
   area in greater depth.

## Quick start

Requirements:

- Windows 10 or Windows 11;
- Python 3.10 or newer; and
- PowerShell.

Create the local virtual environment once:

```powershell
py -3 -m venv .venv
```

LagScope uses only the Python standard library, so no third-party packages are
required.

Run a short check directly:

```powershell
.\.venv\Scripts\python.exe .\src\lagscope.py --count 5
```

Check the installed project version:

```powershell
.\.venv\Scripts\python.exe .\src\lagscope.py --version
```

Run a two-hour gaming session with the PowerShell launcher:

```powershell
.\Start-LagScope.ps1 -Minutes 120
```

If the local PowerShell execution policy blocks scripts, use a process-only
bypass:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-LagScope.ps1 -Minutes 120
```

## Useful options

```powershell
# Treat latency at or above 80 ms as slow.
.\Start-LagScope.ps1 -Minutes 120 -LatencyThresholdMs 80

# Select another public target and sampling interval.
.\Start-LagScope.ps1 -Minutes 60 -Target 1.1.1.1 -IntervalSeconds 2

# Use the Python CLI and choose a specific CSV path.
.\.venv\Scripts\python.exe .\src\lagscope.py `
    --duration-minutes 60 `
    --csv .\output\ranked-session.csv

# Display every accepted option.
.\.venv\Scripts\python.exe .\src\lagscope.py --help
```

`--count` and `--duration-minutes` are mutually exclusive. If neither is
provided, LagScope collects five paired observations.

## Interpreting classifications

| Gateway evidence | Public evidence | Classification |
|---|---|---|
| Failed | Failed | `LOCAL_PATH_SUSPECTED` |
| Successful | Failed | `UPSTREAM_PATH_SUSPECTED` |
| Failed | Successful | `GATEWAY_ICMP_UNAVAILABLE` |
| Slow | Slow | `LOCAL_LATENCY_SUSPECTED` |
| Normal | Slow | `UPSTREAM_LATENCY_SUSPECTED` |
| Slow | Normal | `GATEWAY_ICMP_SLOW` |
| Successful, missing latency | Successful | `LATENCY_UNAVAILABLE` |
| Normal | Normal | `HEALTHY` |

These classifications narrow the likely failure domain; they do not claim to
prove a root cause.

## Evidence output

If `--csv` is omitted, LagScope creates a file such as:

```text
output/lagscope-session-20260813-003000-123456.csv
```

Each row keeps the gateway and public measurements together with their shared
observation timestamp and diagnosis. This preserves the correlation required
to decide whether a spike was already visible on the local hop.

At the end of a session, LagScope also displays:

- the number of healthy and non-healthy observations;
- a count for every observed classification;
- the most frequent non-healthy classification; and
- a cautious troubleshooting conclusion based on that pattern.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests mock live probing, HTTPS connections, and elapsed time. They can
therefore reproduce success, failure, latency, TLS, HTTP, duration, and
interruption scenarios without relying on the current Internet connection.

## Current limitations

- The implementation targets Windows and parses English `ping.exe` output.
- Gateway and public probes are consecutive rather than simultaneous.
- ICMP may be blocked, rate-limited, or deprioritised by otherwise healthy
  devices.
- The HTTPS check sends `HEAD /` to one configured service. A successful result
  does not prove every application path or transaction is healthy.
- Some valid applications reject `HEAD` requests or require a different path.
- DNS results may come from a cache.
- Diagnoses and the configurable latency threshold are heuristics.
- CSV evidence is written when monitoring finishes or is stopped cleanly;
  abrupt process or power failure can lose the current in-memory session.
- The program currently discovers the Windows IPv4 default route only.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the execution flow and
design boundaries.
