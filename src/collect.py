"""Collect raw job postings from a public API.

This module only fetches and stores raw data. No cleaning happens here — that is
transform.py's job. Keeping the two apart means we can re-run the transform step
without hitting the network again.

Source: the Arbeitnow job board API (public, no key required). It paginates 300
postings per page, so we walk a few pages to get a usable sample.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://www.arbeitnow.com/api/job-board-api"
USER_AGENT = "job-market-analyzer/1.0 (portfolio project)"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MAX_PAGES = 10  # 300 postings per page -> up to ~3000


def fetch_page(url: str, retries: int = 3) -> dict:
    """GET one page of the API and return the decoded JSON.

    Retries on transient network errors with a short backoff so a flaky
    connection does not kill the whole pipeline.
    """
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"failed to fetch {url}") from last_error


def save_raw(jobs: list[dict]) -> Path:
    """Persist a raw snapshot so runs are reproducible."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = RAW_DIR / f"jobs-{stamp}.json"
    path.write_text(json.dumps({"data": jobs}, ensure_ascii=False), encoding="utf-8")
    return path


def collect() -> dict:
    """Walk the pages, stop when the API stops giving more, store a snapshot."""
    jobs: list[dict] = []
    url: str | None = f"{API_URL}?page=1"
    page = 0

    while url and page < MAX_PAGES:
        page += 1
        payload = fetch_page(url)
        batch = payload.get("data", [])
        if not batch:
            break
        jobs.extend(batch)
        url = (payload.get("links") or {}).get("next")

    path = save_raw(jobs)
    print(f"[collect] {len(jobs)} postings over {page} pages -> {path.name}")
    return {"data": jobs}


if __name__ == "__main__":
    collect()
