# Planizi — Injection de charge avec JMeter (étapes 15 à 18)

Toutes les commandes se lancent dans **PowerShell, depuis le dossier `charge/`**.

```
charge/
├── plan.jmx              plan de test : connexion puis « Mon planning »
├── comptes.csv           24 comptes de test (charge.01 … charge.24, mot de passe planizi123)
├── comptes-test.sql      crée ces 24 comptes et leurs shifts — à jouer sur les DEUX déploiements
├── etalonnage.jmx        plafond de l'injecteur (ressource statique du proxy)
├── etalonnage.md         rapport d'étalonnage (à compléter)
├── campagne.ps1          lance une campagne complète, palier par palier, + relevé serveur
├── releve-hote.ps1       relevé serveur vu de Windows (lancé par campagne.ps1)
├── releve-vm.sh          relevé serveur DANS une VM (E/S disque, connexions à la base)
├── analyse.py            courbes + tableaux de synthèse
└── resultats/            fichiers bruts : dk-<N>-<série>.csv, vm-<N>-<série>.csv, relevés serveur
docs/
├── charge-mesures.md     généré par analyse.py
├── charge/*.png          courbes générées par analyse.py
└── rapport-charge.md     rapport de 3 à 4 pages
```

**Le scénario.** Un utilisateur virtuel prend un compte dans `comptes.csv`, se connecte (`POST /connexion`), puis consulte « Mon planning » (`GET /planning`). C'est l'équivalent pour Planizi du parcours « se connecter, consulter ses notes » du sujet, et c'est le seul parcours qui traverse les trois couches : proxy → Flask → PostgreSQL.

| Requête | Ce qui est vérifié (assertions) |
|---|---|
| 1 - Connexion | code **302**, en-têtes `Location: /planning` et `session=` (cookie de session Flask) |
| 2 - Mon planning | code **200**, la page contient « Mon planning » et au moins un `class="shift "` |

Un mauvais mot de passe renvoie la page de connexion avec un code **200**, sans cookie : l'assertion « code 302 » échoue. Sans session, `/planning` renvoie **302** vers `/connexion` : l'assertion « code 200 » échoue. Sans assertions, ces deux échecs passeraient pour des succès.

---

## 0. Installer Java et JMeter (une seule fois)

1. **Java 17 ou plus récent.** Dans PowerShell, `java -version`. S'il est absent : installer *Eclipse Temurin 21 (LTS)* depuis adoptium.net, avec l'option « Set JAVA_HOME » cochée. Fermer puis rouvrir PowerShell.
2. **JMeter.** Télécharger **apache-jmeter-5.6.3.zip** sur jmeter.apache.org (*Download Releases → Binaries*), puis l'extraire dans **`C:\apache-jmeter-5.6.3`**. `campagne.ps1` le trouve tout seul à cet emplacement.
3. Vérifier : `C:\apache-jmeter-5.6.3\bin\jmeter.bat --version`.
4. Pour taper `jmeter` au lieu du chemin complet, dans la session PowerShell en cours :
   ```powershell
   $env:Path += ';C:\apache-jmeter-5.6.3\bin'
   ```

## 1. Préparer les comptes de test sur les deux déploiements

Les données de démonstration ne contiennent que 12 comptes actifs. On en ajoute 24, identiques des deux côtés. Chacun a un shift par jour ouvré sur la semaine en cours et la suivante, pour que « Mon planning » ne soit jamais vide le jour de la mesure.

**Conteneurs** (depuis `charge/`, la pile démarrée) :

```powershell
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
Get-Content -Raw -Encoding utf8 .\comptes-test.sql | docker compose -f ..\docker\compose.yaml exec -T donnees psql -U planizi -d planizi
```

Attendu : `comptes_de_test = 24`, `shifts_de_test = 240`.

**Machines virtuelles** : copier `comptes-test.sql` dans la VM données, puis :

```bash
psql -U <utilisateur> -d planizi -f comptes-test.sql
```

> `campagne.ps1 -Deploiement dk` réinitialise la base conteneurs (`down -v`, `up`) et rejoue ce script à chaque campagne. Côté VM, il faut rejouer à la main `schema.sql`, `donnees.sql` puis `comptes-test.sql` avant chaque campagne.

## 2. Étape 15 — Valider le plan de test

Ouvrir le plan dans l'**interface graphique**, qui ne sert qu'à construire et à valider le plan, jamais à mesurer :

```powershell
C:\apache-jmeter-5.6.3\bin\jmeter.bat -t plan.jmx
```

Par défaut, le plan joue **1 utilisateur, 1 itération** sur `localhost:8080`. Cliquer sur ▶ (Démarrer), puis ouvrir « Arbre de résultats (validation GUI) » : les deux requêtes doivent être **vertes**. 📸 Capture n° 1 : le parcours réussi.

**Le test du test** : fermer JMeter, puis le relancer avec un mot de passe forcé à une valeur fausse :

```powershell
C:\apache-jmeter-5.6.3\bin\jmeter.bat -t plan.jmx -Jmot_de_passe_force=faux
```

▶ : les deux requêtes doivent être **rouges**. La connexion renvoie « code différent de 302 », et le planning renvoie « code différent de 200 », puisqu'il n'y a pas de session. 📸 Capture n° 2 : le parcours en échec.

Pour viser les VM depuis l'interface : ajouter `-Jhote=<adresse du proxy VM> -Jport=<port>`.

Livrables : `plan.jmx`, `comptes.csv`, les deux captures.

## 3. Étape 16 — Étalonner le protocole

**a. Plafond de l'injecteur.** Pile conteneurs démarrée, VM éteintes :

