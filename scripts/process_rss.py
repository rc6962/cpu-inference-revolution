"""Cross-platform process RSS collection using standard library only."""
from __future__ import annotations

import platform
import sys


def get_process_rss_bytes() -> tuple[int | None, int | None, str]:
    """Return (current_rss_bytes, peak_rss_bytes, method_description).

    All values are normalized to bytes. Returns (None, None, reason) on failure.
    On Windows, peak_rss equals current_rss (peak not available via PowerShell method).
    """
    system = platform.system()

    # Windows: PowerShell Get-Process (most reliable cross-subprocess)
    if system == "Windows":
        try:
            import os as _os
            import subprocess as _subprocess
            pid = _os.getpid()
            out = _subprocess.check_output(
                ["powershell", "-Command", f"(Get-Process -Id {pid}).WorkingSet64"],
                text=True, timeout=5,
            ).strip()
            rss = int(out)
            # Peak not available via this method; return current as both
            return rss, rss, "Windows/PowerShell/WorkingSet64"
        except Exception as exc:
            return None, None, f"Windows RSS error: {exc}"

    # Linux: /proc/self/status
    if system == "Linux":
        try:
            with open("/proc/self/status") as f:
                rss_kb = 0
                hwm_kb = 0
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                    elif line.startswith("VmHWM:"):
                        hwm_kb = int(line.split()[1])
                return rss_kb * 1024, hwm_kb * 1024, "Linux/proc/self/status"
        except Exception as exc:
            return None, None, f"Linux RSS error: {exc}"

    # macOS: ps command
    if system == "Darwin":
        try:
            import subprocess
            out = subprocess.check_output(
                ["ps", "-o", "rss=", "-p", str(sys.modules["os"].getpid() if "os" in sys.modules else 0)],
                text=True, timeout=5,
            ).strip()
            rss_kb = int(out)
            # Peak not available via ps; return current as both
            return rss_kb * 1024, rss_kb * 1024, "macOS/ps (peak=current)"
        except Exception as exc:
            return None, None, f"macOS RSS error: {exc}"

    return None, None, f"Unsupported platform: {system}"
