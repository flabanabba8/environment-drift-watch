# Verification

- Fifteen unit tests passed, including owner-only permissions for each new baseline type under a permissive POSIX umask, changed and replaced files, service and package fixtures, and subprocess credential isolation.
- Hermes plugin validation passed without warnings. Earlier read-only live comparisons exercised a local systemd service and a Debian package; no service was changed.
- Existing baselines are not retroactively chmodded. Scheduling, automatic restoration, production monitoring, Windows, a reviewed demo and a complete publication audit remain unverified.
