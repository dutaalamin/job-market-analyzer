"""Transform raw postings into tidy, queryable records.

Responsibilities:
  * normalise messy strings (title, company, location, job type)
  * derive a role category and a seniority level from the title
  * extract the skill set from the tags, title and description
  * strip HTML (the source escapes tags, so we unescape first)

Everything here is pure: raw dicts in, tidy dicts out. That makes it trivial to
unit-test and to re-run without touching the network.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Skill dictionary
# --------------------------------------------------------------------------- #

# Order matters: longer / more specific names first so that e.g. "javascript"
# is matched before the "java" rule ever sees the text.
SKILL_PATTERNS: list[tuple[str, str]] = [
    ("JavaScript", r"\bjavascript\b"),
    ("TypeScript", r"\btypescript\b"),
    ("Node.js", r"\bnode(?:\.js|js)?\b"),
    ("React", r"\breact(?:\.js|js)?\b"),
    ("Vue", r"\bvue(?:\.js|js)?\b"),
    ("Angular", r"\bangular\b"),
    ("Next.js", r"\bnext(?:\.js|js)?\b"),
    ("Svelte", r"\bsvelte\b"),
    ("Python", r"\bpython\b"),
    ("Django", r"\bdjango\b"),
    ("Flask", r"\bflask\b"),
    ("FastAPI", r"\bfastapi\b"),
    ("Pandas", r"\bpandas\b"),
    ("NumPy", r"\bnumpy\b"),
    ("Java", r"\bjava\b"),
    ("Kotlin", r"\bkotlin\b"),
    ("Scala", r"\bscala\b"),
    ("Golang", r"\bgolang\b"),
    ("Rust", r"\brust\b"),
    ("Ruby", r"\bruby\b"),
    ("PHP", r"\bphp\b"),
    ("Laravel", r"\blaravel\b"),
    ("C#", r"\bc#"),
    ("C++", r"\bc\+\+"),
    ("Swift", r"\bswift\b"),
    ("SQL", r"\bsql\b"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
    ("MySQL", r"\bmysql\b"),
    ("MongoDB", r"\bmongo(?:db)?\b"),
    ("Redis", r"\bredis\b"),
    ("Elasticsearch", r"\belasticsearch\b"),
    ("Snowflake", r"\bsnowflake\b"),
    ("BigQuery", r"\bbigquery\b"),
    ("Redshift", r"\bredshift\b"),
    ("Airflow", r"\bairflow\b"),
    ("dbt", r"\bdbt\b"),
    ("Spark", r"\bspark\b"),
    ("Kafka", r"\bkafka\b"),
    ("ETL", r"\betl\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("Terraform", r"\bterraform\b"),
    ("AWS", r"\baws\b|amazon web services"),
    ("GCP", r"\bgcp\b|google cloud"),
    ("Azure", r"\bazure\b"),
    ("CI/CD", r"\bci/cd\b|continuous integration"),
    ("Git", r"\bgit\b"),
    ("Linux", r"\blinux\b"),
    ("GraphQL", r"\bgraphql\b"),
    ("REST", r"\brest\b|\brestful\b"),
    ("HTML", r"\bhtml\b"),
    ("CSS", r"\bcss\b"),
    ("Tailwind", r"\btailwind\b"),
    ("Machine Learning", r"\bmachine learning\b"),
    ("TensorFlow", r"\btensorflow\b"),
    ("PyTorch", r"\bpytorch\b"),
    ("Figma", r"\bfigma\b"),
]

_COMPILED = [(name, re.compile(pattern)) for name, pattern in SKILL_PATTERNS]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_SENIORITY_RULES: list[tuple[str, str]] = [
    ("Principal", r"\bprincipal\b"),
    ("Staff", r"\bstaff\b"),
    ("Lead", r"\blead\b|\bhead of\b|\bteamlead\b|\bteam lead\b"),
    ("Senior", r"\bsenior\b|\bsr\.?\b"),
    ("Junior", r"\bjunior\b|\bjr\.?\b|\bentry[- ]level\b|\bintern\b|\bwerkstudent\b|\bworking student\b|\btrainee\b"),
]

_CATEGORY_RULES: list[tuple[str, str]] = [
    ("Data", r"\bdata\b|\banalyst\b|\banalytics\b|\bbi\b|\bmachine learning\b|\bml\b|\bai\b|\bscientist\b"),
    ("Engineering", r"\bengineer\b|\bdeveloper\b|\bprogrammer\b|\bsoftware\b|\bdevops\b|\bfrontend\b|\bbackend\b|\bfull[- ]?stack\b|\barchitect\b"),
    ("Design", r"\bdesigner\b|\bdesign\b|\bux\b|\bui\b|\bproduct design\b"),
    ("Product", r"\bproduct manager\b|\bproduct owner\b|\bproduct\b"),
    ("Marketing", r"\bmarketing\b|\bseo\b|\bcontent\b|\bsocial media\b|\bgrowth\b|\bbrand\b"),
    ("Sales", r"\bsales\b|\baccount manager\b|\bbusiness development\b|\bsdr\b"),
    ("Finance", r"\bfinance\b|\baccountant\b|\baccounting\b|\bcontroller\b|\bpayroll\b"),
    ("Support", r"\bsupport\b|\bcustomer service\b|\bhelpdesk\b|\bcustomer success\b"),
    ("Operations", r"\boperations\b|\blogistics\b|\bsupply chain\b|\bprocurement\b"),
    ("HR", r"\bhr\b|\brecruit\b|\btalent\b|\bpeople\b|\bhuman resources\b"),
]


def strip_html(value: str) -> str:
    """Decode entities then remove tags and collapse whitespace.

    The source double-escapes HTML, so we unescape before stripping tags.
    """
    text = html.unescape(value or "")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def extract_skills(*texts: str) -> list[str]:
    """Return the skills mentioned across the given texts, de-duplicated."""
    haystack = " ".join(texts).lower()
    found: list[str] = []
    for name, pattern in _COMPILED:
        if pattern.search(haystack) and name not in found:
            found.append(name)
    return found


def seniority_of(title: str) -> str:
    lowered = title.lower()
    for level, pattern in _SENIORITY_RULES:
        if re.search(pattern, lowered):
            return level
    return "Mid"


def category_of(title: str, tags: list[str] | None = None) -> str:
    """Bucket a posting into a broad role family.

    Title first (most reliable), then the source tags as a fallback.
    """
    haystack = " ".join([title, *(tags or [])]).lower()
    for name, pattern in _CATEGORY_RULES:
        if re.search(pattern, haystack):
            return name
    return "Other"


def to_iso_date(value: object) -> str:
    """Normalise a value to YYYY-MM-DD. Handles unix timestamps and ISO strings."""
    if value in (None, ""):
        return ""
    # Unix timestamp (seconds)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
        except (ValueError, OSError):
            return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)[:10]


def normalise_job(raw: dict) -> dict | None:
    """Turn one raw posting into a tidy record, or None if unusable."""
    title = (raw.get("title") or "").strip()
    company = (raw.get("company_name") or "").strip()
    if not title or not company:
        return None

    description = strip_html(raw.get("description", ""))
    job_types = raw.get("job_types") or []
    tags = [t.strip() for t in (raw.get("tags") or []) if t.strip()]

    # Skills come from the text only — source "tags" are broad categories
    # (Engineering, Sales, Remote…), not technologies.
    skills = extract_skills(title, description)

    return {
        "external_id": str(raw.get("slug") or raw.get("url") or "").strip(),
        "title": title,
        "company": company,
        "category": category_of(title, tags),
        "job_type": ", ".join(job_types) if job_types else "unknown",
        "seniority": seniority_of(title),
        "location": (raw.get("location") or "Unspecified").strip() or "Unspecified",
        "salary": "",
        "published": to_iso_date(raw.get("created_at")),
        "url": (raw.get("url") or "").strip(),
        "skills": skills,
    }


def transform(payload: dict) -> list[dict]:
    """Normalise every posting, dropping unusable ones and duplicates."""
    seen: set[str] = set()
    records: list[dict] = []
    for raw in payload.get("data", []):
        record = normalise_job(raw)
        if record is None:
            continue
        key = record["external_id"] or f"{record['title']}|{record['company']}"
        if key in seen:
            continue
        seen.add(key)
        records.append(record)
    print(f"[transform] {len(records)} clean records")
    return records


if __name__ == "__main__":
    import json

    sample = {
        "data": [
            {
                "slug": "acme-senior-data-engineer",
                "title": "Senior Data Engineer",
                "company_name": "Acme",
                "location": "Berlin",
                "tags": ["Python", "SQL", "Airflow"],
                "job_types": ["full_time"],
                "created_at": 1790000000,
                "url": "https://example.com/job",
                "description": "&lt;p&gt;We use &lt;b&gt;Python&lt;/b&gt; and GCP.&lt;/p&gt;",
            }
        ]
    }
    print(json.dumps(transform(sample), indent=2))
