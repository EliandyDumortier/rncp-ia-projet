#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_server.py — API REST FastAPI pour le système de recommandation de K-Dramas.

Ce module implémente une API REST complète avec :
    - Authentification JWT (inscription, connexion, profil).
    - CRUD complet pour les K-Dramas, acteurs, genres et notes.
    - Pagination sur tous les endpoints de liste.
    - Documentation OpenAPI automatique (Swagger UI + ReDoc).
    - Endpoints dédiés aux droits RGPD (effacement, portabilité).
    - Middleware CORS et rate limiting.
    - Gestion d'erreurs structurée.

Compétence RNCP C5 : Conception et développement d'une API REST.

Auteur : Équipe Data
Projet : Système de recommandation de K-Dramas par IA
Étape : 1 — Collecte et préparation des données
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, date, timedelta, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    Boolean,
    Text,
    ForeignKey,
    create_engine,
    select,
    func,
    or_,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    relationship,
    sessionmaker,
)

# ---------------------------------------------------------------------------
# Configuration et logging
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api_server")

# Variables de configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/kdrama_db")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# ---------------------------------------------------------------------------
# Base de données (SQLAlchemy)
# ---------------------------------------------------------------------------
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base déclarative SQLAlchemy pour les modèles ORM."""
    pass


class Kdrama(Base):
    """Modèle ORM pour la table kdramas."""
    __tablename__ = "kdramas"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[Optional[int]] = Column(Integer, unique=True)
    titre: Mapped[str] = Column(String(300), nullable=False)
    titre_original: Mapped[Optional[str]] = Column(String(300))
    english_name: Mapped[Optional[str]] = Column(String(300))
    date_diffusion: Mapped[Optional[date]] = Column(Date)
    annee_diffusion: Mapped[Optional[int]] = Column(Integer)
    nb_episodes: Mapped[Optional[int]] = Column(Integer)
    nb_saisons: Mapped[Optional[int]] = Column(Integer)
    duree_episode: Mapped[Optional[int]] = Column(Integer)
    duree_episode_minutes: Mapped[Optional[int]] = Column(Integer)
    synopsis: Mapped[Optional[str]] = Column(Text)
    note_moyenne: Mapped[Optional[float]] = Column(Float)
    nb_votes: Mapped[Optional[int]] = Column(Integer)
    langue_originale: Mapped[Optional[str]] = Column(String(100))
    pays_origine: Mapped[Optional[str]] = Column(String(100), default="KR")
    source: Mapped[str] = Column(String(50), default="tmdb")
    url_source: Mapped[Optional[str]] = Column(String(500))
    poster: Mapped[Optional[str]] = Column(String(500))
    genres: Mapped[Optional[str]] = Column(Text)
    acteurs: Mapped[Optional[str]] = Column(Text)
    reseaux_diffusion: Mapped[Optional[str]] = Column(Text)
    tags: Mapped[Optional[str]] = Column(Text)
    rang: Mapped[Optional[int]] = Column(Integer)
    popularite: Mapped[Optional[float]] = Column(Float)
    nb_watchers: Mapped[Optional[int]] = Column(Integer)
    realisateur: Mapped[Optional[str]] = Column(String(300))
    scenariste: Mapped[Optional[str]] = Column(String(300))
    date_creation: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    date_modification: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DramaSentiment(Base):
    """Modèle ORM pour la table drama_sentiments."""
    __tablename__ = "drama_sentiments"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    drama_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.kdramas.id"), nullable=False)
    ending_type: Mapped[str] = Column(String(20), default="unknown")  # happy, sad, bittersweet, unknown
    ending_confidence: Mapped[float] = Column(Float, default=0.5)  # 0-1 confidence score
    sentiment_score: Mapped[float] = Column(Float, default=0.5)  # -1 to 1 sentiment
    sentiment_summary: Mapped[Optional[str]] = Column(Text)
    is_ongoing: Mapped[bool] = Column(Boolean, default=False)
    is_completed: Mapped[bool] = Column(Boolean, default=True)
    total_episodes: Mapped[Optional[int]] = Column(Integer)
    scraped_date: Mapped[Optional[datetime]] = Column(DateTime)
    last_updated: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source_urls: Mapped[Optional[str]] = Column(Text)  # JSON array of URLs
    data_quality_score: Mapped[Optional[float]] = Column(Float)
    top_comments: Mapped[Optional[str]] = Column(Text)  # JSON array
    notable_triggers: Mapped[Optional[str]] = Column(Text)  # JSON array
    viewer_consensus: Mapped[Optional[str]] = Column(Text)


class Acteur(Base):
    """Modèle ORM pour la table acteurs."""
    __tablename__ = "acteurs"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[Optional[int]] = Column(Integer, unique=True)
    nom: Mapped[str] = Column(String(200), nullable=False)
    nom_original: Mapped[Optional[str]] = Column(String(200))
    date_naissance: Mapped[Optional[datetime]] = Column(DateTime)
    sexe: Mapped[Optional[str]] = Column(String(1))
    biographie: Mapped[Optional[str]] = Column(Text)


class Genre(Base):
    """Modèle ORM pour la table genres."""
    __tablename__ = "genres"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = Column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = Column(Text)


class Utilisateur(Base):
    """Modèle ORM pour la table utilisateurs (conforme RGPD)."""
    __tablename__ = "utilisateurs"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    pseudonyme: Mapped[str] = Column(String(100), nullable=False, unique=True)
    email_hache: Mapped[str] = Column(String(64), nullable=False, unique=True)
    mot_de_passe_hache: Mapped[str] = Column(String(255), nullable=False)
    consentement_collecte: Mapped[bool] = Column(Boolean, default=False)
    consentement_marketing: Mapped[bool] = Column(Boolean, default=False)
    date_consentement: Mapped[Optional[datetime]] = Column(DateTime)
    methode_consentement: Mapped[Optional[str]] = Column(String(100))
    role: Mapped[str] = Column(String(20), default="user")
    date_inscription: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    date_derniere_activite: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    date_suppression: Mapped[Optional[datetime]] = Column(DateTime)
    est_supprime: Mapped[bool] = Column(Boolean, default=False)
    fin_heureuse_uniquement: Mapped[bool] = Column(Boolean, default=False)
    date_creation: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    date_modification: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Note(Base):
    """Modèle ORM pour la table notes."""
    __tablename__ = "notes"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.utilisateurs.id", ondelete="CASCADE"))
    kdrama_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.kdramas.id", ondelete="CASCADE"))
    note: Mapped[int] = Column(Integer, nullable=False)
    commentaire: Mapped[Optional[str]] = Column(Text)
    date_note: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class HistoriqueVisionnage(Base):
    """Modèle ORM pour la table historique_visionnage (suivi du visionnage)."""
    __tablename__ = "historique_visionnage"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.utilisateurs.id", ondelete="CASCADE"))
    kdrama_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.kdramas.id", ondelete="CASCADE"))
    episodes_vus: Mapped[Optional[int]] = Column(Integer, default=0)
    statut: Mapped[str] = Column(String(20), default="en_cours")  # a_voir, en_cours, termine, abandonne
    date_debut: Mapped[Optional[datetime]] = Column(DateTime)
    date_fin: Mapped[Optional[datetime]] = Column(DateTime)
    date_creation: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    date_modification: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favori(Base):
    """Modèle ORM pour la table favoris (liste de favoris K-Drama)."""
    __tablename__ = "favoris"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.utilisateurs.id", ondelete="CASCADE"))
    kdrama_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.kdramas.id", ondelete="CASCADE"))
    date_ajout: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class InteretUtilisateur(Base):
    """Modèle ORM pour la table interet_utilisateur (want to watch / not interested)."""
    __tablename__ = "interet_utilisateur"
    __table_args__ = {"schema": "kdrama"}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.utilisateurs.id", ondelete="CASCADE"))
    kdrama_id: Mapped[int] = Column(Integer, ForeignKey("kdrama.kdramas.id", ondelete="CASCADE"))
    interesse: Mapped[bool] = Column(Boolean, nullable=False)
    date_creation: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    date_modification: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UtilisateurGenrePrefere(Base):
    """Modèle ORM pour la table utilisateur_genres_preferes (genres favoris, max 3)."""
    __tablename__ = "utilisateur_genres_preferes"
    __table_args__ = {"schema": "kdrama"}

    utilisateur_id: Mapped[int] = Column(
        Integer, ForeignKey("kdrama.utilisateurs.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = Column(
        Integer, ForeignKey("kdrama.genres.id", ondelete="CASCADE"), primary_key=True
    )
    date_ajout: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


class UtilisateurActeurPrefere(Base):
    """Modèle ORM pour la table utilisateur_acteurs_preferes (acteurs favoris, max 5)."""
    __tablename__ = "utilisateur_acteurs_preferes"
    __table_args__ = {"schema": "kdrama"}

    utilisateur_id: Mapped[int] = Column(
        Integer, ForeignKey("kdrama.utilisateurs.id", ondelete="CASCADE"), primary_key=True
    )
    acteur_id: Mapped[int] = Column(
        Integer, ForeignKey("kdrama.acteurs.id", ondelete="CASCADE"), primary_key=True
    )
    date_ajout: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Sécurité (JWT + hachage des mots de passe)
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hacher_email(email: str) -> str:
    """Hache un email avec SHA-256 (conformité RGPD).

    Args:
        email: Email en clair à hacher.

    Returns:
        Hash SHA-256 hexadécimal de l'email.
    """
    import hashlib
    return hashlib.sha256(email.lower().strip().encode("utf-8")).hexdigest()


def verifier_mot_de_passe(mot_de_passe_clair: str, mot_de_passe_hache: str) -> bool:
    """Vérifie un mot de passe contre son hash bcrypt.

    Args:
        mot_de_passe_clair: Mot de passe en clair saisi par l'utilisateur.
        mot_de_passe_hache: Hash bcrypt stocké en base.

    Returns:
        True si le mot de passe correspond, False sinon.
    """
    return pwd_context.verify(mot_de_passe_clair, mot_de_passe_hache)


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    """Hache un mot de passe avec bcrypt.

    Args:
        mot_de_passe: Mot de passe en clair.

    Returns:
        Hash bcrypt du mot de passe.
    """
    return pwd_context.hash(mot_de_passe)


def creer_token_jwt(donnees: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un token JWT signé.

    Args:
        donnees: Données à encoder dans le token (doit contenir 'sub').
        expires_delta: Durée de validité du token.

    Returns:
        Token JWT encodé en chaîne.
    """
    to_encode = donnees.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_EXPIRATION_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(lambda: SessionLocal()),
) -> Utilisateur:
    """Dépendance FastAPI : récupère l'utilisateur courant depuis le token JWT.

    Args:
        token: Token JWT extrait de l'en-tête Authorization.
        db: Session de base de données.

    Returns:
        Objet Utilisateur authentifié.

    Raises:
        HTTPException: 401 si le token est invalide ou l'utilisateur introuvable.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired JWT token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    utilisateur = db.query(Utilisateur).filter(
        Utilisateur.id == int(user_id),
        Utilisateur.est_supprime == False
    ).first()
    if utilisateur is None:
        raise credentials_exception

    db.close()
    return utilisateur


def get_current_admin(
    current_user: Utilisateur = Depends(get_current_user),
) -> Utilisateur:
    """Dépendance FastAPI : vérifie que l'utilisateur courant est administrateur.

    Args:
        current_user: Utilisateur authentifié.

    Returns:
        L'utilisateur administrateur.

    Raises:
        HTTPException: 403 si l'utilisateur n'est pas admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Modèles Pydantic (validation et sérialisation)
