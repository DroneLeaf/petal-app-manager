=======================================
Petal App Manager Profiling Tools
=======================================

Comprehensive profiling infrastructure for analyzing PAM performance under different operational scenarios to identify bottlenecks and optimize resource usage on low-resource devices (RPi, Orin).

Table of Contents
==================

* `Overview`_
* `Quick Start`_
* `Profiling Scenarios`_
* `Output Formats & Visualizations`_
* `Interpretation Guide`_
* `Troubleshooting`_

----

Overview
=========

This profiling tool uses **py-spy**, a sampling profiler that can profile ALL threads and async tasks in PAM:

✅ **Captures complete PAM behavior:**

* MAVLink worker threads for message processing
* Redis worker threads for pub/sub handling
* MQTT worker threads for message handling
* Async background tasks (health status publishing, petal loading, etc.)
* Petal startup/shutdown async methods
* Proxy initialization and runtime behavior

✅ **Better profiling characteristics:**

* Lower overhead (~3% CPU)
* Sampling-based (minimal interference)
* Runs PAM via uvicorn (real runtime conditions)

✅ **Rich visualization:**

* Interactive Speedscope viewer with flame graph, icicle graph, and timeline views
* Per-thread filtering and analysis
* No installation required (web-based viewer)

----

Quick Start
============

1. Prerequisites
-----------------

Ensure you have:

* PAM development environment set up
* Python 3.11.x virtual environment at ``.venv``
* Redis, MQTT broker, and other PAM dependencies running

2. Install Dependencies
------------------------

.. code-block:: bash

   # Navigate to petal-app-manager directory
   cd /home/droneleaf/petal-app-manager-dev/petal-app-manager

   # Activate virtual environment
   source .venv/bin/activate

   # Install profiling tools
   pip install -r tools/profiling/requirements-profiling.txt

   # (Optional) Install Speedscope CLI for local viewing
   # Note: The web version at https://www.speedscope.app/ requires NO installation!
   # Only install CLI if you prefer local viewing over uploading to web.
   # Requires Node.js/npm to be installed first:
   npm install -g speedscope

**Installed Python tools:**

* ``py-spy`` - Multi-threaded sampling profiler (used by profile_pam.py)

**Optional CLI tools:**

* ``speedscope`` (npm) - Local speedscope viewer (web version at speedscope.app requires no installation)

3. Run Your First Profile
---------------------------

.. code-block:: bash

   # Quick test - 30 seconds
   python tools/profiling/profile_pam.py \
       --scenario idle-no-leaffc \
       --duration 30

   # Full profile - 60 seconds
   python tools/profiling/profile_pam.py \
       --scenario idle-no-leaffc \
       --duration 60

This will:

1. Start PAM via uvicorn on port 8001
2. Profile for the specified duration
3. Generate Speedscope JSON file
4. Save to ``tools/profiling/profiles/``

4. View Results
----------------

**Interactive (best for thread analysis):**

**Option 1: Web-based (Recommended - No installation required!)**

.. code-block:: text

   1. Visit https://www.speedscope.app/
   2. Click "Browse" and select the .speedscope.json file from:
      tools/profiling/profiles/pam_*_pyspy.speedscope.json
   3. Toggle between views:
      - Time Order: See execution timeline
      - Left Heavy: Flame graph (top-down)
      - Sandwich: Icicle graph (bottom-up)
   4. Use thread filter to isolate worker threads

**Option 2: CLI (if you installed speedscope via npm)**

.. code-block:: bash

   # View speedscope locally (opens in browser)
   speedscope tools/profiling/profiles/pam_idle-no-leaffc_*_pyspy.speedscope.json

   # Or navigate to the file and run
   cd tools/profiling/profiles
   speedscope pam_*_pyspy.speedscope.json

----

Profiling Scenarios
====================

Example scenario labels for organizing profile data:

* ``idle-no-leaffc``
* ``idle-with-leaffc``
* ``esc-calibration``
* ``rc-stream``
* ``mission-execution``

**Note:** Scenarios are labels for record keeping only. The profiler captures whatever PAM is actually doing at runtime.

**Recommended duration:** 60-120s for most scenarios, 120-300s for longer operations.

Example SITL Mission for Profiling
------------------------------------

