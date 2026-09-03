# Étape 5 — Monitorage et résolution d'incident

Cette étape répond aux compétences RNCP C20 et C21 : surveiller l'application d'intelligence artificielle et résoudre un incident technique documenté et versionné.

## État

L'implémentation est conçue pour superviser le système local complet sans modifier son orchestration principale. Les preuves d'exécution sont générées dans `.validation/` et ne sont pas versionnées.

## Architecture prévue

- exporteur de santé applicative sur le port `9101` ;
- Prometheus sur `9090` ;
- Grafana sur `3000` ;
- Alertmanager sur `9093` ;
- Mailpit sur `8025` pour démontrer les alertes e-mail.

La procédure d'installation et la démonstration seront complétées avec l'implémentation. La correspondance détaillée avec les critères est tenue dans [docs/matrice_criteres.md](docs/matrice_criteres.md).