# ---------------------------------------------------------------------------

class KdramaBase(BaseModel):
    """Modèle de base pour un K-Drama."""
    titre: str = Field(..., max_length=300, description="International title of the K-Drama")
    titre_original: Optional[str] = Field(None, max_length=300)
    english_name: Optional[str] = Field(None, max_length=300)
    date_diffusion: Optional[datetime] = None
    nb_episodes: Optional[int] = Field(None, gt=0)
    nb_saisons: Optional[int] = Field(None, gt=0)
    duree_episode: Optional[int] = None
    synopsis: Optional[str] = None
    note_moyenne: Optional[float] = Field(None, ge=0, le=10)
    nb_votes: Optional[int] = Field(None, ge=0)
    langue_originale: Optional[str] = Field(None, max_length=100)
    pays_origine: Optional[str] = Field("KR", max_length=100)
    poster: Optional[str] = None
    genres: Optional[str] = None
    acteurs: Optional[str] = None
    reseaux_diffusion: Optional[str] = None
    tags: Optional[str] = None
    rang: Optional[int] = None
    popularite: Optional[float] = None
    nb_watchers: Optional[int] = None
    realisateur: Optional[str] = None
    scenariste: Optional[str] = None

    class Config:
        from_attributes = True


class KdramaCreate(KdramaBase):
    """Modèle pour la création d'un K-Drama."""
    tmdb_id: Optional[int] = None


class KdramaUpdate(BaseModel):
    """Modèle pour la mise à jour partielle d'un K-Drama."""
    titre: Optional[str] = Field(None, max_length=300)
    titre_original: Optional[str] = None
    date_diffusion: Optional[datetime] = None
    nb_episodes: Optional[int] = Field(None, gt=0)
    nb_saisons: Optional[int] = Field(None, gt=0)
    synopsis: Optional[str] = None
    note_moyenne: Optional[float] = Field(None, ge=0, le=10)
    nb_votes: Optional[int] = Field(None, ge=0)


