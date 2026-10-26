# Planizi — Trois machines virtuelles face à trois conteneurs

*Compte rendu de l'étape 14. Relevés bruts : `docs/mesures-vm-20261026-1435.md` (VM) et `docs/mesures-conteneurs-20261025-1634.md` / `…-1644.md` (conteneurs). Isolation : `docs/matrice-joignabilite.md` (conteneurs, 11/11 cas conformes) et captures `PreuveVM/` (VM, 6/6 cas conformes).*

## 1. Conditions de mesure

| | Trois VM | Trois conteneurs |
|---|---|---|
| Poste | Intel i7-1260P, 16 cœurs logiques, 15,7 Gio, Windows 11 | même poste, même séance de travail |
| Technique | VirtualBox 7.2.4, clones intégraux d'un modèle Ubuntu Server (disque dynamique de 10 Go), démarrage sans fenêtre | Docker Desktop, moteur 29.9.1, Compose 5.6, VM WSL 2 (16 CPU, 7,6 Gio, `.wslconfig` par défaut) |
| Ressources | proxy 1 vCPU / 1 Go ; métier 2 vCPU / 2 Go ; données 2 vCPU / 2 Go | mêmes valeurs en limites `cpus` / `mem_limit` (groupes de contrôle) |
| Protocole | 3 exécutions, médiane — `docker/mesures-vm.ps1` | 3 exécutions, médiane — `docker/mesures.ps1` |
| Latence | 3 × 50 requêtes `GET /connexion` sur http://localhost:8080 | idem |

Les deux déploiements n'ont jamais tourné en même temps : ils publient le même port 8080.

## 2. Tableau comparatif chiffré

| Grandeur | Trois VM | Trois conteneurs | Écart |
|---|---|---|---|
| Temps de démarrage (tout éteint → 1re réponse HTTP 200) | **105 s** (94 et 116 s ; 1 essai sur 3 en échec) — 193 s avant correction de la configuration réseau | **5,9 s** (5,84 à 5,91 s) | **× 18** |
| Mémoire occupée par la charge applicative | **2 362 Mio** (3 processus VirtualBox ; 5 120 Mio alloués) | **107 Mio** (somme `docker stats`) | × 22 |
| Mémoire en comptant le moteur | 2 362 Mio | **858 Mio** (VM WSL 2 entière, pile lancée ; 739 Mio sans la pile) | **× 2,8** |
| Empreinte disque | **26,1 Gio** : 3 disques de base de 7,8 Gio + 2,7 Gio d'instantanés | **1,1 Gio** : 1,06 Gio d'images + 46 Mio de volume (disque virtuel Docker entier : 3,2 Gio, cache de construction compris) | **× 24** (× 8 face au disque Docker entier) |
| Latence `GET /connexion` (médiane) | **234 ms** | **7,6 ms** | **× 31**, soit + 227 ms |
| Mise en place depuis zéro | séance de la partie 2 (non chronométrée) | **52 s** : téléchargement, construction et premier démarrage (`mesures.ps1 -MiseEnPlace`) | — |

**Le moteur compte.** Sous Windows, les conteneurs tournent eux-mêmes dans une VM Linux (`vmmemWSL`). Sans elle, les conteneurs paraîtraient 22 fois plus légers. Avec elle, l'écart tombe à 2,8. C'est ce second chiffre qui est honnête. La pile Planizi n'ajoute que 90 à 120 Mio à cette VM : le reste est le prix fixe du moteur, partagé par tous les conteneurs. Selon son cache, cette VM a occupé de 0,7 à 3 Gio au fil des relevés.

**Disque.** Chaque VM est un clone intégral de la VM modèle. Elle porte donc **son propre** disque Ubuntu Server de 7,8 Gio : un disque dynamique ne rétrécit jamais, et celui-ci a gardé tout ce que l'installation et `apt upgrade` y ont écrit. S'y ajoutent les instantanés pris avant chaque couche : 0,7 à 1,1 Gio par VM, soit 2,7 Gio au total. Côté conteneurs, une image n'embarque qu'une distribution Debian minimale et les dépendances d'un seul processus : 203 Mio pour le métier, 267 Mio pour le proxy, 589 Mio pour PostgreSQL. Les données vivent à part, dans un volume de 46 Mio. Même en comptant tout le disque virtuel de Docker Desktop (3,2 Gio, cache de construction compris), l'écart reste de 8 fois. *(Un premier relevé de 1,15 Gio ne comptait que le dernier fichier de différences de chaque VM. Il est corrigé ici.)*

