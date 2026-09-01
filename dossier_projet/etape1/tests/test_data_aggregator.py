import pytest
from pathlib import Path
import sys
import json
import tempfile
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_aggregator import (
    DataAggregator,
    QualityReport,
    GENRE_NORMALISATION,
    ANNEE_MIN,
    ANNEE_MAX,
)
import pandas as pd


class TestGenreNormalisation:
    """Test genre normalization mapping."""

    def test_genre_normalisation_has_common_genres(self):
        """Test that genre normalization includes common genres."""
        expected = ["romance", "comedy", "drama", "thriller", "mystery"]
        for genre in expected:
            assert genre in GENRE_NORMALISATION

    def test_genre_normalisation_returns_english(self):
        """Test that genre normalization returns English names."""
        assert GENRE_NORMALISATION["romance"] == "Romance"
        assert GENRE_NORMALISATION["comedy"] == "Comedy"
        assert GENRE_NORMALISATION["drama"] == "Drama"


class TestQualityReport:
    """Test QualityReport dataclass."""

    def test_quality_report_initialization(self):
        """Test QualityReport can be instantiated."""
        report = QualityReport(
            total_brut=100,
            total_apres_nettoyage=90,
            total_apres_fusion=85,
            doublons_supprimes=5,
        )
        assert report.total_brut == 100
        assert report.total_apres_nettoyage == 90
        assert report.total_apres_fusion == 85

    def test_quality_report_default_values(self):
        """Test QualityReport has sensible defaults."""
        report = QualityReport()
        assert report.total_brut == 0
        assert report.doublons_supprimes == 0
        assert isinstance(report.valeurs_manquantes, dict)


class TestDataAggregatorNettoyerChaines:
    """Test string cleaning functionality."""

    def test_nettoyer_chaine_removes_whitespace(self):
        """Test that string cleaning removes extra whitespace."""
        value = "  Multiple   spaces  "
        cleaned = DataAggregator._nettoyer_chaine(value)
        assert cleaned == "Multiple spaces"

    def test_nettoyer_chaine_removes_html_tags(self):
        """Test that string cleaning removes HTML tags."""
        value = "Text with <b>HTML</b> tags"
        cleaned = DataAggregator._nettoyer_chaine(value)
        assert "<b>" not in cleaned
        assert "<" not in cleaned

    def test_nettoyer_chaine_handles_none(self):
        """Test that string cleaning handles None values."""
        assert DataAggregator._nettoyer_chaine(None) is None

    def test_nettoyer_chaine_handles_nan(self):
        """Test that string cleaning handles NaN values."""
        assert DataAggregator._nettoyer_chaine(float('nan')) is None


class TestDataAggregatorNettoyerNotes:
    """Test numeric note cleaning."""

    def test_nettoyer_notes_normalizes_scale(self):
        """Test that notes are normalized to 0-10 scale."""
        aggregator = DataAggregator()
        df = pd.DataFrame({"note_moyenne": [85.0, 9.5, 3.2]})
        df_cleaned = aggregator.nettoyer_notes(df)
        # 85 should be converted to 8.5
        assert df_cleaned["note_moyenne"][0] == 8.5
        # 9.5 should stay 9.5
        assert df_cleaned["note_moyenne"][1] == 9.5

    def test_nettoyer_notes_removes_invalid(self):
        """Test that invalid notes are removed."""
        aggregator = DataAggregator()
        df = pd.DataFrame({"note_moyenne": [5.0, -1.0, 15.0, 8.5]})
        df_cleaned = aggregator.nettoyer_notes(df)
        # Invalid values should become NaN
        assert pd.isna(df_cleaned["note_moyenne"][1])  # -1
        assert pd.isna(df_cleaned["note_moyenne"][2])  # 15


class TestDataAggregatorNormaliserGenres:
    """Test genre normalization."""

    def test_normaliser_genres_empty_list(self):
        """Test genre normalization with empty input."""
        aggregator = DataAggregator()
        df = pd.DataFrame({"genres": [[]]})
        df_result = aggregator.normaliser_genres(df)
        assert df_result["genres"][0] == []

    def test_normaliser_genres_single_genre(self):
        """Test genre normalization with single genre."""
        aggregator = DataAggregator()
        df = pd.DataFrame({"genres": [["romance"]]})
        df_result = aggregator.normaliser_genres(df)
        assert "Romance" in df_result["genres"][0]

    def test_normaliser_genres_handles_none(self):
        """Test genre normalization handles None values."""
        aggregator = DataAggregator()
        df = pd.DataFrame({"genres": [None]})
        df_result = aggregator.normaliser_genres(df)
        assert df_result["genres"][0] == []


