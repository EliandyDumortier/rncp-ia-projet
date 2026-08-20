# ============================================================
# API REST exposant le modèle de recommandation de K-Dramas
# Fichier : model_api.py
#
# Framework : FastAPI
# Sécurité : JWT (JSON Web Tokens), rate limiting, validation Pydantic
# Monitoring : Prometheus (via model_monitoring.py)
#
# Endpoints :
#   GET  /health          — Santé de l'API et du modèle
#   GET  /metrics         — Métriques Prometheus
#   POST /auth/token      — Obtention d'un token JWT
#   POST /recommend       — Recommandations personnalisées
#   POST /predict         — Prédiction de note
#   GET  /model/info      — Informations sur le modèle
#   GET  /alerts          — Alertes actives du monitoring
#
# Auteur : Équipe MLOps
# Étape 3 — RNCP AI Project
# ============================================================

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Importation des modules internes
from model_monitoring import get_monitor, get_alert_rules
from recommendation_model import (
    DEFAULT_MODEL_DIR,
    HybridRecommender,
    RecommendationResult,
    load_real_data,
)

# ============================================================
# Configuration du logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# Configuration (variables d'environnement)
# ============================================================

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _env_path in (
    Path.cwd() / ".env",
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape3" / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape1" / ".env",
):
    load_dotenv(_env_path, override=False)


def _get_required_env(var_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {var_name}. "
            "Configure it in dossier_projet/etape3/.env or the shell environment."
        )
    return value


JWT_SECRET_KEY = _get_required_env("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "24"))

API_RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "100/minute")
MODEL_RATE_LIMIT = os.environ.get("MODEL_RATE_LIMIT", "30/minute")

ADMIN_PASSWORD = _get_required_env("ADMIN_PASSWORD")
USER_PASSWORD = _get_required_env("USER_PASSWORD")

# Demo users (production should use a database-backed user store)
DEMO_USERS = {
    "admin": {
        "password": ADMIN_PASSWORD,
        "role": "admin",
    },
    "user": {
        "password": USER_PASSWORD,
        "role": "user",
    },
}

# ============================================================
# Initialisation du rate limiter
# ============================================================

limiter = Limiter(key_func=get_remote_address)
bearer_scheme = HTTPBearer(auto_error=False)

# ============================================================
# Modèles Pydantic (validation des entrées/sorties)
# ============================================================

class TokenRequest(BaseModel):
    """Modèle de requête pour l'authentification."""
    username: str = Field(..., min_length=1, max_length=50, description="Username")
    password: str = Field(..., min_length=1, max_length=200, description="Password")


class TokenResponse(BaseModel):
    """Modèle de réponse contenant le token JWT."""
    access_token: str = Field(..., description="JWT token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Validity duration in seconds")


