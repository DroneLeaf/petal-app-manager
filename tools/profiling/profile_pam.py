#!/usr/bin/env python3
"""
Profiling script for Petal App Manager using py-spy

py-spy can profile ALL threads (including async tasks and worker threads),
unlike cProfile which only profiles the main thread.

Usage:
    python profile_pam_pyspy.py --scenario idle-no-leaffc --duration 60
    python profile_pam_pyspy.py --scenario idle-with-leaffc --duration 120
"""

import argparse
import subprocess
import sys
import time
import signal
from datetime import datetime
from pathlib import Path
import os

class PySpyProfiler:
    """Manages py-spy profiling sessions for PAM"""

    def __init__(self, scenario: str, duration: int, output_dir: Path):
        self.scenario = scenario
        self.duration = duration
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped base filename
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_name = f"pam_{scenario}_{self.timestamp}_pyspy"
        
        # Output file for speedscope format
        self.speedscope_file = self.output_dir / f"{self.base_name}.speedscope.json"

    def run_profiling(self):
        """Run profiling for the specified duration"""
        print(f"=" * 80)
        print(f"Profiling PAM with py-spy - Scenario: {self.scenario}")
        print(f"Duration: {self.duration} seconds")
        print(f"Output: {self.speedscope_file}")
        print(f"=" * 80)
        print()

        # Get PAM source directory
        pam_src_path = Path(__file__).parent.parent.parent / "src"
        env = os.environ.copy()
        env['PYTHONPATH'] = str(pam_src_path) + ':' + env.get('PYTHONPATH', '')
        
        try:
            print(f"[Profiler] Generating Speedscope interactive profile...")
            
            # Build py-spy command
            pyspy_cmd = [
                "py-spy", "record",
                "--duration", str(self.duration),
                "--rate", "100",  # Sample 100 times per second
                "--subprocesses",  # Profile subprocesses too
                "--idle",  # Include idle/sleeping threads
                "--format", "speedscope",
                "--output", str(self.speedscope_file),
                "--",  # Everything after this is the command to run
                sys.executable, "-m", "uvicorn",
                "petal_app_manager.main:app",
                "--host", "127.0.0.1",
                "--port", "9000",
                "--log-level", "info"
            ]
            
            print(f"[Profiler] Running py-spy for {self.duration} seconds...")
            print(f"[Profiler] PAM will start on port 9000...")
            print()
            
            result = subprocess.run(
                pyspy_cmd,
                env=env,
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"\n[Profiler] ✗ Failed: {result.stderr}")
                return
            
            print(f"\n[Profiler] ✓ Success!")
            print(f"[Profiler] Profile saved: {self.speedscope_file}")
            self.print_next_steps()

        except KeyboardInterrupt:
            print("\n[Profiler] Profiling interrupted by user")
            if self.speedscope_file.exists():
                print(f"[Profiler] Partial profile may have been saved to: {self.speedscope_file}")
        except Exception as e:
            print(f"\n[Profiler] ✗ Error during profiling: {e}")
            import traceback
            traceback.print_exc()

    def print_next_steps(self):
        """Print next steps for viewing results"""
        print(f"\n{'=' * 80}")
        print("NEXT STEPS - How to view the profile:")
        print(f"{'=' * 80}")
        print(f"\n📊 Speedscope Interactive Profile:")
        print(f"")
        print(f"   Option 1: Web (Recommended)")
        print(f"   1. Visit https://www.speedscope.app/")
        print(f"   2. Click 'Browse' and select: {self.speedscope_file}")
        print(f"   3. Use thread filter to analyze individual workers")
        print(f"   4. Toggle between views:")
        print(f"      - Time Order: Timeline view")
        print(f"      - Left Heavy: Flame graph (top-down)")
        print(f"      - Sandwich: Icicle graph (bottom-up)")
        print(f"")
        print(f"   Option 2: CLI (requires npm)")
        print(f"   npm install -g speedscope")
        print(f"   speedscope {self.speedscope_file}")
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
  # Profile idle behavior for 60 seconds
  python profile_pam.py --scenario idle-no-leaffc --duration 60

  # Quick test (30 seconds)
  python profile_pam.py --scenario idle-no-leaffc --duration 30

  # Profile mission execution (3 minutes)
  python profile_pam.py --scenario mission-execution --duration 180
        """
    )
    
    parser.add_argument(
        '--scenario',
        required=True,
        type=str,
        help='Scenario label for organizing profile files (e.g., idle-no-leaffc, mission-execution)'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Profiling duration in seconds (default: 60)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path(__file__).parent / 'profiles',
        help='Output directory for profile files (default: tools/profiling/profiles)'
    )

    args = parser.parse_args()

    # Create and run profiler
    profiler = PySpyProfiler(
        scenario=args.scenario,
        duration=args.duration,
        output_dir=args.output
    )
    
    profiler.run_profiling()


if __name__ == '__main__':
    main()
