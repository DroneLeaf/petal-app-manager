Dependencies Installation
=========================

.. note::
   **Recommended Approach**: Use HEAR-CLI for automated installation (see Quick Start Guide). 
   The manual instructions below are provided for reference and custom setups.

System Requirements
-------------------

**Operating System**
   - Ubuntu 20.04 LTS or newer
   - Debian 11 or newer
   - Other Linux distributions (may require package name adjustments)

**Hardware Requirements**
   - Minimum 2GB RAM (4GB recommended for development)
   - 8GB available disk space
   - Internet connection for downloading dependencies

**Architecture Support**
   - x86_64 (Intel/AMD)
   - aarch64 (ARM64 - Raspberry Pi 4, NVIDIA Orin)

Python 3.11 Installation
-------------------------

Python 3.11 is installed via Miniforge to avoid conflicts with system Python:

**Install Dependencies**

.. code-block:: bash

   sudo apt-get update
   sudo apt-get install -y ca-certificates curl bzip2 wget

**Download and Install Miniforge**

.. code-block:: bash

   # Detect architecture automatically
   ARCH="$(uname -m)"
   case "${ARCH}" in
       x86_64|amd64) MINIFORGE_ARCH="x86_64" ;;
       aarch64|arm64) MINIFORGE_ARCH="aarch64" ;;
   esac
   
   # Download installer
   INSTALLER="Miniforge3-Linux-${MINIFORGE_ARCH}.sh"
   curl -L "https://github.com/conda-forge/miniforge/releases/latest/download/${INSTALLER}" -o "${INSTALLER}"
   chmod +x "${INSTALLER}"
   
   # Install Miniforge
   bash "${INSTALLER}" -b -p "${HOME}/miniforge3"

**Create Python 3.11 Environment**

.. code-block:: bash

   # Update conda
   ~/miniforge3/bin/conda update -y -n base conda
   
   # Create Python 3.11 environment
   ~/miniforge3/bin/conda create -y -n py311 python=3.11
   
   # Create system-wide symlinks
   sudo ln -sf "${HOME}/miniforge3/envs/py311/bin/python3.11" /usr/local/bin/python3.11
   sudo ln -sf "${HOME}/miniforge3/envs/py311/bin/pip3.11" /usr/local/bin/pip3.11

**Add to PATH**

.. code-block:: bash

   echo 'export PATH="$HOME/miniforge3/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   
   # Disable auto-activation of base environment
   conda config --set auto_activate_base false

**Verify Installation**

.. code-block:: bash

   python3.11 --version
   # Should output: Python 3.11.x

PDM Installation
----------------

PDM (Python Development Master) is used for dependency management:

**Install PDM**

.. code-block:: bash

   # Ensure Python 3.11 venv module is available
   python3.11 -m venv --help
   
   # Install PDM
   curl -sSL https://pdm-project.org/install-pdm.py | python3.11 -

**Configure PDM**

.. code-block:: bash

   # Add PDM to PATH
   export PATH="$HOME/.local/bin:$PATH"
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
   
   # Configure PDM to allow pip within virtual environments
   pdm config venv.with_pip True

**Verify Installation**

.. code-block:: bash

   pdm --version
   # Should output PDM version

Redis Installation and Configuration
-------------------------------------

Redis 7.2+ is required with UNIX socket support:

**Add Redis Official Repository**

.. code-block:: bash

   # Install dependencies
   sudo apt-get update
   sudo apt-get install -y lsb-release curl gpg apt-transport-https ca-certificates gnupg
   
   # Add Redis signing key
   curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
   sudo chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg
   
   # Add Redis repository
   DISTRO="$(lsb_release -cs)"
   echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $DISTRO main" | \
       sudo tee /etc/apt/sources.list.d/redis.list

**Install Redis**

.. code-block:: bash

   sudo apt-get update
   sudo apt-get install -y redis

**Configure Redis for UNIX Socket**

.. code-block:: bash

   # Backup original configuration
   sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.bak
   
   # Enable UNIX socket
   sudo sed -i 's|^# *unixsocket .*|unixsocket /var/run/redis/redis-server.sock|' /etc/redis/redis.conf
   sudo sed -i 's|^# *unixsocketperm .*|unixsocketperm 777|' /etc/redis/redis.conf
   sudo sed -i 's|^.*daemonize.*|daemonize no|' /etc/redis/redis.conf
   sudo sed -i 's|^.*supervised.*|supervised systemd|' /etc/redis/redis.conf
   
   # Restart and enable Redis
   sudo systemctl daemon-reload
   sudo systemctl restart redis-server
   sudo systemctl enable redis-server
   
   # Set socket permissions
   sudo chmod 777 /var/run/redis/redis-server.sock

**Verify Redis Installation**

.. code-block:: bash

   # Check version
   redis-server --version
   
   # Test connection
   redis-cli -s /var/run/redis/redis-server.sock ping
   # Should output: PONG

Redis Development Tools
-----------------------

Optional C++ development tools for Redis integration:

**Install Development Libraries**

.. code-block:: bash

   sudo apt-get install -y libhiredis-dev cmake build-essential

**Install redis-plus-plus (C++ Client)**

.. code-block:: bash

   # Create temporary directory
   mkdir -p ~/.tmp/redis-build
   cd ~/.tmp/redis-build
   
   # Clone and build redis-plus-plus
   git clone https://github.com/sewenew/redis-plus-plus.git
   cd redis-plus-plus
   mkdir build && cd build
   cmake ..
   make
   sudo make install
   
   # Cleanup
   cd ~ && rm -rf ~/.tmp/redis-build

Controller Dashboard
--------------------

Optional web-based controller dashboard:

.. code-block:: bash

   hear-cli local_machine run_program --p controller_dashboard_prepare

.. note::
   The controller dashboard requires HEAR-CLI to be installed and configured.
