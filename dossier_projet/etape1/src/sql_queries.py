#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sql_queries.py — Requêtes SQL d'extraction pour la base de données K-Drama.

Ce module contient l'ensemble des requêtes SQL d'extraction (SELECT, JOIN,
GROUP BY, agrégations, sous-requêtes, vues) utilisées pour interroger la base
PostgreSQL des K-Dramas. Les requêtes sont encapsulées dans une classe
SQLQueryExecutor qui gère la connexion, l'exécution sécurisée (paramètres liés)
et la journalisation.

Compétence RNCP C2 : Requêtes SQL d'extraction.

Auteur : Équipe Data
Projet : Système de recommandation de K-Dramas par IA
Étape : 1 — Collecte et préparation des données
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sql_queries")

# Chargement des variables d'environnement
load_dotenv()

# ---------------------------------------------------------------------------
# Constantes — Requêtes SQL
# ---------------------------------------------------------------------------

# Requête 1 : Liste de tous les K-Dramas avec informations de base
SQL_LISTE_KDRAMAS = """
    SELECT
        id,
        titre,
        titre_original,
        date_diffusion,
        nb_episodes,
        nb_saisons,
        note_moyenne,
        nb_votes,
        langue_originale,
        source
    FROM kdramas
    ORDER BY note_moyenne DESC NULLS LAST, nb_votes DESC
    LIMIT :limit
    OFFSET :offset
"""

# Requête 2 : K-Dramas diffusés après une année donnée
SQL_KDRAMAS_APRES_ANNEE = """
    SELECT
        id,
        titre,
        titre_original,
        date_diffusion,
        nb_episodes,
        note_moyenne,
        nb_votes
    FROM kdramas
    WHERE EXTRACT(YEAR FROM date_diffusion) >= :annee_min
    ORDER BY date_diffusion DESC
"""

# Requête 3 : K-Dramas et leurs genres (JOIN plusieurs-à-plusieurs)
SQL_KDRAMAS_GENRES = """
    SELECT
        k.id AS kdrama_id,
        k.titre,
        k.titre_original,
        g.id AS genre_id,
        g.nom AS genre
    FROM kdramas k
    JOIN kdrama_genres kg ON k.id = kg.kdrama_id
    JOIN genres g ON kg.genre_id = g.id
    ORDER BY k.titre, g.nom
"""

# Requête 4 : K-Dramas et leurs acteurs principaux (JOIN avec filtre)
SQL_KDRAMAS_ACTEURS_PRINCIPAUX = """
    SELECT
        k.id AS kdrama_id,
        k.titre,
        a.id AS acteur_id,
        a.nom AS acteur,
        ka.role,
        ka.role_principal
    FROM kdramas k
    JOIN kdrama_acteurs ka ON k.id = ka.kdrama_id
    JOIN acteurs a ON ka.acteur_id = a.id
    WHERE ka.role_principal = TRUE
    ORDER BY k.titre, a.nom
"""

# Requête 5 : Notes des utilisateurs avec détails du K-Drama (JOIN multiple)
SQL_NOTES_UTILISATEURS = """
    SELECT
        n.id AS note_id,
        u.pseudonyme,
        u.id AS utilisateur_id,
        k.id AS kdrama_id,
        k.titre,
        k.titre_original,
        n.note,
        n.commentaire,
        n.date_note
    FROM notes n
    JOIN utilisateurs u ON n.utilisateur_id = u.id
    JOIN kdramas k ON n.kdrama_id = k.id
    ORDER BY n.date_note DESC
    LIMIT :limit
"""

# Requête 6 : Note moyenne et nombre de votes par K-Drama (GROUP BY + agrégation)
SQL_STATS_NOTES_PAR_KDRAMA = """
    SELECT
        k.id,
        k.titre,
        k.titre_original,
        COUNT(n.id) AS nombre_notes,
        ROUND(AVG(n.note), 2) AS moyenne_utilisateurs,
        k.note_moyenne AS moyenne_source,
        k.nb_votes AS nb_votes_source
    FROM kdramas k
    LEFT JOIN notes n ON k.id = n.kdrama_id
    GROUP BY k.id, k.titre, k.titre_original, k.note_moyenne, k.nb_votes
    HAVING COUNT(n.id) > 0
    ORDER BY moyenne_utilisateurs DESC
"""