class KdramaResponse(KdramaBase):
    """Modèle de réponse pour un K-Drama (avec id)."""
    id: int
    tmdb_id: Optional[int] = None
    source: str
    date_creation: datetime
    date_modification: datetime

    class Config:
        from_attributes = True


class ActeurResponse(BaseModel):
    """Modèle de réponse pour un acteur."""
    id: int
    tmdb_id: Optional[int] = None
    nom: str
    nom_original: Optional[str] = None
    date_naissance: Optional[datetime] = None
    sexe: Optional[str] = None
    biographie: Optional[str] = None

    class Config:
        from_attributes = True


class GenreResponse(BaseModel):
    """Modèle de réponse pour un genre."""
    id: int
    nom: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Modèle pour l'inscription d'un utilisateur."""
    pseudonyme: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    mot_de_passe: str = Field(..., min_length=8, max_length=128)
    consentement_collecte: bool = Field(..., description="Consent to data collection (GDPR art. 6.1.a)")
    consentement_marketing: bool = Field(False, description="Consent to marketing (GDPR art. 7)")


class UserResponse(BaseModel):
    """Modèle de réponse pour un utilisateur (sans données sensibles)."""
    id: int
    pseudonyme: str
    date_inscription: datetime
    role: str
    consentement_collecte: bool
    consentement_marketing: bool
    fin_heureuse_uniquement: bool = False
    genres_preferes: list[str] = Field(default_factory=list)
    acteurs_preferes: list["ActeurResponse"] = Field(default_factory=list)
    nb_dramas_vus: int = 0
    nb_favoris: int = 0

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    """Modèle pour la mise à jour des préférences de recommandation (toutes optionnelles)."""
    genres: Optional[list[str]] = Field(
        None, description="Noms des genres favoris (maximum 3)."
    )
    acteur_ids: Optional[list[int]] = Field(
        None, description="Identifiants des acteurs/actrices favoris (maximum 5)."
    )
    fin_heureuse_uniquement: Optional[bool] = Field(
        None, description="Ne recommander que des dramas à fin heureuse."
    )

    @field_validator("genres")
    @classmethod
    def _valider_genres(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and len(v) > 3:
            raise ValueError("Maximum 3 favorite genres allowed")
        return v

    @field_validator("acteur_ids")
    @classmethod
    def _valider_acteurs(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is not None and len(v) > 5:
            raise ValueError("Maximum 5 favorite actors allowed")
        return v


class Token(BaseModel):
    """Modèle de réponse pour le token JWT."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class NoteCreate(BaseModel):
    """Modèle pour la création d'une note."""
    note: int = Field(..., ge=1, le=10, description="Rating from 1 to 10")
    commentaire: Optional[str] = Field(None, max_length=2000)


class NoteResponse(BaseModel):
    """Modèle de réponse pour une note."""
    id: int
    utilisateur_id: int
    kdrama_id: int
    note: int
    commentaire: Optional[str] = None
    date_note: datetime

    class Config:
        from_attributes = True


class FavoriResponse(BaseModel):
    """Modèle de réponse pour un favori."""
    id: int
    utilisateur_id: int
    kdrama_id: int
    date_ajout: datetime

    class Config:
        from_attributes = True


class HistoriqueVisionnageUpsert(BaseModel):
    """Modèle pour créer/mettre à jour une entrée d'historique de visionnage."""
    kdrama_id: int
    episodes_vus: int = Field(0, ge=0)
    statut: str = Field(
        "en_cours",
        pattern="^(a_voir|en_cours|termine|abandonne)$",
        description="a_voir, en_cours, termine ou abandonne",
    )


class HistoriqueVisionnageResponse(BaseModel):
    """Modèle de réponse pour une entrée d'historique de visionnage."""
    id: int
    utilisateur_id: int
    kdrama_id: int
    episodes_vus: int
    statut: str
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    date_creation: datetime
    date_modification: datetime

    class Config:
        from_attributes = True


class InteretUpdate(BaseModel):
    """Modèle pour signaler l'intérêt d'un utilisateur pour un drama."""
    interesse: bool = Field(
        ..., description="True = je veux regarder, False = pas intéressé(e)"
    )


class InteretResponse(BaseModel):
    """Modèle de réponse pour un retour d'intérêt utilisateur."""
    id: int
    utilisateur_id: int
    kdrama_id: int
    interesse: bool
    date_creation: datetime
    date_modification: datetime

    class Config:
        from_attributes = True


