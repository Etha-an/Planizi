# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Planizi - couche METIER (Flask servi par gunicorn)
# Contexte de construction : la racine du depot (..), voir compose.yaml.
# Fichier d'exclusion associe : metier.Dockerfile.dockerignore
# ---------------------------------------------------------------------------

# Image officielle, version EXPLICITE (patch + variante + distribution) :
# reconstruite dans trois mois, elle contiendra exactement le meme Python.
FROM python:3.12.8-slim-bookworm

# - pas de fichiers .pyc ecrits a l'execution (le code appartient a root, lecture seule)
# - logs non bufferises (visibles tout de suite dans `docker compose logs`)
# - pip sans cache : rien d'inutile ne reste dans la couche
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Compte systeme sans privileges (ne change jamais -> couche toujours en cache)
RUN useradd --system --no-create-home --shell /usr/sbin/nologin planizi

# 2) DEPENDANCES AVANT LE CODE : cette couche n'est reconstruite que si
#    requirements.txt change. gunicorn est le serveur de production ; il est
#    ajoute ici (version epinglee) pour ne pas toucher au depot applicatif.
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn==23.0.0

# 3) Le code applicatif en dernier : une modification de app.py ne
#    reinvalide que cette couche (quelques Ko).
COPY . .

USER planizi

# Port interne uniquement (aucune publication : voir compose.yaml)
EXPOSE 8000

# Ecoute sur 0.0.0.0 : dans un conteneur c'est la bonne pratique, l'isolation
# vient de la NON-publication du port, pas de l'adresse d'ecoute.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "app:app"]
