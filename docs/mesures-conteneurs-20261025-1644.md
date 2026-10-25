# Mesures — déploiement sur trois conteneurs

Relevé du 2026-10-25 16:44. Protocole : 3 exécutions, médiane retenue.

| Grandeur | Valeur |
|---|---|
| Mise en place (téléchargement + construction + 1er démarrage) | 52.0 s |
| Temps de démarrage (up -> HTTP 200) | 5.89 s  (exécutions : 5.91 ; 5.89 ; 5.84) |
| Mémoire - somme des 3 conteneurs (docker stats) | 107.3 Mio |
| Mémoire - VM du moteur Docker, pile lancée | 3023 Mio |
| Mémoire - VM du moteur Docker, sans la pile | 2931 Mio |
| Image planizi-metier:1.0 | 202.6 Mio |
| Image planizi-proxy:1.0 | 266.5 Mio |
| Image postgres:16.9-bookworm | 588.6 Mio |
| Volume pgdata (données) | 45.9 Mio |
| Disque virtuel Docker Desktop (docker_data.vhdx) | 3.24 Gio |
| Disque virtuel Docker Desktop (ext4.vhdx) | 0.10 Gio |
| Latence applicative (médiane des médianes) | 7.57 ms |

## Configuration

- Poste : 12th Gen Intel(R) Core(TM) i7-1260P, 15.7 Gio de RAM, Microsoft Windows 11 Famille 10.0.26200
- Docker : Client 29.9.1 / Moteur 29.9.1 ; Compose 5.6.0
- Moteur : CPU allou├®s : 16 ; m├®moire allou├®e : 8172797952 octets ; noyau : 6.6.87.2-microsoft-standard-WSL2 ; OS moteur : Docker Desktop
- .wslconfig : absent (valeurs par défaut de WSL 2)
- URL mesurée : http://localhost:8080/connexion (50 requêtes par exécution)

## docker system df

```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          3         3         1.115GB   0B (0%)
Containers      3         3         114.7kB   0B (0%)
Local Volumes   1         1         48.02MB   0B (0%)
Build Cache     23        0         535.2MB   43.36MB
```