# Requête 7 : Top 10 des genres les plus représentés (GROUP BY + COUNT)
SQL_TOP_GENRES = """
    SELECT
        g.id,
        g.nom AS genre,
        COUNT(kg.kdrama_id) AS nombre_kdramas,
        ROUND(COUNT(kg.kdrama_id) * 100.0 / :total_kdramas, 2) AS pourcentage
    FROM genres g
    JOIN kdrama_genres kg ON g.id = kg.genre_id
    GROUP BY g.id, g.nom
    ORDER BY nombre_kdramas DESC
    LIMIT :limit
"""

# Requête 8 : Statistiques par année de diffusion (GROUP BY + AVG + COUNT)
SQL_STATS_PAR_ANNEE = """
    SELECT
        EXTRACT(YEAR FROM date_diffusion) AS annee,
        COUNT(*) AS nombre_kdramas,
        ROUND(AVG(note_moyenne), 2) AS note_moyenne_annuelle,
        ROUND(AVG(nb_episodes), 0) AS episodes_moyens,
        ROUND(AVG(nb_votes), 0) AS votes_moyens,
        MIN(date_diffusion) AS premiere_diffusion,
        MAX(date_diffusion) AS derniere_diffusion
    FROM kdramas
    WHERE date_diffusion IS NOT NULL
    GROUP BY annee
    ORDER BY annee DESC
"""

# Requête 9 : K-Dramas dont la note est supérieure à la moyenne globale (sous-requête)
SQL_KDRAMAS_AU_DESSUS_MOYENNE = """
    SELECT
        id,
        titre,
        titre_original,
        date_diffusion,
        note_moyenne,
        nb_votes
    FROM kdramas
    WHERE note_moyenne > (
        SELECT AVG(note_moyenne)
        FROM kdramas
        WHERE note_moyenne IS NOT NULL
    )
    ORDER BY note_moyenne DESC
"""

# Requête 10 : Acteurs ayant joué dans plus de N K-Dramas (HAVING + agrégation)
SQL_ACTEURS_PRODUCTIFS = """
    SELECT
        a.id,
        a.nom,
        a.nom_original,
        COUNT(ka.kdrama_id) AS nombre_kdramas,
        ROUND(AVG(k.note_moyenne), 2) AS note_moyenne_filmo
    FROM acteurs a
    JOIN kdrama_acteurs ka ON a.id = ka.acteur_id
    JOIN kdramas k ON ka.kdrama_id = k.id
    GROUP BY a.id, a.nom, a.nom_original
    HAVING COUNT(ka.kdrama_id) > :seuil_min
    ORDER BY nombre_kdramas DESC, note_moyenne_filmo DESC
"""

# Requête 11 : Recherche de K-Dramas par titre (ILIKE pour insensibilité à la casse)
SQL_RECHERCHE_PAR_TITRE = """
    SELECT
        id,
        titre,
        titre_original,
        date_diffusion,
        nb_episodes,
        note_moyenne,
        nb_votes
    FROM kdramas
    WHERE titre ILIKE :pattern
       OR titre_original ILIKE :pattern
    ORDER BY note_moyenne DESC NULLS LAST
    LIMIT :limit
"""

# Requête 12 : K-Dramas par genre (JOIN + filtre sur le genre)
SQL_KDRAMAS_PAR_GENRE = """
    SELECT
        k.id,
        k.titre,
        k.titre_original,
        k.date_diffusion,
        k.nb_episodes,
        k.note_moyenne,
        k.nb_votes
    FROM kdramas k
    JOIN kdrama_genres kg ON k.id = kg.kdrama_id
    JOIN genres g ON kg.genre_id = g.id
    WHERE g.nom ILIKE :genre
    ORDER BY k.note_moyenne DESC NULLS LAST
    LIMIT :limit
"""

# Requête 13 : Statistiques globales de la base (agrégations multiples)
SQL_STATISTIQUES_GLOBALES = """
    SELECT
        (SELECT COUNT(*) FROM kdramas) AS total_kdramas,
        (SELECT COUNT(*) FROM acteurs) AS total_acteurs,
        (SELECT COUNT(*) FROM genres) AS total_genres,
        (SELECT COUNT(*) FROM utilisateurs) AS total_utilisateurs,
        (SELECT COUNT(*) FROM notes) AS total_notes,
        (SELECT ROUND(AVG(note_moyenne), 2) FROM kdramas WHERE note_moyenne IS NOT NULL) AS note_moyenne_globale,
        (SELECT ROUND(AVG(nb_episodes), 1) FROM kdramas WHERE nb_episodes IS NOT NULL) AS episodes_moyens_globaux,
        (SELECT MIN(date_diffusion) FROM kdramas WHERE date_diffusion IS NOT NULL) AS premiere_diffusion,
        (SELECT MAX(date_diffusion) FROM kdramas WHERE date_diffusion IS NOT NULL) AS derniere_diffusion
"""

