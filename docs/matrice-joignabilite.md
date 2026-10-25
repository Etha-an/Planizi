# Matrice de joignabilité — déploiement en conteneurs

Relevé du 2026-10-25 16:40 — 11/11 cas conformes.

Tests TCP lancés depuis un terminal ouvert dans chaque conteneur (`docker compose exec <service> bash -c "exec 3<>/dev/tcp/<cible>/<port>"`), et depuis Windows pour la ligne « hôte ».

| Depuis | Vers | Attendu | Obtenu | Détail | |
|---|---|---|---|---|---|
| L'hôte | proxy :80 | oui | oui | connexion établie (processus : wslrelay) | ✅ |
| L'hôte | metier :8000 | doit échouer | échec | refusée / aucune écoute | ✅ |
| L'hôte | donnees :5432 | doit échouer | échec | refusée / aucune écoute | ✅ |
| conteneur proxy | metier :8000 | oui | oui | connexion établie | ✅ |
| conteneur proxy | donnees :5432 | doit échouer | échec | délai dépassé (aucune route) | ✅ |
| conteneur metier | proxy :80 | oui | oui | connexion établie | ✅ |
| conteneur metier | donnees :5432 | oui | oui | connexion établie | ✅ |
| conteneur donnees | proxy :80 | doit échouer | échec | bash: line 1: proxy: Temporary failure in name resolution bash: line 1: /dev/tcp/proxy/80: Invalid argument | ✅ |
| conteneur donnees | metier :8000 | oui | oui | connexion établie | ✅ |
| conteneur proxy | donnees par IP (172.19.0.2):5432 | doit échouer | échec | délai dépassé (aucune route) | ✅ |
| conteneur donnees | proxy par IP (172.18.0.3):80 | doit échouer | échec | bash: connect: Network is unreachable bash: line 1: /dev/tcp/172.18.0.3/80: Network is unreachable | ✅ |

Ports publiés :

```
planizi-proxy-1 -> 0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
planizi-metier-1 -> 8000/tcp
planizi-donnees-1 -> 5432/tcp
```
