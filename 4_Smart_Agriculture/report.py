"""Backwards-compatible entry point - delegates to the monitor reporter.

Prefer:  python monitor.py report [--csv]
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from monitor import cmd_report
from argparse import Namespace

if __name__ == "__main__":
    cmd_report(Namespace(csv="--csv" in sys.argv))
