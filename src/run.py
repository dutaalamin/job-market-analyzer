"""Orchestrate the whole pipeline: collect -> transform -> load -> analyze.

    python src/run.py            # full run (hits the network)
    python src/run.py --offline  # reuse the latest raw snapshot
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import analyze  # noqa: E402
from collect import collect  # noqa: E402
from load import load  # noqa: E402
from transform import transform  # noqa: E402

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def latest_snapshot() -> dict:
    snapshots = sorted(RAW_DIR.glob("jobs-*.json"))
    if not snapshots:
        raise SystemExit("no raw snapshot found — run without --offline first")
    print(f"[collect] reusing {snapshots[-1].name}")
    return json.loads(snapshots[-1].read_text(encoding="utf-8"))


def main() -> None:
    offline = "--offline" in sys.argv
    payload = latest_snapshot() if offline else collect()
    records = transform(payload)
    load(records)
    analyze()
    print("[done] pipeline complete")


if __name__ == "__main__":
    main()
