# Étalonnage du protocole de charge (étape 16)

> Remplir les `…` à partir de `docs/charge-mesures.md` (sections « Étalonnage » et « Répétabilité »).

## Configuration du poste et des déploiements

| | Valeur |
|---|---|
| Poste | … (processeur), 16 cœurs logiques, … Gio de RAM — Windows 11 |
| JMeter / Java | 5.6.3 / Java 1.8.0_441 (tas max 1 Gio) |
| VM proxy / métier / données | 1 vCPU · 1 Go / 2 vCPU · 2 Go / 2 vCPU · 2 Go |
| Conteneurs proxy / métier / données | limites identiques : `cpus` 1 / 2 / 2, `mem_limit` 1g / 2g / 2g |
| Processus gunicorn | VM : 2 workers — conteneurs : 2 workers (`WEB_CONCURRENCY`) |

## 1. Plafond de l'injecteur

`etalonnage.jmx` : `GET /static/app.css`, servi par le proxy seul, sans temps de réflexion.

| Utilisateurs | Débit (req/s) | p95 (ms) | Processeur de JMeter (% d'un cœur) | Processeur de l'hôte |
|---|---|---|---|---|
| 10 | 4 752,6 | 4 | non relevé | non relevé |
| 50 | 4 919,9 | 19 | non relevé | non relevé |
| 100 | 4 262,8 | 52 | non relevé | non relevé |

Aucune erreur sur les trois tirs (environ 320 000 requêtes chacun). Le débit est **plat** de 10 à 100 utilisateurs : on touche bien le plafond de la chaîne de mesure (JMeter + redirection de port de Docker Desktop + nginx), pas celui d'un service applicatif.

Plafond retenu : **≈ 4 300 req/s** (valeur la plus basse). Débit maximal attendu de l'application : 100 utilisateurs × 1 requête toutes les ~1,5 s de réflexion ≈ **65 req/s**, soit **plus de 60 fois moins** que le plafond. L'injecteur n'est donc pas le facteur limitant, même au palier le plus chargé.

## 2. Paramètres gelés

| Paramètre | Valeur |
|---|---|
| Paliers | 1, 5, 10, 25, 50, 100 |
| Montée | 30 s (exclue de la mesure) |
| Plateau mesuré | 90 s |
| Temps de réflexion | 1 à 2 s, uniforme, avant chaque requête |
| Pause entre paliers | 20 s |
| Comptes | 24 comptes `charge.*`, recyclés |
| Base | réinitialisée avant chaque campagne (schema + donnees + comptes-test) |

## 3. Répétabilité (deux campagnes identiques, ordre de passage alterné)

| Utilisateurs | VM : débit s1 / s2 (req/s) | Écart | Conteneurs : débit s1 / s2 (req/s) | Écart |
|---|---|---|---|---|
| 1 | 0,6 / 0,6 | 4,0 % | 0,6 / 0,6 | 1,8 % |
| 10 | 5,7 / 5,6 | 0,8 % | 6,4 / 6,4 | 0,1 % |
| 25 | 10,0 / 10,1 | 1,2 % | 15,9 / 15,6 | 1,9 % |
| 50 | 9,9 / 10,3 | 4,5 % | 28,1 / 30,2 | 7,2 % |
| 75 | 9,9 / 10,1 | 2,5 % | 29,8 / 32,7 | 9,7 % |
| 100 | 10,2 / 10,3 | 1,4 % | 31,6 / 33,0 | 4,4 % |
| 200 | 9,8 / 10,1 | 2,9 % | 32,8 / 32,9 | 0,5 % |

Conclusion : l'écart de débit maximal est de **4,5 % (VM)** et **9,7 % (conteneurs)**, sous le seuil de 10 % du sujet. La latence p95 varie de moins de 11 % hors de la zone de saturation des conteneurs ; dans cette zone (50 à 100 utilisateurs : 16 à 54 %), où une faible variation de débit allonge fortement la file d'attente. Tableau complet : `docs/charge-mesures.md`, section « Répétabilité ».
