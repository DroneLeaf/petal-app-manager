#!/usr/bin/env python3
"""
CPU Monitor for Petal App Manager - Process Level Only

Tracks absolute CPU usage of the PAM process over time.
Saves time-series data and generates plots.

Usage:
    python monitor_cpu.py --interval 2 --save-data cpu.csv --plot
    python monitor_cpu.py --interval 1 --save-data detailed.csv --plot
"""

import argparse
import subprocess
import psutil
import time
import sys
import csv
import signal
from datetime import datetime
from pathlib import Path

# Global flag for graceful shutdown
interrupted = False


def signal_handler(signum, frame):
    """Handle interruption signals gracefully"""
    global interrupted
    interrupted = True
    print("\n[Monitor] Received interrupt signal, saving data...")


class ProcessCPUMonitor:
    """Monitor CPU usage for PAM process over time"""
    
    def __init__(self, max_retries: int = 10, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.pid = self._find_pam_pid()
        
        if not self.pid:
            raise RuntimeError("PAM process not found. Is it running?")
        
        self.process = psutil.Process(self.pid)
        self.timeseries_data = []
        
        # Get system info
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)
        
        print(f"Monitoring PAM process (PID: {self.pid})")
        print(f"System CPUs: {cpu_count_physical} physical cores, {cpu_count_logical} logical cores (threads)")
        print("=" * 80)
    
    def _find_pam_pid(self):
        """Find PAM uvicorn process PID with retry logic"""
        for attempt in range(self.max_retries):
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'uvicorn.*petal_app_manager'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                pids = result.stdout.strip().split('\n')
                pid = int(pids[0]) if pids and pids[0] else None
                
                if pid:
                    # Verify process exists and is accessible
                    try:
                        psutil.Process(pid)
                        return pid
                    except psutil.NoSuchProcess:
                        pass
                        
            except (subprocess.CalledProcessError, ValueError):
                pass
            
            if attempt < self.max_retries - 1:
                print(f"Waiting for PAM to start... (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(self.retry_delay)
        
        return None
    
    def get_cpu_snapshot(self, interval: float = 1.0, elapsed_time: float = 0.0):
        """Get single CPU and memory measurement"""
        timestamp = datetime.now()
        
        try:
            cpu_percent = self.process.cpu_percent(interval=interval)
            mem_info = self.process.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)  # Convert bytes to MB
            mem_percent = self.process.memory_percent()
        except psutil.NoSuchProcess:
            # Process terminated, return 0
            print(f"\nWarning: PAM process terminated (PID: {self.pid})")
            cpu_percent = 0.0
            mem_mb = 0.0
            mem_percent = 0.0
        
        self.timeseries_data.append({
            'timestamp': timestamp,
            'elapsed_seconds': elapsed_time,
            'cpu_percent': cpu_percent,
            'memory_mb': mem_mb,
            'memory_percent': mem_percent
        })
        
        return timestamp, cpu_percent, mem_mb
    
    def monitor_continuous(self, interval: int):
        """Monitor continuously until interrupted"""
        global interrupted
        start_time = time.time()
        snapshot_count = 0
        
        print(f"Monitoring until interrupted (interval: {interval}s)")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            while not interrupted:
                # Check if process still exists
                if not self.process.is_running():
                    print(f"\nPAM process terminated. Stopping monitoring.")
                    break
                
                elapsed = time.time() - start_time
                timestamp, cpu_pct, mem_mb = self.get_cpu_snapshot(interval=interval, elapsed_time=elapsed)
                snapshot_count += 1
                
                print(f"[{elapsed:6.1f}s] CPU: {cpu_pct:6.2f}%  Memory: {mem_mb:8.1f} MB")
                
                # Sleep until next interval
                next_snapshot = snapshot_count * interval
                sleep_time = max(0, next_snapshot - elapsed)
                
                if sleep_time > 0 and not interrupted:
                    time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\n\n[Monitor] Monitoring interrupted by user")
        except psutil.NoSuchProcess:
            print("\n\n[Monitor] PAM process terminated unexpectedly")
        
        if interrupted:
            print(f"\n[Monitor] Interrupted. Collected {snapshot_count} snapshots.")
        else:
            print(f"\nComplete. Collected {snapshot_count} snapshots.")
    
    def save_to_csv(self, output_path: str):
        """Export time-series data to CSV"""
        if not self.timeseries_data:
            print("No data to save")
            return
            
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['elapsed_seconds', 'cpu_percent', 'memory_mb', 'memory_percent', 'timestamp'])
            
            for data in self.timeseries_data:
                writer.writerow([
                    f"{data['elapsed_seconds']:.2f}",
                    data['cpu_percent'],
                    f"{data['memory_mb']:.2f}",
                    f"{data['memory_percent']:.2f}",
                    data['timestamp'].isoformat()
                ])
        
        print(f"Saved data to: {output_path}")
    
    def plot(self, output_path: str = None):
        """Generate CPU and memory usage plot"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            print("Error: matplotlib not found. Install with: pip install matplotlib")
            return
        
        if not self.timeseries_data:
            print("No data to plot")
            return
        
        elapsed_times = [d['elapsed_seconds'] for d in self.timeseries_data]
        cpu_values = [d['cpu_percent'] for d in self.timeseries_data]
        memory_mb_values = [d['memory_mb'] for d in self.timeseries_data]
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
        
        # CPU Usage subplot
        ax1.plot(elapsed_times, cpu_values, linewidth=2.5, color='#2E86AB', 
               label='CPU Usage', marker='o', markersize=4)
        ax1.fill_between(elapsed_times, cpu_values, alpha=0.3, color='#2E86AB')
        ax1.set_ylabel('CPU Usage (%)', fontsize=12, fontweight='bold')
        ax1.set_title('PAM Process CPU Usage Over Time', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.legend(loc='upper right', fontsize=10)
        
        # Memory Usage subplot
        ax2.plot(elapsed_times, memory_mb_values, linewidth=2.5, color='#A23B72', 
               label='Memory Usage', marker='s', markersize=4)
        ax2.fill_between(elapsed_times, memory_mb_values, alpha=0.3, color='#A23B72')
        ax2.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Memory Usage (MB)', fontsize=12, fontweight='bold')
        ax2.set_title('PAM Process Memory Usage Over Time', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.legend(loc='upper right', fontsize=10)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"Saved plot to: {output_path}")
        else:
            plt.show()
        
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor PAM process CPU usage over time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor with 2-second intervals (stops on Ctrl+C)
  python monitor_cpu.py --scenario idle-no-leaffc --interval 2
  
  # High-resolution monitoring (1-second intervals) with plot
  python monitor_cpu.py --scenario mission-execution --interval 1 --plot
        """
    )
    
    parser.add_argument(
        '--scenario',
        required=True,
        type=str,
        help='Scenario label for organizing output files (e.g., idle-no-leaffc, mission-execution)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=2,
        help='Interval between measurements in seconds (default: 2)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path(__file__).parent / 'profiles',
        help='Output directory for profile files (default: tools/profiling/profiles)'
    )
    
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate and save CPU usage plot as PNG'
    )
    
    args = parser.parse_args()
    
    # Create output directory if needed
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"pam_{args.scenario}_{timestamp}_cpu"
    csv_path = args.output / f"{base_name}.csv"
    png_path = args.output / f"{base_name}.png"
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"Output files:")
    print(f"  CSV:  {csv_path}")
    if args.plot:
        print(f"  Plot: {png_path}")
    print()
    
    monitor = None
    try:
        monitor = ProcessCPUMonitor()
        
        # Run monitoring
        monitor.monitor_continuous(interval=args.interval)
    
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Always save data, even if interrupted
        if monitor and monitor.timeseries_data:
            print()
            # Save data
            monitor.save_to_csv(str(csv_path))
            
            # Generate plot
            if args.plot:
                monitor.plot(output_path=str(png_path))


if __name__ == '__main__':
    main()
