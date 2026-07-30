import os
import sys
from pathlib import Path

# Keep tests free of external email / Celery workers (override .env if loaded)
os.environ.setdefault("EMAIL_PROVIDER", "console")
os.environ.setdefault("EMAIL_ASYNC", "false")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
