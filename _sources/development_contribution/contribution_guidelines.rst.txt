Contribution Guidelines
=======================

Thank you for your interest in contributing to the Petal Stack! This guide will help you 
understand the dependency architecture and version management across all repositories.

Dependency Architecture
-----------------------

Understanding the Petal Stack Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Petal Stack consists of multiple repositories with specific dependency relationships:

.. graphviz::
   :caption: Petal Stack Dependency Architecture

   digraph dependency_structure {
       rankdir=TB;
       node [shape=box, style=filled];
       
       // Core components
       pam [label="Petal App Manager\n(pyproject.toml)\nDefault: main", fillcolor=lightblue];
       pymavlink [label="pymavlink\n(mavlink/pymavlink/__init__.py)\nDefault: dev-sitl", fillcolor=orange];
       leafsdk [label="LeafSDK\n(pyproject.toml)\nDefault: main", fillcolor=lightgreen];
       
       // Petals
       flight_log [label="petal-flight-log\n(pyproject.toml)\nDefault: master", fillcolor=palegreen];
       warehouse [label="petal-warehouse\n(pyproject.toml)\nDefault: main", fillcolor=palegreen];
       leafsdk_petal [label="petal-leafsdk\n(pyproject.toml)\nDefault: main\n⚠️ Depends on LeafSDK", fillcolor=palegreen];
       journey [label="petal-user-journey-coordinator\n(pyproject.toml)\nDefault: main", fillcolor=palegreen];
       qgc [label="petal-qgc-mission-server\n(pyproject.toml)\nDefault: main", fillcolor=palegreen];
       
       // Dependencies
       pam -> pymavlink [label="PROD: PyPI\nSITL: file://", color=blue, style=bold];
       pam -> flight_log [label="PROD: git tag\nSITL: editable", color=blue, style=bold];
       pam -> warehouse [label="PROD: git tag\nSITL: editable", color=blue, style=bold];
       pam -> leafsdk_petal [label="PROD: git tag\nSITL: editable", color=blue, style=bold];
       pam -> journey [label="PROD: git tag\nSITL: editable", color=blue, style=bold];
       pam -> qgc [label="PROD: git tag\nSITL: editable", color=blue, style=bold];
       
       leafsdk_petal -> leafsdk [label="PROD: PyPI\nSITL: editable", color=green, style=bold];
       
       // Legend
       subgraph cluster_legend {
           label="Legend";
           style=filled;
           color=lightgray;
           rankdir=TB;
           
           leg_note [label="Version stored in pyproject.toml (except pymavlink: __init__.py)\nPROD = Production deployment | SITL = Development environment", shape=plaintext];
       }
   }

**Key Points:**

- **PAM (Petal App Manager)**: Only depends on ``pymavlink`` and the petals
- **petal-leafsdk**: Special case - depends on ``LeafSDK``
- **Production (PROD)**: Uses PyPI packages or git tags for stable releases
- **SITL (Development)**: Uses editable installs for live development
- **CI/CD**: Does not install petals (framework testing only)

Version Management by Repository
---------------------------------

Petal App Manager
~~~~~~~~~~~~~~~~~

**Repository**: ``petal-app-manager``

**Default Branch**: ``main``

**Version Location**: ``pyproject.toml``

**Deployment Modes**:

- **Production**: Installs petals directly from git tags (versions specified in ``pyproject.toml``)
- **CI/CD**: Does not install petals (framework testing only)
- **SITL**: Installs petals in editable mode + ``LeafSDK`` (editable)

**Release Process**:

1. Update version in ``pyproject.toml``
2. Update petal versions in ``pyproject.toml`` under ``[project.optional-dependencies]``
3. Commit changes
4. Create and push git tag: ``git tag v0.1.x && git push origin v0.1.x``

Individual Petals
~~~~~~~~~~~~~~~~~

All petals follow the same versioning pattern:

petal-flight-log
^^^^^^^^^^^^^^^^

**Default Branch**: ``master``

**Version Location**: ``pyproject.toml``

**Release Process**:

1. Bump version in ``pyproject.toml``
2. Commit changes
3. Create and push git tag: ``git tag v0.1.x && git push origin v0.1.x``
4. PAM will install in production directly from this git tag

petal-warehouse
^^^^^^^^^^^^^^^

**Default Branch**: ``main``

**Version Location**: ``pyproject.toml``

**Release Process**: Same as ``petal-flight-log``

petal-user-journey-coordinator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Default Branch**: ``main``

**Version Location**: ``pyproject.toml``

**Release Process**: Same as ``petal-flight-log``

petal-qgc-mission-server
^^^^^^^^^^^^^^^^^^^^^^^^^

**Default Branch**: ``main``

**Version Location**: ``pyproject.toml``

**Release Process**: Same as ``petal-flight-log``

petal-leafsdk (Special Case)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Default Branch**: ``main``

