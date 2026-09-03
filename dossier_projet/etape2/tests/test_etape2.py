"""Regression tests for the auditable E2 watch and pricing calculations."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import benchmark_ia  # noqa: E402
import veille_rss  # noqa: E402


class PricingTests(unittest.TestCase):
    def test_reference_volume_is_six_million_tokens(self) -> None:
        self.assertEqual(benchmark_ia.TOTAL_TOKENS, 6_000_000)

    def test_documented_token_costs(self) -> None:
        self.assertEqual(benchmark_ia.token_cost(0.02), 0.12)
        self.assertEqual(benchmark_ia.token_cost(0.15), 0.90)

    def test_report_states_limits(self) -> None:
        report = benchmark_ia.build_report()
        self.assertIn("Aucune latence ou qualité cloud n'est inventée", report)
        self.assertIn("non comparable", report)


class FeedFilterTests(unittest.TestCase):
    def test_raw_collection_does_not_overwrite_reviewed_report(self) -> None:
        self.assertEqual(veille_rss.RAPPORT_FILE.name, "collecte_veille_rss.md")

    def test_short_keyword_uses_word_boundaries(self) -> None:
        self.assertFalse(veille_rss._contient_mot_cle("CIA funding", ["ai"]))
        self.assertFalse(veille_rss._contient_mot_cle("A detailed report", ["ai"]))
        self.assertTrue(veille_rss._contient_mot_cle("AI regulation", ["ai"]))

    def test_filter_is_case_and_accent_insensitive(self) -> None:
        self.assertTrue(
            veille_rss._contient_mot_cle(
                "Réglementation des données personnelles", ["reglementation"]
            )
        )


if __name__ == "__main__":
    unittest.main()