# Requête 14 : Top N K-Dramas les mieux notés avec leurs genres (vue agrégée)
SQL_TOP_KDRAMAS_AVEC_GENRES = """
    SELECT
        k.id,
        k.titre,
        k.titre_original,
        k.date_diffusion,
        k.nb_episodes,
        k.note_moyenne,
        k.nb_votes,
        STRING_AGG(g.nom, ', ' ORDER BY g.nom) AS liste_genres
    FROM kdramas k
    LEFT JOIN kdrama_genres kg ON k.id = kg.kdrama_id
    LEFT JOIN genres g ON kg.genre_id = g.id
    WHERE k.note_moyenne IS NOT NULL
    GROUP BY k.id, k.titre, k.titre_original, k.date_diffusion,
             k.nb_episodes, k.note_moyenne, k.nb_votes
    ORDER BY k.note_moyenne DESC
    LIMIT :limit
"""

# Requête 15 : Distribution des notes par tranche (CASE + GROUP BY)
SQL_DISTRIBUTION_NOTES = """
    SELECT
        CASE
            WHEN note_moyenne >= 9.0 THEN '9.0 - 10.0 (Excellent)'
            WHEN note_moyenne >= 8.0 THEN '8.0 - 9.0 (Très bon)'
            WHEN note_moyenne >= 7.0 THEN '7.0 - 8.0 (Bon)'
            WHEN note_moyenne >= 5.0 THEN '5.0 - 7.0 (Moyen)'
            WHEN note_moyenne >= 0 THEN '0.0 - 5.0 (Faible)'
            ELSE 'Non noté'
        END AS tranche_note,
        COUNT(*) AS nombre_kdramas,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pourcentage
    FROM kdramas
    GROUP BY tranche_note
    ORDER BY tranche_note DESC
"""

# Requête 16 : K-Dramas par réseau de diffusion (JOIN + GROUP BY)
SQL_KDRAMAS_PAR_RESEAU = """
    SELECT
        r.nom AS reseau,
        COUNT(kr.kdrama_id) AS nombre_kdramas,
        ROUND(AVG(k.note_moyenne), 2) AS note_moyenne_reseau
    FROM reseaux r
    JOIN kdrama_reseaux kr ON r.id = kr.reseau_id
    JOIN kdramas k ON kr.kdrama_id = k.id
    WHERE k.note_moyenne IS NOT NULL
    GROUP BY r.id, r.nom
    ORDER BY nombre_kdramas DESC
"""

# --- Définition des vues SQL ---

# Vue 1 : K-Dramas populaires (note >= 7.0 et >= 100 votes)
SQL_VUE_KDRAMAS_POPULAIRES = """
    CREATE OR REPLACE VIEW v_kdramas_populaires AS
    SELECT
        k.id,
        k.titre,
        k.titre_original,
        k.date_diffusion,
        k.nb_episodes,
        k.note_moyenne,
        k.nb_votes,
        STRING_AGG(g.nom, ', ' ORDER BY g.nom) AS liste_genres
    FROM kdramas k
    LEFT JOIN kdrama_genres kg ON k.id = kg.kdrama_id
    LEFT JOIN genres g ON kg.genre_id = g.id
    WHERE k.note_moyenne >= 7.0 AND k.nb_votes >= 100
    GROUP BY k.id, k.titre, k.titre_original, k.date_diffusion,
             k.nb_episodes, k.note_moyenne, k.nb_votes
    ORDER BY k.note_moyenne DESC
"""

# Vue 2 : Statistiques par acteur (nombre de K-Dramas, note moyenne)
SQL_VUE_STATS_ACTEURS = """
    CREATE OR REPLACE VIEW v_stats_acteurs AS
    SELECT
        a.id,
        a.nom,
        a.nom_original,
        COUNT(ka.kdrama_id) AS nombre_kdramas,
        ROUND(AVG(k.note_moyenne), 2) AS note_moyenne_filmo,
        MAX(k.date_diffusion) AS derniere_apparition
    FROM acteurs a
    LEFT JOIN kdrama_acteurs ka ON a.id = ka.acteur_id
    LEFT JOIN kdramas k ON ka.kdrama_id = k.id
    GROUP BY a.id, a.nom, a.nom_original
"""

