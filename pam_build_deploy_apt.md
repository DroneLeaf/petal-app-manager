# PAM — Build & Deploy to APT Repository

- [PAM — Build \& Deploy to APT Repository](#pam--build--deploy-to-apt-repository)
  - [Overview](#overview)
  - [Pipeline: `build_deploy_apt.yml`](#pipeline-build_deploy_aptyml)
    - [Job 1 — `build`](#job-1--build)
    - [Job 2 — `deploy`](#job-2--deploy)
  - [Package Builder: `build-deb.sh`](#package-builder-build-debsh)
  - [Two-Phase Install Design](#two-phase-install-design)
  - [Required GitHub Secrets](#required-github-secrets)
  - [How to Contribute / What to Edit](#how-to-contribute--what-to-edit)
    - [Releasing a new version](#releasing-a-new-version)
    - [Changing package metadata](#changing-package-metadata)
    - [Adding/removing system dependencies](#addingremoving-system-dependencies)
    - [Changing default app configuration](#changing-default-app-configuration)
    - [Changing the first-run setup logic](#changing-the-first-run-setup-logic)
    - [Changing the systemd services](#changing-the-systemd-services)
    - [Changing the APT server](#changing-the-apt-server)
    - [Changing the trigger event](#changing-the-trigger-event)
  - [Maintainer:](#maintainer)


## Overview

When a new GitHub release is created with a tag like `v0.2.5`, a CI pipeline automatically:
1. Builds a `.deb` Debian package from the source
2. Uploads it as a release asset on GitHub
3. Publishes it to the DroneLeaf APT repository at `repo.droneleaf.io`

After that, users can install the app with:
```bash
sudo apt install petal-app-manager
```

---

## Pipeline: `build_deploy_apt.yml`

Triggered by: **creating a GitHub release** (tag must follow `vX.Y.Z`)

### Job 1 — `build`

| Step | What it does |
|------|--------------|
| Set version | Strips the `v` prefix from the tag → `X.Y.Z` |
| Validate version | Ensures the version matches `X.Y.Z` format |
| Set architecture | Maps `runner.architecture` → `arm64` or `all` |
| Run `build-deb.sh` | Builds the `.deb` package (see below) |
| Verify build | Prints package metadata and contents |
| Upload artifact | Stores the `.deb` for the deploy job |
| Upload release asset | Attaches the `.deb` to the GitHub release |

### Job 2 — `deploy`

Downloads the `.deb` artifact and pushes it to the APT repository via `curl` POST request (to overcome cloudflare bodysize limits)
```bash
curl -u "$USER:$PASS" --data-binary "@pkg.deb" http://<server>/repository/apt/
```

---

## Package Builder: `build-deb.sh`

This script constructs the `.deb` package directory structure and calls `dpkg-deb` to produce the final file.

**What gets bundled:**
- The full application source → `/opt/petal-app-manager/`
- A default `.env` config file (preserved on upgrades)
- A `setup-complete.sh` helper script
- Two systemd service units

**Output:** `petal-app-manager_X.Y.Z_<arch>.deb`

---

## Two-Phase Install Design

The package install is split in two to avoid a dpkg lock conflict (postinst cannot call `apt-get` while dpkg holds its own lock).

```
dpkg installs package
    └── postinst runs
            ├── Installs pyenv + Python 3.11 (compiled, no apt needed)
            ├── Installs PDM via pip
            ├── Writes Redis apt repo config (file writes only — no apt-get)
            └── Starts petal-app-manager-setup.service --no-block
                    └── (runs after dpkg exits)
                        ├── Waits for dpkg lock to be free
                        ├── apt-get install redis
                        ├── Configures Redis UNIX socket
                        ├── pdm install -G prod
                        └── Enables + starts petal-app-manager.service
```

The setup service is a **oneshot** that runs once and is skipped on subsequent boots (guarded by a `.setup-complete` flag file).

---

## Required GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `REPOSITORY_USERNAME` | APT server credentials |
| `REPOSITORY_PASSWORD` | APT server credentials |
| `REPOSITORY_SERVER_IP` | IP address of the APT server |
| `REPOSITORY_HOSTNAME` | Hostname sent in the `Host` header |

---

## How to Contribute / What to Edit

### Releasing a new version
Just create a GitHub release with a `vX.Y.Z` tag — everything else is automatic.

### Changing package metadata
Edit the variables at the top of `build-deb.sh`:
```bash
PKG_NAME, PKG_VERSION, PKG_ARCH, PKG_MAINTAINER, PKG_DESCRIPTION, PKG_HOMEPAGE
```

### Adding/removing system dependencies
Edit the `PKG_DEPENDS` array in `build-deb.sh`. These are installed on the target machine at `apt install` time.

### Changing default app configuration
Edit the `cat > .env` heredoc block in `build-deb.sh`. Note: the `.env` is a dpkg conffile — it is **not overwritten** on upgrades if the user has modified it.

### Changing the first-run setup logic
Edit the `setup-complete.sh` heredoc in `build-deb.sh` — this controls what happens after the package is installed (Redis setup, PDM install, etc.).

### Changing the systemd services
The two service unit files (`petal-app-manager.service` and `petal-app-manager-setup.service`) are also written as heredocs inside `build-deb.sh`.

### Changing the APT server
Update the `REPOSITORY_*` secrets in the GitHub repository settings.

### Changing the trigger event
Edit the `on:` block in `build_deploy_apt.yml` (currently `release: types: [created]`).

## Maintainer:
Hashem Allaham <hashem.allaham@droneleaf.io>