class RecommendRequest(BaseModel):
    """
    Modèle de requête pour les recommandations.

    Deux modes :
      - user_id fourni : recommandations personnalisées pour l'utilisateur.
      - drama_id fourni : dramas similaires au drama spécifié.
    """
    user_id: int | None = Field(
        default=None,
        ge=1,
        le=1000000,
        description="User ID (optional)",
    )
    drama_id: int | None = Field(
        default=None,
        ge=1,
        le=1000000,
        description="Reference drama ID (optional)",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of recommendations to return (1-50)",
    )

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Valide que top_k est dans une plage raisonnable."""
        if v < 1 or v > 50:
            raise ValueError("top_k must be between 1 and 50")
        return v

    def get_mode(self) -> str:
        """Retourne le mode de recommandation."""
        if self.user_id is not None:
            return "user"
        return "item"


class RecommendResponse(BaseModel):
    """Modèle de réponse pour les recommandations."""
    success: bool = Field(..., description="Request status")
    mode: str = Field(..., description="Recommendation mode (user/item)")
    count: int = Field(..., description="Number of results")
    recommendations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of recommendations",
    )
    request_id: str = Field(..., description="Unique request identifier")
    latency_ms: float = Field(..., description="Latency in milliseconds")


class PredictRequest(BaseModel):
    """Modèle de requête pour la prédiction de note."""
    user_id: int = Field(..., ge=1, le=1000000, description="User ID")
    drama_id: int = Field(..., ge=1, le=1000000, description="Drama ID")


class PredictResponse(BaseModel):
    """Modèle de réponse pour la prédiction de note."""
    success: bool = Field(..., description="Request status")
    user_id: int = Field(..., description="User ID")
    drama_id: int = Field(..., description="Drama ID")
    predicted_rating: float = Field(..., description="Predicted rating (0-10)")
    confidence: str = Field(..., description="Confidence level")
    latency_ms: float = Field(..., description="Latency in milliseconds")


class HealthResponse(BaseModel):
    """Modèle de réponse pour le health check."""
    model_config = ConfigDict(protected_namespaces=())

    status: str = Field(..., description="Overall status")
    model_loaded: bool = Field(..., description="Model loaded")
    model_trained: bool = Field(..., description="Model trained")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="ISO timestamp")


# ============================================================
# Gestionnaire de modèle (singleton)
# ============================================================

class ModelManager:
    """
    Gestionnaire du cycle de vie du modèle de recommandation.

    Responsabilités :
      - Charger le modèle depuis le disque ou l'entraîner à la volée.
      - Gérer les erreurs de chargement.
      - Fournir un accès thread-safe au modèle.
    """

    def __init__(self) -> None:
        self.model: HybridRecommender | None = None
        self._load_attempted = False

    def load_or_train(self) -> HybridRecommender:
        """
        Tente de charger le modèle depuis le disque. Si aucun modèle
        n'est trouvé, entraîne un modèle de démonstration.

        Returns:
            Instance HybridRecommender prête pour l'inférence.
        """
        if self.model is not None:
            return self.model

        if self._load_attempted:
            # Évite de retenter le chargement à chaque requête
            raise RuntimeError("The model could not be loaded.")

        self._load_attempted = True

        # Tentative de chargement depuis le disque
        try:
            model_path = DEFAULT_MODEL_DIR / "model.joblib"
            if model_path.exists():
                logger.info("Chargement du modèle depuis %s", model_path)
                self.model = HybridRecommender.load()
                logger.info("Modèle chargé avec succès.")
            else:
                logger.info(
                    "Aucun modèle trouvé. Entraînement d'un modèle de démonstration..."
                )
                self._train_demo_model()
        except Exception as e:
            logger.error("Erreur lors du chargement du modèle : %s", e)
            # Fallback : entraînement d'un modèle de démo
            try:
                self._train_demo_model()
            except Exception as train_err:
                logger.error(
                    "Échec de l'entraînement de fallback : %s", train_err
                )
                raise

        # Mise à jour du monitoring
        monitor = get_monitor()
        monitor.set_model_status(self.model is not None)
        if self.model is not None:
            info = self.model.get_model_info()
            monitor.set_model_info(
                model_type=info["model_type"],
                alpha=info["alpha"],
                embedding_model=info["embedding_model"],
                num_dramas=info["metrics"]["num_dramas"] if info["metrics"] else 0,
            )

        return self.model  # type: ignore[return-value]

    def _train_demo_model(self) -> None:
        """Entraîne un modèle avec les données réelles de l'étape 1."""
        logger.info("Chargement des données réelles depuis l'étape 1...")
        dramas_df, interactions_df = load_real_data(num_users=50)
        self.model = HybridRecommender(alpha=0.6)
        self.model.train(dramas_df, interactions_df)
        logger.info(
            "Modèle entraîné avec succès sur %d dramas réels et %d interactions.",
            len(dramas_df),
            len(interactions_df),
        )

    def get_model(self) -> HybridRecommender:
        """
        Retourne le modèle chargé ou lève une exception.

        Returns:
            Instance HybridRecommender.

        Raises:
            HTTPException: Si le modèle n'est pas disponible.
        """
        if self.model is None:
            try:
                self.load_or_train()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Model unavailable: {e}",
                )
        assert self.model is not None
        return self.model


# Instance globale
model_manager = ModelManager()


# ============================================================
# Authentification JWT
# ============================================================

