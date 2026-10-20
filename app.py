from flask import Flask, render_template, request, redirect, session, flash, abort, url_for
from functools import wraps
import json
import database
import planning_db
import os
from dotenv import load_dotenv

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")


# --- Contrôles d'accès ---

def login_requis(vue):
    @wraps(vue)
    def verifiee(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/connexion')
        return vue(*args, **kwargs)
    return verifiee

def manager_requis(vue):
    @wraps(vue)
    def verifiee(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/connexion')
        if not session.get('role_manager'):
            abort(403)
        return vue(*args, **kwargs)
    return verifiee

def superviseur_requis(vue):
    @wraps(vue)
    def verifiee(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/connexion')
        if not session.get('role_supervisor'):
            abort(403)
        return vue(*args, **kwargs)
    return verifiee

@app.before_request
def rafraichir_session():
    """Relit rôles et état du compte à chaque requête : un changement fait par le superviseur
    (rôle retiré, compte désactivé ou supprimé) s'applique immédiatement, sans reconnexion."""
    if 'user_id' not in session or request.endpoint == 'static':
        return
    compte = database.roles_utilisateur(session['user_id'])
    if not compte or not compte['valid']:
        session.clear()
        return
    session['prenom'] = compte['prenom']
    session['initiales'] = compte['prenom'][:1] + compte['nom'][:1]
    session['role_manager'] = compte['manager']
    session['role_supervisor'] = compte['supervisor']

# Couleur de chaque utilisateur, utilisable dans tous les templates (barre du haut, équipes, écran 5)
app.jinja_env.globals['couleur_utilisateur'] = planning_db.couleur_utilisateur

def page_du_role():
    """Écran 6 (Validation) pour un superviseur, écran 4 (Mes équipes) pour un manager, écran 3 (Mon planning) sinon."""
    if session.get('role_supervisor'):
        return '/valider-compte'
    return '/equipes' if session.get('role_manager') else '/planning'


@app.route('/')
def accueil():
    if 'user_id' not in session:
        return redirect('/connexion')
    return redirect(page_du_role())

@app.route('/inscription')
def page_inscription():
    return render_template('inscription.html')

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        login_saisi = request.form['login']
        mdp_saisi = request.form['mot_de_passe']

        # On interroge notre base de données
        resultat = database.verifier_connexion(login_saisi, mdp_saisi)

        if resultat['succes'] == True:
            # CONNEXION RÉUSSIE : Création du cookie de session
            user = resultat['utilisateur']
            session.clear()
            session['user_id'] = user['id']
            session['prenom'] = user['prenom']
            session['role_manager'] = user['manager']
            session['role_supervisor'] = user['supervisor']

            # Écran 3 si employé, écran 4 si manager
            return redirect(page_du_role())
        else:
            # ECHEC : On recharge la page en affichant l'erreur (étape 1, 2 ou 3)
            return render_template('connexion.html', erreur_msg=resultat['erreur'])

    # Mode GET classique (affichage du formulaire)
    return render_template('connexion.html', inscrit=request.args.get('inscrit'))


@app.route('/deconnexion')
def deconnexion():
    session.clear() # On détruit le cookie de session !
    return redirect('/connexion')

@app.route('/creer-compte', methods=['POST'])
def creer_compte():
    # 1. Le déclencheur est activé ! On récupère toutes les données du formulaire
    nom_saisi = request.form['nom'].strip()
    prenom_saisi = request.form['prenom'].strip()
    email_saisi = request.form['email'].strip()
    mdp_saisi = request.form['mot_de_passe']
    mdp_confirm = request.form['mot_de_passe_confirmation']

    # 2. On revérifie côté serveur (le JS de la page peut être contourné)
    if not (nom_saisi and prenom_saisi and email_saisi and mdp_saisi):
        return render_template('inscription.html', erreur_msg="Tous les champs doivent être remplis.")
    if mdp_saisi != mdp_confirm:
        return render_template('inscription.html', erreur_msg="Les mots de passe ne correspondent pas.")

    # 3. On envoie tout ça à notre fichier database.py pour le traitement
    resultat = database.ajouter_utilisateur(nom_saisi, prenom_saisi, email_saisi, mdp_saisi)
    if not resultat['succes']:
        return render_template('inscription.html', erreur_msg=resultat['erreur'])

    # 4. Retour à l'écran de connexion, avec l'identifiant généré
    return redirect(url_for('connexion', inscrit=resultat['login']))

@app.route('/valider-compte', methods=['GET', 'POST'])
@superviseur_requis
def valider_compte():
    if request.method == 'POST':
        # 1. On récupère l'ID caché et l'action du bouton
        user_id = request.form['user_id']
        action = request.form['action']

        # 2. On choisit la bonne fonction selon le bouton cliqué
        if action == 'valider':
            # 1. On récupère les nouvelles données
            poste = request.form.get('poste')
            contrat = request.form.get('contrat')

            # Si la case est cochée, on met 1, sinon 0
            manager = 1 if request.form.get('manager') else 0
            supervisor = 1 if request.form.get('supervisor') else 0

            # 2. On envoie tout à la base de données
            database.valider_utilisateur(user_id, poste, contrat, manager, supervisor)
        elif action == 'refuser':
            database.refuser_utilisateur(user_id)

        # 3. On redirige vers la même page pour continuer à valider le reste de la liste !
        return redirect('/valider-compte')

    utilisateurs = database.utilisateurs_non_valide()

    return render_template('validation.html', donnees_validation=utilisateurs)


# --- Écran 6 bis : onglet Utilisateurs du superviseur ---

@app.route('/utilisateurs')
@superviseur_requis
def utilisateurs():
    return render_template('utilisateurs.html',
                           utilisateurs=database.utilisateurs_valides(),
                           message_ok=request.args.get('ok'),
                           message_erreur=request.args.get('erreur'))

@app.route('/utilisateurs/<int:user_id>', methods=['POST'])
@superviseur_requis
def modifier_utilisateur(user_id):
    soi_meme = user_id == session['user_id']
    retour = lambda **message: redirect(url_for('utilisateurs', **message))

    if request.form.get('action') == 'desactiver':
        if soi_meme:
            return retour(erreur="Vous ne pouvez pas désactiver votre propre compte.")
        database.desactiver_utilisateur(user_id)
        return retour(ok="Compte désactivé : il est de nouveau en attente dans l'onglet Validation.")

    champs = {cle: request.form.get(cle, '').strip() for cle in ('nom', 'prenom', 'email', 'login', 'poste', 'contrat')}
    if not (champs['nom'] and champs['prenom'] and champs['email'] and champs['login']):
        return retour(erreur="Nom, prénom, email et login sont obligatoires.")
    if len(champs['poste']) > 100:
        return retour(erreur="Le poste ne doit pas dépasser 100 caractères.")
    contrat = None
    if champs['contrat']:
        if not champs['contrat'].isdigit() or not 0 <= int(champs['contrat']) <= 60:
            return retour(erreur="Le contrat doit être un nombre d'heures entre 0 et 60.")
        contrat = int(champs['contrat'])

    supervisor = 1 if request.form.get('supervisor') else 0
    if soi_meme and not supervisor:
        return retour(erreur="Vous ne pouvez pas retirer votre propre rôle de superviseur.")

    resultat = database.modifier_utilisateur(
        user_id, champs['nom'], champs['prenom'], champs['email'], champs['login'].lower(),
        champs['poste'] or None, contrat,
        1 if request.form.get('manager') else 0, supervisor,
        request.form.get('nouveau_mdp') or None,
    )
    if not resultat['succes']:
        return retour(erreur=resultat['erreur'])
    return retour(ok=f"{champs['prenom']} {champs['nom']} a été mis à jour.")


# --- Écran 3 : planning de l'employé connecté ---

@app.route('/planning')
@login_requis
def planning():
    lundi = planning_db.lundi_de(request.args.get('semaine'))
    utilisateur = planning_db.recuperer_utilisateur(session['user_id'])
    if not utilisateur:
        # Compte supprimé depuis la connexion
        session.clear()
        return redirect('/connexion')
    # Tout ce qui chevauche la semaine est affiché (une nuit commencée dimanche dernier compris),
    # mais seuls les shifts qui commencent dans la semaine comptent dans le total.
    lignes = planning_db.shifts_visibles_semaine(session['user_id'], lundi)
    segments = planning_db.decouper_par_jour(lignes, lundi)
    shifts = [planning_db.formater_shift(l) for l in lignes if l['debut'].date() >= lundi]
    total = sum(s['duree'] for s in shifts)
    plage_debut, plage_fin = planning_db.plage_horaire(segments)

    return render_template(
        'planning.html',
        page='planning',
        utilisateur=utilisateur,
        semaine=planning_db.infos_semaine(lundi),
        segments=segments,
        nb_shifts=len(shifts),
        total=planning_db.format_heures(total),
        taux=min(100, round(100 * total / utilisateur['contrat'])) if utilisateur['contrat'] else 0,
        jours_travailles=len({s['jour'] for s in segments}),
        # Légende : types de base + types personnalisés présents dans la semaine, triés ensemble
        legende=sorted({(c, planning_db.classe_categorie(c)) for c in planning_db.CATEGORIES}
                       | {(s['categorie'], s['classe']) for s in segments},
                       key=lambda t: planning_db.cle_tri(t[0])),
        plage_debut=plage_debut,
        heures=range(plage_debut, plage_fin),
        # Grille plus compacte quand la plage est large (shifts de nuit)
        hauteur_heure=30 if plage_fin - plage_debut > 15 else 44,
    )


# --- Écran 4 : équipes du manager ---

@app.route('/equipes')
@manager_requis
def equipes():
    lundi = planning_db.lundi_de(request.args.get('semaine'))
    mes_equipes = planning_db.equipes_du_manager(session['user_id'], lundi)
    for equipe in mes_equipes:
        equipe['planifie_txt'] = planning_db.format_heures(equipe['heures_planifiees'])
        equipe['contrat_txt'] = planning_db.format_heures(equipe['heures_contrat'])
        equipe['taux'] = min(100, round(100 * equipe['heures_planifiees'] / equipe['heures_contrat'])) if equipe['heures_contrat'] else 0

    return render_template('equipes.html', page='equipes', equipes=mes_equipes,
                           employes=planning_db.membres_disponibles(session['user_id']),
                           semaine=planning_db.infos_semaine(lundi))


def lire_formulaire_equipe():
    """Nom et membres envoyés par la fenêtre de création / modification d'équipe."""
    nom = request.form.get('nom', '').strip()
    try:
        ids = {int(i) for i in request.form.getlist('membres')}
    except ValueError:
        abort(400)
    if not ids <= {e['id'] for e in planning_db.membres_disponibles(session['user_id'])}:
        abort(400)  # id inconnu, superviseur, soi-même ou compte non validé
    return nom, sorted(ids)

def nom_equipe_invalide(nom):
    if not nom:
        return "Le nom de l'équipe est obligatoire."
    if len(nom) > 100:
        return "Le nom de l'équipe ne doit pas dépasser 100 caractères."
    return None

@app.route('/equipes/creer', methods=['POST'])
@manager_requis
def creer_equipe():
    nom, ids = lire_formulaire_equipe()
    erreur = nom_equipe_invalide(nom)
    if erreur:
        flash(erreur, 'erreur')
    else:
        planning_db.creer_equipe(nom, session['user_id'], ids)
        flash(f"Équipe « {nom} » créée avec {len(ids)} membre(s).", 'succes')
    return redirect('/equipes')

@app.route('/equipes/<int:team_id>/modifier', methods=['POST'])
@manager_requis
def modifier_equipe(team_id):
    if not planning_db.equipe_geree(team_id, session['user_id']):
        abort(403)
    nom, ids = lire_formulaire_equipe()
    erreur = nom_equipe_invalide(nom)
    if erreur:
        flash(erreur, 'erreur')
    else:
        planning_db.modifier_equipe(team_id, nom, ids)
        flash(f"Équipe « {nom} » mise à jour ({len(ids)} membre(s)).", 'succes')
    return redirect('/equipes')

@app.route('/equipes/<int:team_id>/supprimer', methods=['POST'])
@manager_requis
def supprimer_equipe(team_id):
    equipe = planning_db.equipe_geree(team_id, session['user_id'])
    if not equipe:
        abort(403)
    planning_db.supprimer_equipe(team_id)
    flash(f"Équipe « {equipe['nom']} » supprimée. Les shifts des employés sont conservés.", 'succes')
    return redirect('/equipes')


# --- Écran 5 : organisation du planning d'une équipe ---

@app.route('/equipes/<int:team_id>', methods=['GET', 'POST'])
@manager_requis
def organisation(team_id):
    equipe = planning_db.equipe_geree(team_id, session['user_id'])
    if not equipe:
        abort(403)  # Le manager ne gère pas cette équipe

    lundi = planning_db.lundi_de(request.values.get('semaine'))
    membres = planning_db.membres_equipe(team_id)

    if request.method == 'POST':
        employe = request.form.get('employe', '')
        retour = url_for('organisation', team_id=team_id, semaine=lundi.isoformat(), employe=employe or None,
                         type=request.args.get('type') or None)
        try:
            brouillon = json.loads(request.form.get('modifications', '{}'))
        except ValueError:
            flash("Données de planning invalides.", 'erreur')
            return redirect(retour)

        noms = {str(m['id']): f"{m['prenom']} {m['nom']}" for m in membres}
        categories = planning_db.index_categories(planning_db.categories_connues())
        modifications = {}
        for employe_id, shifts_bruts in (brouillon.items() if isinstance(brouillon, dict) else []):
            if employe_id not in noms:
                abort(403)  # Employé hors de l'équipe
            voisins = planning_db.shifts_voisins(int(employe_id), lundi)
            shifts, erreur = planning_db.preparer_shifts(shifts_bruts, lundi, noms[employe_id], voisins, categories)
            if erreur:
                flash(erreur, 'erreur')
                return redirect(retour)
            modifications[int(employe_id)] = shifts

        if not modifications:
            flash("Aucune modification à appliquer.", 'info')
        else:
            planning_db.appliquer_planning(modifications, session['user_id'], lundi)
            flash(f"Planning mis à jour pour {len(modifications)} employé(s).", 'succes')
        return redirect(retour)

    return render_template(
        'organisation.html',
        page='equipes',
        equipe=equipe,
        membres=membres,
        shifts=planning_db.shifts_equipe_semaine(team_id, lundi),
        semaine=planning_db.infos_semaine(lundi),
        categories=planning_db.categories_connues(),
        couleurs=planning_db.COULEURS_UTILISATEURS,
        categorie_max=planning_db.CATEGORIE_MAX,
        nb_teintes=planning_db.NB_TEINTES,
        employe_choisi=request.args.get('employe', type=int),
    )


@app.errorhandler(400)
def requete_invalide(erreur):
    return render_template('erreur.html', page=None, code=400,
                           message="Requête invalide."), 400

@app.errorhandler(403)
def acces_refuse(erreur):
    return render_template('erreur.html', page=None, code=403,
                           message="Vous n'avez pas accès à cette page."), 403

@app.errorhandler(404)
def page_introuvable(erreur):
    return render_template('erreur.html', page=None, code=404,
                           message="Cette page n'existe pas."), 404


if __name__ == '__main__':
    app.run(debug=True)