# Vue 3 : Utilisateurs anonymisés (conformité RGPD — pas d'email ni de hash)
SQL_VUE_UTILISATEURS_ANONYMISES = """
    CREATE OR REPLACE VIEW v_utilisateurs_anonymises AS
    SELECT
        id,
        pseudonyme,
        date_inscription,
        consentement_collecte,
        consentement_marketing,
        date_consentement,
        role,
        date_derniere_activite
    FROM utilisateurs
"""


# ===========================================================================
# Classe d'exécution des requêtes
# ===========================================================================
@dataclass
class QueryResult:
    """Résultat d'une requête SQL exécutée.

    Attributes:
        query_name: Nom identifiant la requête.
        rows: Liste de dictionnaires (un par ligne de résultat).
        row_count: Nombre de lignes retournées.
        duration_ms: Durée d'exécution en millisecondes.
    """

    query_name: str
    rows: list[dict]
    row_count: int
    duration_ms: float


class SQLQueryExecutor:
    """Exécuteur de requêtes SQL pour la base K-Drama.

    Gère la connexion à PostgreSQL via SQLAlchemy et fournit des méthodes
    pour exécuter chaque requête d'extraction de manière sécurisée
    (paramètres liés pour prévenir les injections SQL).

    Attributes:
        database_url: URL de connexion PostgreSQL.
        engine: Moteur SQLAlchemy pour la connexion à la base.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        """Initialise l'exécuteur SQL.

        Args:
            database_url: URL de connexion PostgreSQL.
                Si None, charge depuis DATABASE_URL dans l'environnement.

        Raises:
            ValueError: Si aucune URL de base de données n'est trouvée.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError(
                "URL de base de données introuvable. Définissez DATABASE_URL dans .env"
            )
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            connect_args={"options": "-c search_path=kdrama,public"},
        )
        logger.info("SQLQueryExecutor initialisé (base connectée)")

    def execute(
        self,
        query: str,
        params: Optional[dict] = None,
        query_name: str = "requete"
    ) -> QueryResult:
        """Exécute une requête SQL et retourne le résultat.

        Utilise des paramètres liés (named parameters) pour prévenir
        les injections SQL. Journalise le nom de la requête, la durée
        d'exécution et le nombre de résultats.

        Args:
            query: Chaîne SQL à exécuter (avec paramètres nommés :param).
            params: Dictionnaire des paramètres à lier.
            query_name: Nom identifiant la requête (pour la journalisation).

        Returns:
            Objet QueryResult contenant les lignes et les métadonnées.
        """
        params = params or {}
        start_time = time.time()

        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = [dict(row._mapping) for row in result]

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Requête '%s' exécutée: %d lignes en %.1fms",
            query_name,
            len(rows),
            duration_ms,
        )

        return QueryResult(
            query_name=query_name,
            rows=rows,
            row_count=len(rows),
            duration_ms=duration_ms,
        )

    def execute_to_dataframe(
        self,
        query: str,
        params: Optional[dict] = None,
        query_name: str = "requete"
    ) -> pd.DataFrame:
        """Exécute une requête et retourne un DataFrame pandas.

        Args:
            query: Chaîne SQL à exécuter.
            params: Paramètres à lier.
            query_name: Nom de la requête (journalisation).

        Returns:
            DataFrame pandas contenant les résultats.
        """
        params = params or {}
        start_time = time.time()
        df = pd.read_sql(text(query), self.engine, params=params)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Requête '%s' -> DataFrame: %d lignes × %d colonnes en %.1fms",
            query_name,
            len(df),
            len(df.columns),
            duration_ms,
        )
        return df

    def create_views(self) -> None:
        """Crée les vues SQL dans la base de données.

        Exécute les ordres DDL de création des vues :
            - v_kdramas_populaires
            - v_stats_acteurs
            - v_utilisateurs_anonymises (RGPD)
        """
        views = [
            ("v_kdramas_populaires", SQL_VUE_KDRAMAS_POPULAIRES),
            ("v_stats_acteurs", SQL_VUE_STATS_ACTEURS),
            ("v_utilisateurs_anonymises", SQL_VUE_UTILISATEURS_ANONYMISES),
        ]
        with self.engine.connect() as conn:
            for view_name, ddl in views:
                conn.execute(text(f"DROP VIEW IF EXISTS {view_name} CASCADE"))
                conn.execute(text(ddl))
                logger.info("Vue créée: %s", view_name)
            conn.commit()

    # -------------------------------------------------------------------
    # Méthodes métier — une par requête d'extraction
    # -------------------------------------------------------------------

    def get_liste_kdramas(self, limit: int = 100, offset: int = 0) -> QueryResult:
        """Récupère la liste paginée des K-Dramas triés par note.

        Args:
            limit: Nombre maximum de résultats.
            offset: Décalage pour la pagination.

        Returns:
            QueryResult contenant la liste des K-Dramas.
        """
        return self.execute(
            SQL_LISTE_KDRAMAS,
            {"limit": limit, "offset": offset},
            "liste_kdramas",
        )

    def get_kdramas_after_year(self, annee_min: int) -> QueryResult:
        """Récupère les K-Dramas diffusés à partir d'une année donnée.

        Args:
            annee_min: Année minimale de diffusion.

        Returns:
            QueryResult des K-Dramas récents.
        """
        return self.execute(
            SQL_KDRAMAS_APRES_ANNEE,
            {"annee_min": annee_min},
            "kdramas_apres_annee",
        )

    def get_kdramas_genres(self) -> QueryResult:
        """Récupère tous les K-Dramas avec leurs genres associés.

        Returns:
            QueryResult de la jointure K-Dramas ↔ Genres.
        """
        return self.execute(SQL_KDRAMAS_GENRES, query_name="kdramas_genres")

    def get_kdramas_acteurs_principaux(self) -> QueryResult:
        """Récupère les K-Dramas avec leurs acteurs principaux uniquement.

        Returns:
            QueryResult de la jointure filtrée sur role_principal = TRUE.
        """
        return self.execute(
            SQL_KDRAMAS_ACTEURS_PRINCIPAUX,
            query_name="kdramas_acteurs_principaux",
        )

    def get_notes_utilisateurs(self, limit: int = 100) -> QueryResult:
        """Récupère les notes récentes des utilisateurs avec détails du K-Drama.

        Args:
            limit: Nombre maximum de notes à récupérer.

        Returns:
            QueryResult des notes avec pseudonyme, titre et note.
        """
        return self.execute(
            SQL_NOTES_UTILISATEURS,
            {"limit": limit},
            "notes_utilisateurs",
        )

    def get_stats_notes_par_kdrama(self) -> QueryResult:
        """Calcule la note moyenne et le nombre de notes par K-Drama.

        Compare la moyenne des utilisateurs avec la note de la source
        (TMDB/MyDramaList) pour détecter les écarts.

        Returns:
            QueryResult des statistiques de notes par K-Drama.
        """
        return self.execute(
            SQL_STATS_NOTES_PAR_KDRAMA,
            query_name="stats_notes_par_kdrama",
        )

    def get_top_genres(self, limit: int = 10, total_kdramas: int = 1) -> QueryResult:
        """Récupère le classement des genres les plus représentés.

        Args:
            limit: Nombre maximum de genres à retourner.
            total_kdramas: Nombre total de K-Dramas (pour le pourcentage).

        Returns:
            QueryResult du top des genres.
        """
        return self.execute(
            SQL_TOP_GENRES,
            {"limit": limit, "total_kdramas": total_kdramas},
            "top_genres",
        )

    def get_stats_par_annee(self) -> QueryResult:
        """Calcule les statistiques de K-Dramas par année de diffusion.

        Returns:
            QueryResult des statistiques annuelles (nombre, note moyenne, etc.).
        """
        return self.execute(SQL_STATS_PAR_ANNEE, query_name="stats_par_annee")

    def get_kdramas_above_average(self) -> QueryResult:
        """Récupère les K-Dramas dont la note dépasse la moyenne globale.

        Utilise une sous-requête pour calculer la moyenne globale.

        Returns:
            QueryResult des K-Dramas au-dessus de la moyenne.
        """
        return self.execute(
            SQL_KDRAMAS_AU_DESSUS_MOYENNE,
            query_name="kdramas_above_average",
        )

    def get_acteurs_productifs(self, seuil_min: int = 5) -> QueryResult:
        """Récupère les acteurs ayant joué dans au moins N K-Dramas.

        Args:
            seuil_min: Nombre minimum de K-Dramas (clause HAVING).

        Returns:
            QueryResult des acteurs les plus productifs.
        """
        return self.execute(
            SQL_ACTEURS_PRODUCTIFS,
            {"seuil_min": seuil_min},
            "acteurs_productifs",
        )

    def search_kdramas_by_title(self, titre: str, limit: int = 20) -> QueryResult:
        """Recherche des K-Dramas par titre (insensible à la casse).

        Args:
            titre: Mot-clé à rechercher dans le titre.
            limit: Nombre maximum de résultats.

        Returns:
            QueryResult des K-Dramas correspondants.
        """
        pattern = f"%{titre}%"
        return self.execute(
            SQL_RECHERCHE_PAR_TITRE,
            {"pattern": pattern, "limit": limit},
            "recherche_par_titre",
        )

    def get_kdramas_by_genre(self, genre: str, limit: int = 50) -> QueryResult:
        """Récupère les K-Dramas d'un genre donné.

        Args:
            genre: Nom du genre à filtrer (ex: "Romance").
            limit: Nombre maximum de résultats.

        Returns:
            QueryResult des K-Dramas du genre spécifié.
        """
        return self.execute(
            SQL_KDRAMAS_PAR_GENRE,
            {"genre": f"%{genre}%", "limit": limit},
            "kdramas_par_genre",
        )

    def get_statistiques_globales(self) -> QueryResult:
        """Récupère les statistiques globales de la base de données.

        Retourne en une seule requête les totaux et moyennes pour
        chaque table (K-Dramas, acteurs, genres, utilisateurs, notes).

        Returns:
            QueryResult avec une ligne de statistiques globales.
        """
        return self.execute(
            SQL_STATISTIQUES_GLOBALES,
            query_name="statistiques_globales",
        )

    def get_top_kdramas_avec_genres(self, limit: int = 20) -> QueryResult:
        """Récupère le top des K-Dramas avec leurs genres agrégés en chaîne.

        Utilise STRING_AGG pour concaténer les genres en une seule chaîne.

        Args:
            limit: Nombre maximum de K-Dramas.

        Returns:
            QueryResult du top des K-Dramas avec liste de genres.
        """
        return self.execute(
            SQL_TOP_KDRAMAS_AVEC_GENRES,
            {"limit": limit},
            "top_kdramas_avec_genres",
        )

    def get_distribution_notes(self) -> QueryResult:
        """Calcule la distribution des notes par tranche.

        Utilise CASE WHEN pour catégoriser les notes en tranches
        (Excellent, Très bon, Bon, Moyen, Faible, Non noté).

        Returns:
            QueryResult de la distribution des notes.
        """
        return self.execute(
            SQL_DISTRIBUTION_NOTES,
            query_name="distribution_notes",
        )

    def get_kdramas_par_reseau(self) -> QueryResult:
        """Calcule les statistiques de K-Dramas par réseau de diffusion.

        Returns:
            QueryResult du nombre de K-Dramas et note moyenne par réseau.
        """
        return self.execute(
            SQL_KDRAMAS_PAR_RESEAU,
            query_name="kdramas_par_reseau",
        )


