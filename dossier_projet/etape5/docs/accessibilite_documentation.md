# Contrôle d'accessibilité de la documentation E5

Relecture effectuée sur les documents Markdown du dossier `etape5`.

## Structure et navigation

- les titres suivent une hiérarchie logique sans saut volontaire de niveau ;
- les liens possèdent un intitulé décrivant leur destination ;
- les tableaux disposent d'une ligne d'en-tête ;
- les procédures sont ordonnées et les commandes sont isolées dans des blocs identifiés ;
- les phrases restent courtes et les sigles PSI et MLOps sont expliqués à leur première utilisation utile.

## Perception de l'information

- aucune instruction ne dépend uniquement d'une couleur ;
- les états utilisent aussi les mots `PASS`, `FAIL`, `SAIN`, `DÉGRADÉ` ou `INDISPONIBLE` ;
- les futures captures doivent comporter une légende et un texte alternatif ;
- les exemples ne contiennent pas d'animation ou de clignotement.

## Utilisation et confidentialité

- les commandes peuvent être copiées au clavier ;
- les adresses des interfaces sont fournies sous forme textuelle ;
- les messages d'erreur indiquent une action corrective sans exposer de secret ;
- les captures et tickets ne doivent contenir ni JWT, ni mot de passe, ni chaîne de connexion.

## Vérification avant remise

Lors de la composition du rapport final, exporter dans un format balisé, vérifier l'ordre de lecture, la présence des textes alternatifs, le contraste des captures et l'agrandissement à 200 %. Cette vérification finale dépend du logiciel utilisé pour produire le rapport et ne peut pas être garantie par le dépôt Markdown seul.