**Version Location**: ``pyproject.toml``

**⚠️ Important**: This petal depends on ``LeafSDK``

**Release Process**:

1. **First**, ensure ``LeafSDK`` is updated and published to PyPI (see below)
2. Bump ``LeafSDK`` version in ``petal-leafsdk``'s ``pyproject.toml`` dependencies
3. Bump ``petal-leafsdk`` version in ``pyproject.toml``
4. Commit changes
5. Create and push git tag: ``git tag v0.1.x && git push origin v0.1.x``

Non-Petal Packages
------------------

LeafSDK
~~~~~~~

**Repository**: ``LeafSDK``

**Default Branch**: ``main``

**Version Location**: ``pyproject.toml``

**Deployment**:

- **Production**: Installed from PyPI (due to dependency from ``petal-leafsdk``)
- **SITL**: Installed in editable mode

**Release Process**:

1. Commit all changes
2. Bump version in ``pyproject.toml``
3. Create and push git tag: ``git tag v0.2.x && git push origin v0.2.x``
4. This triggers a CI/CD workflow to publish to PyPI

mavlink/pymavlink (Very Special Case)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Repository**: ``leaf-mavlink``

**Default Branch**: ``dev-sitl``

**Version Location**: ``mavlink/pymavlink/__init__.py``

**Deployment**:

- **Production**: Installed from PyPI
- **CI/CD**: Installed from PyPI  
- **SITL**: Installed via ``file://`` (not editable, requires rebuild)

**⚠️ Critical Notes**:

- Message definitions and pymavlink must be maintained together
- Always commit both message changes and submodule updates together
- Ensure the ``mavlink`` repository is checked out to ``dev-sitl`` branch

**Release Process**:

1. **Add/Modify MAVLink Messages**:

   .. code-block:: bash

      # Edit message definitions
      cd ~/petal-app-manager-dev/mavlink
      # Ensure on dev-sitl branch
      git checkout dev-sitl
      
      # Edit: message_definitions/v1.0/droneleaf_mav_msgs.xml
      # Add your new message definitions

2. **Format XML Files** (if CI/CD "Formatting Checks" job fails):

   .. code-block:: bash

      cd ~/petal-app-manager-dev/mavlink
      ./scripts/format_xml.sh /v1.0/common.xml
      ./scripts/format_xml.sh /v1.0/droneleaf_mav_msgs.xml

3. **Bump pymavlink Version**:

   .. code-block:: bash

      # Edit: mavlink/pymavlink/__init__.py
      # Update __version__ = '0.1.x'

4. **Commit All Changes** (including submodule updates):

   .. code-block:: bash

      cd ~/petal-app-manager-dev/mavlink/pymavlink
      git add .
      git commit -m "chore: bump version to 0.1.x"
    
      # IMPORTANT: Also commit the submodule update in parent if needed
      cd ~/petal-app-manager-dev/mavlink
      git add .
      git commit -m "feat: add new MAVLink message definitions"

5. **Tag and Push**:

   .. code-block:: bash

      # Tag the latest commit on mavlink/pymavlink
      cd ~/petal-app-manager-dev/mavlink/pymavlink
      git tag v0.1.x
      git push origin dev-sitl
      git push origin v0.1.x
      
      # This triggers a release to PyPI via workflow

**MAVLink Message Definition Location**:

.. code-block:: text

   ~/petal-app-manager-dev/mavlink/message_definitions/v1.0/droneleaf_mav_msgs.xml

Example message definition structure:

.. code-block:: xml

   <message id="77000" name="LEAF_MODE">
     <description>The system mode, as defined by enum LEAF_MODE</description>
     <field type="uint8_t" name="mode" enum="LEAF_MODE">The new leaf mode.</field>
   </message>

Adding New DroneLeaf MAVLink Messages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When adding a new custom DroneLeaf message, follow this complete workflow:

**Step 1: Define the Message in XML**

Edit ``message_definitions/v1.0/droneleaf_mav_msgs.xml``:

.. code-block:: xml

   <!-- Add a new message -->
   <message id="77XXX" name="LEAF_YOUR_NEW_MESSAGE">
     <description>Description of what this message does</description>
     <field type="uint8_t" name="status">Status field description</field>
     <field type="float" name="value">Value field description</field>
   </message>

   <!-- Add a new enum (if needed) -->
   <enum name="LEAF_YOUR_NEW_ENUM">
     <entry value="0" name="LEAF_YOUR_NEW_ENUM_VALUE1">
       <description>First value description</description>
     </entry>
     <entry value="1" name="LEAF_YOUR_NEW_ENUM_VALUE2">
       <description>Second value description</description>
     </entry>
   </enum>

**Step 2: Use the Message in Python Code**

After the message is built into pymavlink, use it in your petal code:

