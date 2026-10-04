# Changelog

## Unreleased

- Use the configured public target consistently for dependency checks and
  paired monitoring.
- Persist each completed observation immediately instead of waiting for the end
  of the session.
- Add direct tests for Windows route and ping output parsing.
- Replace tutorial-style source annotations with concise implementation comments.

## 2.0.0

- Added a distinct TLS and HTTPS application-layer dependency check.
- Added structured handling for successful HTTP responses, HTTP error statuses,
  certificate failures, timeouts, and malformed HTTP responses.
- Added a session-level assessment that counts classifications and identifies
  the dominant non-healthy pattern without claiming a proven root cause.
- Expanded automated coverage to 36 deterministic tests.
- Documented how LagScope complements Wireshark rather than replacing it.

## 1.0.0

- Added Windows default-gateway discovery and layered gateway, public IP, DNS,
  and TCP dependency checks.
- Added paired gateway and public-target monitoring.
- Added latency, packet-loss, and simplified jitter summaries.
- Added fixed-count and timed-session modes, graceful interruption, PowerShell
  launching, automatic CSV evidence, and 25 deterministic tests.