class DramaSentimentResponse(BaseModel):
    """Modèle de réponse pour le sentiment d'un drama."""
    id: int
    drama_id: int
    ending_type: str  # happy, sad, bittersweet, unknown
    ending_confidence: float
    sentiment_score: float
    sentiment_summary: Optional[str] = None
    is_ongoing: bool
    is_completed: bool
    total_episodes: Optional[int] = None
    scraped_date: Optional[datetime] = None
    last_updated: datetime
    source_urls: Optional[str] = None
    data_quality_score: Optional[float] = None
    top_comments: Optional[str] = None
    notable_triggers: Optional[str] = None
    viewer_consensus: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """Modèle générique pour les réponses paginées."""
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Application FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="API K-Drama — Système de recommandation",
    description=(
        "REST API for the AI-powered K-Drama recommendation system. "
        "Manages K-Dramas, actors, genres, ratings, and users. "
        "GDPR compliant (right to erasure, data portability)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Middleware pour logger tous les requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"\n>>> REQUEST: {request.method} {request.url.path}", flush=True)
    try:
        response = await call_next(request)
        print(f"<<< RESPONSE: {response.status_code}", flush=True)
        return response
    except Exception as e:
        print(f"!!! ERROR: {type(e).__name__}: {e}", flush=True)
        raise



# Dépendance : session de base de données
def get_db():
    """Fournit une session de base de données par requête.

    Yields:
        Session SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", include_in_schema=False, summary="Redirection vers la documentation")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


@app.get("/test-db", summary="Test database connection")
def test_db(db: Session = Depends(get_db)):
    """Simple test to verify database works."""
    try:
        count = db.query(Kdrama).count()
        return {"status": "ok", "kdrama_count": count}
    except Exception as e:
        return {"status": "error", "error": str(e), "type": type(e).__name__}


# ---------------------------------------------------------------------------
# Endpoints d'authentification
# ---------------------------------------------------------------------------
def build_user_response(utilisateur: "Utilisateur", db: Session) -> "UserResponse":
    """Construit un UserResponse enrichi (préférences + statistiques).

    Args:
        utilisateur: Utilisateur authentifié.
        db: Session de base de données.

    Returns:
        UserResponse avec genres/acteurs favoris et compteurs.
    """
    genres_preferes = [
        g.nom
        for g in db.query(Genre)
        .join(UtilisateurGenrePrefere, UtilisateurGenrePrefere.genre_id == Genre.id)
        .filter(UtilisateurGenrePrefere.utilisateur_id == utilisateur.id)
        .order_by(Genre.nom)
        .all()
    ]
    acteurs_preferes = (
        db.query(Acteur)
        .join(UtilisateurActeurPrefere, UtilisateurActeurPrefere.acteur_id == Acteur.id)
        .filter(UtilisateurActeurPrefere.utilisateur_id == utilisateur.id)
        .order_by(Acteur.nom)
        .all()
    )
    nb_dramas_vus = (
        db.query(HistoriqueVisionnage)
        .filter(HistoriqueVisionnage.utilisateur_id == utilisateur.id)
        .count()
    )
    nb_favoris = db.query(Favori).filter(Favori.utilisateur_id == utilisateur.id).count()

    return UserResponse(
        id=utilisateur.id,
        pseudonyme=utilisateur.pseudonyme,
        date_inscription=utilisateur.date_inscription,
        role=utilisateur.role,
        consentement_collecte=utilisateur.consentement_collecte,
        consentement_marketing=utilisateur.consentement_marketing,
        fin_heureuse_uniquement=utilisateur.fin_heureuse_uniquement,
        genres_preferes=genres_preferes,
        acteurs_preferes=acteurs_preferes,
        nb_dramas_vus=nb_dramas_vus,
        nb_favoris=nb_favoris,
    )


@app.post(
    "/api/v1/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
    description="Creates a user account. Email is hashed (SHA-256) and password is hashed (bcrypt) in compliance with GDPR.",
)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Inscrit un nouvel utilisateur.

    Args:
        user_data: Données d'inscription (pseudonyme, email, mot de passe, consentements).
        db: Session de base de données.

    Returns:
        Les informations de l'utilisateur créé (sans données sensibles).

    Raises:
        HTTPException: 400 si le pseudonyme ou l'email est déjà utilisé.
        HTTPException: 400 si le consentement de collecte n'est pas donné.
    """
    # Vérification du consentement RGPD obligatoire
    if not user_data.consentement_collecte:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent to data collection is mandatory (GDPR art. 6.1.a)",
        )

    # Vérification de l'unicité du pseudonyme
    if db.query(Utilisateur).filter(Utilisateur.pseudonyme == user_data.pseudonyme).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This username is already taken",
        )

    # Vérification de l'unicité de l'email (via le hash)
    email_hash = hacher_email(user_data.email)
    if db.query(Utilisateur).filter(Utilisateur.email_hache == email_hash).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already linked to an account",
        )

    # Création de l'utilisateur
    nouvel_utilisateur = Utilisateur(
        pseudonyme=user_data.pseudonyme,
        email_hache=email_hash,
        mot_de_passe_hache=hacher_mot_de_passe(user_data.mot_de_passe),
        consentement_collecte=user_data.consentement_collecte,
        consentement_marketing=user_data.consentement_marketing,
        date_consentement=datetime.utcnow(),
        methode_consentement="formulaire_inscription",
        role="user",
    )
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)

    logger.info("Nouvel utilisateur inscrit: %s (id=%d)", user_data.pseudonyme, nouvel_utilisateur.id)
    return build_user_response(nouvel_utilisateur, db)