# ===========================================================================
# Point d'entrée — démonstration des requêtes
# ===========================================================================
if __name__ == "__main__":
    try:
        executor = SQLQueryExecutor()

        print("\n" + "=" * 60)
        print("DÉMONSTRATION DES REQUÊTES SQL D'EXTRACTION")
        print("=" * 60)

        # Création des vues
        print("\n→ Création des vues SQL...")
        executor.create_views()

        # Statistiques globales
        print("\n→ Statistiques globales de la base:")
        stats = executor.get_statistiques_globales()
        for row in stats.rows:
            for key, value in row.items():
                print(f"  {key}: {value}")

        # Top 10 des genres
        print("\n→ Top 10 des genres les plus représentés:")
        top_genres = executor.get_top_genres(limit=10, total_kdramas=stats.rows[0]["total_kdramas"] or 1)
        for row in top_genres.rows:
            print(f"  {row['genre']}: {row['nombre_kdramas']} K-Dramas ({row['pourcentage']}%)")

        # Distribution des notes
        print("\n→ Distribution des notes par tranche:")
        dist = executor.get_distribution_notes()
        for row in dist.rows:
            print(f"  {row['tranche_note']}: {row['nombre_kdramas']} ({row['pourcentage']}%)")

        # Statistiques par année
        print("\n→ Statistiques par année de diffusion (5 dernières):")
        annees = executor.get_stats_par_annee()
        for row in annees.rows[:5]:
            print(f"  {int(row['annee'])}: {row['nombre_kdramas']} K-Dramas, note moy. {row['note_moyenne_annuelle']}")

        print("\n" + "=" * 60)
        print("Démonstration terminée avec succès.")
        print("=" * 60)

    except Exception as e:
        logger.error("Erreur lors de la démonstration: %s", e)
        raise