For profiling mission execution in SITL (Software-In-The-Loop), use this sample mission plan:

**File:** ``tools/profiling/example_mission_sitl.json``

.. code-block:: json

   {
     "config": {
       "joystick_mode": "ENABLED_ON_PAUSE"
     },
     "edges": [
       {
         "from": "Takeoff",
         "to": "Wait 1"
       },
       {
         "from": "Wait 1",
         "to": "GotoLocalWaypoint 1"
       },
       {
         "from": "GotoLocalWaypoint 1",
         "to": "GotoLocalWaypoint 2"
       },
       {
         "from": "GotoLocalWaypoint 2",
         "to": "GotoLocalWaypoint 3"
       },
       {
         "from": "GotoLocalWaypoint 3",
         "to": "Wait 2"
       },
       {
         "from": "Wait 2",
         "to": "Land"
       }
     ],
     "id": "main",
     "nodes": [
       {
         "name": "Takeoff",
         "params": {
           "alt": 1
         },
         "type": "Takeoff"
       },
       {
         "name": "Wait 1",
         "params": {
           "duration": 2
         },
         "type": "Wait"
       },
       {
         "name": "GotoLocalWaypoint 1",
         "params": {
           "speed": [
             0.2
           ],
           "waypoints": [
             [
               0.5,
               0,
               1
             ]
           ],
           "yaw_speed": [
             30
           ],
           "yaws_deg": [
             0
           ]
         },
         "type": "GotoLocalPosition"
       },
       {
         "name": "GotoLocalWaypoint 2",
         "params": {
           "speed": [
             0.2,
             0.2
           ],
           "waypoints": [
             [
               0.5,
               0.5,
               1
             ],
             [
               0,
               0,
               1
             ]
           ],
           "yaw_speed": [
             30,
             30
           ],
           "yaws_deg": [
             0,
             0
           ]
         },
         "type": "GotoLocalPosition"
       },
       {
         "name": "GotoLocalWaypoint 3",
         "params": {
           "speed": [
             0.2,
             0.3,
             0.4
           ],
           "waypoints": [
             [
               0,
               0.5,
               1
             ],
             [
               0.5,
               0.5,
               1
             ],
             [
               0.5,
               0,
               1
             ]
           ],
           "yaw_speed": [
             10,
             20,
             20
           ],
           "yaws_deg": [
             0,
             10,
             20
           ]
         },
         "type": "GotoLocalPosition"
       },
       {
         "name": "Wait 2",
         "params": {
           "duration": 2
         },
         "type": "Wait"
       },
       {
         "name": "Land",
         "params": {},
         "type": "Land"
       }
     ]
   }

**How to profile with this mission:**

1. Start profiling:

   .. code-block:: bash

      python tools/profiling/profile_pam.py --scenario mission-execution --duration 120

2. While profiler is running, send mission via MQTT or HTTP:

   .. code-block:: bash

      # Via HTTP (using curl)
      curl -X POST http://localhost:8001/petal-leafsdk/mission/plan \
        -H "Content-Type: application/json" \
        -d @tools/profiling/example_mission_sitl.json

3. The profile will capture mission execution including:

   * Mission loading and validation
   * Mission runner loop execution
   * MAVLink command generation
   * Waypoint processing

----

Output Formats & Visualizations
=================================

Speedscope JSON (Interactive) ⭐
---------------------------------

Each profiling run generates a single Speedscope JSON file:

**File:** ``pam_<scenario>_<timestamp>_pyspy.speedscope.json``

**Three interactive views in one:**

* **Time Order:** Chronological execution timeline
* **Left Heavy:** Flame graph (top-down call hierarchy)
* **Sandwich:** Icicle graph (bottom-up call hierarchy)

**Features:**

* Filter by thread name to isolate workers
* Search for specific functions
* Zoom into call stacks
* See exact time percentages and call counts
* No installation required (web viewer at speedscope.app)

**How to view:**

1. Visit https://www.speedscope.app/
2. Click "Browse" and select the ``.speedscope.json`` file
3. Use the thread dropdown to analyze individual workers
4. Toggle between the three view modes

**Or with CLI (if installed):**

.. code-block:: bash

   speedscope tools/profiling/profiles/pam_*_pyspy.speedscope.json