@app.post(
    "/api/v1/auth/login",
    response_model=Token,
    summary="Connexion utilisateur",
    description="Authenticates a user and returns a JWT token.",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authentifie un utilisateur et génère un token JWT.

    Args:
        form_data: Formulaire OAuth2 (username = pseudonyme, password).
        db: Session de base de données.

    Returns:
        Token JWT avec type et durée d'expiration.

    Raises:
        HTTPException: 401 si les identifiants sont invalides.
    """
    utilisateur = db.query(Utilisateur).filter(
        Utilisateur.pseudonyme == form_data.username,
        Utilisateur.est_supprime == False,
    ).first()

    if not utilisateur or not verifier_mot_de_passe(
        form_data.password, utilisateur.mot_de_passe_hache
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Mise à jour de la date de dernière activité
    utilisateur.date_derniere_activite = datetime.utcnow()
    db.commit()

    # NOTE: ce token (sub=id utilisateur réel, HS256, JWT_SECRET) est aussi
    # accepté tel quel par le model-api de l'étape 3 (/recommend, /predict),
    # qui partage le même secret — voir dossier_projet/etape3/src/model_api.py.
    token = creer_token_jwt(
        data={"sub": str(utilisateur.id), "role": utilisateur.role}
    )
    logger.info("Connexion réussie: %s (id=%d)", utilisateur.pseudonyme, utilisateur.id)
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRATION_MINUTES * 60,
    )


@app.get(
    "/api/v1/auth/me",
    response_model=UserResponse,
    summary="Profil de l'utilisateur connecté",
    description="Returns the authenticated user's information.",
)
def get_me(
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne le profil de l'utilisateur connecté.

    Args:
        current_user: Utilisateur authentifié (via JWT).
        db: Session de base de données.

    Returns:
        Les informations de l'utilisateur (sans données sensibles), avec
        préférences de recommandation et statistiques.
    """
    return build_user_response(current_user, db)


@app.patch(
    "/api/v1/auth/me/preferences",
    response_model=UserResponse,
    summary="Mise à jour des préférences de recommandation",
    description=(
        "Updates the authenticated user's optional recommendation preferences: "
        "favorite genres (max 3), favorite actors (max 5), and the strict "
        "happy-ending-only flag. All fields are optional; omit a field to "
        "leave it unchanged."
    ),
)
def update_my_preferences(
    prefs: PreferencesUpdate,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour les préférences de recommandation de l'utilisateur connecté.

    Args:
        prefs: Genres favoris (noms, max 3), acteurs favoris (ids, max 5) et/ou
            préférence de fin heureuse. Tous les champs sont optionnels.
        current_user: Utilisateur authentifié.
        db: Session de base de données.

    Returns:
        Le profil utilisateur mis à jour.

    Raises:
        HTTPException: 400 si un genre ou un acteur indiqué n'existe pas.
    """
    if prefs.fin_heureuse_uniquement is not None:
        current_user.fin_heureuse_uniquement = prefs.fin_heureuse_uniquement

    if prefs.genres is not None:
        genres_trouves = (
            db.query(Genre).filter(Genre.nom.in_(prefs.genres)).all() if prefs.genres else []
        )
        if len(genres_trouves) != len(set(prefs.genres)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more selected genres do not exist",
            )
        db.query(UtilisateurGenrePrefere).filter(
            UtilisateurGenrePrefere.utilisateur_id == current_user.id
        ).delete()
        for genre in genres_trouves:
            db.add(UtilisateurGenrePrefere(utilisateur_id=current_user.id, genre_id=genre.id))

    if prefs.acteur_ids is not None:
        acteurs_trouves = (
            db.query(Acteur).filter(Acteur.id.in_(prefs.acteur_ids)).all()
            if prefs.acteur_ids
            else []
        )
        if len(acteurs_trouves) != len(set(prefs.acteur_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more selected actors do not exist",
            )
        db.query(UtilisateurActeurPrefere).filter(
            UtilisateurActeurPrefere.utilisateur_id == current_user.id
        ).delete()
        for acteur in acteurs_trouves:
            db.add(UtilisateurActeurPrefere(utilisateur_id=current_user.id, acteur_id=acteur.id))

    db.commit()
    logger.info("Préférences mises à jour pour l'utilisateur id=%d", current_user.id)
    return build_user_response(current_user, db)


@app.delete(
    "/api/v1/auth/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Droit à l'effacement (RGPD art. 17)",
    description="Anonymizes and deletes the authenticated user's account.",
)
def delete_me(
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Implémente le droit à l'effacement (RGPD art. 17).

    Anonymise le compte au lieu de le supprimer physiquement pour
    préserver l'intégrité référentielle des notes et avis existants, et
    supprime toutes les données personnelles liées aux préférences de
    recommandation (historique, favoris, intérêts, genres/acteurs favoris).

    Args:
        current_user: Utilisateur authentifié.
        db: Session de base de données.
    """
    current_user.pseudonyme = f"utilisateur_supprime_{current_user.id}"
    current_user.email_hache = f"ANONYMIZED_{current_user.id}"
    current_user.mot_de_passe_hache = "ANONYMIZED"
    current_user.consentement_collecte = False
    current_user.consentement_marketing = False
    current_user.date_consentement = None
    current_user.fin_heureuse_uniquement = False
    current_user.est_supprime = True

    db.query(HistoriqueVisionnage).filter(
        HistoriqueVisionnage.utilisateur_id == current_user.id
    ).delete()
    db.query(Favori).filter(Favori.utilisateur_id == current_user.id).delete()
    db.query(InteretUtilisateur).filter(
        InteretUtilisateur.utilisateur_id == current_user.id
    ).delete()
    db.query(UtilisateurGenrePrefere).filter(
        UtilisateurGenrePrefere.utilisateur_id == current_user.id
    ).delete()
    db.query(UtilisateurActeurPrefere).filter(
        UtilisateurActeurPrefere.utilisateur_id == current_user.id
    ).delete()

    db.commit()
    logger.info("Compte anonymisé (RGPD art. 17): id=%d", current_user.id)


@app.get(
    "/api/v1/auth/me/export",
    summary="Portabilité des données (RGPD art. 20)",
    description="Exports all user data in JSON format.",
)
def export_my_data(
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exporte les données de l'utilisateur (RGPD art. 20 — portabilité).

    Args:
        current_user: Utilisateur authentifié.
        db: Session de base de données.

    Returns:
        Dictionnaire JSON contenant toutes les données de l'utilisateur,
        y compris les préférences de recommandation (genres/acteurs
        favoris, fin heureuse), les favoris, l'historique de visionnage
        et les retours d'intérêt.
    """
    notes = db.query(Note).filter(Note.utilisateur_id == current_user.id).all()
    historique = (
        db.query(HistoriqueVisionnage)
        .filter(HistoriqueVisionnage.utilisateur_id == current_user.id)
        .all()
    )
    favoris = db.query(Favori).filter(Favori.utilisateur_id == current_user.id).all()
    interets = (
        db.query(InteretUtilisateur)
        .filter(InteretUtilisateur.utilisateur_id == current_user.id)
        .all()
    )
    profil = build_user_response(current_user, db)
    return {
        "utilisateur": {
            "id": current_user.id,
            "pseudonyme": current_user.pseudonyme,
            "date_inscription": current_user.date_inscription.isoformat(),
            "role": current_user.role,
            "consentement_collecte": current_user.consentement_collecte,
            "consentement_marketing": current_user.consentement_marketing,
            "fin_heureuse_uniquement": current_user.fin_heureuse_uniquement,
            "genres_preferes": profil.genres_preferes,
            "acteurs_preferes": [a.nom for a in profil.acteurs_preferes],
        },
        "notes": [
            {
                "id": n.id,
                "kdrama_id": n.kdrama_id,
                "note": n.note,
                "commentaire": n.commentaire,
                "date_note": n.date_note.isoformat(),
            }
            for n in notes
        ],
        "historique_visionnage": [
            {
                "id": h.id,
                "kdrama_id": h.kdrama_id,
                "episodes_vus": h.episodes_vus,
                "statut": h.statut,
                "date_creation": h.date_creation.isoformat(),
            }
            for h in historique
        ],
        "favoris": [
            {"id": f.id, "kdrama_id": f.kdrama_id, "date_ajout": f.date_ajout.isoformat()}
            for f in favoris
        ],
        "interets": [
            {
                "id": i.id,
                "kdrama_id": i.kdrama_id,
                "interesse": i.interesse,
                "date_creation": i.date_creation.isoformat(),
            }
            for i in interets
        ],
        "export_date": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoints CRUD — K-Dramas
# ---------------------------------------------------------------------------
@app.get("/api/v1/test-simple")
def test_simple():
    """Simple test without database."""
    logger.info("test_simple endpoint called")
    return {"status": "ok", "message": "Simple test works"}


@app.get("/api/v1/kdramas-simple")
def list_kdramas_simple(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Test kdramas endpoint with database."""
    logger.info(f"list_kdramas_simple called")

    try:
        logger.info("Querying kdramas from database")
        kdramas = db.query(Kdrama).limit(page_size).all()
        logger.info(f"Got {len(kdramas)} kdramas")

        return {
            "items": [{"id": k.id, "titre": k.titre, "poster": k.poster} for k in kdramas],
            "total": len(kdramas),
        }
    except Exception as e:
        logger.error(f"ERROR: {type(e).__name__}: {e}", exc_info=True)
        raise




@app.get(
    "/api/v1/kdramas",
    summary="Liste paginée des K-Dramas",
    description="Returns a paginated, sortable list of K-Dramas with optional search.",
)
def list_kdramas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by title"),
    genre: Optional[str] = Query(None, description="Filter by genre(s), comma-separated for multiple"),
    sort_by: str = Query("note_moyenne", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
):
    print(f"\n=== list_kdramas START: page={page}, page_size={page_size}, genre={genre} ===")
    try:
        print("1. Creating query")
        query = db.query(Kdrama)
        print("2. Query created")

        if search:
            print(f"3. Applying search: {search}")
            query = query.filter(
                (Kdrama.titre.ilike(f"%{search}%"))
                | (Kdrama.titre_original.ilike(f"%{search}%"))
            )

        if genre:
            # Supports one or several comma-separated genres (OR match against any of them).
            # Genres field contains messy strings like: ["Comedy", "Drama"] or "Comedy, Drama"
            genre_list = [g.strip() for g in genre.split(",") if g.strip()]
            print(f"4. Applying genre filter: {genre_list}")
            if genre_list:
                query = query.filter(
                    or_(*[Kdrama.genres.ilike(f"%{g}%") for g in genre_list])
                )
            print(f"   Genre filter: genres ILIKE ANY of {genre_list}")
            test_count = query.count()
            print(f"   Results after genre filter: {test_count}")

        print(f"5. Applying sort: {sort_by} {sort_order}")
        sort_column = getattr(Kdrama, sort_by, Kdrama.note_moyenne)
        if sort_order == "desc":
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)

        print("6. Counting total")
        total = query.count()
        print(f"7. Total: {total}")

        offset = (page - 1) * page_size
        print(f"8. Fetching offset={offset}, limit={page_size}")
        kdramas = query.offset(offset).limit(page_size).all()
        print(f"9. Fetched {len(kdramas)} rows")

        print("10. Building items list")
        items = []
        for i, k in enumerate(kdramas):
            print(f"  - Item {i}: id={k.id}, titre={k.titre[:30] if k.titre else 'None'}")
            items.append({
                "id": k.id,
                "titre": k.titre,
                "poster": k.poster,
                "genres": k.genres,
                "note_moyenne": float(k.note_moyenne) if k.note_moyenne else 0,
                "nb_episodes": k.nb_episodes or 0,
                "annee_diffusion": k.annee_diffusion or 0,
                "synopsis": k.synopsis or "",
            })

        print(f"11. Built {len(items)} items")
        result = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
        print(f"12. Returning result\n=== list_kdramas SUCCESS ===\n")
        return result

    except Exception as e:
        print(f"\n!!! ERROR: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        print("!!! END ERROR\n")
        raise HTTPException(
            status_code=500,
            detail=f"Error: {type(e).__name__}: {str(e)}"
        )


@app.get(
    "/api/v1/kdramas/genres",
    summary="Genres from K-Dramas catalog",
    description="Returns unique genres extracted from the kdramas table (source of truth)",
)
def list_kdrama_genres(db: Session = Depends(get_db)):
    """Returns unique genres from the kdramas table.

    This endpoint queries the actual K-Drama genres field and extracts unique values,
    providing the authoritative list of genres available in the catalog.

    Args:
        db: Session de base de données.

    Returns:
        List of unique genres from kdramas table.
    """
    from sqlalchemy import text

    try:
        result = db.execute(
            text("""
                SELECT DISTINCT
                  TRIM(regexp_replace(
                    TRIM(unnest(string_to_array(genres, ','))),
                    '["\[\]\\\\]', '', 'g'
                  )) AS genre
                FROM kdrama.kdramas
                WHERE genres IS NOT NULL AND genres != ''
                ORDER BY genre
            """)
        )
        genres = [row[0] for row in result.fetchall() if row[0] and row[0].strip()]
        return genres
    except Exception as e:
        logger.error("Error fetching kdrama genres: %s", e)
        return []


@app.get(
    "/api/v1/kdramas/{kdrama_id}",
    response_model=KdramaResponse,
    summary="Détails d'un K-Drama",
    description="Returns detailed information for a K-Drama by ID.",
)
def get_kdrama(kdrama_id: int, db: Session = Depends(get_db)):
    """Retourne les détails d'un K-Drama spécifique.

    Args:
        kdrama_id: Identifiant unique du K-Drama.
        db: Session de base de données.

    Returns:
        Le K-Drama correspondant.

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
    """
    kdrama = db.query(Kdrama).filter(Kdrama.id == kdrama_id).first()
    if not kdrama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )
    return kdrama


@app.post(
    "/api/v1/kdramas",
    response_model=KdramaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Création d'un K-Drama (admin)",
    description="Creates a new K-Drama. Admin only.",
)
def create_kdrama(
    kdrama_data: KdramaCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_admin),
):
    """Crée un nouveau K-Drama (réservé aux admins).

    Args:
        kdrama_data: Données du K-Drama à créer.
        db: Session de base de données.
        current_user: Utilisateur admin authentifié.

    Returns:
        Le K-Drama créé.
    """
    nouveau_kdrama = Kdrama(**kdrama_data.model_dump())
    db.add(nouveau_kdrama)
    db.commit()
    db.refresh(nouveau_kdrama)
    logger.info("K-Drama créé: %s (id=%d) par %s", nouveau_kdrama.titre, nouveau_kdrama.id, current_user.pseudonyme)
    return nouveau_kdrama


@app.put(
    "/api/v1/kdramas/{kdrama_id}",
    response_model=KdramaResponse,
    summary="Modification d'un K-Drama (admin)",
    description="Updates a K-Drama's information. Admin only.",
)
def update_kdrama(
    kdrama_id: int,
    kdrama_data: KdramaUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_admin),
):
    """Met à jour un K-Drama existant (réservé aux admins).

    Args:
        kdrama_id: Identifiant du K-Drama à modifier.
        kdrama_data: Données de mise à jour (partielle).
        db: Session de base de données.
        current_user: Utilisateur admin authentifié.

    Returns:
        Le K-Drama mis à jour.

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
    """
    kdrama = db.query(Kdrama).filter(Kdrama.id == kdrama_id).first()
    if not kdrama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )

    # Mise à jour des champs fournis uniquement
    update_data = kdrama_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kdrama, field, value)

    db.commit()
    db.refresh(kdrama)
    logger.info("K-Drama modifié: id=%d par %s", kdrama_id, current_user.pseudonyme)
    return kdrama


