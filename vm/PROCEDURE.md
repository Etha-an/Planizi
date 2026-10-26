# Planizi — Déploiement sur trois machines virtuelles (procédure de l'étape 9)

Procédure manuelle de la partie 2, conservée telle qu'elle a été suivie, pour être lue à côté de `docker/` (partie 3).
Mesures de ces VM : `docs/mesures-vm-20261026-1435.md` ; comparaison : `docs/comparaison.md`.

> Ajout postérieur (mesures de la partie 3) : sur vm-metier et vm-donnees, l'attente `systemd-networkd-wait-online`
> générée par netplan (`--dns -o routable`) bloquait chaque démarrage 2 minutes, faute de DNS sur le réseau interne.
> Corrigé par `sudo systemctl edit systemd-networkd-wait-online.service` :
> ```ini
> [Service]
> ExecStart=
> ExecStart=/usr/lib/systemd/systemd-networkd-wait-online -i enp0s8 -o routable --timeout=30
> ```

---

## 0. Contexte et plan d'adressage

| Machine | Rôle | vCPU / RAM (plan) | Adaptateur 1 | Adaptateur 2 |
|---|---|---|---|---|
| vm-proxy | Nginx, point d'entrée unique | 1 / 1 Go | NAT (8080 → 80) | Réseau interne `intnet-app`, 10.10.10.10/24 |
| vm-metier | Application Flask (Gunicorn) | 2 / 2 Go | NAT temporaire, désactivé ensuite | Réseau interne `intnet-app`, 10.10.10.20/24 |
| vm-donnees | PostgreSQL | 2 / 2 Go | NAT temporaire, désactivé ensuite | Réseau interne `intnet-app`, 10.10.10.30/24 |

- Sous-réseau interne : `10.10.10.0/24`, nom du réseau interne VirtualBox : `intnet-app`.
- Accès depuis le poste : `http://localhost:8080`.
- Les valeurs vCPU / RAM sont celles du plan. La configuration effective de chaque VM n'a pas été relevée dans VirtualBox : **non disponible**.
- Système invité : Ubuntu Server, sans interface graphique (Python 3.14 sur la VM). Numéro de version exact : **non disponible**.
- Noms des interfaces relevés avec `ip a` : `enp0s3` (carte NAT, adaptateur 1) et `enp0s8` (réseau interne, adaptateur 2). La carte appelée `eth0`/`eth1` dans le sujet s'appelle `enp0s3`/`enp0s8` sur Ubuntu.

### Écarts assumés par rapport au sujet

1. **SGBD et code applicatif.** L'application Planizi utilisait MySQL. Pour respecter la topologie du sujet (PostgreSQL), le code a été porté vers PostgreSQL (voir § 1.4). Ce n'est donc pas un changement « de configuration uniquement ».
2. **Nom de la base.** La base s'appelle `planning` (et non `notes` comme dans le sujet). L'utilisateur applicatif s'appelle `app`.
3. **Renvoi Nginx.** Le sujet renvoie seulement `/api/` vers le métier. Planizi est une application Flask qui génère elle-même toutes ses pages (templates Jinja2, fichiers statiques), donc Nginx renvoie **toutes** les requêtes (`location /`) vers vm-metier.
4. **Point d'entrée Gunicorn.** L'objet Flask s'appelle `app` dans `app.py` : la cible est `app:app` (et non `app:application`).
5. **Installation des paquets.** Méthode retenue : « installer avant d'isoler ». vm-metier et vm-donnees ont gardé un adaptateur NAT le temps des installations, puis cet adaptateur a été désactivé.

---

## 1. Procédure de déploiement

### 1.1 Machine modèle et clones (étape 7, rappel)

**Création de la VM dans VirtualBox**
- Nouvelle VM, ISO Ubuntu Server, type Linux, case « Skip Unattended Installation » cochée.
- Disque virtuel : 10 Go. RAM passée à 2048 Mo après un premier échec de l'installateur (erreur après `installing kernel`).

**Installation d'Ubuntu Server**
- Réseau par défaut, champ proxy laissé vide, partitionnement par défaut (LVM).
- Case « Install OpenSSH server » cochée, aucun snap.

**Préparation du modèle (dans la VM)**
```bash
sudo apt update && sudo apt upgrade -y
sudo poweroff
```
La VM a ensuite été renommée `modele` dans VirtualBox.

