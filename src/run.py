"""Orchestrate the whole pipeline:

    collect -> transform -> load -> dbt build -> analyze

    python src/run.py            # full run (hits the network)
    python src/run.py --offline  # reuse the latest raw snapshot
    python src/run.py --history  # load every raw snapshot, for trend analysis
    python src/run.py --skip-dbt # skip the dbt transform layer
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import analyze  # noqa: E402
from collect import collect  # noqa: E402
from load import load  # noqa: E402
from transform import transform  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DBT_DIR = ROOT / "dbt"


def snapshot_id(path: Path) -> str:
    """The collector's timestamp, taken from the filename.

    Deriving it from the name rather than the file mtime keeps the value stable
    when the repo is cloned: git does not preserve mtimes, so an mtime-based id
    would reorder the whole history on a fresh checkout.
    """
    return path.stem.replace("jobs-", "")


def snapshot_files() -> list[Path]:
    files = sorted(RAW_DIR.glob("jobs-*.json"))
    if not files:
        raise SystemExit("no raw snapshot found — run without --offline first")
    return files


def latest_snapshot() -> dict:
    path = snapshot_files()[-1]
    print(f"[collect] reusing {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_dbt() -> None:
    """Build the dbt models and run their data-quality tests."""
    env_warehouse = str(ROOT / "data" / "warehouse.duckdb")
    print("[dbt] building models + tests")
    result = subprocess.run(
        ["dbt", "build", "--profiles-dir", ".", "--quiet"],
        cwd=DBT_DIR,
        env={**__import__("os").environ, "JMA_WAREHOUSE": env_warehouse},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit("dbt build failed")
    print("[dbt] models + tests passed")


def main() -> None:
    offline = "--offline" in sys.argv
    skip_dbt = "--skip-dbt" in sys.argv
    history = "--history" in sys.argv

    if history:
        # Re-transform every snapshot so the warehouse is a pure function of the
        # raw files. 10 s per snapshot; worth it for a run that is idempotent.
        files = snapshot_files()
        print(f"[collect] history mode: {len(files)} snapshot(s)")
        snapshots = [
            (snapshot_id(path), transform(json.loads(path.read_text(encoding="utf-8"))))
            for path in files
        ]
    else:
        payload = latest_snapshot() if offline else collect()
        records = transform(payload)
        snapshots = [(snapshot_id(snapshot_files()[-1]), records)]

    load(snapshots)

    if skip_dbt:
        print("[dbt] skipped")
    else:
        run_dbt()

    analyze()
    print("[done] pipeline complete")


if __name__ == "__main__":
    main()
