#!/usr/bin/env bash

set -Eeuo pipefail

# ==============================================================================
# build-deb.sh — Debian package builder for petal-app-manager
# ==============================================================================
#
# Usage (CI/CD):
#   chmod +x build-deb.sh
#   PKG_VERSION="<version>" ./build-deb.sh
#
# Two-phase install design
# ────────────────────────
# postinst   : user creation · prebuilt Python 3.11 (python-build-standalone) · PDM
#              Writes Redis apt-repo config files (no apt-get — dpkg lock safe)
#              Enables + starts  petal-app-manager-setup.service  (--no-block)
#
# setup svc  : Oneshot service that runs AFTER dpkg releases its lock.
#              Waits for lock release → apt-get install redis → Redis socket
#              config → pdm install -G prod → enable main service.
#              Idempotent: skipped if .setup-complete already exists.
#
# main svc   : Starts only After= the setup service has finished.
#
# Maintainer: Hashem Allaham <hashem.allaham@droneleaf.io>
# ==============================================================================


# ------------------------------------------------------------------------------
# Package metadata
# ------------------------------------------------------------------------------

PKG_NAME="petal-app-manager"
PKG_VERSION="${PKG_VERSION:-0.0.0}"
PKG_ARCH="${PKG_ARCH:-all}"
PKG_MAINTAINER="DroneLeaf Team <https://droneleaf.io>"
PKG_DESCRIPTION="Petal App Manager — modular FastAPI runtime for DroneLeaf petals"
PKG_HOMEPAGE="https://github.com/DroneLeaf/petal-app-manager"

# ------------------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------------------

BUILD_DIR="build"
OUTPUT_FILE="${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

INSTALL_DIR="/opt/${PKG_NAME}"      # installation path (root directory) — also where .env lives
DATA_DIR="/var/lib/${PKG_NAME}"
LOG_DIR="/var/log/${PKG_NAME}"

APP_USER="root"
APP_GROUP="root"

SERVICE_NAME="${PKG_NAME}.service"
SETUP_SERVICE_NAME="${PKG_NAME}-setup.service"
SETUP_FLAG="${INSTALL_DIR}/.setup-complete"

# ------------------------------------------------------------------------------
# Python  (prebuilt relocatable CPython, fetched on target via postinst)
#
# python-build-standalone tarballs are linked against glibc 2.17, so one
# aarch64 build runs on Ubuntu 20.04 focal (glibc 2.31) AND 24.04 noble (2.39)
# with no on-target compilation.  Bump PBS_RELEASE + PYTHON_VERSION together to
# a pair that exists at:
#   https://github.com/astral-sh/python-build-standalone/releases
# ------------------------------------------------------------------------------

PYTHON_VERSION="3.11.15"
PBS_RELEASE="20260610"
PYTHON_DIR="${INSTALL_DIR}/python"
PYTHON_BIN="${PYTHON_DIR}/bin/python3.11"
PDM_BIN="${PYTHON_DIR}/bin/pdm"

# ------------------------------------------------------------------------------
# Debian package dependencies
#
# • Prebuilt Python (python-build-standalone) needs no compiler toolchain for
#   CPython itself.  build-essential + a few -dev libs are kept only in case a
#   prod dependency wheel builds from sdist; trim further if none do.
# • Redis apt-key / repo tools (README §3) — curl+gnupg needed in postinst to
#   write the keyring file.  Redis server itself is NOT listed here; the setup
#   service installs Redis 7.2+ from the official apt repo after dpkg exits.
# ------------------------------------------------------------------------------

PKG_DEPENDS=(
    "curl"
    "ca-certificates"
    "gnupg"
    "lsb-release"
    "apt-transport-https"
    "git"
)

DEPENDS=$(IFS=', '; echo "${PKG_DEPENDS[*]}")

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
NC="\033[0m"

info() { echo -e "${BLUE}[INFO]${NC}    $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}      $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}    $*"; }
fail() { echo -e "${RED}[FAIL]${NC}    $*"; exit 1; }

