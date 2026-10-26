# Planizi — Déploiement sur trois conteneurs Docker

Procédure pas à pas, de la configuration de Docker Desktop jusqu'aux mesures. Toutes les commandes se lancent dans **PowerShell, depuis le dossier `docker/`** du dépôt.

```
Planizi/
├── app.py, database.py, …      code applicatif — INCHANGÉ
├── schema.sql, donnees.sql      scripts SQL — montés tels quels dans le conteneur de données
├── static/, templates/
├── docker/
│   ├── compose.yaml                      services, réseaux, volume, publication
│   ├── metier.Dockerfile                 construction de l'image applicative
│   ├── metier.Dockerfile.dockerignore    ce qui n'entre pas dans l'image métier
│   ├── proxy.Dockerfile                  configuration et fichiers du client
│   ├── proxy.Dockerfile.dockerignore     ce qui n'entre pas dans l'image proxy
│   ├── nginx.conf                        configuration du proxy
│   ├── .env.example / .env               configuration (le .env n'est pas versionné)
│   ├── preuve-donnees.sql                preuve du peuplement (étape 11)
│   ├── verifier-isolation.ps1            matrice de joignabilité (étape 14)
│   ├── mesures.ps1                       mesures, 3 exécutions, médiane (étape 14)
│   └── PROCEDURE.md                      ce fichier
└── docs/
    └── comparaison.md                    tableau chiffré et analyse des écarts
```

> **Pourquoi deux fichiers d'exclusion et pas un `.dockerignore` unique ?** Le contexte de construction est la racine du dépôt (`..`), pour ne déplacer aucun fichier de code. Un `.dockerignore` placé dans `docker/` ne serait donc jamais lu. BuildKit (activé par défaut dans Docker Desktop) applique automatiquement le fichier `<nom du Dockerfile>.dockerignore` placé à côté du Dockerfile — ce qui permet en plus une exclusion propre à chaque image : le métier n'embarque pas les CSS, le proxy n'embarque que `static/` et `nginx.conf`.

---

## 0. Configurer Docker Desktop (une seule fois)

1. **Lancer Docker Desktop** (menu Démarrer). Accepter les conditions ; la connexion à un compte Docker est facultative (« Skip »).
2. **Settings → General** : vérifier que *Use the WSL 2 based engine* est coché. Si Windows demande d'installer ou de mettre à jour WSL, accepter (`wsl --update` dans un terminal administrateur), puis redémarrer Docker Desktop.
3. **Settings → Resources** : avec WSL 2, la mémoire et les processeurs de la VM Docker sont fixés par `%UserProfile%\.wslconfig`. Laisser les valeurs par défaut, ou les fixer, mais **les noter** : elles font partie de la configuration consignée des mesures. Exemple :
   ```ini
   [wsl2]
   memory=4GB
   processors=4
   ```
   (puis `wsl --shutdown` et relancer Docker Desktop).
4. Attendre que l'icône de la baleine indique *Engine running*, puis vérifier :
   ```powershell
   docker version            # doit afficher Client ET Server
   docker compose version    # Compose v2
   ```
5. **VirtualBox et Docker Desktop cohabitent** (VirtualBox 7 passe par Hyper-V quand WSL 2 est actif), mais **éteignez les VM pendant les mesures** de l'étape 14, sinon elles faussent la mémoire et le temps de démarrage.

> Sous Windows, le moteur Docker tourne lui-même dans une machine virtuelle Linux (WSL 2, processus `vmmemWSL` dans le Gestionnaire des tâches). Sa mémoire est relevée par `mesures.ps1` : sans elle, la comparaison serait faussée en faveur des conteneurs.

## 1. Configuration

Les variables de l'étape 4 sont réemployées **telles quelles**, avec de nouvelles valeurs :

| Variable | VM (étape 4) | Conteneurs |
|---|---|---|
| `DB_HOST` | adresse IP statique de la VM données | `donnees` — nom du service, fixé dans `compose.yaml` |
| `DB_PORT` | 5432 | 5432 (fixé dans `compose.yaml`) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | valeurs de la VM | `docker/.env` |
| `SECRET_KEY` | valeur de la VM | `docker/.env` |

