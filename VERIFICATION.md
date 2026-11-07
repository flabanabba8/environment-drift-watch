# Verification

- Mixed-case protected-directory fixtures passed on Linux and native Windows; no real credentials were used. This is not a full platform or publication audit.

- Sixteen unit tests passed, including owner-only permissions for each new baseline type under a permissive POSIX umask, changed and replaced files, service and package fixtures, and subprocess credential isolation.
- Hermes plugin validation passed without warnings. Earlier read-only live comparisons exercised a local systemd service and a Debian package; no service was changed.
- Native Windows Python 3.14 detected a change to a synthetic file baseline. Windows service/package monitoring and ACL behavior were not tested.
- Existing baselines are not retroactively chmodded. Scheduling, automatic restoration, production monitoring, full Windows coverage, a reviewed demo and a complete publication audit remain unverified.