class TestDataAggregatorSuppressionCorrompus:
    """Test corruption removal."""

    def test_supprimer_corrompus_requires_titre(self):
        """Test that records without title are removed."""
        aggregator = DataAggregator()
        df = pd.DataFrame({
            "titre": ["Drama A", None, "Drama C"],
            "date_diffusion": ["2023-01-01", "2023-01-02", "2023-01-03"],
        })
        df_cleaned = aggregator.supprimer_corrompus(df)
        assert len(df_cleaned) == 2
        assert None not in df_cleaned["titre"].values

    def test_supprimer_corrompus_validates_episodes(self):
        """Test that invalid episode counts are handled."""
        aggregator = DataAggregator()
        df = pd.DataFrame({
            "titre": ["A", "B", "C"],
            "nb_episodes": [10, 0, -5],
        })
        df_cleaned = aggregator.supprimer_corrompus(df)
        # 0 and negative should be invalid
        assert len(df_cleaned) == 1
        assert df_cleaned["nb_episodes"][0] == 10


class TestDataAggregatorNormaliserTitre:
    """Test title normalization for deduplication."""

    def test_normaliser_titre_removes_accents(self):
        """Test that title normalization removes accents."""
        titre1 = "Café"
        titre2 = "Cafe"
        normalized1 = DataAggregator._normaliser_titre(titre1)
        normalized2 = DataAggregator._normaliser_titre(titre2)
        assert normalized1 == normalized2

    def test_normaliser_titre_case_insensitive(self):
        """Test that title normalization is case-insensitive."""
        titre1 = "The Glory"
        titre2 = "the glory"
        normalized1 = DataAggregator._normaliser_titre(titre1)
        normalized2 = DataAggregator._normaliser_titre(titre2)
        assert normalized1 == normalized2

    def test_normaliser_titre_handles_none(self):
        """Test title normalization handles None."""
        assert DataAggregator._normaliser_titre(None) == ""


class TestDataAggregatorIntegration:
    """Integration tests for the full pipeline."""

    def test_pipeline_with_empty_sources(self, tmp_path):
        """Test pipeline handles empty data sources."""
        aggregator = DataAggregator(
            raw_dir=tmp_path / "raw",
            clean_dir=tmp_path / "clean",
        )
        (tmp_path / "raw").mkdir()
        (tmp_path / "clean").mkdir()

        df_final, rapport = aggregator.run_pipeline()
        assert len(df_final) == 0
        assert rapport.total_brut == 0

    def test_pipeline_exports_json(self, tmp_path):
        """Test that pipeline exports JSON files."""
        aggregator = DataAggregator(
            raw_dir=tmp_path / "raw",
            clean_dir=tmp_path / "clean",
        )
        (tmp_path / "raw").mkdir()
        (tmp_path / "clean").mkdir()

        # Create minimal test data
        test_data = [
            {
                "titre": "Test Drama",
                "english_name": "Test Drama",
                "genres": ["Drama"],
                "note_moyenne": 8.5,
            }
        ]
        raw_file = tmp_path / "raw" / "raw_tmdb.json"
        with open(raw_file, "w") as f:
            json.dump(test_data, f)

        df_final, _ = aggregator.run_pipeline()

        # Check JSON export
        json_file = tmp_path / "clean" / "kdramas_clean.json"
        assert json_file.exists()

    def test_pipeline_exports_csv(self, tmp_path):
        """Test that pipeline exports CSV files."""
        aggregator = DataAggregator(
            raw_dir=tmp_path / "raw",
            clean_dir=tmp_path / "clean",
        )
        (tmp_path / "raw").mkdir()
        (tmp_path / "clean").mkdir()

        # Create minimal test data
        test_data = [
            {
                "titre": "Test Drama",
                "english_name": "Test Drama",
                "genres": ["Drama"],
                "note_moyenne": 8.5,
            }
        ]
        raw_file = tmp_path / "raw" / "raw_tmdb.json"
        with open(raw_file, "w") as f:
            json.dump(test_data, f)

        df_final, _ = aggregator.run_pipeline()

        # Check CSV export
        csv_file = tmp_path / "clean" / "kdramas_clean.csv"
        assert csv_file.exists()
