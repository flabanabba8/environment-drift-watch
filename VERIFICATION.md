# Verification

- Mixed-case protected-directory fixtures passed on Linux and native Windows; no real credentials were used. This is not a full platform or publication audit.

- Sixteen unit tests passed, including owner-only permissions for each new baseline type under a permissive POSIX umask, changed and replaced files, service and package fixtures, and subprocess credential isolation.
- Hermes plugin validation passed without warnings. Earlier read-only live comparisons exercised a local systemd service and a Debian package; no service was changed.
- Native Windows Python 3.14 detected a change to a synthetic file baseline. Windows service/package monitoring and ACL behavior were not tested.
- Existing baselines are not retroactively chmodded. Scheduling, automatic restoration, production monitoring, full Windows coverage, a reviewed demo and a complete publication audit remain unverified.
- 2026-11-07: real-input trial through Hermes's tool registry in a disposable profile. File baselines recorded a config file and /etc/hostname; after editing the config, drift_compare reported it changed (sha256 and size) and /etc/hostname unchanged. Package baselines for ffmpeg and python3 compared as unchanged. Real limitation found: baselines reject symlinks, so common files such as /etc/os-release cannot be baselined.
- 2026-11-07: `drift_baseline` accepts optional `follow_symlinks` (default false) so files such as /etc/os-release can be baselined: the target file is measured and the resolved link target is recorded; a repointed link, or a link replaced by a regular file, is reported as changed in `link_target`. The first version of this change made every ordinary file report an unrecorded field; an existing test caught it and it was fixed. 17 tests pass.
