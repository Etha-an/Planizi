# Planizi — Trois machines virtuelles face à trois conteneurs

> Les cellules `…` sont à remplir : colonne VM avec les relevés de l'étape 10, colonne conteneurs avec le rapport produit par `docker/mesures.ps1`. Les phrases marquées *(à confirmer)* sont des hypothèses à valider ou corriger une fois les chiffres en main.

## 1. Conditions de mesure

| | Trois VM (étape 10) | Trois conteneurs (étape 14) |
|---|---|---|
| Poste | … | même poste |
| Hyperviseur / moteur | VirtualBox … | Docker Desktop … (moteur …, WSL 2) |
| Ressources allouées | 3 × (… vCPU, … Mio) | VM Docker : … CPU, … Mio (`.wslconfig` : …) |
| Protocole | 3 exécutions, médiane | 3 exécutions, médiane |
| URL / requêtes (latence) | … | … |

## 2. Tableau comparatif chiffré

| Grandeur | Trois VM | Trois conteneurs | Écart |
|---|---|---|---|
| Temps de démarrage (jusqu'à la 1re réponse HTTP 200) | … s | … s | × … |
| Mémoire — charge applicative | … Mio (3 VM) | … Mio (somme `docker stats`) | × … |
| Mémoire — avec le moteur | … Mio (processus VirtualBox) | … Mio (VM `vmmemWSL`, pile lancée) | × … |
| Empreinte disque | … Gio (3 fichiers `.vdi`) | … Mio (3 images) + … Mio (volume) — disque virtuel Docker : … Gio | × … |
| Latence applicative (médiane) | … ms | … ms | … ms |
| Temps de mise en place depuis zéro | … min | … min (dont … s machine) | × … |

**Mémoire du moteur.** Sous Windows, le moteur Docker s'exécute dans une VM Linux (WSL 2). Sa consommation a été relevée via le processus `vmmemWSL`, pile lancée et pile arrêtée (… Mio sans la pile). C'est le chiffre « avec le moteur » qu'il faut comparer aux trois VM ; le chiffre `docker stats` seul favoriserait les conteneurs.

## 3. Les deux procédures côte à côte

| | Procédure VM (étape 9) | `compose.yaml` + Dockerfiles |
|---|---|---|
| Longueur | … lignes / … commandes | `compose.yaml` … lignes, Dockerfiles … lignes |
| Temps de lecture | … | … |
| Ce qui reste implicite | … (ordre des opérations, état initial des VM, paquets déjà présents…) | versions du moteur et de Compose, ressources de la VM Docker, chemin de montage des scripts SQL |
| Réseau | 2 adaptateurs « réseau interne », IP statiques, pare-feu | 2 réseaux déclarés en 5 lignes, noms de service |

## 4. Analyse

### 4.1 De combien les chiffres diffèrent

… (reprendre les écarts du tableau : ordres de grandeur, et non une liste de chiffres)

### 4.2 Quelle propriété technique explique chaque écart

- **Démarrage.** Une VM démarre un système complet (firmware, noyau, systemd, services) avant que l'application ne soit lancée. Un conteneur est un simple processus créé sur un noyau déjà en marche : il ne reste que le démarrage de PostgreSQL, de gunicorn et de nginx. *(à confirmer : écart attendu d'un ordre de grandeur)*
- **Mémoire.** Chaque VM réserve la mémoire de son système invité (noyau, cache disque, services) ; trois VM = trois noyaux. Les conteneurs partagent un seul noyau, et l'isolation passe par les espaces de nommage (ce que le processus voit) et les groupes de contrôle (ce qu'il consomme). Sous Windows, une partie de l'avantage est reprise par la VM du moteur Docker, d'où les deux lignes du tableau.
- **Disque.** Un disque de VM contient un système d'exploitation complet ; une image ne contient que les couches utiles à un processus, et les couches communes ne sont stockées qu'une fois. La taille de l'image métier (… Mio) tient à : base `slim`, fichier d'exclusion, `pip` sans cache.
- **Latence.** Le chemin réseau est comparable : un proxy, un saut vers le métier, un saut vers la base. Les deux techniques passent par un pont réseau virtuel ; l'écart attendu est faible, l'essentiel du temps est passé dans Flask et PostgreSQL. *(à confirmer)*
- **Mise en place.** Ici l'écart vient de la description déclarative : `compose.yaml` remplace l'installation des paquets, l'adressage statique, les unités systemd et l'ouverture des ports. Reconstruire ne coûte rien, donc on n'a plus besoin de snapshot.
- **Isolation réseau plus stricte.** En VM, le proxy pouvait encore atteindre la base au niveau IP ; ici, il n'a aucun réseau commun avec elle (voir `matrice-joignabilite.md`), et rien n'est joignable depuis l'hôte hormis le port 8080. L'isolation est acquise par défaut, c'est l'ouverture qui se déclare.

### 4.3 Ce que le déploiement en conteneurs a perdu

- **Une frontière d'isolation plus fine, donc plus fragile.** Le noyau étant partagé, la frontière entre conteneurs est logicielle et non matérielle : une faille du noyau ou du moteur (évasion de conteneur) touche tous les services à la fois, alors qu'une VM compromise reste confinée par l'hyperviseur. Le processus `root` d'un conteneur est le `root` du noyau hôte, d'où le compte `planizi` sans privilèges dans l'image métier.
- **Plus de système d'exploitation propre.** Impossible d'exécuter un autre système que celui de l'hôte : sous Windows, il faut justement une VM Linux pour faire tourner les conteneurs Linux.
- **Moins de contrôle sur la machine.** Pas de noyau, de modules ou de paramètres système propres à un service ; pas de systemd ; un seul processus principal par conteneur.
- **Un état éphémère.** Tout ce qui est écrit hors d'un volume disparaît à la destruction du conteneur : une modification « à la main » dans un conteneur est perdue au prochain `up`.
- **Une dépendance au moteur.** Le démon Docker (et sa VM sous Windows) devient un point unique : s'il s'arrête, les trois couches s'arrêtent ensemble.

## 5. Conclusion

… (énoncer l'écart principal, la propriété qui l'explique, et la contrepartie — sans désigner de gagnant)
