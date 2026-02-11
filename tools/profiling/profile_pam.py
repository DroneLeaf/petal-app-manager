#!/usr/bin/env python3
"""
Profiling script for Petal App Manager using py-spy

py-spy can profile ALL threads (including async tasks and worker threads),
unlike cProfile which only profiles the main thread.

Usage:
    python profile_pam.py --scenario idle-no-leaffc
    python profile_pam.py --scenario idle-with-leaffc
"""

import argparse
import subprocess
import sys
import time
import signal
from datetime import datetime
from pathlib import Path

# Global flag for graceful shutdown
interrupted = False


def signal_handler(signum, frame):
    """Handle interruption signals gracefully"""
    global interrupted
    interrupted = True
    print("\n[Profiler] Received interrupt signal, stopping profiler...")


class PySpyProfiler:
    """Manages py-spy profiling sessions for PAM"""

    def __init__(self, scenario: str, output_dir: Path):
        self.scenario = scenario
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped base filename
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_name = f"pam_{scenario}_{self.timestamp}_profile"
        
        # Output file for speedscope format
        self.speedscope_file = self.output_dir / f"{self.base_name}.speedscope.json"

    def find_pam_process(self):
        """Find running PAM process"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'uvicorn.*petal_app_manager'],
                capture_output=True,
                text=True,
                check=True
            )
            pids = result.stdout.strip().split('\n')
            return int(pids[0]) if pids and pids[0] else None
        except (subprocess.CalledProcessError, ValueError):
            return None

    def run_profiling(self):
        """Run profiling until interrupted"""
        print(f"=" * 80)
        print(f"Profiling PAM with py-spy - Scenario: {self.scenario}")
        print(f"Profile output: {self.speedscope_file}")
        print(f"=" * 80)
        print()

        # Find running PAM process
        print(f"[Profiler] Searching for running PAM process...")
        pam_pid = self.find_pam_process()
        
        if pam_pid is None:
            print(f"[Profiler] ✗ Error: No running PAM process found")
            print(f"[Profiler] Please start PAM first, then run this profiler")
            print(f"[Profiler] Example: uvicorn petal_app_manager.main:app --host 127.0.0.1 --port 9000")
            return
        
        print(f"[Profiler] ✓ Found PAM process (PID: {pam_pid})")
        print()
        
        pyspy_process = None
        
        try:
            print(f"[Profiler] Starting py-spy profiling...")
            print()
            
            # Build py-spy command to attach to existing process
            # Use full path to py-spy from venv with sudo
            pyspy_path = Path(sys.executable).parent / "py-spy"
            pyspy_cmd = [
                "sudo", str(pyspy_path), "record",
                "--pid", str(pam_pid),
                "--rate", "100",  # Sample 50 times per second (lower overhead than 100)
                "--subprocesses",  # Profile subprocesses too
                "--idle",  # Include idle/sleeping threads
                "--format", "speedscope",
                "--output", str(self.speedscope_file)
            ]
            
            print(f"[Profiler] Profiling PID {pam_pid}...")
            print(f"[Profiler] Press Ctrl+C to stop and save profile")
            print()
            
            # Use Popen so we can handle interruptions gracefully
            # Don't capture stdout/stderr - let py-spy print directly so we see errors
            pyspy_process = subprocess.Popen(
                pyspy_cmd,
                stdout=None,
                stderr=None,
                text=True
            )
            
            # Wait for py-spy to complete (or until interrupted)
            # Poll instead of communicate() so we can handle Ctrl+C
            global interrupted
            while pyspy_process.poll() is None and not interrupted:
                time.sleep(0.5)
            
            # Check if interrupted during poll loop
            if interrupted and pyspy_process.poll() is None:
                print("\n[Profiler] Waiting for py-spy to finish writing profile...")
                try:
                    pyspy_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("[Profiler] Force stopping py-spy...")
                    pyspy_process.kill()
                    pyspy_process.wait()
            
            returncode = pyspy_process.returncode if pyspy_process else None
            if returncode is not None:
                print(f"\n[Profiler] py-spy exited with code: {returncode}")

        except KeyboardInterrupt:
            print("\n[Profiler] Profiling interrupted by user (Ctrl+C)")
            
        except Exception as e:
            print(f"\n[Profiler] ✗ Error during profiling: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Always cleanup and check for saved profile
            # py-spy handles Ctrl+C itself, just wait for it to finish writing
            if pyspy_process and pyspy_process.poll() is None:
                print("[Profiler] Waiting for py-spy to finish writing profile...")
                try:
                    pyspy_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("[Profiler] Force stopping py-spy...")
                    pyspy_process.kill()
                    pyspy_process.wait()
            
            # Give filesystem time to flush
            time.sleep(0.5)
            
            # Check if profile was saved (py-spy writes partial profiles on interruption)
            if self.speedscope_file.exists():
                file_size = self.speedscope_file.stat().st_size
                if file_size > 0:
                    returncode = pyspy_process.returncode if pyspy_process else None
                    if returncode == 0:
                        print(f"\n[Profiler] ✓ Success!")
                    else:
                        print(f"\n[Profiler] ⚠ Profiling interrupted, but partial profile saved")
                    print(f"[Profiler] Profile saved: {self.speedscope_file} ({file_size:,} bytes)")
                    self.print_next_steps()
                else:
                    print(f"\n[Profiler] ✗ Profile file is empty")
            else:
                print(f"\n[Profiler] ✗ No profile file generated")

    def print_next_steps(self):
        """Print next steps for viewing results"""
        print(f"\n{'=' * 80}")
        print("RESULTS - Generated Files:")
        print(f"{'=' * 80}")
        print(f"\n📊 Speedscope Interactive Profile:")
        print(f"   {self.speedscope_file}")
        
        print(f"\n{'=' * 80}")
        print("How to view:")
        print(f"{'=' * 80}")
        print(f"\nSpeedscope Profile:")
        print(f"   1. Visit https://www.speedscope.app/")
        print(f"   2. Click 'Browse' and select: {self.speedscope_file}")
        print(f"   3. Toggle between views:")
        print(f"      - Time Order: Timeline view")
        print(f"      - Left Heavy: Flame graph (top-down)")
        print(f"      - Sandwich: Icicle graph (bottom-up)")
        
        print(f"\n{'=' * 80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Profile Petal App Manager using py-spy (all threads & async tasks)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example scenario labels for organizing profiles:
  idle-no-leaffc      - Baseline idle state
  idle-with-leaffc    - Idle with leafFC connected
  esc-calibration     - ESC calibration operation
  rc-stream           - RC streaming operation
  mission-execution   - Mission execution operation

Note: Scenario labels are for record keeping only. Use any descriptive
      label you want. The profiler captures whatever PAM is actually 
      doing during the profiling period.

Output Format:
  - Speedscope (JSON)          : Interactive visualization at speedscope.app
                                 Includes flame graph, icicle graph, and timeline views

Examples:
  # Start PAM first:
  uvicorn petal_app_manager.main:app --host 127.0.0.1 --port 9000

  # Then profile idle behavior (Ctrl+C to stop)
  python profile_pam.py --scenario idle-no-leaffc
        """
    )
    
    parser.add_argument(
        '--scenario',
        required=True,
        type=str,
        help='Scenario label for organizing profile files (e.g., idle-no-leaffc, mission-execution)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path(__file__).parent / 'profiles',
        help='Output directory for profile files (default: tools/profiling/profiles)'
    )

    args = parser.parse_args()

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run profiler
    profiler = PySpyProfiler(
        scenario=args.scenario,
        output_dir=args.output
    )
    
    profiler.run_profiling()


if __name__ == '__main__':
    main()
