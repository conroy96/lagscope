# LagScope interview demo

## One-minute explanation

LagScope is a Windows-first command-line tool I built to collect useful evidence
during gaming lag and disconnects. It checks the dependency path from the local
gateway through public reachability, DNS, TCP, TLS, and HTTP. During monitoring,
it pairs a gateway ping with a public-target ping so a latency spike can be
compared with the local hop at approximately the same time. It stores the raw
evidence in CSV, calculates separate statistics, and reports a likely failure
domain. The conclusions are deliberately cautious because ICMP evidence cannot
prove a physical root cause.

## Demonstration

From PowerShell in the repository directory:

```powershell
# Confirm the version and accepted options.
.\.venv\Scripts\python.exe .\src\lagscope.py --version
.\.venv\Scripts\python.exe .\src\lagscope.py --help

# Run a short successful session.
.\.venv\Scripts\python.exe .\src\lagscope.py --count 3 --interval 0.2

# Demonstrate DNS failure isolation.
.\.venv\Scripts\python.exe .\src\lagscope.py `
    --service-host definitely-not-real.invalid `
    --count 1 `
    --timeout-ms 500

# Demonstrate a TLS certificate failure.
.\.venv\Scripts\python.exe .\src\lagscope.py `
    --service-host wrong.host.badssl.com `
    --service-port 443 `
    --count 1 `
    --timeout-ms 2000

# Run the deterministic automated suite.
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## What the demonstration proves

- The CLI accepts and validates configurable inputs.
- Each dependency produces structured evidence instead of crashing the program.
- TCP success and HTTPS success are treated as separate facts.
- Paired local and public measurements can distinguish likely local and upstream
  patterns.
- Automated tests reproduce failures without depending on the live network.

## What it does not prove

- A successful sample does not prove the connection is always healthy.
- Ping failure does not prove the target is down because ICMP may be filtered or
  deprioritised.
- The diagnosis narrows the likely failure domain; it does not replace packet
  capture, device logs, interface counters, or application telemetry.

## AI use

I defined the problem, diagnostic sequence, evidence model, checkpoints, and
expected behaviour. I used AI to help implement and review parts of the code and
tests, then ran the program, inspected failures, verified the behaviour, and
worked through how the functions connect. I would describe that process honestly
rather than claim that every line was written from memory.
