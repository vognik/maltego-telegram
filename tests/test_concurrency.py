"""
Tests for concurrent transform and client execution.
Ensures Maltego multi-object selection and simultaneous execution runs without errors.
"""

import subprocess
import sys


def test_concurrent_project_runs():
    """Verify multiple concurrent project.py process invocations do not lock or collide."""
    cmd = [sys.executable, "project.py", "local", "CompressedImageToOS", "test_val"]
    
    # Spawn 4 concurrent processes simulating Maltego running transforms on 4 selected entities
    processes = [
        subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]

    for p in processes:
        stdout, stderr = p.communicate(timeout=15)
        assert p.returncode == 0, f"Process failed with stderr: {stderr}"
        assert "<MaltegoMessage>" in stdout
