"""
main.py — thin wrapper that runs setup.py.

Usage:
    python main.py
"""
import os
import sys
import subprocess


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    setup = os.path.join(here, "setup.py")
    subprocess.check_call([sys.executable, setup])


if __name__ == "__main__":
    main()
