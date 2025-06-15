import platform

from pathlib import Path
import subprocess
from typing import Optional
from petal_app_manager.utils import utils

class MachineID:
    def __init__(self, log):
        self.log = log

    def get_machine_id(self) -> Optional[str]:
        """Get the machine ID."""
        machine_id = self._get_machine_id()
        if not machine_id:
            self.log.error("Failed to retrieve machine ID.")
            return None
        return machine_id

    def _get_machine_id(self) -> Optional[str]:
        """Get the machine ID using the machine ID executable."""
        try:
            # Determine architecture
            arch = platform.machine().lower()
            is_arm = "arm" in arch
            
            # Build path to executable
            script_dir = Path(__file__)
            machine_id_exe = script_dir / (
                "machineid_arm" if is_arm else "machineid_x86"
            )
            
            # Check if executable exists
            if not machine_id_exe.exists():
                self.log.error(f"Machine ID executable not found at {machine_id_exe}")
                return None
            
            # Execute and get output
            result = subprocess.run(
                [str(machine_id_exe)], 
                capture_output=True, 
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception as e:
            self.log.error(f"Failed to get machine ID: {e}")
            return None