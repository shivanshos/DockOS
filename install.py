#!/usr/bin/env python3
"""DockOS interactive Ubuntu bootstrap. Run: python3 install.py

Installs third-party Obsidian plugins ONLY from the official community registry.
Review plugin code and permissions before opening the vault.
"""
import getpass
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json"
API = "https://api.github.com"
PLUGINS = [
    "QuickAdd", "Templater", "Tasks", "Homepage", "Calendar",
    "Periodic Notes", "Dataview", "Commander", "Omnisearch", "Excalidraw",
    "Zotero Integration", "Tracker", "Heatmap Calendar", "Kanban Bases View",
    "Metadata Menu", "Modal Forms", "Style Settings", "Iconize",
    "Obsidian Git", "Smart Connections"
]
FOLDERS = [
    "00_System/Dashboard", "00_System/Navigation", "00_System/Configuration",
    "00_System/Standards", "00_System/Templates", "00_System/Automation",
    "00_System/Documentation", "01_Inbox/Quick_Captures",
    "01_Inbox/Unprocessed", "01_Inbox/Imports", "02_Journal/Daily",
    "02_Journal/Weekly", "02_Journal/Monthly", "02_Journal/Yearly",
    "03_Projects/Active", "03_Projects/Planned", "03_Projects/On_Hold",
    "03_Projects/Completed", "04_Areas/Business", "04_Areas/Personal",
    "04_Areas/Finance", "04_Areas/Health", "04_Areas/Technology",
    "05_Knowledge/Concepts", "05_Knowledge/Evergreen_Notes",
    "05_Knowledge/References", "05_Knowledge/Learning",
    "06_Research/Questions", "06_Research/Investigations",
    "06_Research/Experiments", "06_Research/Sources",
    "06_Research/Findings", "07_Operations/Tasks", "07_Operations/Goals",
    "07_Operations/Processes", "07_Operations/Decisions",
    "07_Operations/Meetings", "07_Operations/Logs", "07_Operations/Metrics",
    "08_Assets/Images", "08_Assets/Documents", "08_Assets/Media",
    "08_Assets/Attachments", "09_Archive"
]
CORE = ["backlinks", "outgoing-link", "tag-pane", "properties", "page-preview",
        "daily-notes", "templates", "note-composer", "command-palette",
        "slash-command", "editor-status", "bookmarks", "outline",
        "file-recovery", "sync", "bases", "canvas", "graph", "workspaces"]

def question(label, default=None):
    prompt = f"{label} [{default}]: " if default is not None else f"{label}: "
    answer = input(prompt).strip()
    return answer or default

def yesno(label, default=True):
    suffix = "Y/n" if default else "y/N"
    v = input(f"{label} ({suffix}): ").strip().lower()
    return default if not v else v in ("y", "yes")

def request(url):
    headers = {"User-Agent": "DockOS-Installer/1.0", "Accept": "application/vnd.github+json"}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=35) as r:
        return r.read()

def json_request(url):
    return json.loads(request(url).decode("utf-8"))

