# Rapport de résolution — E5-INC-001

## Résumé

Lors du premier déploiement Render, l'API du modèle ne parvenait pas à entraîner son modèle à partir de PostgreSQL. La valeur `DATABASE_URL` avait été copiée avec des guillemets littéraux. L'API restait joignable et son endpoint `/health` renvoyait HTTP 200 avec un corps `status: degraded`, ce qui pouvait masquer l'incident aux plateformes ne regardant que le code HTTP.

## Cause racine et facteurs aggravants

La chaîne transmise à SQLAlchemy n'était pas une URL valide, car les guillemets faisaient partie de la valeur. Deux comportements aggravaient le diagnostic :

1. la validation n'interceptait pas cette erreur avant SQLAlchemy ;
2. les messages d'exception pouvaient reprendre la chaîne fautive, donc potentiellement ses identifiants ;
3. la readiness ne signalait pas l'indisponibilité fonctionnelle par un code HTTP d'erreur.

## Reproduction en développement

Le test `test_get_database_url_rejects_render_value_with_quotes` configure une URL PostgreSQL fictive, contenant un mot de passe sentinelle et entourée de guillemets. Il reproduit de façon déterministe la configuration responsable, sans utiliser le secret Render réel.

Le test `test_health_returns_503_when_model_is_unavailable` reproduit le faux positif de disponibilité en retirant temporairement le modèle du gestionnaire pendant le test.

## Résolution implémentée

1. Normalisation des espaces externes de la valeur.
2. Rejet explicite des guillemets littéraux avant toute création de moteur SQLAlchemy.
3. Message d'erreur actionnable qui ne reprend jamais la valeur reçue.
4. Filtrage défensif des identifiants présents dans les exceptions journalisées.
5. Réponses d'erreur publiques génériques, avec détail conservé uniquement dans les logs expurgés.
6. Retour HTTP 503 de `/health` lorsque le modèle n'est pas chargé et entraîné.
7. Ajout de tests de non-régression pour la configuration, les logs et la readiness.

## Validation et retour arrière

La validation exécute les tests des étapes 3 et 5, puis reconstruit le conteneur du modèle. En cas de régression, le commit de correction peut être annulé indépendamment des configurations Prometheus/Grafana. Le retour à HTTP 200 dégradé n'est toutefois pas recommandé : il empêcherait Render, Docker et Prometheus de distinguer la vie du processus de sa capacité à fournir des prédictions.

## Versionnement

La correction est portée par la branche `etape5/monitoring-app` dans un commit dédié. La pull request vers `develop` constituera la preuve finale C21.5 ; elle ne doit être considérée comme acquise qu'après création et fusion de cette pull request.
