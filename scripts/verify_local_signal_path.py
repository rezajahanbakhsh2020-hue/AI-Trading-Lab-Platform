#!/usr/bin/env python3
"""CLI wrapper for the local publication-to-snapshot proof.

Reads the ephemeral service credential from the environment
(PROJECT2_API_KEY or PROJECT1_SERVICE_KEY) and never prints, logs, or
persists it.

Usage:
  python3 scripts/verify_local_signal_path.py \
    --base-url http://127.0.0.1:8000 \
    --symbol XAUUSD --timeframe 1H --decision buy
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.platform.services.publication_proof import main

if __name__ == "__main__":
    raise SystemExit(main())