**Clonage (VirtualBox)**
- Clic droit sur `modele` → Cloner, trois fois : `vm-proxy`, `vm-metier`, `vm-donnees`.
- Politique MAC : « Générer de nouvelles adresses MAC pour toutes les cartes réseau ». Type : clone intégral.
- Incident : un clone `vm-proxy` raté a été retiré sans supprimer ses fichiers, et son dossier dans `%USERPROFILE%\VirtualBox VMs\` bloquait la réutilisation du nom. Il a été supprimé avec :
  ```powershell
  Remove-Item -Recurse -Force "$env:USERPROFILE\VirtualBox VMs\vm-proxy"
  ```

**Personnalisation de chaque clone (exemple pour vm-metier)**
```bash
sudo hostnamectl set-hostname vm-metier
sudo nano /etc/hosts        # ligne « 127.0.1.1 proxy » remplacée par « 127.0.1.1 vm-metier »
sudo truncate -s 0 /etc/machine-id
sudo systemd-machine-id-setup && sudo reboot
```
Même chose sur vm-proxy (`vm-proxy`) et vm-donnees (`vm-donnees`).

**Ressources** : réglées dans Configuration → Système (onglet Carte mère pour la RAM, onglet Processeur pour les vCPU), selon le plan du § 0.

**Snapshots** : un snapshot « base propre » sur chaque clone (Machine → Prendre un instantané).

### 1.2 Réseau et adressage (étape 8)

**Réglages VirtualBox**

| VM | Adapter 1 | Adapter 2 |
|---|---|---|
| vm-proxy | NAT ; redirections : `Rule 1` TCP 8080 → 80, `SSH` TCP 2222 → 22 | Réseau interne, nom `intnet-app` |
| vm-metier | NAT, temporaire (redirection temporaire 2224 → 22 pour la copie du code, retirée ensuite) | Réseau interne, nom `intnet-app` |
| vm-donnees | NAT, temporaire (redirection temporaire 2223 → 22 pour la copie des scripts SQL, retirée ensuite) | Réseau interne, nom `intnet-app` |

Pour les redirections, l'IP hôte et l'IP invité sont laissées vides.

**Fichier netplan** : `/etc/netplan/00-installer-config.yaml` (le fichier `50-cloud-init.yaml` n'existait pas).

Le fichier d'origine contenait un bloc `match: macaddress` / `set-name` lié à l'adresse MAC du modèle. Comme les clones ont de nouvelles adresses MAC, ce bloc a été supprimé et tout le contenu a été réécrit.

vm-proxy (contenu définitif) :
```yaml
network:
  version: 2
  ethernets:
    enp0s3:
      dhcp4: true
    enp0s8:
      dhcp4: false
      addresses: [10.10.10.10/24]
```

vm-metier et vm-donnees pendant l'installation : même structure, avec respectivement `10.10.10.20/24` et `10.10.10.30/24`.

vm-metier après isolation (le bloc `enp0s3` est supprimé) :
```yaml
network:
  version: 2
  ethernets:
    enp0s8:
      dhcp4: false
      addresses: [10.10.10.20/24]
```
vm-donnees après isolation : identique, avec `10.10.10.30/24`.

**Application et vérification**
```bash
sudo chmod 600 /etc/netplan/00-installer-config.yaml
sudo netplan apply
ip a
ping -c2 10.10.10.30   # depuis vm-metier
ping -c2 10.10.10.20   # depuis vm-proxy
```
Résultats des pings : **non disponibles** (non transmis pendant la séance).

### 1.3 Ordre du déploiement (étape 9)

Ordre imposé par le sujet : vm-donnees, puis vm-metier, puis vm-proxy, avec un snapshot avant chaque couche.

### 1.4 Adaptation du code de Planizi à PostgreSQL (sur le poste, avant déploiement)

Dossier : `Planizi/` sur le poste Windows. L'export d'origine `data.sql` (MySQL, encodé en UTF-16, accents abîmés par la redirection PowerShell) est conservé tel quel.

| Fichier | Modification |
|---|---|
| `schema.sql` (nouveau) | Création des tables `"user"`, `team`, `user_team`, `shift` en PostgreSQL |
| `donnees.sql` (nouveau) | Données de démonstration converties depuis `data.sql`, accents réparés, compteurs `id` recalés |
| `database.py` | `mysql.connector` remplacé par `psycopg2`, `RealDictCursor`, port par défaut 5432, table écrite `"user"` |
| `planning_db.py` | `GROUP_CONCAT` → `STRING_AGG`, `TIMESTAMPDIFF` → `EXTRACT(EPOCH …)`, `INSERT IGNORE` → `ON CONFLICT DO NOTHING`, `lastrowid` → `RETURNING id`, suppression de `start_transaction()` |
| `migrer.py` | `DATABASE()` → `current_schema()`, `UPDATE … JOIN` → `UPDATE … FROM`, `TINYINT(1)` → `SMALLINT` |
| `seed.py` | Même adaptations (`RETURNING id`, table entre guillemets) |
| `requirements.txt` | `mysql-connector-python` remplacé par `psycopg2-binary==2.9.11` (la 2.9.10 ne s'installe pas sous Python 3.14) |

`user` est un mot réservé en PostgreSQL, d'où les guillemets `"user"` partout. Le portage a été testé sur un PostgreSQL 16 (connexion, planning, équipes, organisation d'un shift de nuit, inscription, validation, désactivation).

Contenu de `schema.sql` :
```sql
-- Planizi : structure de la base (PostgreSQL)
-- Usage : psql -d planizi -f schema.sql
-- « user » est un mot réservé en PostgreSQL : la table est toujours écrite entre guillemets.

