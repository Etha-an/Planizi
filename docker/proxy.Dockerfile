# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Planizi - couche PRESENTATION (proxy inverse nginx)
# Sert les fichiers du client (static/) et renvoie le reste au service metier.
# Contexte de construction : la racine du depot (..), voir compose.yaml.
# Fichier d'exclusion associe : proxy.Dockerfile.dockerignore
# ---------------------------------------------------------------------------

# Image officielle, version explicite (variante Debian : bash et curl presents,
# utiles pour la sonde de sante et la matrice de joignabilite de l'etape 14).
FROM nginx:1.27.5-bookworm

# Configuration : remplace le site par defaut
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Fichiers du client, copies DANS l'image (pas de montage)
COPY static/ /usr/share/nginx/html/static/

EXPOSE 80