Créer le `.env` (non versionné) avec un mot de passe et une clé aléatoires, en une commande :

```powershell
$mdp = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
$cle = -join (1..32 | % { '{0:x2}' -f (Get-Random -Max 256) })
"DB_NAME=planizi`nDB_USER=planizi`nDB_PASSWORD=$mdp`nSECRET_KEY=$cle" | Set-Content -Encoding ascii .env
Get-Content .env
```

(ou `Copy-Item .env.example .env` puis remplir à la main).

## 2. Étape 11 — La couche données

```powershell
docker compose up -d donnees
docker compose ps                     # attendre STATUS = Up … (healthy)
```

Ce que fait la déclaration du service `donnees` :

- image officielle **`postgres:16.9-bookworm`** (version explicite) ;
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` lus dans `.env` ;
- volume nommé **`pgdata`** sur `/var/lib/postgresql/data` ;
- `schema.sql` et `donnees.sql` montés en lecture seule dans `/docker-entrypoint-initdb.d/` (sous les noms `01-…` et `02-…` pour fixer l'ordre) ;
- **aucun `ports:`**, raccordé au seul réseau `interne` ;
- sonde de santé `pg_isready -h 127.0.0.1` : en TCP, car pendant l'initialisation PostgreSQL tourne sur un serveur temporaire qui n'écoute que sur le socket Unix. Interroger en TCP garantit que la base n'est déclarée prête qu'**après** l'exécution des scripts.

**Preuve du peuplement** (livrable) :

```powershell
Get-Content preuve-donnees.sql | docker compose exec -T donnees psql -U planizi -d planizi
```

Attendu : 15 utilisateurs, 3 équipes, 14 appartenances, 145 shifts.

**Persistance** : détruire le conteneur, le recréer, recompter — les données sont toujours là, car elles vivent dans le volume :

```powershell
docker compose rm -sf donnees
docker compose up -d donnees
docker volume ls                      # planizi_pgdata
docker volume inspect planizi_pgdata
```

**Inspecter la base** sans publier son port :

```powershell
docker compose exec donnees psql -U planizi -d planizi
```

> ⚠️ Les scripts d'initialisation ne sont joués **qu'au premier démarrage, volume vide**. Après une modification de `schema.sql` ou `donnees.sql`, il faut supprimer le volume : `docker compose down -v`.

## 3. Étape 12 — La couche métier

```powershell
docker compose build metier
docker image ls planizi-metier        # colonne SIZE : à reporter dans docs/comparaison.md
docker history planizi-metier:1.0     # taille de chaque couche
```

Choix du `metier.Dockerfile` :

- base légère **`python:3.12.8-slim-bookworm`** (version explicite) ;
- `requirements.txt` copié et installé **avant** le code : tant qu'il ne change pas, la couche des dépendances vient du cache. Vérification : modifier un commentaire dans `app.py`, relancer `docker compose build metier` → l'étape `pip install` apparaît `CACHED`, seule la copie du code est refaite ;
- `pip` sans cache (`PIP_NO_CACHE_DIR=1`), et fichier d'exclusion : pas de `venv/`, `__pycache__/`, `.git/`, `.env`, maquettes, CSS ni SQL dans l'image ;
- 2 workers gunicorn (`WEB_CONCURRENCY=2`), et limites `cpus` / `mem_limit` identiques aux VM (proxy 1 CPU / 1 Go, métier et données 2 CPU / 2 Go) : même capacité des deux côtés pour que la comparaison mesure la technique d'isolation, pas un réglage ;
- `gunicorn==23.0.0` ajouté dans le Dockerfile (pas dans `requirements.txt`) pour ne rien modifier au dépôt applicatif ;
- exécution sous un compte système `planizi`, sans privilèges ;
- `gunicorn --bind 0.0.0.0:8000` : **écouter sur toutes les interfaces est ici la bonne pratique**. En VM, c'était une faute (la machine avait des interfaces qui devaient rester privées) ; dans un conteneur, il n'y a qu'une interface par réseau raccordé, et l'isolation vient de la **non-publication du port**. Un service n'écoutant que sur `127.0.0.1` serait injoignable par le proxy.
- `DB_HOST=donnees` : le métier joint la base **par son nom**, résolu par le DNS interne de Docker ;
- raccordé à `frontal` et `interne`, aucun port publié.

## 4. Étape 13 — Le proxy et la composition

```powershell
docker compose up -d --build          # construit les deux images et démarre l'ensemble
docker compose ps                     # CAPTURE D'ÉCRAN À FAIRE : les 3 services Up (healthy)
```

Puis ouvrir **http://localhost:8080** (comptes de démonstration : mot de passe `planizi123`, par exemple `e.renucci` ou `admin.planizi`).

- `proxy.Dockerfile` : image officielle `nginx:1.27.5-bookworm`, `nginx.conf` et `static/` **copiés dans l'image** ;
- `nginx.conf` : `/static/` servi par nginx, tout le reste renvoyé à `http://metier:8000` — **le nom du service**, résolu par le DNS de Docker (`resolver 127.0.0.11`, ce qui permet au proxy de retrouver le métier même si son conteneur est recréé avec une autre adresse) ;
- seule publication de port du projet : `8080:80` sur le proxy ;
- dépendances conditionnées à l'état de santé : `metier` attend `donnees: service_healthy`, `proxy` attend `metier: service_healthy` (sonde sur `/connexion`).

### Commandes de cycle de vie (à connaître)

| Commande | Effet | Données |
|---|---|---|
| `docker compose up -d --build` | (re)construit si besoin et démarre | conservées |
| `docker compose stop` / `start` | arrête / relance les conteneurs existants | conservées |
| `docker compose restart` | redémarre les trois services | conservées |
| `docker compose down` | arrête **et supprime** conteneurs et réseaux | **conservées** (le volume reste) |
| `docker compose down -v` | idem **+ supprime le volume** | **EFFACÉES** — les scripts SQL seront rejoués au prochain `up` |
| `docker compose logs -f metier` | journaux d'un service | — |
| `docker compose exec metier bash` | terminal dans un conteneur | — |

Vérifier que l'ensemble démarre, s'arrête et redémarre par une commande unique : `docker compose up -d`, `docker compose down`, `docker compose up -d`, puis rafraîchir la page.

> On ne corrige pas un conteneur : on corrige sa description (Dockerfile, `compose.yaml`, `nginx.conf`), puis on le remplace (`docker compose up -d --build`).

## 5. Étape 14 — Vérifier et comparer

### Matrice de joignabilité

```powershell
powershell -ExecutionPolicy Bypass -File .\verifier-isolation.ps1
```

Le script vérifie d'abord que les trois services sont `healthy` (un échec doit venir de l'absence de route, pas d'un service arrêté), puis teste chaque case depuis un terminal ouvert **dans** chaque conteneur (`bash -c "exec 3<>/dev/tcp/<cible>/<port>"`) et depuis Windows. Il ajoute une contre-épreuve : la base est injoignable depuis le proxy **même par son adresse IP**, pas seulement parce que son nom n'est pas résolu. Résultat : `docs/matrice-joignabilite.md`.

> Si un PostgreSQL est installé directement sur Windows, il écoute déjà sur `localhost:5432` et la case « hôte → données » paraîtra joignable : le script affiche le processus qui écoute. Arrêter ce service Windows pendant le test (`services.msc`).

### Mesures

VM VirtualBox éteintes, autres applications lourdes fermées :

```powershell
powershell -ExecutionPolicy Bypass -File .\mesures.ps1                      # démarrage, mémoire, disque, latence
powershell -ExecutionPolicy Bypass -File .\mesures.ps1 -MiseEnPlace         # + mise en place depuis zéro
```

Adapter `-Url` et `-Requetes` pour reprendre **exactement** le protocole de l'étape 10. Le rapport (`docs/mesures-conteneurs-<date>.md`) contient les valeurs et la configuration du poste (CPU, RAM, versions, `.wslconfig`). Reporter les médianes dans `docs/comparaison.md`.
