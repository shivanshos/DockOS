#!/usr/bin/env python3
"""DockOS trial diagnostics; never installs, starts sync, or edits a vault."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv

PLUGINS = ["QuickAdd", "Templater", "Tasks", "Homepage", "Calendar",
           "Periodic Notes", "Dataview", "Commander", "Omnisearch", "Excalidraw",
           "Zotero Integration", "Tracker", "Heatmap Calendar", "Kanban Bases View",
           "Metadata Menu", "Modal Forms", "Style Settings", "Iconize",
           "Obsidian Git", "Smart Connections"]
ALIASES = {"kanban bases view": ["bases kanban", "kanban for bases", "kanban bases view"],
           "obsidian git": ["git", "obsidian git"]}
REGISTRY = "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json"


def command(argv, timeout=30, env=None):
    # Never print child stdout/stderr: these may contain credentials or account details.
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, env=env)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 124, ""


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def sync_mode(output):
    # Require the explicit configuration field, not an arbitrary mention of pull-only.
    clean = re.sub(r"\x1b\[[0-9;]*m", "", output)
    match = re.search(r"(?im)^\s*Sync mode:\s*(pull-only|bidirectional|mirror-remote)\s*$", clean)
    return match.group(1) if match else None


def restic_smoke(restic):
    # Entire test repository, password and restore target are disposable and isolated.
    with tempfile.TemporaryDirectory(prefix="dockos-restic-test-") as d:
        base = Path(d)
        source = base / "source"
        source.mkdir()
        payload = os.urandom(4096)
        (source / "probe.bin").write_bytes(payload)
        password = base / "password"
        password.write_text(os.urandom(32).hex() + "\n")
        password.chmod(0o600)
        env = dict(os.environ)
        # Use CLI -r/-p below and remove inherited backend credentials for this local test.
        for key in list(env):
            if key.startswith(("RESTIC_", "AWS_", "B2_", "AZURE_", "GOOGLE_", "RCLONE_")):
                env.pop(key)
        prefix = [restic, "--no-cache", "-r", str(base / "repo"), "-p", str(password)]
        steps = [["init"], ["backup", str(source), "--tag", "dockos-smoke"],
                 ["check", "--read-data"],
                 ["restore", "latest", "--target", str(base / "restore")]]
        for step in steps:
            rc, _ = command(prefix + step, timeout=120, env=env)
            if rc:
                return False, "disposable " + step[0] + " failed (output withheld)"
        files = list((base / "restore").rglob("probe.bin"))
        ok = len(files) == 1 and hashlib.sha256(files[0].read_bytes()).digest() == hashlib.sha256(payload).digest()
        return ok, "disposable init/backup/full integrity check/restore/hash comparison"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=Path("/home/dockos/vaults/DockOS-Trial"))
    parser.add_argument("--account", default="dockos")
    parser.add_argument("--offline", action="store_true", help="skip public HTTPS checks")
    parser.add_argument("--skip-smoke", action="store_true", help="skip disposable runtime tests")
    args = parser.parse_args()
    counts = Counter()

    def report(status, label, detail=""):
        counts[status] += 1
        print(f"{status:7} {label}" + (f" — {detail}" if detail else ""), flush=True)

    def check(ok, label, detail=""):
        report("PASS" if ok else "FAIL", label, detail)

    print("DockOS trial validation; child output and secret values are withheld", flush=True)
    try:
        account = pwd.getpwnam(args.account)
    except KeyError:
        account = None
    correct_user = bool(account and os.geteuid() == account.pw_uid and os.geteuid() != 0)
    check(correct_user, "Dedicated unprivileged account", "run as the configured DockOS account")
    os_release = Path("/etc/os-release").read_text()
    check('ID=ubuntu' in os_release and 'VERSION_ID="26.04"' in os_release, "Ubuntu 26.04")
    check((os.cpu_count() or 0) >= 2, "At least 2 CPU cores")
    mem = re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text())
    check(bool(mem and int(mem.group(1)) >= 7 * 1024 * 1024), "At least 7 GiB RAM")
    check(shutil.disk_usage("/").free >= 5 * 1024**3, "At least 5 GiB free disk space")

    binaries = {}
    for name in ["python3", "node", "npm", "restic", "git", "curl", "jq", "systemctl"]:
        binaries[name] = shutil.which(name)
        check(bool(binaries[name]), "Dependency: " + name)
    ob = shutil.which("ob")
    if not ob and account:
        candidate = Path(account.pw_dir) / ".local/bin/ob"
        ob = str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    check(bool(ob), "Dependency: Obsidian Headless")
    if binaries["node"]:
        rc, out = command([binaries["node"], "--version"])
        match = re.fullmatch(r"v(\d+)\.\d+\.\d+\s*", out)
        check(rc == 0 and bool(match) and int(match.group(1)) >= 22, "Node.js >=22")
        rc, _ = command([binaries["node"], "-e", "if(require('crypto').createHash('sha256').update('test').digest('hex').length!==64)process.exit(1)"])
        check(rc == 0, "Node runtime smoke")
    if correct_user and not args.skip_smoke:
        try:
            with tempfile.TemporaryDirectory(prefix="dockos-venv-test-") as d:
                venv.EnvBuilder(with_pip=True).create(d)
                rc, _ = command([str(Path(d) / "bin/python"), "-m", "pip", "--version"])
                check(rc == 0, "Python venv and pip smoke")
        except Exception:
            report("FAIL", "Python venv and pip smoke", "creation failed; output withheld")
        if binaries["restic"]:
            ok, detail = restic_smoke(binaries["restic"])
            check(ok, "Restic backup/restore smoke", detail)
    else:
        report("BLOCKED", "Disposable venv and Restic smoke", "requires correct account and smoke tests enabled")
    if ob and correct_user:
        rc, _ = command([ob, "--help"])
        check(rc == 0, "Headless CLI loads")

    registry = None
    if not args.offline:
        for label, url in [("Obsidian plugin catalog HTTPS", REGISTRY),
                           ("npm registry HTTPS", "https://registry.npmjs.org/obsidian-headless/latest")]:
            try:
                with urllib.request.urlopen(url, timeout=15) as response:
                    data = json.load(response)
                check(True, label)
                if url == REGISTRY:
                    registry = data
            except Exception:
                report("FAIL", label, "network/TLS/response failure; output withheld")
    else:
        report("BLOCKED", "Public HTTPS checks", "offline mode")

    vault = args.vault.expanduser().resolve()
    exists = vault.is_dir()
    check(exists, "Trial vault exists")
    if exists:
        st = vault.stat()
        check(bool(account and st.st_uid == account.pw_uid), "Trial vault ownership")
        check(st.st_mode & 0o077 == 0, "Trial vault owner-only permissions")
        for folder in ["00_System/Templates", "00_System/Configuration", "00_System/Documentation",
                       "01_Inbox", "02_Journal/Daily", "03_Projects", "04_Areas", "05_Knowledge",
                       "06_Research", "07_Operations", "08_Assets", "09_Archive"]:
            check((vault / folder).is_dir(), "Vault folder: " + folder)
        check((vault / "00_System/Dashboard/Home.md").is_file(), "Dashboard note")
        enabled = load_json(vault / ".obsidian/community-plugins.json")
        enabled = enabled if isinstance(enabled, list) else []
        lock = load_json(vault / "00_System/Configuration/plugin-lock.json")
        lock = lock if isinstance(lock, dict) else {}
        if isinstance(registry, list):
            by_name = {x["name"].casefold(): x for x in registry}
            for name in PLUGINS:
                choices = [name.casefold()] + ALIASES.get(name.casefold(), [])
                entry = next((by_name[n] for n in choices if n in by_name), None)
                if not entry:
                    report("FAIL", "Plugin: " + name, "selected name not resolved in official catalog")
                    continue
                pid = entry["id"]
                # Catalog identifiers must not escape the plugins directory.
                if not re.fullmatch(r"[A-Za-z0-9_-]+", pid):
                    report("FAIL", "Plugin: " + name, "invalid catalog identifier")
                    continue
                directory = vault / ".obsidian/plugins" / pid
                manifest = load_json(directory / "manifest.json")
                valid = isinstance(manifest, dict) and manifest.get("id") == pid and bool(manifest.get("version"))
                ok = valid and (directory / "main.js").is_file() and (directory / "main.js").stat().st_size > 0 and pid in enabled
                check(ok, "Plugin installed/enabled: " + name)
                locked = lock.get(pid)
                check(valid and isinstance(locked, dict) and locked.get("version") == manifest.get("version")
                      and locked.get("repo") == entry["repo"], "Plugin version lock: " + name)
        else:
            report("BLOCKED", "All 20 selected plugins", "official catalog not available")
    else:
        report("BLOCKED", "Vault structure and all 20 plugins", "trial vault not provisioned")
    report("BLOCKED", "Desktop plugin functionality", "Headless does not validate desktop plugin execution")

    if exists and ob and correct_user:
        rc, output = command([ob, "sync-config", "--path", str(vault)])
        mode = sync_mode(output) if rc == 0 else None
        check(mode == "pull-only", "Sync configured pull-only", "mode field must be explicitly readable")
        rc, _ = command([ob, "sync-status", "--path", str(vault)])
        check(rc == 0, "Headless sync-status command")
    else:
        report("BLOCKED", "Headless sync configuration/status", "requires user, CLI and trial vault")
    report("BLOCKED", "Live isolated remote sync", "not started by diagnostics; needs verified trial remote and authentication")

    if binaries["systemctl"]:
        for name in ["dockos-sync.service", "dockos-backup.timer"]:
            if correct_user:
                active, _ = command(["systemctl", "--user", "is-active", "--quiet", name])
                enabled_rc, _ = command(["systemctl", "--user", "is-enabled", "--quiet", name])
                check(active == 0 and enabled_rc == 0, "User automation active/enabled: " + name)
            else:
                report("BLOCKED", "User automation: " + name, "requires correct account and user systemd manager")
        if account:
            rc, out = command(["loginctl", "show-user", args.account, "--property=Linger", "--value"])
            check(rc == 0 and out.strip() == "yes", "User services persist after logout (lingering)")

    if account:
        secret_dir = Path(account.pw_dir) / ".config/dockos"
        for name in ["backup.env", "restic-password"]:
            path = secret_dir / name
            ok = path.is_file() and not path.is_symlink()
            if ok:
                st = path.stat()
                ok = st.st_uid == account.pw_uid and st.st_mode & 0o077 == 0
            check(ok, "Backup credential file protected: " + name)
    report("BLOCKED", "Configured backup repository/real-vault restore", "disposable smoke does not validate the chosen backup destination")
    report("BLOCKED", "Reboot recovery", "requires a separately observed reboot; diagnostics do not reboot")
    report("BLOCKED", "Remote firewall, external SSH and client UI", "cannot be proven by this local test")
    print("\nSUMMARY " + " ".join(f"{s}={counts[s]}" for s in ("PASS", "FAIL", "BLOCKED")))
    print("READY only after FAIL and required BLOCKED checks have been resolved.")
    return 1 if counts["FAIL"] else 2 if counts["BLOCKED"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("FAIL    Diagnostic stopped unexpectedly; raw output withheld to protect credentials.")
        sys.exit(1)