.. code-block:: python

   from pymavlink.dialects.v20 import droneleaf_mav_msgs as leafMAV

   # Register a handler for receiving the message
   proxy.register_handler(
       str(leafMAV.MAVLINK_MSG_ID_LEAF_YOUR_NEW_MESSAGE),
       my_handler_function
   )

   # Create and send the message
   msg = leafMAV.MAVLink_leaf_your_new_message(
       status=1,
       value=3.14
   )
   proxy.send("mav", msg)

   # Use enum values
   if current_status == leafMAV.LEAF_YOUR_NEW_ENUM_VALUE1:
       # Handle this state
       pass

**Step 3: Register in Message Verification Config**

Edit ``mavlink/pymavlink/.github/workflows/required_pymavlink_messages.json`` to register 
your new symbols. This ensures CI verifies they exist after building pymavlink.

.. code-block:: json

   {
     "dialects": {
       "pymavlink.dialects.v20.droneleaf_mav_msgs": {
         "message_ids": {
           "items": [
             "MAVLINK_MSG_ID_LEAF_STATUS",
             "MAVLINK_MSG_ID_LEAF_YOUR_NEW_MESSAGE"
           ]
         },
         "message_classes": {
           "items": [
             "MAVLink_leaf_status_message",
             "MAVLink_leaf_your_new_message"
           ]
         },
         "enums": {
           "LEAF_YOUR_NEW_ENUM": [
             "LEAF_YOUR_NEW_ENUM_VALUE1",
             "LEAF_YOUR_NEW_ENUM_VALUE2"
           ]
         }
       }
     }
   }

**What to Register:**

.. list-table:: Message Verification Categories
   :header-rows: 1
   :widths: 25 35 40

   * - Category
     - Example
     - When to Add
   * - ``message_ids``
     - ``MAVLINK_MSG_ID_LEAF_STATUS``
     - When you register a handler for the message
   * - ``message_classes``
     - ``MAVLink_leaf_status_message``
     - When you create/send the message
   * - ``enums``
     - ``LEAF_STATUS_FLYING``
     - When you use enum values in code
   * - ``constants``
     - ``ENABLED_ALWAYS``
     - When you use standalone constants

**Step 4: Verify Locally (Optional)**

.. code-block:: bash

   # Create and activate a virtual environment with Python 3.11
   cd ~/petal-app-manager-dev/mavlink/pymavlink
   python3.11 -m venv .venv
   source .venv/bin/activate

   # Build and install pymavlink with new message definitions
   # MDEF must point to the message_definitions directory
   MDEF=~/petal-app-manager-dev/mavlink/message_definitions/v1.0 python3 -m pip install . -v

   # Run verification script
   python .github/workflows/verify_pymavlink_messages.py --verbose

.. note::

   The ``MDEF`` environment variable must point to the directory containing the message 
   definition XML files. Typically, this is the ``message_definitions/v1.0`` folder in the 
   mavlink repository (e.g., ``/home/droneleaf/petal-app-manager-dev/mavlink/message_definitions/v1.0``).

**Step 5: Commit, Tag, and Push**

Follow the standard release process above. The CI workflow will:

1. Clone ``leaf-mavlink`` with latest message definitions
2. Build pymavlink from source
3. Run the verification script
4. Fail if any registered symbol is missing

**⚠️ Important**: Only messages that are **actually used in source code** should be 
registered in the verification config - not all messages from the dialect files.

Version Summary Table
---------------------

.. list-table:: Repository Version Management
   :header-rows: 1
   :widths: 25 15 20 40

   * - Repository
     - Default Branch
     - Version File
     - Installation Method
   * - petal-app-manager
     - main
     - pyproject.toml
     - PROD: git tag | SITL: editable
   * - petal-flight-log
     - master
     - pyproject.toml
     - PROD: git tag | SITL: editable
   * - petal-warehouse
     - main
     - pyproject.toml
     - PROD: git tag | SITL: editable
   * - petal-user-journey-coordinator
     - main
     - pyproject.toml
     - PROD: git tag | SITL: editable
   * - petal-qgc-mission-server
     - main
     - pyproject.toml
     - PROD: git tag | SITL: editable
   * - petal-leafsdk
     - main
     - pyproject.toml
     - PROD: git tag | SITL: editable (⚠️ depends on LeafSDK)
   * - LeafSDK
     - main
     - pyproject.toml
     - PROD: PyPI | SITL: editable
   * - leaf-mavlink (pymavlink)
     - dev-sitl
     - pymavlink/__init__.py
     - PROD: PyPI | CI/CD: PyPI | SITL: file://

Getting Help
------------

**Communication Channels**

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Request Comments**: For code-specific questions

**Resources**

- :doc:`../getting_started/index` - Setup guides
- :doc:`adding_petals` - Petal development guide
- :doc:`../api_reference/index` - API documentation
- :doc:`../known_issues` - Common problems and solutions

Thank you for contributing to the Petal Stack! 🚁✨