```powershell
foreach ($n in 10, 50, 100) {
  C:\apache-jmeter-5.6.3\bin\jmeter.bat -n -t etalonnage.jmx -l "resultats\etalonnage-dk-$n.csv" "-Jutilisateurs=$n"
}
python analyse.py
```

`etalonnage.jmx` frappe `/static/app.css`, servi par nginx seul, sans temps de réflexion. Le débit obtenu, probablement plusieurs centaines à milliers de req/s, est le plafond de JMeter sur ton poste. Il doit être **nettement supérieur** au débit de l'application. Avec un temps de réflexion de 1 à 2 s, 100 utilisateurs produisent au plus environ 65 req/s.

**b. Paliers et durées — gelés pour toutes les campagnes :**

| Paramètre | Valeur | Raison |
|---|---|---|
| Paliers | 1, 5, 10, 25, 50, 100 (ajouter 150, 200 si rien ne sature) | progression large, comme le suggère le sujet |
| Montée | 30 s | montée progressive, exclue de la mesure |
| Plateau mesuré | 90 s | ≥ 60 s hors montée (contrainte du sujet) |
| Temps de réflexion | 1 à 2 s, aléatoire uniforme | usage réel, pas une attaque |
| Pause entre paliers | 20 s | retour au repos |

**c. Répétabilité.** Lancer **deux fois** la même campagne sur les conteneurs, puis comparer :

```powershell
powershell -ExecutionPolicy Bypass -File .\campagne.ps1 -Deploiement dk -Serie s1
powershell -ExecutionPolicy Bypass -File .\campagne.ps1 -Deploiement dk -Serie s2
python analyse.py          # section « Répétabilité » : écart ≤ 10 % attendu
```

Si l'écart dépasse 10 %, il faut d'abord stabiliser le poste (antivirus, mises à jour, navigateur ouvert…) avant de mesurer quoi que ce soit.

Compléter ensuite `etalonnage.md`.

## 4. Étape 17 — Les campagnes

**Avant tout : les mêmes réglages des deux côtés.** Noter, dans `etalonnage.md` puis dans le rapport :
- le nombre de **vCPU** et la **RAM** de chaque VM ;
- les ressources de la VM Docker (`docker info` : CPUs, Total Memory) ;
- le nombre de **processus gunicorn** (`--workers`) des deux côtés. Les deux côtés sont alignés : 2 workers, et `cpus`/`mem_limit` dans `compose.yaml` égaux aux vCPU/RAM des VM.

Si la VM métier n'a qu'un vCPU alors que Docker en voit huit, l'écart mesuré viendra de ce réglage, pas de la technique d'isolation.

**Ordre de passage :**

| Série | 1ʳᵉ campagne | 2ᵉ campagne |
|---|---|---|
| s1 | conteneurs (`-Deploiement dk -Serie s1`) | VM (`-Deploiement vm -Serie s1`) |
| s2 | VM (`-Deploiement vm -Serie s2`) | conteneurs (`-Deploiement dk -Serie s2`) |

**Campagne conteneurs** (VM éteintes) :

```powershell
powershell -ExecutionPolicy Bypass -File .\campagne.ps1 -Deploiement dk -Serie s1
```

**Campagne VM** (`docker compose down` dans `docker\`, puis démarrer les 3 VM) :
1. Dans la VM données, réinitialiser la base (schema → donnees → comptes-test), puis lancer le relevé :
   ```bash
   sudo bash releve-vm.sh donnees > vm-donnees-s1.csv
   ```
   Lancer aussi, si tu le souhaites, `bash releve-vm.sh metier > vm-metier-s1.csv` dans la VM métier.
2. Sur Windows :
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\campagne.ps1 -Deploiement vm -Serie s1 -Hote <IP du proxy> -Port <port>
   ```
3. À la fin, arrêter les relevés (Ctrl+C) et copier les fichiers `vm-*-s1.csv` dans `charge\resultats\`.

Ce que relève chaque campagne :
- **JMeter** : chaque requête, horodatée, avec sa durée, son code, son succès et le nombre d'utilisateurs actifs.
- **`releve-hote.ps1`**, toutes les 5 s :
  - le processeur de l'hôte et celui de JMeter (`java`), pour vérifier que l'injecteur n'est pas limitant ;
  - en conteneurs : processeur, mémoire et E/S disque de chaque conteneur, plus le nombre de connexions ouvertes à PostgreSQL ;
  - en VM : processeur et mémoire de chaque processus `VirtualBoxVM` (une VM = un processus), vus de Windows.
- **`releve-vm.sh`** : processeur, mémoire, E/S disque et connexions, vus de l'intérieur de la VM.

Une campagne de 6 paliers dure environ 15 minutes.

## 5. Étape 18 — Analyser

```powershell
pip install matplotlib        # inutile avec Anaconda
python analyse.py --charge-egale 25
```

Produit `docs\charge-mesures.md` : étalonnage, tableau complet par palier (débit, centiles p50/p90/p95/p99, erreurs par requête, utilisateurs effectifs), métriques serveur par palier, répétabilité, synthèse. Produit aussi les courbes `docs\charge\` : débit, latence p95, taux d'erreur, et processeur par service. Ces chiffres servent à rédiger `docs\rapport-charge.md`.

La saturation est détectée automatiquement : c'est le premier palier après lequel le débit progresse de moins de 10 % alors que le p95 augmente, ou dès que les erreurs dépassent 5 %. Elle est à confirmer en regardant les courbes. Le goulot se lit dans le tableau serveur : c'est le service dont le processeur plafonne au moment où le débit cesse de croître.