@app.delete(
    "/api/v1/kdramas/{kdrama_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Suppression d'un K-Drama (admin)",
    description="Deletes a K-Drama. Admin only.",
)
def delete_kdrama(
    kdrama_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_admin),
):
    """Supprime un K-Drama (réservé aux admins).

    Args:
        kdrama_id: Identifiant du K-Drama à supprimer.
        db: Session de base de données.
        current_user: Utilisateur admin authentifié.

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
    """
    kdrama = db.query(Kdrama).filter(Kdrama.id == kdrama_id).first()
    if not kdrama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )
    db.delete(kdrama)
    db.commit()
    logger.info("K-Drama supprimé: id=%d par %s", kdrama_id, current_user.pseudonyme)


# ---------------------------------------------------------------------------
# Endpoints — Acteurs
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/acteurs",
    response_model=PaginatedResponse,
    summary="Liste paginée des acteurs",
)
def list_acteurs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retourne la liste paginée des acteurs.

    Args:
        page: Numéro de page.
        page_size: Taille de page.
        search: Recherche par nom.
        db: Session de base de données.

    Returns:
        Réponse paginée des acteurs.
    """
    query = db.query(Acteur)
    if search:
        query = query.filter(
            (Acteur.nom.ilike(f"%{search}%"))
            | (Acteur.nom_original.ilike(f"%{search}%"))
        )
    total = query.count()
    offset = (page - 1) * page_size
    acteurs = query.order_by(Acteur.nom).offset(offset).limit(page_size).all()
    return {
        "items": acteurs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@app.get(
    "/api/v1/acteurs/{acteur_id}",
    response_model=ActeurResponse,
    summary="Détails d'un acteur",
)
def get_acteur(acteur_id: int, db: Session = Depends(get_db)):
    """Retourne les détails d'un acteur.

    Args:
        acteur_id: Identifiant de l'acteur.
        db: Session de base de données.

    Returns:
        L'acteur correspondant.

    Raises:
        HTTPException: 404 si l'acteur n'existe pas.
    """
    acteur = db.query(Acteur).filter(Acteur.id == acteur_id).first()
    if not acteur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Actor with ID {acteur_id} not found",
        )
    return acteur


# ---------------------------------------------------------------------------
# Endpoints — Genres
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/genres",
    response_model=list[GenreResponse],
    summary="Liste des genres",
)
def list_genres(db: Session = Depends(get_db)):
    """Retourne la liste de tous les genres.

    Args:
        db: Session de base de données.

    Returns:
        Liste des genres.
    """
    return db.query(Genre).order_by(Genre.nom).all()


# ---------------------------------------------------------------------------
# Endpoints — Notes
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/kdramas/{kdrama_id}/notes",
    response_model=PaginatedResponse,
    summary="Notes d'un K-Drama",
)
def list_notes_kdrama(
    kdrama_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retourne les notes d'un K-Drama spécifique.

    Args:
        kdrama_id: Identifiant du K-Drama.
        page: Numéro de page.
        page_size: Taille de page.
        db: Session de base de données.

    Returns:
        Réponse paginée des notes du K-Drama.
    """
    query = db.query(Note).filter(Note.kdrama_id == kdrama_id)
    total = query.count()
    offset = (page - 1) * page_size
    notes = query.order_by(Note.date_note.desc()).offset(offset).limit(page_size).all()
    return {
        "items": notes,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@app.post(
    "/api/v1/kdramas/{kdrama_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une note à un K-Drama",
    description="The authenticated user rates a K-Drama (1-10).",
)
def create_note(
    kdrama_id: int,
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Permet à un utilisateur authentifié de noter un K-Drama.

    Args:
        kdrama_id: Identifiant du K-Drama à noter.
        note_data: Données de la note (note 1-10, commentaire optionnel).
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        La note créée.

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
        HTTPException: 400 si l'utilisateur a déjà noté ce K-Drama.
    """
    # Vérification de l'existence du K-Drama
    kdrama = db.query(Kdrama).filter(Kdrama.id == kdrama_id).first()
    if not kdrama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )

    # Vérification : l'utilisateur n'a pas déjà noté ce K-Drama
    note_existante = db.query(Note).filter(
        Note.utilisateur_id == current_user.id,
        Note.kdrama_id == kdrama_id,
    ).first()
    if note_existante:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already rated this K-Drama. Use PUT to update your rating.",
        )

    nouvelle_note = Note(
        utilisateur_id=current_user.id,
        kdrama_id=kdrama_id,
        note=note_data.note,
        commentaire=note_data.commentaire,
    )
    db.add(nouvelle_note)
    db.commit()
    db.refresh(nouvelle_note)
    logger.info("Note créée: kdrama=%d, user=%d, note=%d", kdrama_id, current_user.id, note_data.note)
    return nouvelle_note


# ---------------------------------------------------------------------------
# Endpoints — Favoris (bookmarks, distincts des notes)
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/favoris",
    response_model=list[FavoriResponse],
    summary="Liste des favoris de l'utilisateur connecté",
)
def list_my_favoris(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Retourne la liste des favoris de l'utilisateur connecté.

    Args:
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        Liste des favoris, du plus récent au plus ancien.
    """
    return (
        db.query(Favori)
        .filter(Favori.utilisateur_id == current_user.id)
        .order_by(Favori.date_ajout.desc())
        .all()
    )


@app.post(
    "/api/v1/favoris/{kdrama_id}",
    response_model=FavoriResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un K-Drama aux favoris",
)
def add_favori(
    kdrama_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Ajoute un K-Drama aux favoris de l'utilisateur connecté (idempotent).

    Args:
        kdrama_id: Identifiant du K-Drama à ajouter.
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        Le favori créé (ou existant si déjà présent).

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
    """
    if not db.query(Kdrama).filter(Kdrama.id == kdrama_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )

    existant = db.query(Favori).filter(
        Favori.utilisateur_id == current_user.id,
        Favori.kdrama_id == kdrama_id,
    ).first()
    if existant:
        return existant

    favori = Favori(utilisateur_id=current_user.id, kdrama_id=kdrama_id)
    db.add(favori)
    db.commit()
    db.refresh(favori)
    logger.info("Favori ajouté: kdrama=%d, user=%d", kdrama_id, current_user.id)
    return favori


@app.delete(
    "/api/v1/favoris/{kdrama_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un K-Drama des favoris",
)
def remove_favori(
    kdrama_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Retire un K-Drama des favoris de l'utilisateur connecté.

    Args:
        kdrama_id: Identifiant du K-Drama à retirer.
        db: Session de base de données.
        current_user: Utilisateur authentifié.
    """
    db.query(Favori).filter(
        Favori.utilisateur_id == current_user.id,
        Favori.kdrama_id == kdrama_id,
    ).delete()
    db.commit()
    logger.info("Favori retiré: kdrama=%d, user=%d", kdrama_id, current_user.id)


# ---------------------------------------------------------------------------
# Endpoints — Historique de visionnage
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/historique",
    response_model=list[HistoriqueVisionnageResponse],
    summary="Historique de visionnage de l'utilisateur connecté",
)
def list_my_historique(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Retourne l'historique de visionnage de l'utilisateur connecté.

    Args:
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        Liste des entrées d'historique, de la plus récente à la plus ancienne.
    """
    return (
        db.query(HistoriqueVisionnage)
        .filter(HistoriqueVisionnage.utilisateur_id == current_user.id)
        .order_by(HistoriqueVisionnage.date_modification.desc())
        .all()
    )


@app.put(
    "/api/v1/historique/{kdrama_id}",
    response_model=HistoriqueVisionnageResponse,
    summary="Créer/mettre à jour une entrée d'historique de visionnage",
)
def upsert_historique(
    kdrama_id: int,
    payload: HistoriqueVisionnageUpsert,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Crée ou met à jour le statut de visionnage d'un K-Drama.

    Args:
        kdrama_id: Identifiant du K-Drama.
        payload: Statut et nombre d'épisodes vus.
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        L'entrée d'historique créée ou mise à jour.

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
    """
    if not db.query(Kdrama).filter(Kdrama.id == kdrama_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )

    entree = db.query(HistoriqueVisionnage).filter(
        HistoriqueVisionnage.utilisateur_id == current_user.id,
        HistoriqueVisionnage.kdrama_id == kdrama_id,
    ).first()

    if entree is None:
        entree = HistoriqueVisionnage(
            utilisateur_id=current_user.id,
            kdrama_id=kdrama_id,
            episodes_vus=payload.episodes_vus,
            statut=payload.statut,
            date_debut=datetime.utcnow(),
        )
        db.add(entree)
    else:
        entree.episodes_vus = payload.episodes_vus
        entree.statut = payload.statut
        if payload.statut == "termine" and entree.date_fin is None:
            entree.date_fin = datetime.utcnow()

    db.commit()
    db.refresh(entree)
    logger.info(
        "Historique mis à jour: kdrama=%d, user=%d, statut=%s",
        kdrama_id, current_user.id, payload.statut,
    )
    return entree


# ---------------------------------------------------------------------------
# Endpoints — Intérêt utilisateur ("want to watch" / "not interested")
# ---------------------------------------------------------------------------
@app.put(
    "/api/v1/kdramas/{kdrama_id}/interet",
    response_model=InteretResponse,
    summary="Signaler l'intérêt pour un K-Drama",
    description=(
        "Records whether the authenticated user wants to watch (interesse=true) "
        "or is not interested (interesse=false) in a K-Drama. Used both for the "
        "user's own experience and as feedback/training signal for the "
        "recommendation model (etape 3)."
    ),
)
def set_interet(
    kdrama_id: int,
    payload: InteretUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Crée ou met à jour le retour d'intérêt d'un utilisateur pour un drama.

    Args:
        kdrama_id: Identifiant du K-Drama.
        payload: Intérêt (True = veut regarder, False = pas intéressé).
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        Le retour d'intérêt créé ou mis à jour.

    Raises:
        HTTPException: 404 si le K-Drama n'existe pas.
    """
    if not db.query(Kdrama).filter(Kdrama.id == kdrama_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )

    entree = db.query(InteretUtilisateur).filter(
        InteretUtilisateur.utilisateur_id == current_user.id,
        InteretUtilisateur.kdrama_id == kdrama_id,
    ).first()

    if entree is None:
        entree = InteretUtilisateur(
            utilisateur_id=current_user.id,
            kdrama_id=kdrama_id,
            interesse=payload.interesse,
        )
        db.add(entree)
    else:
        entree.interesse = payload.interesse

    db.commit()
    db.refresh(entree)
    logger.info(
        "Intérêt enregistré: kdrama=%d, user=%d, interesse=%s",
        kdrama_id, current_user.id, payload.interesse,
    )
    return entree


@app.get(
    "/api/v1/kdramas/{kdrama_id}/interet",
    response_model=Optional[InteretResponse],
    summary="Récupérer l'intérêt de l'utilisateur pour un K-Drama",
)
def get_interet(
    kdrama_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Retourne le retour d'intérêt existant de l'utilisateur pour un drama, s'il existe.

    Args:
        kdrama_id: Identifiant du K-Drama.
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        Le retour d'intérêt existant, ou None.
    """
    return db.query(InteretUtilisateur).filter(
        InteretUtilisateur.utilisateur_id == current_user.id,
        InteretUtilisateur.kdrama_id == kdrama_id,
    ).first()


# ---------------------------------------------------------------------------
# Sentiment Endpoints (Drama Ending Sentiment Analysis)
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/kdramas/{kdrama_id}/sentiment",
    response_model=DramaSentimentResponse,
    summary="Get drama sentiment/ending classification",
    description="Returns sentiment data and ending type for a specific drama.",
)
def get_drama_sentiment(kdrama_id: int, db: Session = Depends(get_db)):
    """Retourne le sentiment et le type d'ending pour un K-Drama.

    Args:
        kdrama_id: Identifiant unique du K-Drama.
        db: Session de base de données.

    Returns:
        Sentiment data with ending_type (happy/sad/bittersweet/unknown).

    Raises:
        HTTPException: 404 if drama or sentiment not found.
    """
    # Check drama exists
    kdrama = db.query(Kdrama).filter(Kdrama.id == kdrama_id).first()
    if not kdrama:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"K-Drama with ID {kdrama_id} not found",
        )

    # Try to get sentiment
    try:
        sentiment = db.query(DramaSentiment).filter(
            DramaSentiment.drama_id == kdrama_id
        ).first()

        if not sentiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No sentiment data available for drama {kdrama_id}",
            )

        return sentiment
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching sentiment for kdrama %d: %s", kdrama_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch sentiment data",
        )