## 3. Les deux procédures côte à côte

| | Procédure VM (étape 9) | `compose.yaml` + Dockerfiles |
|---|---|---|
| Longueur | **≈ 48 commandes** (42 dans les VM, 6 sur le poste) + **45 lignes de configuration** (netplan ×3, `postgresql.conf`, `pg_hba.conf`, unité systemd, site nginx, `.env`), plus une vingtaine d'actions dans l'interface de VirtualBox (clonage ×3, cartes réseau, redirections, snapshots) — `vm/PROCEDURE.md` | **115 lignes** : 77 (`compose.yaml`) + 14 (`metier.Dockerfile`) + 4 (`proxy.Dockerfile`) + 20 (`nginx.conf`), et **une** commande : `docker compose up -d --build` |
| Réseau | 2 adaptateurs par VM, adresses statiques 10.10.10.10/20/30 (netplan), un adaptateur NAT ouvert le temps des installations puis désactivé, redirections de port temporaires pour copier le code par `scp` | 2 réseaux déclarés en 4 lignes, les services se joignent par leur nom |
| Démarrage | unité systemd `planizi.service` (`After=network-online.target`), PostgreSQL et nginx activés par défaut ; l'ordre entre les VM n'est garanti par rien | `depends_on` + sondes de santé : l'ordre et l'état « prêt » sont déclarés |
| Ce qui reste implicite | versions installées par `apt` et `pip` au moment du déploiement (PostgreSQL 18, Python 3.14, gunicorn 26.2 sans version fixée), mots de passe saisis à la main, état initial du modèle, attente réseau du système invité (voir ci-dessous) | versions du moteur et de Compose, ressources de la VM WSL ; les versions des images et des paquets Python, elles, sont fixées |

Le temps de lecture suit la longueur : la procédure VM se lit en une vingtaine de minutes et comporte cinq incidents corrigés en cours de route (clone raté, `ExecStart` coupé, `app.app`, code copié sur la mauvaise VM, `python3-venv` manquant). Les fichiers Docker se lisent en quelques minutes et se rejouent sans intervention.

Les mesures ont aussi fait apparaître un implicite caché de la procédure VM. Netplan faisait attendre à vm-metier et vm-donnees un serveur DNS absent du réseau interne, pendant **2 minutes à chaque démarrage**. C'est l'attente `systemd-networkd-wait-online` ; une fois corrigée, le démarrage des systèmes invités passe de 130 à 11-25 s. Rien dans le fichier de procédure ne le laissait voir. En conteneurs, ce réglage n'existe pas : il n'y a pas de système invité à démarrer.

**Une isolation obtenue plus simplement en conteneurs.** Côté VM, la matrice relevée sur les captures `PreuveVM/` est conforme (6/6) : le PC n'atteint que vm-proxy (port 8080) ; depuis le PC, 10.10.10.20:8000 et 10.10.10.30:5432 sont injoignables ; vm-proxy joint vm-metier (ping, `curl` → 200) mais pas le port 5432 de vm-donnees (`nc -zv -w2 10.10.10.30 5432` : délai dépassé) ; vm-metier joint vm-donnees. Cette isolation repose pourtant sur la configuration de chaque machine, alors que les trois VM partagent **un seul** réseau interne, 10.10.10.0/24 (`intnet-app`). En conteneurs, le proxy et la base n'ont aucun réseau commun : la connexion échoue avant même d'atteindre PostgreSQL, par le nom (non résolu) comme par l'adresse IP (aucune route), comme le montre la matrice (11/11). Deux réseaux ont coûté 4 lignes de `compose.yaml` ; en VM, il aurait fallu une deuxième carte, un deuxième sous-réseau et trois fichiers de configuration de plus. À noter : `ss` montre sur vm-metier un port 80 ouvert sur toutes les adresses, inutile à l'application (serveur web probablement installé par erreur).

## 4. Analyse

### 4.1 De combien les chiffres diffèrent

Démarrage **18 fois** plus rapide en conteneurs. Mémoire **2,8 fois** plus faible en comptant le moteur, et 22 fois sans lui. Latence d'une page simple **31 fois** plus basse. Disque **24 fois** plus petit (8 fois en comptant tout le disque virtuel de Docker). En charge (étapes 15 à 18, `docs/rapport-charge.md`), les conteneurs soutiennent 3,2 fois plus de débit à ressources égales.

### 4.2 Quelle propriété technique explique chaque écart

