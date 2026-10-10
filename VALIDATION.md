# DockOS trial validation

Run `python3 scripts/validate_trial.py --vault /home/dockos/vaults/DockOS-Trial` as the unprivileged `dockos` account. The current installer does not create this account or trial path automatically. A root run reports an account failure and skips user-dependent runtime checks. Missing software and provisioning are reported, not installed.

This checks Ubuntu/resources, dependency presence, Node compatibility/runtime, Python venv/pip, HTTPS access to the official Obsidian community catalog and npm, trial vault structure/ownership/permissions, all 20 selected plugin manifests/enabled entries/version locks, Headless CLI/config/status, expected user automation units, lingering and backup credential-file permissions.

A small disposable local Restic repository is initialized, backed up, fully integrity checked and restored. SHA-256 comparison verifies the restored test payload. Temporary files are removed by Python on normal completion/error; no existing backup repository is touched. This demonstrates the installed Restic binary works locally, not that a production or offsite repository works. Use `--skip-smoke` to skip both disposable runtime tests. Use `--offline` to skip public HTTPS queries.

No packages are installed, vault contents changed, sync started, configuration altered, services started, credentials requested or reboot performed. Child command output is captured and withheld, including failures, to avoid leaking secrets. The test itself prints only predefined check labels and status. Review output before sharing. It sends no report anywhere automatically.

`PASS` means the labeled check passed. `FAIL` means a prerequisite or check failed. `BLOCKED` means the check cannot be established by this diagnostic. Exit codes: 0 for complete success, 1 if any failure, 2 for blocked checks without failures. This first diagnostic intentionally leaves integration checks blocked; an all-green production readiness claim cannot be made from it.

Manual/integration acceptance remains: prove trial remote vault identity, secure authentication, an actual pull-only transfer, actual configured-backend backup and restore, desktop plugin functionality, external reachability, and reboot recovery. Do not start sync until the remote is a verified trial vault and the mode is explicitly pull-only. Desktop plugins require an appropriate Obsidian client; Headless synchronization alone does not validate them.

Expected unit names are `dockos-sync.service` and `dockos-backup.timer` in the account's user systemd manager. Different names/system units need explicit adaptation. Permission checks use the bootstrap's expected `~/.config/dockos/backup.env` and `restic-password` paths and do not read their values. No claim is made about provider firewall settings or data-exfiltration resistance of third-party plugin code.

Local checks: `python3 -m unittest discover -s tests -v`. VPS execution is pending. Findings tracked in issue #2.

References:
- https://obsidian.md/help/headless
- https://obsidian.md/help/sync/headless
- https://restic.readthedocs.io/en/stable/manual_rest.html