DROP TABLE IF EXISTS shift, user_team, team, "user" CASCADE;

CREATE TABLE "user" (
    id            INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    nom           VARCHAR(50)  NOT NULL,
    prenom        VARCHAR(50)  NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    poste         VARCHAR(100),
    login         VARCHAR(102) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    manager       SMALLINT     NOT NULL,          -- 0 / 1
    supervisor    SMALLINT     NOT NULL,          -- 0 / 1
    contrat       INTEGER,                        -- heures par semaine
    valid         SMALLINT     NOT NULL DEFAULT 0 -- 0 = en attente, 1 = validé
);

CREATE TABLE team (
    id  INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    nom VARCHAR(255) NOT NULL
);

CREATE TABLE user_team (
    user_id     INTEGER  NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    team_id     INTEGER  NOT NULL REFERENCES team (id)   ON DELETE CASCADE,
    responsable SMALLINT NOT NULL DEFAULT 0,      -- 1 = gère l'équipe, 0 = simple membre
    PRIMARY KEY (user_id, team_id)
);
CREATE INDEX idx_user_team_team ON user_team (team_id);

CREATE TABLE shift (
    id            INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    categorie     VARCHAR(255) NOT NULL,
    debut         TIMESTAMP    NOT NULL,
    fin           TIMESTAMP    NOT NULL,
    effectueur_id INTEGER      NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    assigneur_id  INTEGER      NOT NULL REFERENCES "user" (id) ON DELETE CASCADE
);
CREATE INDEX idx_shift_effectueur ON shift (effectueur_id);
CREATE INDEX idx_shift_assigneur  ON shift (assigneur_id);
```
`donnees.sql` contient les `INSERT` (15 utilisateurs, 3 équipes, 14 appartenances, 145 shifts), puis trois `setval` qui recalent les compteurs. Il est trop long pour être reproduit ici : voir le fichier dans `Planizi/`.

### 1.5 vm-donnees — PostgreSQL

**Installation**
```bash
sudo apt update
sudo apt install postgresql -y
```

**Utilisateur applicatif et base**
```bash
sudo -u postgres psql -c "CREATE USER app WITH PASSWORD '********';"
sudo -u postgres psql -c "CREATE DATABASE planning OWNER app;"
```

**Copie des scripts SQL (PowerShell, sur le poste)**, par la redirection temporaire 2223 → 22 de vm-donnees :
```powershell
cd "C:\Users\renuc\Desktop\Polytech\INFO 4A\Virtu\Planizi"
scp -P 2223 schema.sql donnees.sql ethan@127.0.0.1:~
```

**Exécution des scripts** (avant de restreindre `listen_addresses`) :
```bash
psql -h 127.0.0.1 -U app -d planning -f schema.sql
psql -h 127.0.0.1 -U app -d planning -f donnees.sql
psql -h 127.0.0.1 -U app -d planning -c 'SELECT count(*) FROM "user";'   # attendu : 15
```
Pour `schema.sql`, la sortie obtenue était : 4 NOTICE « does not exist, skipping », puis `DROP TABLE`, 4 `CREATE TABLE` et 3 `CREATE INDEX`. Sorties de `donnees.sql` et du comptage : **non disponibles**.

**`postgresql.conf`** — `/etc/postgresql/<version>/main/postgresql.conf` (numéro de version : **non disponible**) :
```
listen_addresses = '10.10.10.30'
```

**`pg_hba.conf`** — ligne ajoutée à la fin de `/etc/postgresql/<version>/main/pg_hba.conf` :
```
host    planning    app    10.10.10.20/32    scram-sha-256
```

**Redémarrage et vérification**
```bash
sudo systemctl restart postgresql
sudo ss -tlnp | grep 5432      # attendu : 10.10.10.30:5432
```
Sortie de `ss` : **non disponible**.

**Nettoyage** : une première copie du code applicatif était arrivée par erreur sur vm-donnees (la redirection 2224 avait été placée sur la mauvaise VM). Elle a été supprimée :
```bash
rm -rf ~/planizi
```

**Snapshot** : pris après la configuration de PostgreSQL. Nom : **non disponible**.

### 1.6 vm-metier — application (Flask + Gunicorn)

**Installation de Python**
```bash
sudo apt update
sudo apt install python3-venv python3-pip -y
mkdir ~/planizi
```
Le premier `python3 -m venv venv` a échoué (« ensurepip is not available ») parce que `python3-venv` n'avait pas été installé.

**Copie du code (PowerShell, sur le poste)**, par la redirection temporaire 2224 → 22 de vm-metier :
```powershell
ssh -p 2224 ethan@127.0.0.1 hostname   # contrôle : doit répondre vm-metier
cd "C:\Users\renuc\Desktop\Polytech\INFO 4A\Virtu\Planizi"
scp -P 2224 -r app.py database.py planning_db.py migrer.py requirements.txt templates static ethan@127.0.0.1:~/planizi/
```
Le contrôle par `hostname` est nécessaire : les trois clones partagent la même clé d'hôte SSH, donc on ne peut pas savoir autrement quelle VM répond.

**Environnement virtuel**
```bash
cd ~/planizi
rm -rf venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt gunicorn
```

**Variables d'environnement** — `~/planizi/.env`, créé sur la VM et non copié depuis le poste :
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # génère SECRET_KEY
nano .env
chmod 600 .env
```
```
DB_HOST=10.10.10.30
DB_PORT=5432
DB_NAME=planning
DB_USER=app
DB_PASSWORD=********
SECRET_KEY=********
```