@app.get(
    "/api/v1/sentiments",
    summary="List all drama sentiments",
    description="Returns sentiment data for all dramas with optional filtering by ending_type.",
)
def list_sentiments(
    ending_type: Optional[str] = Query(None, description="Filter by ending type: happy, sad, bittersweet, unknown"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of items to return"),
    db: Session = Depends(get_db),
):
    """Liste les sentiments des dramas avec filtrage optionnel.

    Args:
        ending_type: Filter by ending type (happy/sad/bittersweet/unknown).
        skip: Nombre de résultats à ignorer (pagination).
        limit: Nombre de résultats à retourner (max 500).
        db: Session de base de données.

    Returns:
        Liste des sentiments avec métadonnées.
    """
    query = db.query(DramaSentiment)

    if ending_type:
        valid_endings = ["happy", "sad", "bittersweet", "unknown"]
        if ending_type.lower() not in valid_endings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid ending_type. Must be one of: {', '.join(valid_endings)}",
            )
        query = query.filter(DramaSentiment.ending_type == ending_type.lower())

    total = query.count()
    sentiments = query.offset(skip).limit(min(limit, 500)).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": sentiments,
    }


# ---------------------------------------------------------------------------
# Endpoint de santé (health check)
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    summary="Vérification de l'état de l'API",
    description="Health check endpoint for monitoring.",
)
def health_check():
    """Vérifie l'état de l'API et de la base de données.

    Returns:
        Dictionnaire avec le statut de l'API et la version.
    """
    try:
        # Test de connexion à la base
        db = SessionLocal()
        db.execute(select(1))
        db.close()
        db_status = "ok"
    except Exception as e:
        logger.error("Échec du health check DB: %s", e)
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
