#!/usr/bin/env python3
"""Generate the documented E2 decision matrix without invented metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


REVIEW_DATE = date(2026, 9, 3)
OUTPUT = Path(__file__).with_name("rapport_benchmark.md")

# Comparable workload used only when a provider publishes a compatible price.
CATALOGUE_TEXTS = 10_000
QUERIES_PER_DAY = 1_000
DAYS_PER_MONTH = 30
TOKENS_PER_TEXT = 150
TOTAL_TOKENS = (CATALOGUE_TEXTS + QUERIES_PER_DAY * DAYS_PER_MONTH) * TOKENS_PER_TEXT

SOURCES = {
    "OpenAI model pricing": "https://developers.openai.com/api/docs/models/text-embedding-3-small",
    "Cohere pricing": "https://cohere.com/pricing",
    "Cohere trial policy": "https://docs.cohere.com/docs/how-does-cohere-pricing-work",
    "Google Vertex AI pricing": "https://cloud.google.com/vertex-ai/generative-ai/pricing",
    "Google model lifecycle": "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions",
    "all-MiniLM-L6-v2 model card": "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2",
}


@dataclass(frozen=True)
class Service:
    """One candidate and its decision scores (1 unfavorable, 5 favorable)."""

    name: str
    functional_fit: int
    data_governance: int
    cost_predictability: int
    integration: int
    eco_sobriety: int
    price_fact: str
    prerequisites: str
    advantages: str
    limits: str
    exclusion_reason: str = ""
    comparable_monthly_api_cost_usd: Optional[float] = None

    @property
    def score(self) -> float:
        weights = (0.30, 0.25, 0.15, 0.15, 0.15)
        values = (
            self.functional_fit,
            self.data_governance,
            self.cost_predictability,
            self.integration,
            self.eco_sobriety,
        )
        return round(sum(value * weight for value, weight in zip(values, weights)), 2)


def token_cost(price_per_million: float) -> float:
    """Calculate an API-only cost for the explicit reference workload."""
    return round(TOTAL_TOKENS / 1_000_000 * price_per_million, 2)


SERVICES = (
    Service(
        name="Sentence Transformers — all-MiniLM-L6-v2 (local)",
        functional_fit=4,
        data_governance=5,
        cost_predictability=4,
        integration=5,
        eco_sobriety=4,
        price_fact="Licence Apache-2.0 et aucun coût API; hébergement, électricité et maintenance ne sont pas gratuits.",
        prerequisites="Python, PyTorch, sentence-transformers, environ 91 Mo pour un fichier de poids; synopsis principalement en anglais.",
        advantages="Inférence maîtrisée, 384 dimensions, intégration Python simple, aucun envoi des textes à un fournisseur d'embeddings.",
        limits="Fiche officielle étiquetée English; entrées tronquées au-delà de 256 word pieces; capacité et latence dépendent de l'hôte.",
    ),
    Service(
        name="OpenAI — text-embedding-3-small (API)",
        functional_fit=5,
        data_governance=3,
        cost_predictability=5,
        integration=5,
        eco_sobriety=2,
        price_fact="0,02 USD par million de tokens d'entrée, relevé sur la fiche officielle.",
        prerequisites="Compte, clé API, réseau, budget et revue contractuelle/RGPD du sous-traitant.",
        advantages="Multilingue, API documentée, coût variable faible pour le volume de référence.",
        limits="Dépendance réseau et fournisseur; textes transmis à un tiers; impact par requête non publié de façon comparable.",
        comparable_monthly_api_cost_usd=token_cost(0.02),
    ),
    Service(
        name="Google Vertex AI — gemini-embedding-001 (API)",
        functional_fit=5,
        data_governance=3,
        cost_predictability=4,
        integration=3,
        eco_sobriety=2,
        price_fact="0,00015 USD par 1 000 tokens en ligne, soit 0,15 USD par million, relevé sur Vertex AI Pricing.",
        prerequisites="Projet Google Cloud, facturation, IAM, SDK/API Vertex AI et région disponible.",
        advantages="Modèle stable actuel, multilingue, service géré et scalable.",
        limits="Dépendance GCP; 3 072 dimensions par défaut donc stockage supérieur; gouvernance contractuelle à instruire.",
        comparable_monthly_api_cost_usd=token_cost(0.15),
    ),
    Service(
        name="Cohere — Embed (API / Model Vault)",
        functional_fit=5,
        data_governance=3,
        cost_predictability=2,
        integration=4,
        eco_sobriety=2,
        price_fact="Clé trial gratuite mais limitée; aucun prix API Embed par token comparable sur la page consultée. Model Vault Embed 4 démarre à 4 USD/heure ou 2 500 USD/mois.",
        prerequisites="Compte, clé de production ou contrat Model Vault, réseau et revue contractuelle/RGPD.",
        advantages="Embeddings multilingues et options de déploiement entreprise.",
        limits="Coût de production API non comparable depuis les informations publiques consultées; solution surdimensionnée pour ce POC.",
    ),
    Service(
        name="Ollama — nomic-embed-text (local)",
        functional_fit=4,
        data_governance=5,
        cost_predictability=3,
        integration=3,
        eco_sobriety=3,
        price_fact="Aucun coût API, mais coût réel de machine, énergie et exploitation.",
        prerequisites="Service Ollama séparé, téléchargement et cycle de vie du modèle, RAM/disque supplémentaires.",
        advantages="Exécution locale et isolation des textes.",
        limits="Composant d'exploitation supplémentaire sans bénéfice démontré sur le corpus du POC.",
        exclusion_reason="Non retenu: complexité supérieure à sentence-transformers sans gain mesuré avec le protocole du projet.",
    ),
)

NOT_STUDIED = (
    ("AWS Bedrock embeddings", "Écarté du détail: un nouvel écosystème cloud n'apporte pas de besoin fonctionnel non couvert."),
    ("Voyage AI", "Écarté faute de temps pour exécuter un protocole identique et de besoin non couvert par les candidats étudiés."),
    ("Modèles génératifs généralistes", "Écartés: générer du texte est disproportionné pour calculer une similarité de synopsis."),
)


def build_report() -> str:
    """Return the complete Markdown report."""
    formatted_total_tokens = f"{TOTAL_TOKENS:,}".replace(",", " ")
    rows = []
    for service in sorted(SERVICES, key=lambda item: item.score, reverse=True):
        cost = (
            f"{service.comparable_monthly_api_cost_usd:.2f} USD"
            if service.comparable_monthly_api_cost_usd is not None
            else "non comparable"
        )
        rows.append(
            f"| {service.name} | {service.functional_fit} | {service.data_governance} | "
            f"{service.cost_predictability} | {service.integration} | {service.eco_sobriety} | "
            f"**{service.score:.2f}** | {cost} |"
        )

    details = []
    for service in SERVICES:
        details.extend(
            [
                f"### {service.name}",
                "",
                f"- Prix/TCO : {service.price_fact}",
                f"- Prérequis : {service.prerequisites}",
                f"- Avantages : {service.advantages}",
                f"- Limites : {service.limits}",
            ]
        )
        if service.exclusion_reason:
            details.append(f"- Décision : {service.exclusion_reason}")
        details.append("")

    exclusions = [f"- **{name}** — {reason}" for name, reason in NOT_STUDIED]
    sources = [f"- [{name}]({url}) — consulté le {REVIEW_DATE.isoformat()}." for name, url in SOURCES.items()]

    return "\n".join(
        [
            "# Benchmark des services d'embeddings",
            "",
            f"**Date de revue des informations** : {REVIEW_DATE.isoformat()}",
            "",
            "## Besoin et contraintes",
            "",
            "Le service doit représenter des synopsis de K-Dramas pour une recommandation hybride, s'intégrer à Python/FastAPI, fonctionner sur CPU pour le POC, limiter les transferts de données et rester exploitable avec un budget étudiant. Les synopsis sont principalement en anglais; les préférences et requêtes peuvent être multilingues.",
            "",
            "## Méthode et limites",
            "",
            "Cette grille est une **matrice de décision**, pas un classement scientifique. Chaque note va de 1 (défavorable) à 5 (favorable). Pondération: fonctionnel 30 %, gouvernance des données 25 %, prévisibilité du coût 15 %, intégration 15 %, sobriété d'exploitation 15 %. Aucune latence ou qualité cloud n'est inventée: elles restent non mesurées tant que tous les candidats n'ont pas été exécutés avec le même corpus, la même région et le même protocole.",
            "",
            f"Hypothèse de coût API: {formatted_total_tokens} tokens (10 000 textes initiaux + 1 000 requêtes/jour pendant 30 jours, 150 tokens/texte). Coûts hors taxes, stockage, réseau, hébergement et travail humain.",
            "",
            "## Grille de décision",
            "",
            "| Service | Fonctionnel 30 % | Données 25 % | Coût 15 % | Intégration 15 % | Sobriété 15 % | Total / 5 | API pour l'hypothèse |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Analyse par candidat",
            "",
            *details,
            "## Services identifiés mais non étudiés en détail",
            "",
            *exclusions,
            "",
            "## Conclusion",
            "",
            "**Service retenu pour le POC : Sentence Transformers avec `all-MiniLM-L6-v2`, en local.** Il répond au besoin sur les synopsis anglophones, réduit la dépendance à une API externe et son faible volume facilite le déploiement CPU. Ce choix ne signifie ni coût total nul, ni conformité automatique, ni supériorité absolue. Son risque principal est la qualité sur les requêtes non anglaises; une évolution vers un modèle multilingue devra être testée sur un jeu annoté représentatif.",
            "",
            "OpenAI reste l'alternative SaaS la moins chère parmi les coûts API publiés et comparables ici. Google est 7,5 fois plus cher sur l'unité token retenue (0,15 contre 0,02 USD/million); Cohere n'est pas chiffré artificiellement lorsque le tarif public comparable manque.",
            "",
            "## Sources officielles",
            "",
            *sources,
            "",
        ]
    )


def main() -> int:
    OUTPUT.write_text(build_report(), encoding="utf-8")
    print(f"Rapport généré: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
