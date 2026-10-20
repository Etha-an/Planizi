import psycopg2
from psycopg2.extras import RealDictCursor
import os
import re
import unicodedata
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Charge les variables du fichier .env
load_dotenv()

def get_db_connection():
    """Crée et retourne la connexion à la base de données."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dbname=os.getenv("DB_NAME"),
        port=os.getenv("DB_PORT", 5432)
    )

def recuperer_utilisateurs():
    """Récupère tous les utilisateurs de la base."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('SELECT * FROM "user";')
        return cursor.fetchall()
    finally:
        # Toujours fermer, même en cas d'erreur SQL
        cursor.close()
        conn.close()

def utilisateurs_non_valide():
    conn = get_db_connection()
    # Le RealDictCursor est vital pour que Flask comprenne les colonnes
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # On cherche tous ceux qui ont valid = 0
        cursor.execute('SELECT * FROM "user" WHERE valid = 0;')
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def valider_utilisateur(id, poste, contrat, manager, supervisor):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # On met à jour valid, poste, contrat, manager et supervisor
        cursor.execute(
            '''
            UPDATE "user"
            SET valid = 1, poste = %s, contrat = %s, manager = %s, supervisor = %s
            WHERE id = %s;
            ''',
            (poste, contrat, manager, supervisor, id) # L'ordre est très important !
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def refuser_utilisateur(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'DELETE FROM "user" WHERE id = %s;',
            (id,)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def normaliser(texte):
    """'Élodie Marie' -> 'elodiemarie' : sans accents, espaces, tirets ni apostrophes."""
    sans_accents = unicodedata.normalize('NFKD', texte).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]', '', sans_accents.lower())

def generer_login(cursor, nom, prenom):
    """Construit un login 'p.nom' unique : e.renucci, puis e.renucci2, e.renucci3..."""
    base = f"{normaliser(prenom)[:1]}.{normaliser(nom)}"
    cursor.execute('SELECT login FROM "user" WHERE login = %s OR login LIKE %s;', (base, base + '%'))
    pris = {ligne[0] for ligne in cursor.fetchall()}

    login, numero = base, 2
    while login in pris:
        login = f"{base}{numero}"
        numero += 1
    return login

def ajouter_utilisateur(nom, prenom, email, mot_de_passe_en_clair):
    """Hache le mot de passe et sauvegarde le nouvel utilisateur."""
    # Hachage du mot de passe
    mot_de_passe_securise = generate_password_hash(mot_de_passe_en_clair)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        login = generer_login(cursor, nom, prenom)
        # Requête SQL avec 5 valeurs
        cursor.execute(
            'INSERT INTO "user" (nom, prenom, email, login, password_hash, manager, supervisor) VALUES (%s, %s, %s, %s, %s, 0, 0)',
            (nom, prenom, email, login, mot_de_passe_securise)
        )
        conn.commit()
        return {"succes": True, "login": login}
    except psycopg2.IntegrityError:
        # La colonne email est UNIQUE : l'adresse est déjà utilisée
        return {"succes": False, "erreur": "Cet email est déjà utilisé."}
    finally:
        cursor.close()
        conn.close()

def roles_utilisateur(id):
    """Nom, prénom, rôles et état du compte (relu à chaque requête pour appliquer les changements sans reconnexion)."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('SELECT nom, prenom, manager, supervisor, valid FROM "user" WHERE id = %s;', (id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def utilisateurs_valides():
    """Comptes actifs, avec le nombre d'équipes de chacun (onglet Utilisateurs)."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            '''
            SELECT u.id, u.nom, u.prenom, u.email, u.login, u.poste, u.contrat, u.manager, u.supervisor,
                   COUNT(ut.team_id) AS nb_equipes
            FROM "user" u
            LEFT JOIN user_team ut ON ut.user_id = u.id
            WHERE u.valid = 1
            GROUP BY u.id
            ORDER BY u.nom, u.prenom;
            '''
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

LOGIN_VALIDE = re.compile(r'^[a-z0-9._-]{2,102}$')

def modifier_utilisateur(id, nom, prenom, email, login, poste, contrat, manager, supervisor, nouveau_mdp=None):
    """Met à jour un compte. Le mot de passe n'est changé que si nouveau_mdp est fourni."""
    if not LOGIN_VALIDE.match(login):
        return {"succes": False, "erreur": "Le login doit faire 2 à 102 caractères parmi a-z, 0-9, « . », « _ » et « - »."}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # La colonne login n'est pas UNIQUE en base : on vérifie nous-mêmes
        cursor.execute('SELECT 1 FROM "user" WHERE login = %s AND id <> %s;', (login, id))
        if cursor.fetchone():
            return {"succes": False, "erreur": f"Le login « {login} » est déjà utilisé."}

        cursor.execute(
            '''
            UPDATE "user"
            SET nom = %s, prenom = %s, email = %s, login = %s, poste = %s, contrat = %s, manager = %s, supervisor = %s
            WHERE id = %s;
            ''',
            (nom, prenom, email, login, poste, contrat, manager, supervisor, id)
        )
        if nouveau_mdp:
            cursor.execute('UPDATE "user" SET password_hash = %s WHERE id = %s;', (generate_password_hash(nouveau_mdp), id))
        conn.commit()
        return {"succes": True}
    except psycopg2.IntegrityError:
        conn.rollback()
        return {"succes": False, "erreur": "Cet email est déjà utilisé."}
    finally:
        cursor.close()
        conn.close()

def desactiver_utilisateur(id):
    """Repasse le compte en attente : connexion refusée, il réapparaît dans l'onglet Validation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE "user" SET valid = 0 WHERE id = %s;', (id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def verifier_connexion(login, mot_de_passe_tente):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('SELECT * FROM "user" WHERE login = %s;', (login,))
        utilisateur = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    # 1. Si l'utilisateur n'existe pas
    if not utilisateur:
        return {"succes": False, "erreur": "Login ou mot de passe incorrect."}

    # 2. Si le mot de passe ne correspond pas au hash de la base
    if not check_password_hash(utilisateur['password_hash'], mot_de_passe_tente):
        return {"succes": False, "erreur": "Login ou mot de passe incorrect."}

    # 3. Si le mot de passe est bon mais le compte n'est pas validé
    if utilisateur['valid'] == 0:
        return {"succes": False, "erreur": "Votre compte est en attente de validation par un administrateur."}

    # Si tout est bon, on renvoie l'utilisateur complet
    return {"succes": True, "utilisateur": utilisateur}
