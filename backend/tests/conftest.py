"""Put the backend root on sys.path so `app.*` imports resolve.

Keeps `pytest` working from the repo root or from backend/ without needing an
editable install or a PYTHONPATH incantation.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