cleanup() { rm -rf "${BUILD_DIR}"; }
trap cleanup EXIT

# ------------------------------------------------------------------------------
# Banner
# ------------------------------------------------------------------------------

clear 2>/dev/null || true
echo ""
echo "======================================================="
echo " Building ${PKG_NAME} ${PKG_VERSION}"
echo " arch: ${PKG_ARCH}   python: ${PYTHON_VERSION} (prebuilt)"
echo "======================================================="
echo ""

# ------------------------------------------------------------------------------
# Preflight checks
# ------------------------------------------------------------------------------

info "Validating workspace..."
[[ -f pyproject.toml ]] || fail "pyproject.toml not found — run from repo root"
command -v dpkg-deb &>/dev/null || fail "dpkg-deb not found"
command -v rsync    &>/dev/null || { warn "rsync missing — installing..."; sudo apt-get install -y rsync; }
ok "workspace valid"

# ------------------------------------------------------------------------------
# Clean previous build
# ------------------------------------------------------------------------------

info "Cleaning previous build..."
rm -rf "${BUILD_DIR}"
rm -f ./*.deb

mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}${INSTALL_DIR}/scripts"   # bundled helper scripts
mkdir -p "${BUILD_DIR}${DATA_DIR}"
mkdir -p "${BUILD_DIR}${LOG_DIR}"
mkdir -p "${BUILD_DIR}/etc/systemd/system"

ok "directory structure created"

# ------------------------------------------------------------------------------
# Copy application source
# ------------------------------------------------------------------------------

info "Copying application..."
rsync -a \
    --exclude ".git" \
    --exclude ".venv" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache" \
    --exclude ".mypy_cache" \
    --exclude "dist" \
    --exclude "build" \
    --exclude "*.deb" \
    --exclude ".env" \
    --exclude "scripts" \
    ./ "${BUILD_DIR}${INSTALL_DIR}/"

ok "application copied → ${INSTALL_DIR}/"

# ------------------------------------------------------------------------------
# .env  (install directory — conffiles protects it across upgrades)
#
# Variables use the PETAL_ prefix convention from the README.
# Edit before packaging.  The file is preserved on upgrade (dpkg conffile).
# ------------------------------------------------------------------------------

info "Writing .env → ${INSTALL_DIR}/.env ..."

cat > "${BUILD_DIR}${INSTALL_DIR}/.env" <<'ENVEOF'
# .env — Petal App Manager production configuration
# This file is NOT overwritten on package upgrade.
# Customise values for your target hardware before first boot.

# ── General ──────────────────────────────────────────────────────────────────
PETAL_LOG_LEVEL=INFO
PETAL_LOG_TO_FILE=true
PETAL_LOG_DIR=logs

# ── MAVLink ──────────────────────────────────────────────────────────────────
PETAL_MAVLINK_ENDPOINT=udp:127.0.0.1:14551
PETAL_MAVLINK_BAUD=115200
PETAL_MAVLINK_MAXLEN=200
PETAL_MAVLINK_WORKER_SLEEP_MS=1
PETAL_MAVLINK_WORKER_THREADS=4
PETAL_MAVLINK_HEARTBEAT_SEND_FREQUENCY=5.0
PETAL_ROOT_SD_PATH=fs/microsd/log

# ── Cloud ────────────────────────────────────────────────────────────────────
PETAL_ACCESS_TOKEN_URL=http://localhost:3001/session-manager/access-token
PETAL_SESSION_TOKEN_URL=http://localhost:3001/session-manager/session-token
PETAL_S3_BUCKET_NAME=devhube21f2631b51e4fa69c771b1e8107b21cb431a-dev
PETAL_CLOUD_ENDPOINT=https://api.droneleaf.io

# ── Local database ───────────────────────────────────────────────────────────
PETAL_LOCAL_DB_HOST=localhost
PETAL_LOCAL_DB_PORT=3000

# ── Redis ────────────────────────────────────────────────────────────────────
PETAL_REDIS_HOST=localhost
PETAL_REDIS_PORT=6379
PETAL_REDIS_DB=0
PETAL_REDIS_UNIX_SOCKET_PATH=/var/run/redis/redis-server.sock
PETAL_REDIS_HEALTH_MESSAGE_RATE=3.0

# ── Data operations ──────────────────────────────────────────────────────────
PETAL_GET_DATA_URL=/drone/onBoard/config/getData
PETAL_SCAN_DATA_URL=/drone/onBoard/config/scanData
PETAL_UPDATE_DATA_URL=/drone/onBoard/config/updateData
PETAL_SET_DATA_URL=/drone/onBoard/config/setData

# ── MQTT client ──────────────────────────────────────────────────────────────
PETAL_TS_CLIENT_HOST=localhost
PETAL_TS_CLIENT_PORT=3004
PETAL_CALLBACK_HOST=localhost
PETAL_CALLBACK_PORT=3005
PETAL_POLL_INTERVAL=1.0
PETAL_ENABLE_CALLBACKS=true
PETAL_COMMAND_EDGE_TOPIC=command/edge
PETAL_RESPONSE_TOPIC=response
PETAL_TEST_TOPIC=command
PETAL_COMMAND_WEB_TOPIC=command/web
PETAL_MQTT_HEALTH_CHECK_INTERVAL=10.0

# ── Proxy retry ──────────────────────────────────────────────────────────────
PETAL_MQTT_RETRY_INTERVAL=10.0
PETAL_CLOUD_RETRY_INTERVAL=10.0
PETAL_MQTT_STARTUP_TIMEOUT=5.0
PETAL_CLOUD_STARTUP_TIMEOUT=5.0
PETAL_MQTT_SUBSCRIBE_TIMEOUT=5.0

# ── Petal User Journey Coordinator ───────────────────────────────────────────
PETAL_DEBUG_SQUARE_TEST=false
ENVEOF

ok ".env written"

# ------------------------------------------------------------------------------
# scripts/setup-complete.sh
#
# Bundled in the package.  Executed by petal-app-manager-setup.service once
# dpkg releases its lock.  Idempotent — re-running is safe.
# ------------------------------------------------------------------------------

info "Writing setup-complete.sh..."

cat > "${BUILD_DIR}${INSTALL_DIR}/scripts/setup-complete.sh" <<EOF
#!/bin/bash
set -e

# ── constants (stamped at build time) ────────────────────────────────────────
APP_USER="${APP_USER}"
APP_GROUP="${APP_GROUP}"
INSTALL_DIR="${INSTALL_DIR}"
DATA_DIR="${DATA_DIR}"
LOG_DIR="${LOG_DIR}"
PYTHON_DIR="${PYTHON_DIR}"
PYTHON_VERSION="${PYTHON_VERSION}"
PDM_BIN="${PDM_BIN}"
SETUP_FLAG="${SETUP_FLAG}"
SERVICE_NAME="${SERVICE_NAME}"
SETUP_SERVICE_NAME="${SETUP_SERVICE_NAME}"

exec > >(tee -a "${LOG_DIR}/setup.log") 2>&1
echo ""
echo "======================================================="
echo " petal-app-manager first-run setup  \$(date)"
echo "======================================================="

# ── idempotency guard ─────────────────────────────────────────────────────────
if [ -f "\${SETUP_FLAG}" ]; then
    echo "Setup already complete — nothing to do."
    exit 0
fi

# ── wait for dpkg lock ────────────────────────────────────────────────────────
# postinst calls 'systemctl start --no-block', so dpkg may still hold its lock
# for a brief window.  Poll until the lock is free (max 120 s).
echo "==> Waiting for dpkg lock release..."
_waited=0
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
   || fuser /var/lib/dpkg/lock           >/dev/null 2>&1; do
    if [ "\${_waited}" -ge 120 ]; then
        echo "ERROR: dpkg lock not released after 120 s — aborting."
        exit 1
    fi
    sleep 2
    _waited=\$(( _waited + 2 ))
done
echo "    dpkg lock free after \${_waited}s"

# ── Redis 7.2+ ────────────────────────────────────────────────────────────────
echo "==> [1/4] Installing Redis 7.2+..."

_need_redis=true
if command -v redis-server &>/dev/null; then
    _ver="\$(redis-server --version | grep -oP '(?<=v=)\d+\.\d+' | head -1)"
    _major="\$(echo "\${_ver}" | cut -d. -f1)"
    _minor="\$(echo "\${_ver}" | cut -d. -f2)"
    if [ "\${_major}" -gt 7 ] || { [ "\${_major}" -eq 7 ] && [ "\${_minor}" -ge 2 ]; }; then
        echo "    Redis \${_ver} already installed — skipping"
        _need_redis=false
    fi
fi

if [ "\${_need_redis}" = true ]; then
    # The apt source + keyring were written by postinst; just install now.
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y redis
fi

# ── Redis UNIX socket (README §3) ────────────────────────────────────────────
echo "==> [2/4] Configuring Redis UNIX socket..."
REDIS_CONF="/etc/redis/redis.conf"
if [ -f "\${REDIS_CONF}" ]; then
    cp -n "\${REDIS_CONF}" "\${REDIS_CONF}.bak" 2>/dev/null || true

    grep -qE '^unixsocket '    "\${REDIS_CONF}" \
        || sed -i 's|^# *unixsocket .*|unixsocket /var/run/redis/redis-server.sock|' "\${REDIS_CONF}"

    grep -qE '^unixsocketperm ' "\${REDIS_CONF}" \
        || sed -i 's|^# *unixsocketperm .*|unixsocketperm 777|' "\${REDIS_CONF}"

    sed -i 's|^\(# *\)\?daemonize .*\$|daemonize no|'         "\${REDIS_CONF}"
    sed -i 's|^\(# *\)\?supervised .*\$|supervised systemd|'  "\${REDIS_CONF}"
fi

systemctl daemon-reload
systemctl enable  redis-server
systemctl restart redis-server

# Wait for socket (max 15 s)
for _i in \$(seq 1 15); do
    [ -S /var/run/redis/redis-server.sock ] && break
    sleep 1
done
[ -S /var/run/redis/redis-server.sock ] \
    && chmod 777 /var/run/redis/redis-server.sock \
    || echo "WARN: Redis UNIX socket not found yet"

# ── PDM: install production dependencies ─────────────────────────────────────
echo "==> [3/4] Installing production dependencies via PDM..."
cd "\${INSTALL_DIR}"
"\${PDM_BIN}" use -f /usr/local/bin/python3.11
"\${PDM_BIN}" install -G prod --no-editable

# ── Permissions ───────────────────────────────────────────────────────────────
echo "==> [4/4] Fixing permissions..."
chown -R "\${APP_USER}:\${APP_GROUP}" "\${INSTALL_DIR}"
chown -R "\${APP_USER}:\${APP_GROUP}" "\${DATA_DIR}" "\${LOG_DIR}"
chmod 640 "\${INSTALL_DIR}/.env"

# ── Mark complete ─────────────────────────────────────────────────────────────
touch "\${SETUP_FLAG}"

# ── Start the main service ────────────────────────────────────────────────────
echo "==> Starting \${SERVICE_NAME}..."
systemctl daemon-reload
systemctl enable  "\${SERVICE_NAME}"
systemctl start --no-block "\${SERVICE_NAME}" || true

echo ""
echo "======================================================="
echo " Setup finished  \$(date)"
echo "======================================================="
echo " Status : systemctl status  \${SERVICE_NAME}"
echo " Logs   : journalctl -u \${SERVICE_NAME} -f"
echo " Config : \${INSTALL_DIR}/.env"
echo ""
EOF

chmod 755 "${BUILD_DIR}${INSTALL_DIR}/scripts/setup-complete.sh"
ok "setup-complete.sh written"

# ------------------------------------------------------------------------------
# DEBIAN/control
# ------------------------------------------------------------------------------

info "Writing DEBIAN/control..."

cat > "${BUILD_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${PKG_VERSION}
Section: utils
Priority: optional
Architecture: ${PKG_ARCH}
Maintainer: ${PKG_MAINTAINER}
Homepage: ${PKG_HOMEPAGE}
Depends: ${DEPENDS}
Description: ${PKG_DESCRIPTION}
EOF

ok "control written"

# ------------------------------------------------------------------------------
# DEBIAN/conffiles  — dpkg preserves .env across upgrades
# ------------------------------------------------------------------------------

cat > "${BUILD_DIR}/DEBIAN/conffiles" <<EOF
${INSTALL_DIR}/.env
EOF

# ------------------------------------------------------------------------------
# DEBIAN/preinst
# ------------------------------------------------------------------------------

cat > "${BUILD_DIR}/DEBIAN/preinst" <<'EOF'
#!/bin/bash
set -e
echo "=== preinst ==="
for _svc in petal-app-manager.service petal-app-manager-setup.service; do
    systemctl is-active --quiet "${_svc}" 2>/dev/null \
        && systemctl stop "${_svc}" || true
done
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/preinst"

# ------------------------------------------------------------------------------
# DEBIAN/postinst
#
# IMPORTANT: must NOT call apt-get — dpkg holds /var/lib/dpkg/lock-frontend
# for the entire transaction.  All apt operations live in setup-complete.sh
# which runs via the setup service AFTER dpkg exits.
#
# This script:
#   1. Creates the system user
#   2. Downloads prebuilt Python 3.11 (python-build-standalone — no apt, no compile)
#   3. Creates system-wide python3.11 symlinks
#   4. Installs PDM via pip + configures venv.with_pip
#   5. Writes the Redis official apt repo config (key + source list) — file
#      writes only, no apt-get invocation
#   6. Enables + starts the setup service (--no-block so postinst returns
#      immediately without waiting for the service to finish)
# ------------------------------------------------------------------------------

info "Writing postinst..."

cat > "${BUILD_DIR}/DEBIAN/postinst" <<EOF
#!/bin/bash
set -e

APP_USER="${APP_USER}"
APP_GROUP="${APP_GROUP}"
INSTALL_DIR="${INSTALL_DIR}"
DATA_DIR="${DATA_DIR}"
LOG_DIR="${LOG_DIR}"

PYTHON_DIR="${PYTHON_DIR}"
PYTHON_VERSION="${PYTHON_VERSION}"
PBS_RELEASE="${PBS_RELEASE}"
PYTHON_BIN="${PYTHON_BIN}"
PDM_BIN="${PDM_BIN}"

SETUP_SERVICE_NAME="${SETUP_SERVICE_NAME}"

# ── [1/5] System user ─────────────────────────────────────────────────────────
# Running as root
echo "==> [1/5] Running as root — skipping user creation."

# ── [2/5] Python 3.11 — prebuilt relocatable build (no compilation) ───────────
# python-build-standalone ships a portable CPython linked against glibc 2.17,
# so one aarch64 tarball runs on both Ubuntu 20.04 (focal) and 24.04 (noble).
# Replaces the old pyenv source compile that segfaulted on noble/aarch64.
echo "==> [2/5] Installing prebuilt Python \${PYTHON_VERSION}..."
if [ ! -x "\${PYTHON_BIN}" ]; then
    case "\$(uname -m)" in
        aarch64|arm64) PBS_ARCH="aarch64-unknown-linux-gnu" ;;
        x86_64|amd64)  PBS_ARCH="x86_64-unknown-linux-gnu"  ;;
        *) echo "ERROR: unsupported architecture \$(uname -m)"; exit 1 ;;
    esac
    PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/\${PBS_RELEASE}/cpython-\${PYTHON_VERSION}%2B\${PBS_RELEASE}-\${PBS_ARCH}-install_only.tar.gz"
    _tmp="\$(mktemp -d)"
    echo "    downloading \${PBS_URL}"
    curl -fsSL --retry 3 "\${PBS_URL}" -o "\${_tmp}/python.tar.gz"
    # tarball extracts to a top-level 'python/' dir → \${PYTHON_DIR}
    rm -rf "\${PYTHON_DIR}"
    tar -xzf "\${_tmp}/python.tar.gz" -C "\${INSTALL_DIR}"
    rm -rf "\${_tmp}"
fi

# ── [3/5] System-wide symlinks (keeps system python untouched) ────────────────
echo "==> [3/5] Linking python3.11 system-wide..."
ln -sf "\${PYTHON_BIN}" /usr/local/bin/python3.11
ln -sf "\${PYTHON_DIR}/bin/pip3.11" /usr/local/bin/pip3.11
echo "    python3.11 → \$("\${PYTHON_BIN}" --version)"

# ── [4/5] PDM ─────────────────────────────────────────────────────────────────
# Prebuilt CPython already ships pip — no ensurepip bootstrap needed.
echo "==> [4/5] Installing PDM..."
"\${PYTHON_BIN}" -m pip install --quiet --upgrade pip pdm

# Required so packages inside the PDM venv can use pip (README §2)
"\${PDM_BIN}" config venv.with_pip True
echo "    pdm → \$("\${PDM_BIN}" --version)"

# ── [5/5] Redis apt repo — file writes only, NO apt-get ───────────────────────
# The setup service will run apt-get install redis after dpkg releases its lock.
echo "==> [5/5] Configuring Redis apt repo (no install yet)..."

curl -fsSL https://packages.redis.io/gpg \
    | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg

DISTRO="\$(lsb_release -cs)"
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb \${DISTRO} main" \
    > /etc/apt/sources.list.d/redis.list

echo "    Redis apt repo configured for \${DISTRO}"

# ── Enable + launch the setup service (non-blocking) ─────────────────────────
# --no-block: systemctl returns immediately; dpkg can finish and release its
# lock before the service script calls apt-get.
echo "==> Enabling setup service..."
systemctl daemon-reload
systemctl enable "\${SETUP_SERVICE_NAME}"
systemctl start  --no-block "\${SETUP_SERVICE_NAME}"

echo ""
echo "======================================================"
echo " Base install complete.  Setup running in background."
echo "======================================================"
echo ""
echo " Watch progress : journalctl -u \${SETUP_SERVICE_NAME} -f"
echo " Setup log      : ${LOG_DIR}/setup.log"
echo " After setup    : systemctl status ${SERVICE_NAME}"
echo ""

exit 0
EOF

chmod 755 "${BUILD_DIR}/DEBIAN/postinst"
ok "postinst written"

# ------------------------------------------------------------------------------
# DEBIAN/prerm
# ------------------------------------------------------------------------------

cat > "${BUILD_DIR}/DEBIAN/prerm" <<EOF
#!/bin/bash
set -e
for _svc in "${SERVICE_NAME}" "${SETUP_SERVICE_NAME}"; do
    systemctl stop    "\${_svc}" 2>/dev/null || true
    systemctl disable "\${_svc}" 2>/dev/null || true
done
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/prerm"

# ------------------------------------------------------------------------------
# DEBIAN/postrm
# ------------------------------------------------------------------------------

cat > "${BUILD_DIR}/DEBIAN/postrm" <<EOF
#!/bin/bash
set -e

case "\${1:-}" in
    purge)
        rm -rf "${DATA_DIR}"
        rm -rf "${LOG_DIR}"
        rm -rf "${INSTALL_DIR}"          # removes python, .venv, .env, scripts
        rm -f  /etc/apt/sources.list.d/redis.list
        rm -f  /usr/share/keyrings/redis-archive-keyring.gpg
        ;;
esac

systemctl daemon-reload || true
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"

# ------------------------------------------------------------------------------
# petal-app-manager-setup.service  (oneshot — runs once after dpkg exits)
# ------------------------------------------------------------------------------

info "Writing setup service unit..."

cat > "${BUILD_DIR}/etc/systemd/system/${SETUP_SERVICE_NAME}" <<EOF
[Unit]
Description=Petal App Manager — First-Run Setup (Redis + PDM)
Documentation=${PKG_HOMEPAGE}
After=network-online.target
Wants=network-online.target
# Skip if setup was already completed in a previous run
ConditionPathExists=!${SETUP_FLAG}

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${INSTALL_DIR}/scripts/setup-complete.sh
# pdm install of prod deps can take a few min on an RPi
TimeoutStartSec=1800
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${PKG_NAME}-setup

[Install]
WantedBy=multi-user.target
EOF

ok "setup service unit written"

# ------------------------------------------------------------------------------
# petal-app-manager.service  (main app — starts only after setup is done)
# ------------------------------------------------------------------------------

info "Writing main service unit..."

cat > "${BUILD_DIR}/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=Petal App Manager
Documentation=${PKG_HOMEPAGE}
# On first boot, wait for the setup service to finish before starting.
# Wants= (not Requires=) so that on subsequent boots the main service starts
# normally even though the setup service is inactive (condition already met —
# .setup-complete exists and the oneshot is skipped).
After=network.target ${SETUP_SERVICE_NAME} redis-server.service
Wants=${SETUP_SERVICE_NAME}
Requires=redis-server.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}/src
EnvironmentFile=${INSTALL_DIR}/.env
Environment=PYTHONUNBUFFERED=1

ExecStart=${INSTALL_DIR}/.venv/bin/uvicorn petal_app_manager.main:app \\
    --host 0.0.0.0 \\
    --port 9000 \\
    --log-level info \\
    --no-access-log \\
    --http h11

Restart=always
RestartSec=10
TimeoutStopSec=30

StandardOutput=journal
StandardError=journal
SyslogIdentifier=${PKG_NAME}

[Install]
WantedBy=multi-user.target
EOF

ok "main service unit written"

# ------------------------------------------------------------------------------
# Fix permissions
# ------------------------------------------------------------------------------

find "${BUILD_DIR}" -type d -exec chmod 755 {} \;
find "${BUILD_DIR}" -type f -exec chmod 644 {} \;

chmod 755 \
    "${BUILD_DIR}/DEBIAN/preinst" \
    "${BUILD_DIR}/DEBIAN/postinst" \
    "${BUILD_DIR}/DEBIAN/prerm" \
    "${BUILD_DIR}/DEBIAN/postrm" \
    "${BUILD_DIR}${INSTALL_DIR}/scripts/setup-complete.sh"

# Restore execute bit on bundled native binaries stripped by the blanket 644 pass
find "${BUILD_DIR}${INSTALL_DIR}/src" -type f -name "machineid_*" -exec chmod 755 {} \;

# .env not world-readable in the package tree either
chmod 640 "${BUILD_DIR}${INSTALL_DIR}/.env"

# ------------------------------------------------------------------------------
# Build the .deb
# ------------------------------------------------------------------------------

info "Building ${OUTPUT_FILE}..."
dpkg-deb --build "${BUILD_DIR}" "${OUTPUT_FILE}"
ok "built ${OUTPUT_FILE}"

echo ""
echo "======================================================="
echo " Package ready"
echo "======================================================="
echo ""
echo "  Install   : sudo apt install ./${OUTPUT_FILE}"
echo ""
echo "  After install, first-run setup runs automatically."
echo "  Watch it  : journalctl -u ${SETUP_SERVICE_NAME} -f"
echo "  Setup log : ${LOG_DIR}/setup.log"
echo ""
echo "  Once setup completes:"
echo "  Status    : sudo systemctl status ${SERVICE_NAME}"
echo "  Logs      : journalctl -u ${SERVICE_NAME} -f"
echo "  Config    : ${INSTALL_DIR}/.env"
echo "  Remove    : sudo apt remove ${PKG_NAME}"
echo "  Purge     : sudo apt remove --purge ${PKG_NAME}"
echo ""