- **Démarrage.** Démarrer une VM, c'est démarrer un ordinateur : micrologiciel, chargeur de démarrage, noyau, initramfs, systemd et ses attentes réseau, puis les services. Les VM mettent ainsi 94 à 116 s avant que Planizi réponde, alors que leurs systèmes ne mesurent que 11 à 25 s de démarrage interne : le reste se passe avant le noyau et entre les VM. Un conteneur est un processus lancé sur un noyau déjà en marche. Il ne reste que le démarrage de PostgreSQL, de gunicorn et de nginx, puis la cascade des sondes de santé.
- **Mémoire.** Chaque VM porte son propre noyau, ses services système et son cache disque : 700 à 840 Mio occupés par VM, alors que l'application n'en utilise qu'une fraction. Les conteneurs partagent un seul noyau. Les espaces de nommage cloisonnent ce que chaque processus voit, et les groupes de contrôle limitent ce qu'il consomme. Seuls les processus applicatifs occupent de la mémoire, 107 Mio au total.
- **Latence.** `GET /connexion` n'appelle ni la base ni le hachage. Les 227 ms de différence sont donc perdues **avant** le code applicatif, sur le chemin réseau. En VM, la requête traverse le NAT de VirtualBox (un moteur réseau en espace utilisateur), la pile réseau du proxy invité, puis le réseau interne VirtualBox jusqu'au métier. Chaque passage implique des interruptions émulées et des transitions vers l'hyperviseur. En conteneurs, proxy et métier communiquent par un pont du noyau partagé, sans hyperviseur entre eux.
- **Disque.** Une VM stocke un système d'exploitation complet par machine : trois fois Ubuntu Server, plus l'historique de ses instantanés. Un conteneur ne stocke que les couches nécessaires à un processus, et ses données vivent dans un volume séparé. Recréer un conteneur ne réécrit rien, alors que chaque instantané de VM fige un état complet du disque.

### 4.3 Ce que le déploiement en conteneurs a perdu

- **Une frontière d'isolation matérielle.** Les trois conteneurs partagent le noyau. Une faille du noyau ou du moteur (évasion de conteneur) les expose tous, alors qu'une VM compromise reste confinée par l'hyperviseur. Le processus `root` d'un conteneur est le `root` du noyau hôte, d'où l'exécution du métier sous un compte sans privilèges.
- **Un système d'exploitation propre.** Impossible d'exécuter un autre système que celui de l'hôte. C'est pour cela qu'il faut, sous Windows, une VM Linux pour faire tourner ces conteneurs. Sur ce poste, l'avantage mémoire du conteneur passe ainsi de × 22 à × 2,8.
- **Un état durable.** Tout ce qui est écrit hors du volume `pgdata` disparaît à la destruction du conteneur. On ne corrige plus une machine, on corrige sa description et on la remplace.
- **L'autonomie de chaque couche.** Les trois services dépendent d'un même démon Docker et de sa VM : s'il s'arrête, tout s'arrête. Les trois VM sont, elles, indépendantes.

## 5. Limites

- Mesures faites sur un seul poste portable, sous Windows, où les conteneurs ne sont pas « natifs » : ils tournent dans la VM WSL 2.
- **Démarrage des VM peu stable.** Un essai sur trois n'a pas abouti en 300 s, et les deux autres diffèrent de 20 %. Cause probable : une course au démarrage entre l'adresse réseau interne et les services, ou un arrêt forcé suivi d'une attente du chargeur de démarrage. La médiane repose donc sur deux valeurs.
- La configuration réseau des VM a été corrigée pendant les mesures, une attente DNS de 2 minutes. Les deux valeurs sont données, 193 s avant et 105 s après.
- Versions différentes : PostgreSQL 18.6 contre 16.9, Python 3.14 contre 3.12.8, gunicorn 26.2 contre 23.0, Ubuntu contre images Debian. La procédure VM ne fixait aucune version : c'est l'implicite que l'avertissement du sujet sur les images sans version explicite visait.
- Les mesures VM de l'étape 10 n'avaient pas été faites pendant la partie 2 (`recapitulatif-deploiement-planizi.md`). Elles ont été prises ici avec le même protocole que les conteneurs (`docker/mesures-vm.ps1`). Le temps de mise en place des VM depuis zéro n'a pas été chronométré.
- La matrice VM (6 cas) a été relevée à la main à partir de captures, et non par un script comme pour les conteneurs (11 cas).
- La mémoire « vue de l'hôte » d'une VM dépend de ce que le système invité a déjà touché. Elle augmenterait avec l'usage, jusqu'aux 5 120 Mio alloués.