Understanding the Views
------------------------

Flame Graph (Left Heavy)
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Shows top-down call hierarchy
* Width = CPU time (wider = more time)
* Read from bottom (entry) to top (leaf functions)
* Best for: Finding hot paths from entry points

Icicle Graph (Sandwich)
^^^^^^^^^^^^^^^^^^^^^^^^^

* Shows bottom-up call hierarchy (inverted flame)
* Width = CPU time
* Read from top (leaf) to bottom (callers)
* Best for: Finding what calls expensive functions

Timeline (Time Order)
^^^^^^^^^^^^^^^^^^^^^^

* Shows chronological execution
* X-axis = time, Y-axis = call stack depth
* Best for: Understanding execution flow and patterns

----

Interpretation Guide
=====================

What to Look For
-----------------

1. Worker Thread Overhead (Target: <5% CPU in idle)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Where:** Filter by thread in Speedscope, or look for thread names in flame graph

**Look for:**

* ``time.sleep()`` should dominate (95%+ in idle scenarios)
* Actual work (message parsing, pub/sub) should be minimal in idle
* Excessive polling or busy-waiting

**PAM worker threads:**

* MAVLink worker threads: Message processing
* Redis worker threads: Pub/sub handling
* MQTT worker threads: Message handling

**Example findings:**

.. code-block:: text

   Thread: MAVLinkWorker-1
   ├─ time.sleep() ━━━━━━━━━━━━━━━━━━━ 97.5%
   └─ parse_message() ━ 2.5%  ← This should be minimal in idle

2. Async Task Analysis
^^^^^^^^^^^^^^^^^^^^^^^^

**Where:** Search for async task functions in Speedscope (e.g., health status publishing, petal loading)

**Look for:**

* Health publisher frequency and overhead
* Petal loading overhead
* Unnecessary async task creation

**Example:**

.. code-block:: text

   publish_health_status()
   ├─ redis.publish() ━━━━━ 60%
   ├─ get_health_data() ━━ 30%
   └─ json.dumps() ━ 10%

3. Periodic Task Frequency
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Where:** Speedscope search or timeline view

**Look for:**

* Functions appearing frequently in the timeline
* Repetitive call patterns in flame graph
* High sample counts for specific functions

**How to identify:**

1. Use Speedscope search (Ctrl/Cmd+F) to find a function
2. Check how many times it appears across samples
3. Look for regular patterns in timeline view

**Example issue:** Function appears every few milliseconds when it should run every few seconds

4. Blocking Operations
^^^^^^^^^^^^^^^^^^^^^^^

**Where:** Speedscope timeline view, look for long plateaus

**Look for:**

* Synchronous HTTP requests in async context
* File I/O blocking event loop
* Database queries without connection pooling
* Slow JSON parsing on large payloads

**Red flags:**

* ``requests.get()`` in async function (use ``aiohttp`` instead)
* ``open().read()`` on large files (use async I/O)
* ``time.sleep()`` in async function (use ``asyncio.sleep()``)

5. Message Processing Overhead
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Where:** Filter by MAVLink/Redis/MQTT threads

**Look for:**

* Time spent in message deserialization
* Excessive message copying
* Inefficient message routing

Reading Flame Graphs
---------------------

**Visual guide:**

.. code-block:: text

   Width = CPU time (wider = more time spent)
      ↓
   ┌─────────────────────────────────────────────┐
   │          main() [60.0s]                     │  ← Entry point (widest)
   ├─────────────────────┬───────────────────────┤
   │  startup_all()      │   message_loop()      │  ← Major functions
   │     [10.0s]         │      [50.0s]          │
   ├──────┬──────────────┼──────────┬────────────┤
   │load_ │publish_      │parse_msg │process_msg │  ← Leaf functions
   │petals│health()      │()        │()          │     (actual work)
   │[5.0s]│[5.0s]        │[25.0s]   │[25.0s]     │
   └──────┴──────────────┴──────────┴────────────┘
      ↑
   Height = call stack depth

**Interpretation:**

* **Wide plateaus at top** = Functions doing actual work (optimization targets)
* **Thin spikes** = Quick function calls (usually not worth optimizing)
* **Many horizontal slices** = Deep call stacks (potential for inlining)
* **Uneven widths** = Branching logic or different code paths