def atomic_write(path, data, overwrite=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    tmp = path.with_name(path.name + ".dockos-tmp")
    tmp.write_bytes(data if isinstance(data, bytes) else str(data).encode("utf-8"))
    tmp.replace(path)
    return True

def json_file(path, obj, overwrite=False):
    return atomic_write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n", overwrite)

def run(cmd, check=False):
    print("+", " ".join(map(str,cmd)))
    return subprocess.run(cmd, check=check).returncode == 0

def apt_setup(role, packages):
    if not yesno("Install Ubuntu dependencies with apt", True):
        return
    if not shutil.which("apt-get"):
        print("SKIP: apt-get unavailable"); return
    run(["sudo", "apt-get", "update"])
    run(["sudo", "apt-get", "install", "-y"] + packages)

def install_desktop():
    if shutil.which("obsidian"):
        print("Obsidian command already available."); return
    if not yesno("Install current official Obsidian Debian package", True):
        return
    try:
        releases = json_request(API + "/repos/obsidianmd/obsidian-releases/releases/latest")
        arch = platform.machine()
        candidates = [a for a in releases.get("assets", []) if a["name"].endswith(".deb")
                      and (("amd64" in a["name"] or "x64" in a["name"]) if arch=="x86_64"
                           else ("arm64" in a["name"] if arch=="aarch64" else False))]
        if not candidates:
            print("No matching official .deb release asset. Install from https://obsidian.md/download")
            return
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/candidates[0]["name"]
            p.write_bytes(request(candidates[0]["browser_download_url"]))
            run(["sudo","apt-get","install","-y",str(p)])
    except Exception as e:
        print(f"WARNING: Obsidian download unavailable: {e}. Use https://obsidian.md/download")

def scaffold(vault):
    for folder in FOLDERS:
        (vault/folder).mkdir(parents=True, exist_ok=True)
    obs = vault/".obsidian"
    (obs/"plugins").mkdir(parents=True,exist_ok=True)
    os.chmod(vault,0o700)
    json_file(obs/"core-plugins.json", CORE)
    json_file(obs/"daily-notes.json",
              {"folder":"02_Journal/Daily","format":"YYYY-MM-DD","template":"00_System/Templates/Daily"})
    json_file(obs/"templates.json", {"folder":"00_System/Templates"})
    json_file(obs/"app.json", {
        "attachmentFolderPath":"08_Assets/Attachments",
        "newLinkFormat":"relative", "alwaysUpdateLinks":True
    })
    templates = {
      "00_System/Templates/Project.md": """---
type: project
status: planned
created: {{date}}
priority: medium
review_date:
tags: [dockos, project]
---
# {{title}}
## Objective
## Success Criteria
## Tasks
## Decisions
## Activity Log
## Review
""",
      "00_System/Templates/Daily.md": """# {{date}}
## Priorities
## Activity
## Decisions
## Notes
## Review
""",
      "00_System/Templates/Decision.md": """---
type: decision
status: proposed
created: {{date}}
tags: [dockos, decision]
---
# {{title}}
## Context
## Options
## Decision
## Rationale
## Consequences
""",
      "00_System/Templates/Research.md": """---
type: research
status: investigating
created: {{date}}
tags: [dockos, research]
---
# {{title}}
## Question
## Sources
## Findings
## Conclusions
""",
      "00_System/Dashboard/Home.md": """# DockOS
## Navigate
- [[00_System/Documentation/Operations Manual|Operations Manual]]
- [[02_Journal/Daily|Daily Journal]]
- [[03_Projects/Active|Active Projects]]
- [[07_Operations/Logs|Operational Logs]]
## Capture
Use QuickAdd after first-launch configuration.
## Deployment
See [[00_System/Documentation/Deployment Report|Deployment Report]].
""",
      "00_System/Documentation/Operations Manual.md": """# DockOS Operations Manual
Local-first records; Markdown and YAML are canonical.
Review imported records before promotion.
Backups and sync are different services.
Do not store secrets in the vault.
""",
    }
    for name, text in templates.items():
        atomic_write(vault/name, text)
    return obs

def install_plugins(obs):
    print("Resolving 20 selected plugins from official Obsidian community registry.")
    registry = json_request(REPO)
    by_name = {x["name"].casefold():x for x in registry}
    aliases = {"kanban bases view":["bases kanban","kanban for bases","kanban bases view"],
               "heatmap calendar":["heatmap calendar"],
               "obsidian git":["git","obsidian git"],
               "zotero integration":["zotero integration"]}
    installed, failed, lock = [], [], {}
    for name in PLUGINS:
        match = by_name.get(name.casefold())
        if not match:
            for alias in aliases.get(name.casefold(), []):
                match = by_name.get(alias.casefold())
                if match: break
        if not match:
            failed.append({"name":name,"reason":"No exact catalog match"}); print("UNRESOLVED:",name); continue
        pid, repo = match["id"], match["repo"]
        directory = obs/"plugins"/pid
        if (directory/"main.js").exists() and (directory/"manifest.json").exists():
            installed.append(pid); print("EXISTS:", name); continue
        try:
            release = json_request(f"{API}/repos/{repo}/releases/latest")
            assets = {a["name"]:a["browser_download_url"] for a in release.get("assets",[])}
            if not {"main.js","manifest.json"}.issubset(assets):
                raise ValueError("Missing required published release assets")
            payload = {f:request(assets[f]) for f in ("main.js","manifest.json","styles.css") if f in assets}
            manifest = json.loads(payload["manifest.json"].decode("utf-8"))
            if manifest.get("id") != pid:
                raise ValueError(f"Manifest ID mismatch: {manifest.get('id')}")
            directory.mkdir(parents=True,exist_ok=True)
            for fname, blob in payload.items():
                atomic_write(directory/fname,blob,overwrite=True)
            lock[pid] = {"repo":repo,"version":manifest.get("version"),"tag":release.get("tag_name")}
            installed.append(pid)
            print("INSTALLED:",name,manifest.get("version"))
        except Exception as e:
            failed.append({"name":name,"id":pid,"reason":str(e)})
            print("FAILED:",name,str(e))
    # Merge existing enabled list; never list a missing plugin as installed.
    enabled_path = obs/"community-plugins.json"
    try: existing = json.loads(enabled_path.read_text()) if enabled_path.exists() else []
    except Exception: existing = []
    json_file(enabled_path, sorted(set(existing+installed)),overwrite=True)
    json_file(obs.parent/"00_System/Configuration/plugin-lock.json",lock,overwrite=True)
    json_file(obs.parent/"00_System/Configuration/plugin-failures.json",failed,overwrite=True)
    # Known plugin setting schemas. Other plugins use their own valid defaults.
    defaults = {
      "templater-obsidian":{"templates_folder":"00_System/Templates","trigger_on_file_creation":False},
      "obsidian42-brat":None,
      "calendar":{"shouldConfirmBeforeCreate":True},
    }
    for pid, settings in defaults.items():
        if settings and pid in installed:
            json_file(obs/"plugins"/pid/"data.json",settings)
    return installed,failed

def backup_config(vault):
    if not yesno("Configure encrypted Restic backups", True): return
    repo = question("Restic repository path (mounted disk or remote URI)",str(Path.home()/"DockOS-Backups"))
    secret_dir = Path.home()/".config"/"dockos"
    secret_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    pwfile = secret_dir/"restic-password"
    if not pwfile.exists():
        password = getpass.getpass("Backup encryption password (required, save separately): ")
        if len(password)<12: print("SKIP: Require at least 12 characters"); return
        fd=os.open(str(pwfile),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w") as f: f.write(password+"\n")
    envfile=secret_dir/"backup.env"
    # systemd EnvironmentFile supports quoted strings.
    def systemd_quote(s):
        return '"'+s.replace("\\","\\\\").replace('"','\\"')+'"'
    atomic_write(envfile,
      "RESTIC_REPOSITORY="+systemd_quote(repo)+"\n"+
      "RESTIC_PASSWORD_FILE="+systemd_quote(str(pwfile))+"\n",overwrite=True)
    os.chmod(envfile,0o600)
    user_units=Path.home()/".config"/"systemd"/"user"
    service = """[Unit]
Description=DockOS encrypted backup

[Service]
Type=oneshot
EnvironmentFile=%h/.config/dockos/backup.env
ExecStart=/usr/bin/restic backup %h/Documents/DockOS
"""
    # Respect custom vault path.
    service=service.replace("%h/Documents/DockOS",str(vault))
    timer="""[Unit]
Description=Daily DockOS encrypted backup

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
"""
    atomic_write(user_units/"dockos-backup.service",service,overwrite=True)
    atomic_write(user_units/"dockos-backup.timer",timer,overwrite=True)
    print("Created user systemd units.")
    print("ACTION REQUIRED: initialize Restic repository, test manual backup, then enable timer.")
    print(f"  set -a; source {envfile}; set +a")
    print("  restic snapshots || restic init")
    print("  systemctl --user daemon-reload")
    print("  systemctl --user enable --now dockos-backup.timer")
    print("NOTE: Backups run when the user's systemd manager is active; enable lingering if needed.")

def server_setup(vault):
    print("\nSERVER: Obsidian Headless requires Node >=22, Obsidian Sync subscription, and interactive login.")
    print("Do not run desktop Obsidian Sync and Headless Sync on the same device.")
    if not shutil.which("node") or not shutil.which("npm"):
        print("ACTION: install Node.js >=22 from trusted distribution, rerun.")
        return
    proc=subprocess.run(["node","--version"],capture_output=True,text=True)
    try: version=int(proc.stdout.strip().lstrip("v").split(".")[0])
    except Exception: version=0
    if version<22:
        print("ACTION: upgrade Node.js to >=22, rerun."); return
    if yesno("Install official Obsidian Headless npm package", True):
        run(["sudo","npm","install","-g","obsidian-headless"])
    print("Then as the intended unprivileged sync user:")
    print("  ob login")
    print("  ob sync-list-remote")
    print(f"  ob sync-setup --vault DockOS --path '{vault}'")
    print(f"  ob sync-config --path '{vault}' --mode pull-only")
    print(f"  ob sync --path '{vault}' --continuous")
    print("Keep server pull-only until publishing safety is configured.")

def main():
    if platform.system()!="Linux":
        sys.exit("Linux required.")
    print("DOCKOS | Ubuntu hybrid installer | all 20 chosen plugins enabled by default")
    print("Community plugins execute third-party code. Review trust implications before proceeding.")
    if not yesno("Trust selected community plugins and continue",False):
        sys.exit("Cancelled.")
    role=question("Install mode: desktop or server","desktop").lower()
    if role not in ("desktop","server"): sys.exit("Invalid role.")
    default=Path.home()/"Documents"/"DockOS" if role=="desktop" else Path.home()/"vaults"/"DockOS"
    vault=Path(os.path.expanduser(question("Vault directory",str(default)))).resolve()
    if vault==Path.home() or vault==Path("/"): sys.exit("Unsafe vault path")
    print("Target:",vault)
    if not yesno("Proceed with non-destructive initialization",True): sys.exit("Cancelled.")
    apt_setup(role,["curl","git","jq","python3","restic","ca-certificates"])
    if role=="desktop": install_desktop()
    obs=scaffold(vault)
    if role=="desktop" or yesno("Install community plugins into server replica too",False):
        try: installed,failed=install_plugins(obs)
        except Exception as e: installed,failed=[],[{"reason":str(e)}]; print("Plugin catalog unavailable:",e)
    else: installed,failed=[],[]
    if role=="server": server_setup(vault)
    backup_config(vault)
    report=f"""# Deployment Report
Date: {datetime.now(timezone.utc).isoformat()}
Role: {role}
Vault: {vault}
Installed community plugins: {len(installed)}/20
Unresolved/failed: {len(failed)}
Configuration policy: preserve existing plugin data.json, use defaults for undocumented settings.
Sync: requires separate authenticated setup.
Mobile: install Obsidian and pair vault with Obsidian Sync manually.
"""
    atomic_write(vault/"00_System/Documentation/Deployment Report.md",report,overwrite=True)
    print("\nDockOS initial provisioning complete.")
    print(f"Installed {len(installed)}/20 plugins. Check 00_System/Configuration/plugin-failures.json")
    print("Restart Obsidian; enable community plugins in Settings if Restricted Mode is active.")
    print("Finish each plugin's account-specific settings (Zotero, AI keys, etc.) inside Obsidian.")
    print("Server/mobile authentication is intentionally not stored or automated.")

if __name__=="__main__":
    main()
