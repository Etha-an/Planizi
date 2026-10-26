# Charge — mesures (générées par charge/analyse.py)

Fenêtre de mesure : plateau de 90 s après 30 s de montée, montée exclue. Latences en millisecondes, débits en requêtes par seconde (deux requêtes par parcours).

## Étalonnage de l'injecteur (ressource statique servie par le proxy, sans temps de réflexion)

| Déploiement | Utilisateurs | Série | Débit (req/s) | p95 (ms) | Erreurs |
|---|---|---|---|---|---|
| dk | 10 | s1 | 4 752,6 | 4 | 0,00 % |
| dk | 50 | s1 | 4 919,9 | 19 | 0,00 % |
| dk | 100 | s1 | 4 262,8 | 52 | 0,00 % |

## Trois conteneurs — série s1

| Utilisateurs | effectifs | Débit (req/s) | dont réussies | Parcours/s | p50 | p90 | p95 | p99 | Erreurs | Erreurs connexion | Erreurs planning |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 0,6 | 0,6 | 0,3 | 82 | 123 | 126 | 129 | 0,00 % | 0,00 % | 0,00 % |
| 5 | 5 | 3,2 | 3,2 | 1,6 | 85 | 122 | 128 | 135 | 0,00 % | 0,00 % | 0,00 % |
| 10 | 10 | 6,4 | 6,4 | 3,2 | 95 | 117 | 120 | 131 | 0,00 % | 0,00 % | 0,00 % |
| 25 | 25 | 15,9 | 15,9 | 8,0 | 96 | 125 | 153 | 240 | 0,00 % | 0,00 % | 0,00 % |
| 50 | 50 | 28,1 | 28,1 | 14,1 | 212 | 586 | 812 | 1 117 | 0,00 % | 0,00 % | 0,00 % |
| 75 | 75 | 29,8 | 29,8 | 14,9 | 957 | 1 402 | 1 515 | 1 740 | 0,00 % | 0,00 % | 0,00 % |
| 100 | 100 | 31,6 | 31,6 | 15,8 | 1 599 | 1 954 | 2 215 | 3 193 | 0,00 % | 0,00 % | 0,00 % |
| 150 | 150 | 32,9 | 32,9 | 16,4 | 3 060 | 3 323 | 3 374 | 3 456 | 0,00 % | 0,00 % | 0,00 % |
| 200 | 200 | 32,8 | 32,8 | 16,3 | 4 612 | 4 993 | 5 064 | 5 172 | 0,00 % | 0,00 % | 0,00 % |

Latence p95 par requête (ms) :

| Utilisateurs | 1 - Connexion | 2 - Mon planning |
|---|---|---|
| 1 | 127 | 58 |
| 5 | 131 | 57 |
| 10 | 126 | 53 |
| 25 | 175 | 97 |
| 50 | 820 | 790 |
| 75 | 1 538 | 1 454 |
| 100 | 2 247 | 2 181 |
| 150 | 3 403 | 3 342 |
| 200 | 5 087 | 5 037 |