def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crée un token JWT signé.

    Args:
        data: Données à encoder dans le token (sub, role, etc.).
        expires_delta: Durée de validité du token.

    Returns:
        Token JWT encodé en chaîne.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """
    Vérifie et décode un token JWT.

    Args:
        token: Token JWT à vérifier.

    Returns:
        Payload décodé du token.

    Raises:
        HTTPException: Si le token est invalide ou expiré.
    """
    try:
        payload = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, Any]:
    """
    FastAPI dependency: extract and verify JWT token from Authorization header.

    Args:
        credentials: Parsed HTTP authorization credentials.

    Returns:
        Decoded JWT payload.

    Raises:
        HTTPException: If token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    return verify_token(token)


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """
    Dépendance FastAPI : vérifie que l'utilisateur a le rôle admin.

    Args:
        user: Payload JWT décodé.

    Returns:
        Payload de l'utilisateur admin.

    Raises:
        HTTPException: Si l'utilisateur n'est pas admin.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required.",
        )
    return user


# ============================================================
# Application FastAPI
# ============================================================

OPENAPI_TAGS = [
    {"name": "Monitoring", "description": "Service health, metrics, and alerts."},
    {"name": "Authentication", "description": "JWT token generation."},
    {"name": "Recommendation", "description": "Recommendation and prediction endpoints."},
    {"name": "Model", "description": "Model metadata and runtime information."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("=== Starting K-Drama Recommender API ===")
    try:
        model_manager.load_or_train()
        logger.info("Model preloaded successfully.")
    except Exception as e:
        logger.warning(
            "Model could not be preloaded at startup: %s. "
            "It will be loaded on first request.",
            e,
        )
    yield
    logger.info("=== Stopping K-Drama Recommender API ===")


app = FastAPI(
    title="K-Drama Recommender API",
    description=(
        "REST API exposing a hybrid K-Drama recommendation model. "
        "The model combines content-based filtering (sentence-transformers) "
        "and collaborative filtering (scikit-learn NearestNeighbors)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    contact={
        "name": "MLOps Team",
        "email": "mlops@kdrama-recommender.io",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Configuration du rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration CORS (sécurité OWASP : origines restreintes en production)
allowed_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ============================================================
# Middleware : logging et monitoring
# ============================================================

@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """
    Middleware de monitoring : enregistre la latence, le statut,
    et met à jour les métriques Prometheus pour chaque requête.
    """
    start_time = time.time()
    endpoint = request.url.path
    method = request.method

    try:
        response = await call_next(request)
    except Exception as e:
        latency = time.time() - start_time
        monitor = get_monitor()
        monitor.record_request(
            endpoint=endpoint,
            method=method,
            status=500,
            latency=latency,
        )
        logger.error("Erreur non gérée sur %s %s : %s", method, endpoint, e)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    latency = time.time() - start_time
    monitor = get_monitor()
    monitor.record_request(
        endpoint=endpoint,
        method=method,
        status=response.status_code,
        latency=latency,
    )

    # Ajout de headers de sécurité (OWASP)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if endpoint.startswith("/docs") or endpoint.startswith("/redoc"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net https://unpkg.com"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Request-ID"] = f"req-{int(start_time * 1000)}"

    return response


# ============================================================
# Endpoints
# ============================================================

@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
@limiter.limit(API_RATE_LIMIT)
async def health_check(request: Request) -> HealthResponse:
    """
    Vérifie la santé de l'API et du modèle.

    Returns:
        HealthResponse avec le statut de l'API et du modèle.
    """
    model_loaded = model_manager.model is not None
    model_trained = (
        model_manager.model is not None
        and model_manager.model._is_trained
    )

    status_str = "healthy" if model_trained else "degraded"

    return HealthResponse(
        status=status_str,
        model_loaded=model_loaded,
        model_trained=model_trained,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/metrics", tags=["Monitoring"])
@limiter.limit(API_RATE_LIMIT)
async def prometheus_metrics(request: Request):
    """
    Expose les métriques au format Prometheus.

    Cet endpoint est destiné à être scrapé par Prometheus
    pour alimenter les dashboards Grafana et les alertes.

    Returns:
        Réponse texte au format Prometheus.
    """
    monitor = get_monitor()
    metrics_data = monitor.get_metrics()
    return PlainTextResponse(
        content=metrics_data.decode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post(
    "/auth/token",
    response_model=TokenResponse,
    tags=["Authentication"],
)
@limiter.limit("10/minute")
async def get_token(
    request: Request,
    token_request: TokenRequest,
) -> TokenResponse:
    """
    Authentifie un utilisateur et retourne un token JWT.

    Rate limit strict (10/minute) pour prévenir les attaques
    par force brute (OWASP Top 10 — A07:2021 Identification and Authentication Failures).

    Args:
        token_request: Identifiants de l'utilisateur.

    Returns:
        TokenResponse avec le token JWT.

    Raises:
        HTTPException: 401 si les identifiants sont invalides.
    """
    user_data = DEMO_USERS.get(token_request.username)
    if user_data is None or user_data["password"] != token_request.password:
        # Délai artificiel pour ralentir les attaques par force brute
        time.sleep(0.5)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={
            "sub": token_request.username,
            "role": user_data["role"],
        }
    )

    logger.info(
        "Token JWT émis pour l'utilisateur : %s (rôle : %s)",
        token_request.username,
        user_data["role"],
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRATION_HOURS * 3600,
    )


@app.post(
    "/recommend",
    response_model=RecommendResponse,
    tags=["Recommendation"],
    summary="Generate K-Drama recommendations",
)
@limiter.limit(MODEL_RATE_LIMIT)
async def recommend(
    request: Request,
    req: RecommendRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> RecommendResponse:
    """
    Génère des recommandations de K-Dramas personnalisées.

    Deux modes de fonctionnement :
      1. **Mode utilisateur** : fournir `user_id` pour obtenir des
         recommandations basées sur l'historique de l'utilisateur.
      2. **Mode item** : fournir `drama_id` pour obtenir des dramas
         similaires à un drama de référence.

    Au moins un des deux paramètres doit être fourni.

    Authentification requise : token JWT valide dans l'en-tête
    `Authorization: Bearer <token>`.

    Rate limit : 30 requêtes/minute par adresse IP.

    Args:
        req: Paramètres de la requête (user_id et/ou drama_id, top_k).
        current_user: Utilisateur authentifié (via JWT).

    Returns:
        RecommendResponse avec la liste des recommandations.

    Raises:
        HTTPException: 400 si les paramètres sont invalides.
                       401 si non authentifié.
                       503 si le modèle est indisponible.
    """
    start_time = time.time()
    request_id = f"req-{int(start_time * 1000)}"

    # Validation : au moins un identifiant doit être fourni
    if req.user_id is None and req.drama_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of user_id or drama_id must be provided.",
        )

    # Récupération du modèle
    model = model_manager.get_model()

    # Inférence
    try:
        inference_start = time.time()
        results: list[RecommendationResult] = model.recommend(
            user_id=req.user_id,
            drama_id=req.drama_id,
            top_k=req.top_k,
        )
        inference_time = time.time() - inference_start
    except ValueError as e:
        logger.warning("Erreur de validation : %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Erreur lors de l'inférence : %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating recommendations.",
        )

    # Enregistrement des métriques
    monitor = get_monitor()
    for r in results:
        monitor.record_prediction(
            score=r.score,
            model_type="HybridRecommender",
            mode=req.get_mode(),
            inference_time=inference_time,
        )

    latency_ms = (time.time() - start_time) * 1000

    logger.info(
        "Recommandation générée : mode=%s, user=%s, drama=%s, "
        "top_k=%d, résultats=%d, latence=%.2fms",
        req.get_mode(),
        req.user_id,
        req.drama_id,
        req.top_k,
        len(results),
        latency_ms,
    )

    return RecommendResponse(
        success=True,
        mode=req.get_mode(),
        count=len(results),
        recommendations=[r.to_dict() for r in results],
        request_id=request_id,
        latency_ms=round(latency_ms, 2),
    )


@app.post(
    "/predict",
    response_model=PredictResponse,
    tags=["Recommendation"],
    summary="Predict the rating a user would give to a K-Drama",
)
@limiter.limit(MODEL_RATE_LIMIT)
async def predict(
    request: Request,
    req: PredictRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PredictResponse:
    """
    Prédit la note (sur 10) qu'un utilisateur donnerait à un K-Drama.

    Le score prédit est une combinaison pondérée :
      - Filtrage basé sur le contenu (similarité sémantique)
      - Filtrage collaboratif (utilisateurs similaires)

    Authentification requise : token JWT valide.

    Args:
        req: Paramètres (user_id, drama_id).
        current_user: Utilisateur authentifié.

    Returns:
        PredictResponse avec la note prédite et le niveau de confiance.

    Raises:
        HTTPException: 400 si les paramètres sont invalides.
                       401 si non authentifié.
                       503 si le modèle est indisponible.
    """
    start_time = time.time()

    model = model_manager.get_model()

    try:
        inference_start = time.time()
        predicted = model.predict(
            user_id=req.user_id,
            drama_id=req.drama_id,
        )
        inference_time = time.time() - inference_start
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Erreur lors de la prédiction : %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during prediction.",
        )

    # Niveau de confiance basé sur l'écart par rapport au score neutre (5.0)
    deviation = abs(predicted - 5.0)
    if deviation > 3.0:
        confidence = "high"
    elif deviation > 1.5:
        confidence = "medium"
    else:
        confidence = "low"

    # Enregistrement des métriques
    monitor = get_monitor()
    monitor.record_prediction(
        score=predicted,
        model_type="HybridRecommender",
        mode="predict",
        inference_time=inference_time,
    )

    latency_ms = (time.time() - start_time) * 1000

    logger.info(
        "Prédiction : user=%d, drama=%d, score=%.2f, confiance=%s, latence=%.2fms",
        req.user_id,
        req.drama_id,
        predicted,
        confidence,
        latency_ms,
    )

    return PredictResponse(
        success=True,
        user_id=req.user_id,
        drama_id=req.drama_id,
        predicted_rating=round(predicted, 2),
        confidence=confidence,
        latency_ms=round(latency_ms, 2),
    )


@app.get("/model/info", tags=["Model"])
@limiter.limit(API_RATE_LIMIT)
async def model_info(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Retourne les informations détaillées sur le modèle chargé.

    Inclut le type de modèle, les hyperparamètres, les métriques
    d'entraînement et le statut.

    Authentification requise.

    Returns:
        Dictionnaire avec les informations du modèle.
    """
    model = model_manager.get_model()
    return model.get_model_info()


@app.get("/alerts", tags=["Monitoring"])
@limiter.limit(API_RATE_LIMIT)
async def get_alerts(
    request: Request,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """
    Retourne les alertes actives du système de monitoring.

    Cet endpoint vérifie en temps réel les conditions d'alerte
    (dérive de prédiction, taux d'erreur, latence) et retourne
    les alertes déclenchées.

    Privilèges administrateur requis.

    Returns:
        Dictionnaire avec le résumé de santé et les alertes actives.
    """
    monitor = get_monitor()
    return monitor.get_health_summary()


@app.get("/alerts/rules", tags=["Monitoring"])
@limiter.limit(API_RATE_LIMIT)
async def get_alert_rules_endpoint(
    request: Request,
    current_user: dict[str, Any] = Depends(require_admin),
) -> PlainTextResponse:
    """
    Retourne les règles d'alerte Prometheus au format YAML.

    Privilèges administrateur requis.

    Returns:
        Contenu YAML des règles d'alerte.
    """
    return PlainTextResponse(
        content=get_alert_rules(),
        media_type="application/yaml",
    )


# ============================================================
# Gestionnaire d'erreurs global
# ============================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Gestionnaire global pour les erreurs de validation de valeurs."""
    logger.warning("ValueError sur %s : %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """Gestionnaire global pour les erreurs d'exécution du modèle."""
    logger.error("RuntimeError sur %s : %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"Model error: {exc}"},
    )


# ============================================================
# Point d'entrée
# ============================================================

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8001"))

    uvicorn.run(
        "model_api:app",
        host=host,
        port=port,
        reload=os.environ.get("API_RELOAD", "false").lower() == "true",
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