Reading Icicle Graphs
-----------------------

Same as flame graphs, but **inverted** (read bottom-to-top instead of top-to-bottom):

* Bottom = Leaf functions (where CPU time is spent)
* Top = Entry points (callers)
* **Use to answer:** "What calls this expensive function?"

Common Patterns to Identify
-----------------------------

Pattern 1: Busy-Wait Loop
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Flame graph shows:
     while_loop() ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
       └─ check_condition() ━━━━━━━━━━━━━━━━━━ 98%

   Fix: Add sleep() or use event-based waiting

Pattern 2: Excessive Polling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Speedscope timeline shows:
     Repeated calls to poll_status() every few milliseconds
     Function dominates thread CPU time

   Fix: Increase poll interval or use change notifications

Pattern 3: Synchronous I/O in Async Context
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Timeline shows long plateau:
     async_handler() ━━━━━━━━━━━━━━━━━━━━━
       └─ requests.get() ━━━━━━━━━━━━━━━━  (blocking!)

   Fix: Use aiohttp.ClientSession() instead

Pattern 4: Redundant Serialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Flame graph shows:
     send_message() ━━━━━━━━━━━━━
       ├─ json.dumps() ━━━━━ 40%
       ├─ json.loads() ━━━━━ 40%
       └─ actual_work() ━ 20%

   Fix: Cache serialized data or reduce serialize/deserialize cycles

----

Troubleshooting
================

Environment Issues
-------------------

**Q: ``Command not found: python`` or ``pip``**

.. code-block:: bash

   # Check if venv is activated
   echo $VIRTUAL_ENV  # Should show .venv path

   # Activate venv
   source .venv/bin/activate

   # Verify prompt shows (petal-app-manager-3.11)

**Q: ``ModuleNotFoundError: No module named 'petal_app_manager'``**

.. code-block:: bash

   # Ensure you're in the right directory
   pwd  # Should be .../petal-app-manager

   # Verify PYTHONPATH (profiler sets this automatically)
   echo $PYTHONPATH

   # Check if PAM is installed in editable mode
   pip show petal-app-manager

**Q: Wrong Python version**

.. code-block:: bash

   # Check version
   python --version  # Should be 3.11.x

   # If wrong, recreate venv
   rm -rf .venv
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e .

Profiler Issues
----------------

**Q: py-spy error: "Permission denied" or "Operation not permitted"**

.. code-block:: bash

   # Option 1: Run with sudo (not recommended)
   sudo $(which python) tools/profiling/profile_pam_pyspy.py ...

   # Option 2: Grant ptrace capability (Linux)
   sudo setcap cap_sys_ptrace=eip $(which py-spy)

   # Option 3: Adjust ptrace_scope (temporary, less secure)
   echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope

**Q: py-spy error: "No python processes found"**

* This was fixed by having py-spy launch uvicorn directly (not attach to existing process)
* Ensure you're using the updated ``profile_pam_pyspy.py``
* Check that uvicorn is installed: ``pip show uvicorn``

**Q: PAM fails to start during profiling**

.. code-block:: bash

   # Check dependencies are running
   systemctl status redis
   systemctl status mosquitto

   # Check port 8001 is available
   lsof -i :8001  # Should be empty

   # Check PAM can start normally
   python -m uvicorn petal_app_manager.main:app --port 8001
   # Then Ctrl+C and try profiler again

**Q: Profiling terminates early**

.. code-block:: bash

   # Check for errors in output
   python tools/profiling/profile_pam_pyspy.py --scenario idle-no-leaffc --duration 60 2>&1 | tee profile.log

   # Look for common issues:
   # - Import errors
   # - Configuration file missing
   # - Dependency connection failures

Visualization Issues
---------------------

**Q: Speedscope won't load JSON file**