Côté serveur, moyenne sur le plateau (CPU en % d'un cœur, sauf « dans la VM » : % de la VM) :

| Utilisateurs | donnees | donnees-connexions | hote | jmeter | metier | proxy |
|---|---|---|---|---|---|---|
| 1 | CPU 3 % · 37 Mio · E/S 0,00/0,00 Mio/s | 0,0 cnx (max 0) | CPU 107 % | CPU 1 % · 219 Mio | CPU 13 % · 56 Mio · E/S 0,00/0,00 Mio/s | CPU 0 % · 14 Mio · E/S 0,00/0,00 Mio/s |
| 5 | CPU 6 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,0 cnx (max 0) | CPU 141 % | CPU 2 % · 223 Mio | CPU 25 % · 60 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 14 Mio · E/S 0,00/0,00 Mio/s |
| 10 | CPU 9 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 105 % | CPU 2 % · 226 Mio | CPU 43 % · 66 Mio · E/S 0,00/0,00 Mio/s | CPU 3 % · 15 Mio · E/S 0,00/0,00 Mio/s |
| 25 | CPU 21 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,0 cnx (max 0) | CPU 212 % | CPU 3 % · 239 Mio | CPU 92 % · 71 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 15 Mio · E/S 0,00/0,00 Mio/s |
| 50 | CPU 32 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 373 % | CPU 5 % · 268 Mio | CPU 163 % · 91 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 16 Mio · E/S 0,00/0,00 Mio/s |
| 75 | CPU 32 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 394 % | CPU 4 % · 279 Mio | CPU 177 % · 99 Mio · E/S 0,00/0,00 Mio/s | CPU 2 % · 17 Mio · E/S 0,00/0,00 Mio/s |
| 100 | CPU 35 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,2 cnx (max 1) | CPU 338 % | CPU 4 % · 299 Mio | CPU 175 % · 100 Mio · E/S 0,00/0,00 Mio/s | CPU 3 % · 17 Mio · E/S 0,00/0,00 Mio/s |
| 150 | CPU 32 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 242 % | CPU 4 % · 322 Mio | CPU 176 % · 104 Mio · E/S 0,00/0,00 Mio/s | CPU 3 % · 18 Mio · E/S 0,00/0,00 Mio/s |
| 200 | CPU 33 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 230 % | CPU 5 % · 316 Mio | CPU 172 % · 96 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 18 Mio · E/S 0,00/0,00 Mio/s |

## Trois conteneurs — série s2

| Utilisateurs | effectifs | Débit (req/s) | dont réussies | Parcours/s | p50 | p90 | p95 | p99 | Erreurs | Erreurs connexion | Erreurs planning |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 0,6 | 0,6 | 0,3 | 102 | 127 | 130 | 136 | 0,00 % | 0,00 % | 0,00 % |
| 5 | 5 | 3,1 | 3,1 | 1,6 | 96 | 122 | 127 | 140 | 0,00 % | 0,00 % | 0,00 % |
| 10 | 10 | 6,4 | 6,4 | 3,2 | 94 | 120 | 125 | 148 | 0,00 % | 0,00 % | 0,00 % |
| 25 | 25 | 15,6 | 15,6 | 7,8 | 96 | 141 | 170 | 233 | 0,00 % | 0,00 % | 0,00 % |
| 50 | 50 | 30,2 | 30,2 | 15,1 | 160 | 329 | 377 | 458 | 0,00 % | 0,00 % | 0,00 % |
| 75 | 75 | 32,7 | 32,7 | 16,3 | 796 | 1 034 | 1 121 | 1 276 | 0,00 % | 0,00 % | 0,00 % |
| 100 | 100 | 33,0 | 33,0 | 16,5 | 1 523 | 1 798 | 1 867 | 1 958 | 0,00 % | 0,00 % | 0,00 % |
| 150 | 150 | 32,9 | 32,9 | 16,5 | 3 040 | 3 444 | 3 502 | 3 618 | 0,00 % | 0,00 % | 0,00 % |
| 200 | 200 | 32,9 | 32,9 | 16,5 | 4 589 | 4 816 | 4 877 | 5 065 | 0,00 % | 0,00 % | 0,00 % |

Latence p95 par requête (ms) :

| Utilisateurs | 1 - Connexion | 2 - Mon planning |
|---|---|---|
| 1 | 131 | 52 |
| 5 | 138 | 53 |
| 10 | 132 | 52 |
| 25 | 188 | 110 |
| 50 | 404 | 329 |
| 75 | 1 144 | 1 084 |
| 100 | 1 891 | 1 838 |
| 150 | 3 529 | 3 475 |
| 200 | 4 903 | 4 844 |

Côté serveur, moyenne sur le plateau (CPU en % d'un cœur, sauf « dans la VM » : % de la VM) :

| Utilisateurs | donnees | donnees-connexions | hote | jmeter | metier | proxy |
|---|---|---|---|---|---|---|
| 1 | CPU 1 % · 37 Mio · E/S 0,00/0,01 Mio/s | 0,0 cnx (max 0) | CPU 124 % | CPU 1 % · 221 Mio | CPU 6 % · 56 Mio · E/S 0,00/0,00 Mio/s | CPU 0 % · 13 Mio · E/S 0,00/0,00 Mio/s |
| 5 | CPU 9 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,0 cnx (max 0) | CPU 120 % | CPU 2 % · 222 Mio | CPU 25 % · 58 Mio · E/S 0,00/0,00 Mio/s | CPU 0 % · 14 Mio · E/S 0,00/0,00 Mio/s |
| 10 | CPU 10 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,0 cnx (max 0) | CPU 148 % | CPU 3 % · 225 Mio | CPU 42 % · 63 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 14 Mio · E/S 0,00/0,00 Mio/s |
| 25 | CPU 21 % · 38 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 227 % | CPU 3 % · 238 Mio | CPU 85 % · 65 Mio · E/S 0,00/0,00 Mio/s | CPU 2 % · 15 Mio · E/S 0,00/0,00 Mio/s |
| 50 | CPU 28 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 251 % | CPU 4 % · 268 Mio | CPU 150 % · 92 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 15 Mio · E/S 0,00/0,00 Mio/s |
| 75 | CPU 34 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,2 cnx (max 1) | CPU 277 % | CPU 4 % · 272 Mio | CPU 175 % · 92 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 16 Mio · E/S 0,00/0,00 Mio/s |
| 100 | CPU 36 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,0 cnx (max 0) | CPU 265 % | CPU 4 % · 295 Mio | CPU 173 % · 95 Mio · E/S 0,00/0,00 Mio/s | CPU 1 % · 17 Mio · E/S 0,00/0,00 Mio/s |
| 150 | CPU 34 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 277 % | CPU 4 % · 320 Mio | CPU 174 % · 95 Mio · E/S 0,00/0,00 Mio/s | CPU 4 % · 18 Mio · E/S 0,00/0,00 Mio/s |
| 200 | CPU 34 % · 39 Mio · E/S 0,00/0,00 Mio/s | 0,1 cnx (max 1) | CPU 252 % | CPU 5 % · 342 Mio | CPU 173 % · 105 Mio · E/S 0,00/0,00 Mio/s | CPU 3 % · 18 Mio · E/S 0,00/0,00 Mio/s |

## Trois machines virtuelles — série s1

| Utilisateurs | effectifs | Débit (req/s) | dont réussies | Parcours/s | p50 | p90 | p95 | p99 | Erreurs | Erreurs connexion | Erreurs planning |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 0,6 | 0,6 | 0,3 | 232 | 272 | 298 | 393 | 0,00 % | 0,00 % | 0,00 % |
| 5 | 5 | 2,8 | 2,8 | 1,4 | 231 | 322 | 371 | 469 | 0,00 % | 0,00 % | 0,00 % |
| 10 | 10 | 5,7 | 5,7 | 2,8 | 242 | 391 | 456 | 597 | 0,00 % | 0,00 % | 0,00 % |
| 25 | 25 | 10,0 | 10,0 | 5,0 | 1 014 | 1 269 | 1 353 | 1 493 | 0,00 % | 0,00 % | 0,00 % |
| 50 | 50 | 9,9 | 9,9 | 4,9 | 3 568 | 3 881 | 3 957 | 4 081 | 0,00 % | 0,00 % | 0,00 % |
| 75 | 75 | 9,9 | 9,9 | 4,9 | 6 103 | 6 492 | 6 589 | 6 798 | 0,00 % | 0,00 % | 0,00 % |
| 100 | 100 | 10,2 | 10,2 | 5,0 | 8 315 | 8 627 | 8 733 | 8 881 | 0,00 % | 0,00 % | 0,00 % |
| 150 | 150 | 10,1 | 10,1 | 5,0 | 13 477 | 13 943 | 14 067 | 14 303 | 0,00 % | 0,00 % | 0,00 % |
| 200 | 200 | 9,8 | 9,8 | 4,8 | 18 837 | 19 459 | 19 607 | 19 791 | 0,00 % | 0,00 % | 0,00 % |

Latence p95 par requête (ms) :

| Utilisateurs | 1 - Connexion | 2 - Mon planning |
|---|---|---|
| 1 | 345 | 243 |
| 5 | 414 | 363 |
| 10 | 489 | 394 |
| 25 | 1 336 | 1 355 |
| 50 | 3 979 | 3 921 |
| 75 | 6 682 | 6 538 |
| 100 | 8 760 | 8 696 |
| 150 | 14 085 | 14 036 |
| 200 | 19 594 | 19 607 |

Côté serveur, moyenne sur le plateau (CPU en % d'un cœur, sauf « dans la VM » : % de la VM) :

| Utilisateurs | hote | jmeter | vm-donnees | vm-metier | vm-proxy |
|---|---|---|---|---|---|
| 1 | CPU 230 % | CPU 1 % · 220 Mio | CPU 13 % · 206 Mio | CPU 8 % · 242 Mio | CPU 22 % · 152 Mio |
| 5 | CPU 348 % | CPU 2 % · 215 Mio | CPU 21 % · 154 Mio | CPU 22 % · 202 Mio | CPU 21 % · 121 Mio |
| 10 | CPU 348 % | CPU 3 % · 224 Mio | CPU 29 % · 135 Mio | CPU 36 % · 172 Mio | CPU 21 % · 107 Mio |
| 25 | CPU 397 % | CPU 3 % · 236 Mio | CPU 36 % · 140 Mio | CPU 54 % · 173 Mio | CPU 20 % · 128 Mio |
| 50 | CPU 361 % | CPU 3 % · 245 Mio | CPU 37 % · 142 Mio | CPU 54 % · 175 Mio | CPU 20 % · 128 Mio |
| 75 | CPU 431 % | CPU 3 % · 249 Mio | CPU 36 % · 144 Mio | CPU 53 % · 177 Mio | CPU 19 % · 278 Mio |
| 100 | CPU 441 % | CPU 3 % · 252 Mio | CPU 36 % · 145 Mio | CPU 53 % · 177 Mio | CPU 19 % · 278 Mio |
| 150 | CPU 446 % | CPU 3 % · 273 Mio | CPU 36 % · 145 Mio | CPU 54 % · 177 Mio | CPU 19 % · 279 Mio |
| 200 | CPU 394 % | CPU 3 % · 291 Mio | CPU 37 % · 134 Mio | CPU 54 % · 180 Mio | CPU 20 % · 274 Mio |

## Trois machines virtuelles — série s2

| Utilisateurs | effectifs | Débit (req/s) | dont réussies | Parcours/s | p50 | p90 | p95 | p99 | Erreurs | Erreurs connexion | Erreurs planning |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 0,6 | 0,6 | 0,3 | 234 | 273 | 286 | 341 | 0,00 % | 0,00 % | 0,00 % |
| 5 | 5 | 2,9 | 2,9 | 1,4 | 233 | 313 | 354 | 441 | 0,00 % | 0,00 % | 0,00 % |
| 10 | 10 | 5,6 | 5,6 | 2,8 | 236 | 376 | 413 | 532 | 0,00 % | 0,00 % | 0,00 % |
| 25 | 25 | 10,1 | 10,1 | 5,1 | 958 | 1 240 | 1 316 | 1 487 | 0,00 % | 0,00 % | 0,00 % |
| 50 | 50 | 10,3 | 10,3 | 5,1 | 3 353 | 3 752 | 3 868 | 4 040 | 0,00 % | 0,00 % | 0,00 % |
| 75 | 75 | 10,1 | 10,1 | 5,1 | 5 912 | 6 242 | 6 358 | 6 631 | 0,00 % | 0,00 % | 0,00 % |
| 100 | 100 | 10,3 | 10,3 | 5,1 | 8 229 | 8 627 | 8 730 | 8 886 | 0,00 % | 0,00 % | 0,00 % |
| 150 | 150 | 10,2 | 10,2 | 5,1 | 13 242 | 13 615 | 13 701 | 13 903 | 0,00 % | 0,00 % | 0,00 % |
| 200 | 200 | 10,1 | 10,1 | 4,9 | 18 317 | 18 989 | 19 088 | 19 255 | 0,00 % | 0,00 % | 0,00 % |

Latence p95 par requête (ms) :

| Utilisateurs | 1 - Connexion | 2 - Mon planning |
|---|---|---|
| 1 | 273 | 290 |
| 5 | 389 | 325 |
| 10 | 425 | 384 |
| 25 | 1 374 | 1 268 |
| 50 | 3 928 | 3 809 |
| 75 | 6 402 | 6 318 |
| 100 | 8 749 | 8 689 |
| 150 | 13 728 | 13 648 |
| 200 | 19 173 | 19 062 |

Côté serveur, moyenne sur le plateau (CPU en % d'un cœur, sauf « dans la VM » : % de la VM) :

| Utilisateurs | hote | jmeter | vm-donnees | vm-metier | vm-proxy |
|---|---|---|---|---|---|
| 1 | CPU 226 % | CPU 0 % · 218 Mio | CPU 12 % · 137 Mio | CPU 8 % · 181 Mio | CPU 23 % · 282 Mio |
| 5 | CPU 270 % | CPU 2 % · 222 Mio | CPU 20 % · 137 Mio | CPU 22 % · 181 Mio | CPU 22 % · 283 Mio |
| 10 | CPU 332 % | CPU 3 % · 226 Mio | CPU 28 % · 137 Mio | CPU 37 % · 183 Mio | CPU 21 % · 283 Mio |
| 25 | CPU 393 % | CPU 3 % · 237 Mio | CPU 36 % · 139 Mio | CPU 54 % · 184 Mio | CPU 20 % · 283 Mio |
| 50 | CPU 401 % | CPU 3 % · 243 Mio | CPU 36 % · 135 Mio | CPU 55 % · 176 Mio | CPU 19 % · 283 Mio |
| 75 | CPU 420 % | CPU 3 % · 250 Mio | CPU 36 % · 137 Mio | CPU 54 % · 183 Mio | CPU 20 % · 283 Mio |
| 100 | CPU 411 % | CPU 3 % · 253 Mio | CPU 35 % · 139 Mio | CPU 54 % · 184 Mio | CPU 19 % · 284 Mio |
| 150 | CPU 388 % | CPU 3 % · 260 Mio | CPU 35 % · 141 Mio | CPU 54 % · 184 Mio | CPU 20 % · 284 Mio |
| 200 | CPU 423 % | CPU 3 % · 306 Mio | CPU 34 % · 141 Mio | CPU 55 % · 184 Mio | CPU 20 % · 285 Mio |

## Répétabilité

| Déploiement | Utilisateurs | Séries | Débit réussi (req/s) | Écart | p95 (ms) | Écart | |
|---|---|---|---|---|---|---|---|
| dk | 1 | s1 / s2 | 0,6 / 0,6 | 1,8 % | 126 / 130 | 3,2 % | ok |
| dk | 5 | s1 / s2 | 3,2 / 3,1 | 0,1 % | 128 / 127 | 0,7 % | ok |
| dk | 10 | s1 / s2 | 6,4 / 6,4 | 0,1 % | 120 / 125 | 4,2 % | ok |
| dk | 25 | s1 / s2 | 15,9 / 15,6 | 1,9 % | 153 / 170 | 10,9 % | ok |
| dk | 50 | s1 / s2 | 28,1 / 30,2 | 7,2 % | 812 / 377 | 53,6 % | ok |
| dk | 75 | s1 / s2 | 29,8 / 32,7 | 9,7 % | 1 515 / 1 121 | 26,0 % | ok |
| dk | 100 | s1 / s2 | 31,6 / 33,0 | 4,4 % | 2 215 / 1 867 | 15,7 % | ok |
| dk | 150 | s1 / s2 | 32,9 / 32,9 | 0,2 % | 3 374 / 3 502 | 3,8 % | ok |
| dk | 200 | s1 / s2 | 32,8 / 32,9 | 0,5 % | 5 064 / 4 877 | 3,7 % | ok |
| vm | 1 | s1 / s2 | 0,6 / 0,6 | 4,0 % | 298 / 286 | 4,0 % | ok |
| vm | 5 | s1 / s2 | 2,8 / 2,9 | 2,0 % | 371 / 354 | 4,6 % | ok |
| vm | 10 | s1 / s2 | 5,7 / 5,6 | 0,8 % | 456 / 413 | 9,5 % | ok |
| vm | 25 | s1 / s2 | 10,0 / 10,1 | 1,2 % | 1 353 / 1 316 | 2,7 % | ok |
| vm | 50 | s1 / s2 | 9,9 / 10,3 | 4,5 % | 3 957 / 3 868 | 2,2 % | ok |
| vm | 75 | s1 / s2 | 9,9 / 10,1 | 2,5 % | 6 589 / 6 358 | 3,5 % | ok |
| vm | 100 | s1 / s2 | 10,2 / 10,3 | 1,4 % | 8 733 / 8 730 | 0,0 % | ok |
| vm | 150 | s1 / s2 | 10,1 / 10,2 | 0,8 % | 14 067 / 13 701 | 2,6 % | ok |
| vm | 200 | s1 / s2 | 9,8 / 10,1 | 2,9 % | 19 607 / 19 088 | 2,6 % | ok |

## Synthèse (série s1)

| Grandeur | Trois machines virtuelles | Trois conteneurs |
|---|---|---|
| Débit maximal soutenu (req/s réussies) | 10,2 | 32,9 |
| Charge au point de saturation (utilisateurs) | entre 10 et 25 (efficacité à 25 : 71 %) | entre 25 et 50 (efficacité à 50 : 88 %) |
| Latence p95 à charge égale (25 utilisateurs) | 1 353 ms | 153 ms |
| Goulot d'étranglement identifié | candidat : vm-metier (CPU 54 % d'un cœur) | candidat : metier (CPU 163 % d'un cœur) |

Efficacité = débit mesuré / débit attendu si chaque utilisateur était servi aussi vite qu'à faible charge. Un palier est saturé sous 90 % d'efficacité ou au-delà de 5 % d'erreurs. À confirmer sur les courbes.

Efficacité par palier (Trois machines virtuelles) : 1 → 100 % · 5 → 100 % · 10 → 100 % · 25 → 71 % · 50 → 35 % · 75 → 23 % · 100 → 18 % · 150 → 12 % · 200 → 9 %
Efficacité par palier (Trois conteneurs) : 1 → 100 % · 5 → 98 % · 10 → 101 % · 25 → 100 % · 50 → 88 % · 75 → 62 % · 100 → 49 % · 150 → 34 % · 200 → 26 %