**Tests manuels**
```bash
venv/bin/python -c "import database; print(len(database.recuperer_utilisateurs()))"   # attendu : 15
venv/bin/gunicorn --bind 10.10.10.20:8000 app:app
curl -I http://10.10.10.20:8000/connexion                                            # attendu : 200 OK
```
Sorties : **non disponibles**.

**Unité systemd** — `/etc/systemd/system/planizi.service` :
```ini
[Unit]
Description=Planizi (Gunicorn)
After=network-online.target
Wants=network-online.target

[Service]
User=ethan
WorkingDirectory=/home/ethan/planizi
ExecStart=/home/ethan/planizi/venv/bin/gunicorn --workers 2 --bind 10.10.10.20:8000 app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now planizi
sudo systemctl status planizi
```

Incidents rencontrés :
- `ExecStart` coupé en deux lignes : Gunicorn sortait avec le code 2. Corrigé en remettant la commande sur une seule ligne, puis `daemon-reload`, `reset-failed`, `restart`.
- Cible écrite `app.app` au lieu de `app:app` : `ModuleNotFoundError: No module named 'app.app'`. Corrigé.

État final constaté : `active (running)`, Gunicorn 26.2.0, `Listening at: http://10.10.10.20:8000`, 2 workers (sync).

Test de redémarrage avec la machine (`sudo reboot`, puis `curl`) : résultat **non disponible**.

**Isolation (vm-metier et vm-donnees)**
- Dans VirtualBox : Configuration → Réseau → Adapter 1, case « Activer l'interface réseau » décochée (les redirections 2223 et 2224 disparaissent avec).
- Netplan : bloc `enp0s3` supprimé (voir § 1.2), puis `sudo netplan apply`.
- Snapshots pris après l'isolation.

### 1.7 vm-proxy — façade (Nginx)

```bash
sudo apt update
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/default
```
Contenu de `/etc/nginx/sites-available/default` :
```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://10.10.10.20:8000;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo nginx -t
sudo systemctl reload nginx
```
Fichiers du client : ils sont servis par Flask (`static/`, `templates/`) à travers le proxy, et n'ont pas été déposés séparément sur vm-proxy.

**Validation** : `http://localhost:8080` depuis le navigateur du poste, connexion avec un compte de démonstration. Résultat : application fonctionnelle de bout en bout (« ça fonctionne parfaitement »).

### 1.8 Pare-feu

Aucun pare-feu (ufw, nftables…) n'a été configuré pendant la séance : **non disponible**. L'isolation repose sur le réseau interne VirtualBox, `listen_addresses`, `pg_hba.conf` et le bind de Gunicorn sur 10.10.10.20.

---