* Verify file exists and is not empty: ``ls -lh tools/profiling/profiles/*.speedscope.json``
* Check file is valid JSON: ``jq . <file>.speedscope.json | head``
* Try uploading to alternative Speedscope instance
* Check browser console for errors (F12)

Performance Issues
-------------------

**Q: Profile files are too large (>100MB)**

.. code-block:: bash

   # Reduce duration
   python tools/profiling/profile_pam.py --scenario idle-no-leaffc --duration 30

   # Reduce sampling rate (edit profile_pam.py, change --rate 100 to --rate 50)

**Q: Profiling takes too long**

.. code-block:: bash

   # Reduce duration for quick tests
   python tools/profiling/profile_pam.py --scenario idle-no-leaffc --duration 30

Results Interpretation Issues
-------------------------------

**Q: Profile shows 97% time.sleep(), can't see actual work**

Use Speedscope's thread filter to isolate worker threads:

.. code-block:: text

   1. Upload to speedscope.app
   2. Click "Thread" dropdown at top
   3. Select individual worker threads (e.g., MAVLinkWorker, RedisWorker, MQTTWorker)
   4. Now you'll see actual work in each thread (sleep will be much less dominant)

In idle scenarios, sleep dominating is expected. The key is looking at the non-sleep portions to understand overhead.

**Q: Can't find specific function in flame graph**

.. code-block:: text

   Use Speedscope search:
   1. Upload to speedscope.app
   2. Press Ctrl+F or Cmd+F
   3. Type function name
   4. Click through matches to see all occurrences

**Q: Don't understand thread names**

.. code-block:: text

   Common thread naming patterns in PAM:
   - MainThread: Main event loop, PAM startup
   - ThreadPoolExecutor-*: Async executor threads
   - MAVLinkWorker-*: MAVLink message processing
   - RedisWorker-*: Redis pub/sub handlers
   - MQTTWorker-*: MQTT message handlers
   - asyncio_*: Asyncio internal threads

----

Quick Reference
================

Command Cheatsheet
-------------------

.. code-block:: bash

   # SETUP
   source .venv/bin/activate
   pip install -r tools/profiling/requirements-profiling.txt

   # PROFILE
   python tools/profiling/profile_pam.py --scenario idle-no-leaffc --duration 60
   python tools/profiling/profile_pam.py --scenario idle-no-leaffc --duration 30  # Quick test

   # VISUALIZE
   # Upload .speedscope.json to https://www.speedscope.app/
   # Or: speedscope tools/profiling/profiles/*.speedscope.json

File Naming Conventions
------------------------

.. code-block:: text

   Profile output:
     pam_<scenario>_<YYYYMMDD_HHMMSS>_pyspy.speedscope.json

   Examples:
     pam_idle-no-leaffc_20260206_143022_pyspy.speedscope.json
     pam_mission-execution_20260206_150145_pyspy.speedscope.json

Keyboard Shortcuts (Speedscope)
---------------------------------

.. code-block:: text

   Ctrl/Cmd + F    Search for function
   Ctrl/Cmd + +/-  Zoom in/out
   W/A/S/D         Navigate flamegraph
   T               Toggle thread view
   V               Toggle view (flame/icicle/timeline)
   0               Reset zoom

----

Getting Help
=============

If you encounter issues not covered here:

1. **Check terminal output** for error messages
2. **Verify setup** using commands in Quick Reference
3. **Review profile files** exist and have content: ``ls -lh tools/profiling/profiles/``
4. **Check PAM logs** for runtime errors
5. **Test PAM standalone** before profiling: ``python -m uvicorn petal_app_manager.main:app``

**Common first steps:**

.. code-block:: bash

   # Full environment check
   source .venv/bin/activate
   python --version  # Should be 3.11.x
   which py-spy  # Should show .venv/bin/py-spy
   dot -V  # Should show graphviz version
   pwd  # Should be .../petal-app-manager

----

Summary
========

1. **Use** ``profile_pam.py`` - single profiler using py-spy (sees all threads/async tasks)
2. **Start with Speedscope web viewer** - no installation needed, just upload JSON
3. **Profile all 5 scenarios** to identify state-specific bottlenecks
4. **Focus on thread-level analysis** in idle scenarios (should be >95% sleep)
5. **Look for**:

   * Excessive polling (check individual worker threads)
   * Blocking I/O in async context (long plateaus in timeline view)
   * Redundant work (wide bars in flame graph)
   * Worker thread overhead (filter by thread in Speedscope)

**Expected idle behavior:**

* Worker threads: 95%+ in ``time.sleep()``
* Periodic tasks: Health publishing, file monitoring, etc.
* Total CPU: <5% on idle
