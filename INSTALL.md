# DockOS

A personal homelab system for documentation, logging, tracking, note-taking, research, and utilities, built on Obsidian.

## Ubuntu 26.04 installer

The installer is a **single Python 3 entry point** that provisions a new vault, basic core Obsidian settings, all 20 selected community plugins (enabled when their release assets are available), starter templates, and optional encrypted-backup configuration. It supports Ubuntu desktop and Ubuntu Server modes. It does **not** provision a cloud VPS, install mobile applications, log in to Obsidian Sync, or acquire API keys on your behalf.

```bash
git clone https://github.com/shivanshos/DockOS.git
cd DockOS
python3 install.py
```

On this feature branch, use:

```bash
git clone --branch feat/ubuntu-hybrid-installer https://github.com/shivanshos/DockOS.git
cd DockOS
python3 install.py
```

The installer prompts for:
- role: `desktop` or `server`;
- vault directory;
- permission for Ubuntu package installation;
- permission to install the official Obsidian Debian release;
- plugin code trust confirmation;
- optional Restic repository and encryption password.

**Review this script and plugin permissions before running.** Run as your ordinary user account, not root. It invokes `sudo` for apt and (if selected) npm global installation. Community plugins execute JavaScript with access to your vault.

### Server follow-up

Requires Node.js >= 22, an Obsidian Sync subscription, and authentication. The installer prints Headless commands but deliberately requires you to perform authentication and sync enrollment. Start the server replica **pull-only**. Do not run Obsidian desktop Sync and Headless Sync against the same local vault.

### Mobile follow-up

Install Obsidian on the phone, connect Obsidian Sync, and review community plugin compatibility on that device. Mobile app provisioning is not performed by this Linux script.

### Plugin configuration

The script installs and enables the selected plugins whose exact names or documented aliases are found in the official Obsidian community catalog and whose GitHub releases contain a valid matching manifest, `main.js`, and optional `styles.css`. Failures are recorded in `00_System/Configuration/plugin-failures.json`. Versions are recorded in `plugin-lock.json`.

**Not all third-party plugin settings are interchangeable or stable.** Existing per-plugin `data.json` is preserved. A conservative known Templater folder is set; account-specific Zotero, AI provider, and other integrations must be finalized in the app. Missing plugins are not falsely marked installed. Enabling multiple overlapping plugins may cause conflicts.

### Backup follow-up

A `restic-password` file with owner-only permissions and systemd user service/timer units are created if backup setup is selected. **No timer is enabled until you initialize the repository and test the backup.** The script prints the required commands. Store the encryption password outside this machine. Vault sync, Git, and backups are separate mechanisms.

### Rerunning

The installer does not overwrite existing user documents or existing plugin configuration. It may update generated deployment reports, plugin binaries, lock/failure reports, and basic native Obsidian settings. Back up your vault before rerunning on production.

## Repository

- `install.py`: interactive workstation/server bootstrap.
- Further scripts, validated templates, infrastructure-as-code and tests will follow after the initial bootstrap has been tested in Ubuntu 26.04.
