"""Test runner for Henjiu Relay"""

import subprocess
import sys
import os


def run_tests():
    """Run all tests"""
    # Change to project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 60)
    print("🧪 Running Henjiu Relay Tests")
    print("=" * 60)
    
    # Run pytest with coverage
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=False
    )
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
