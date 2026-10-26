#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Planizi - exemples de requêtes (livrable de l'étape 4)
#
# Chaque ligne envoie une requête avec curl et affiche le code HTTP reçu
# (et la page vers laquelle le serveur redirige, le cas échéant).
# La session est gardée dans un fichier « cookies », comme le ferait un navigateur.
#
# Usage (Git Bash, ou terminal Linux) :
#     bash requetes.sh                          # application sur http://localhost:8080
#     bash requetes.sh http://127.0.0.1:5000    # application lancée avec « python app.py »
#
# Comptes de démonstration (mot de passe planizi123) :
#     l.martin       employé
#     e.renucci      manager des équipes Accueil (95) et Support client (97)
#     admin.planizi  superviseur
#     g.morillon     compte en attente de validation
# ---------------------------------------------------------------------------
BASE="${1:-http://localhost:8080}"
MDP="planizi123"
EMP=$(mktemp); MAN=$(mktemp); SUP=$(mktemp)
trap 'rm -f "$EMP" "$MAN" "$SUP"' EXIT

# Affiche « code -> redirection »
req() { curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$@"; }
ligne() { printf '  %-62s %s\n' "$1" "$2"; }
# Affiche le message d'erreur contenu dans la page renvoyée
message() { curl -s "$@" | grep -o -E 'Login ou mot de passe incorrect\.|Votre compte est en attente[^<]*|Les mots de passe ne correspondent pas\.|Cet email est déjà utilisé\.' | head -1; }

echo "== Pages publiques"
ligne "GET  /                  (sans session -> connexion)"          "$(req "$BASE/")"
ligne "GET  /connexion          (formulaire)"                        "$(req "$BASE/connexion")"
ligne "GET  /inscription        (formulaire)"                        "$(req "$BASE/inscription")"
ligne "GET  /planning           (sans session -> connexion)"         "$(req "$BASE/planning")"
ligne "GET  /page-inexistante   (404)"                               "$(req "$BASE/page-inexistante")"

echo "== Connexion : cas d'erreur"
ligne "POST /connexion  mot de passe erroné"        "$(message -d "login=l.martin&mot_de_passe=faux" "$BASE/connexion")"
ligne "POST /connexion  identifiant inconnu"        "$(message -d "login=inconnu&mot_de_passe=$MDP" "$BASE/connexion")"
ligne "POST /connexion  compte en attente"          "$(message -d "login=g.morillon&mot_de_passe=$MDP" "$BASE/connexion")"

echo "== Inscription : contrôles côté serveur (aucun compte créé)"
ligne "POST /creer-compte  mots de passe différents" "$(message -d "nom=Test&prenom=Paul&email=paul.test@planizi.test&mot_de_passe=a1&mot_de_passe_confirmation=a2" "$BASE/creer-compte")"
ligne "POST /creer-compte  email déjà utilisé"       "$(message -d "nom=Test&prenom=Paul&email=lea.martin@planizi.fr&mot_de_passe=a1&mot_de_passe_confirmation=a1" "$BASE/creer-compte")"

echo "== Employé (l.martin)"
ligne "POST /connexion                 -> Mon planning"          "$(req -c "$EMP" -d "login=l.martin&mot_de_passe=$MDP" "$BASE/connexion")"
ligne "GET  /planning                  (écran 3)"                "$(req -b "$EMP" "$BASE/planning")"
ligne "GET  /planning?semaine=2026-10-19  (une autre semaine)"   "$(req -b "$EMP" "$BASE/planning?semaine=2026-10-19")"
ligne "GET  /equipes                   (réservé aux managers)"   "$(req -b "$EMP" "$BASE/equipes")"
ligne "GET  /valider-compte            (réservé au superviseur)" "$(req -b "$EMP" "$BASE/valider-compte")"
ligne "GET  /deconnexion"                                        "$(req -b "$EMP" -c "$EMP" "$BASE/deconnexion")"
ligne "GET  /planning  après déconnexion"                        "$(req -b "$EMP" "$BASE/planning")"

echo "== Manager (e.renucci)"
ligne "POST /connexion                 -> Mes équipes"           "$(req -c "$MAN" -d "login=e.renucci&mot_de_passe=$MDP" "$BASE/connexion")"
ligne "GET  /equipes                   (écran 4)"                "$(req -b "$MAN" "$BASE/equipes")"
ligne "GET  /equipes/95                (son équipe : écran 5)"   "$(req -b "$MAN" "$BASE/equipes/95")"
ligne "GET  /equipes/96                (équipe d'un autre manager)" "$(req -b "$MAN" "$BASE/equipes/96")"
ligne "GET  /planning                  (son propre planning)"    "$(req -b "$MAN" "$BASE/planning")"
ligne "GET  /utilisateurs              (réservé au superviseur)" "$(req -b "$MAN" "$BASE/utilisateurs")"

echo "== Superviseur (admin.planizi)"
ligne "POST /connexion                 -> Validation"            "$(req -c "$SUP" -d "login=admin.planizi&mot_de_passe=$MDP" "$BASE/connexion")"
ligne "GET  /valider-compte            (écran 6)"                "$(req -b "$SUP" "$BASE/valider-compte")"
ligne "GET  /utilisateurs              (écran 6 bis)"            "$(req -b "$SUP" "$BASE/utilisateurs")"

# Routes qui MODIFIENT la base : laissées en commentaire pour ne rien changer par mégarde.
#   Créer un compte (en attente de validation) :
#     curl -d "nom=Durand&prenom=Alice&email=alice.durand@planizi.test&mot_de_passe=secret&mot_de_passe_confirmation=secret" "$BASE/creer-compte"
#   Valider un compte (superviseur) :
#     curl -b "$SUP" -d "user_id=455&action=valider&poste=Agent&contrat=35" "$BASE/valider-compte"
#   Créer une équipe (manager) :
#     curl -b "$MAN" -d "nom=Nouvelle équipe&membres=446" "$BASE/equipes/creer"
