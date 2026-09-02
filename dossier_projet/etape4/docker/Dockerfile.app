# ============================================================
# Dockerfile — Application web React de recommandation de K-Dramas
# Fichier : docker/Dockerfile.app
#
# Étape 4 — C19 (Chaîne de livraison continue)
#
# Construction multi-stage :
#   1. Builder : Node 20 installe les dépendances et build l'app
#   2. Runtime : nginx sert les fichiers statiques
#
# Construction :
#   docker build -f docker/Dockerfile.app -t kdrama-app:4.0 .
#
# Exécution :
#   docker run -p 8080:80 \
#     -e VITE_API_IA_URL=http://api-ia:8000 \
#     kdrama-app:4.0
#
# Auteur : Équipe projet RNCP AI
# ============================================================

# --- Étape 1 : Build de l'application React ---
FROM node:22-slim AS builder

WORKDIR /build

# Arguments de build pour les URLs des APIs
ARG VITE_API_DATA_URL=http://localhost:8000
ARG VITE_API_IA_URL=http://localhost:8001
ENV VITE_API_DATA_URL=${VITE_API_DATA_URL}
ENV VITE_API_IA_URL=${VITE_API_IA_URL}

# Copie des fichiers de dépendances (optimisation du cache Docker)
COPY package.json package-lock.json* ./

# Installation des dépendances
RUN npm ci

# Copie du code source
COPY . .

# Build de production
RUN npm run build

# --- Étape 2 : Serveur nginx (runtime) ---
FROM nginx:alpine AS final

LABEL org.opencontainers.image.title="K-Drama IA — Application Web React"
LABEL org.opencontainers.image.description="Application web React de recommandation de K-Dramas par IA"
LABEL org.opencontainers.image.version="4.0.0"
LABEL org.opencontainers.image.authors="Équipe projet RNCP AI"

# Copie des fichiers buildés vers nginx
COPY --from=builder /build/dist /usr/share/nginx/html

# Configuration nginx pour SPA (single-page app)
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /health { \
        return 200 "{\"status\":\"ok\",\"version\":\"4.0.0\"}"; \
        add_header Content-Type application/json; \
    } \
}' > /etc/nginx/conf.d/default.conf

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
