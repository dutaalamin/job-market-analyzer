"""Regression tests for the transform layer.

The first class exists because of a bug that shipped to the live dashboard:
skills were matched against a lowercased haystack, so the ordinary English word
"next" matched the Next.js pattern. Next.js was reported as the single most
in-demand skill with 501 postings; the real count is 16.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from transform import (  # noqa: E402
    category_of,
    extract_skills,
    normalise_job,
    seniority_of,
    strip_html,
    to_iso_date,
    transform,
)


class SkillDisambiguationTestCase(unittest.TestCase):
    """A skill whose name is also an English word must not match the word."""

    def test_next_week_is_not_next_js(self) -> None:
        self.assertNotIn("Next.js", extract_skills("Next week we ship the roadmap."))
        self.assertNotIn("Next.js", extract_skills("You will learn the next steps."))

    def test_next_js_still_matches(self) -> None:
        self.assertIn("Next.js", extract_skills("We build with Next.js and React."))
        self.assertIn("Next.js", extract_skills("NextJS 14 experience required"))

    def test_rest_needs_api_context(self) -> None:
        self.assertNotIn("REST", extract_skills("You will work with the rest of the team."))
        self.assertIn("REST", extract_skills("Build REST APIs in Python."))
        self.assertIn("REST", extract_skills("Experience with RESTful services"))

    def test_react_capitalised_only(self) -> None:
        self.assertIn("React", extract_skills("Strong React knowledge."))
        self.assertIn("React", extract_skills("react.js and redux"))
        self.assertNotIn("React", extract_skills("we react quickly to incidents"))

    def test_rust_is_the_language_not_corrosion(self) -> None:
        self.assertIn("Rust", extract_skills("Systems work in Rust."))
        self.assertNotIn("Rust", extract_skills("protect against rust and corrosion"))

    def test_swift_is_the_language_not_the_adjective(self) -> None:
        self.assertIn("Swift", extract_skills("iOS developer, Swift and UIKit."))
        self.assertNotIn("Swift", extract_skills("a swift resolution to the ticket"))

    def test_spark_is_the_engine(self) -> None:
        self.assertIn("Spark", extract_skills("Experience with Apache Spark"))
        self.assertNotIn("Spark", extract_skills("a spark of inspiration"))

    def test_javascript_is_not_java(self) -> None:
        self.assertNotIn("Java", extract_skills("JavaScript and TypeScript"))
        self.assertIn("Java", extract_skills("java developer"))

    def test_node_needs_js_suffix(self) -> None:
        self.assertNotIn("Node.js", extract_skills("Node and npm ecosystem"))
        self.assertIn("Node.js", extract_skills("Node.js services"))

    def test_unambiguous_skills_ignore_case(self) -> None:
        # Lowercasing is still right for names that are not English words; only
        # the ambiguous ones are case-sensitive.
        self.assertIn("Python", extract_skills("PYTHON and python"))
        self.assertIn("PostgreSQL", extract_skills("postgres experience"))

    def test_skills_are_deduplicated(self) -> None:
        self.assertEqual(extract_skills("Python, python and PYTHON").count("Python"), 1)

    def test_non_technical_posting_has_no_skills(self) -> None:
        self.assertEqual(extract_skills("Baggerfahrer für Erdarbeiten (m/w/d)"), [])


class CategoryTestCase(unittest.TestCase):
    def test_common_families(self) -> None:
        cases = {
            "Senior Data Engineer": "Data",
            "Frontend Developer": "Engineering",
            "Account Executive DACH": "Sales",
            "Product Designer": "Design",
            "Baggerfahrer": "Other",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(category_of(title), expected)


class SeniorityTestCase(unittest.TestCase):
    def test_levels(self) -> None:
        cases = {
            "Principal Engineer": "Principal",
            "Staff Software Engineer": "Staff",
            "Lead Data Scientist": "Lead",
            "Senior Backend Developer": "Senior",
            "Junior Analyst": "Junior",
            "Werkstudent Marketing": "Junior",
            "Backend Developer": "Mid",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(seniority_of(title), expected)


class HtmlTestCase(unittest.TestCase):
    def test_double_escaped_html_is_stripped(self) -> None:
        raw = "&lt;p&gt;We use &lt;b&gt;Python&lt;/b&gt;.&lt;/p&gt;"
        self.assertEqual(strip_html(raw), "We use Python .")

    def test_none_is_safe(self) -> None:
        self.assertEqual(strip_html(None), "")


class DateTestCase(unittest.TestCase):
    def test_unix_timestamp(self) -> None:
        self.assertEqual(to_iso_date(1792119316), "2026-10-16")

    def test_iso_string(self) -> None:
        self.assertEqual(to_iso_date("2026-10-16T10:32:10Z"), "2026-10-16")

    def test_empty(self) -> None:
        self.assertEqual(to_iso_date(None), "")
        self.assertEqual(to_iso_date(""), "")


class NormaliseTestCase(unittest.TestCase):
    def test_unusable_rows_are_dropped(self) -> None:
        self.assertIsNone(normalise_job({"title": "", "company_name": "Acme"}))
        self.assertIsNone(normalise_job({"title": "Engineer", "company_name": ""}))

    def test_payload_deduplicates_external_id(self) -> None:
        payload = {
            "data": [
                {"slug": "a", "title": "Engineer", "company_name": "X"},
                {"slug": "a", "title": "Engineer", "company_name": "X"},
                {"slug": "b", "title": "Engineer", "company_name": "Y"},
            ]
        }
        self.assertEqual(len(transform(payload)), 2)


if __name__ == "__main__":
    unittest.main()
