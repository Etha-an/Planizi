"""Réinitialise la base Planizi et la remplit avec des données d'exemple.

ATTENTION : supprime TOUS les utilisateurs, équipes et shifts existants.
Usage : venv\\Scripts\\python seed.py        (demande confirmation)
        venv\\Scripts\\python seed.py --oui  (sans confirmation)
"""
import sys
from datetime import date, datetime, time, timedelta

from werkzeug.security import generate_password_hash

from database import get_db_connection, normaliser
from migrer import migrer

MOT_DE_PASSE = 'planizi123'

# (login, nom, prénom, poste, manager, superviseur, contrat, valide)
UTILISATEURS = [
    ('admin.planizi', 'Planizi',   'Admin',   'Superviseur',              0, 1, None, 1),
    ('e.renucci',     'Renucci',   'Ethan',   'Manager',                  1, 0, 35,   1),
    ('c.morel',       'Morel',     'Camille', 'Responsable logistique',   1, 0, 35,   1),
    ('l.martin',      'Martin',    'Léa',     "Hôtesse d'accueil",        0, 0, 35,   1),
    ('h.bernard',     'Bernard',   'Hugo',    "Agent d'accueil",          0, 0, 35,   1),
    ('c.petit',       'Petit',     'Chloé',   "Agente d'accueil",         0, 0, 24,   1),
    ('l.dubois',      'Dubois',    'Lucas',   'Préparateur de commandes', 0, 0, 35,   1),
    ('m.leroy',       'Leroy',     'Manon',   'Cariste',                  0, 0, 35,   1),
    ('n.moreau',      'Moreau',    'Nathan',  'Magasinier',               0, 0, 35,   1),
    ('i.laurent',     'Laurent',   'Inès',    'Conseillère clientèle',    0, 0, 35,   1),
    ('t.simon',       'Simon',     'Théo',    'Conseiller clientèle',     0, 0, 35,   1),
    ('s.michel',      'Michel',    'Sarah',   'Technicienne support',     0, 0, 24,   1),
    # Inscriptions en attente de validation (écran 6)
    ('g.morillon',    'Morillon',  'Gabriel', None,                       0, 0, None, 0),
    ('j.fontaine',    'Fontaine',  'Julie',   None,                       0, 0, None, 0),
    ('k.benali',      'Benali',    'Karim',   None,                       0, 0, None, 0),
]

# équipe -> (responsable, membres) ; c.morel, manager de Logistique, est aussi simple membre de Support client
EQUIPES = {
    'Accueil':        ('e.renucci', ['l.martin', 'h.bernard', 'c.petit']),
    'Logistique':     ('c.morel',   ['l.dubois', 'm.leroy', 'n.moreau']),
    'Support client': ('e.renucci', ['i.laurent', 't.simon', 's.michel', 'h.bernard', 'c.morel']),
}

# --- Profils horaires : liste de (jour 0-6, début, fin, catégorie) ---
def journees(jours, *plages, categorie='Travail'):
    return [(j, debut, fin, categorie) for j in jours for debut, fin in plages]

SEMAINE = range(5)  # lundi -> vendredi
COUPEE = journees(SEMAINE, ('09:00', '12:30'), ('13:30', '17:00'))        # 5 x 7h = 35h
MATIN = journees(SEMAINE, ('08:00', '15:00'))                             # 5 x 7h = 35h
SOIR = journees(SEMAINE, ('13:00', '20:00'))                              # 5 x 7h = 35h
QUATRE_JOURS = journees(range(4), ('08:00', '12:00'), ('13:00', '17:45')) # 4 x 8h45 = 35h
AVEC_SAMEDI = journees(range(1, 6), ('09:00', '12:30'), ('13:30', '17:00'))  # mar -> sam = 35h
TOT_MATIN = journees(SEMAINE, ('06:00', '13:00'))                         # 5 x 7h = 35h
NUIT = journees(range(4), ('21:15', '06:00'))                             # lun -> jeu, fin le lendemain : 4 x 8h45 = 35h
TEMPS_PARTIEL_A =journees([0, 1, 3], ('08:00', '16:00'))                 # 3 x 8h = 24h
TEMPS_PARTIEL_B = journees(range(2, 6), ('09:00', '15:00'))               # 4 x 6h = 24h

def remplacer(profil, jour, debut, nouvelles):
    """Remplace la plage (jour, début) d'un profil par d'autres plages (même durée totale)."""
    return [p for p in profil if not (p[0] == jour and p[1] == debut)] + nouvelles

AVEC_REUNION = remplacer(COUPEE, 0, '09:00', [(0, '09:00', '10:00', 'Réunion'), (0, '10:00', '12:30', 'Travail')])
AVEC_FORMATION = remplacer(COUPEE, 2, '13:30', [(2, '13:30', '17:00', 'Formation')])
# Type personnalisé (créé par un manager depuis l'écran 5)
PARTIEL_ASTREINTE = remplacer(TEMPS_PARTIEL_A, 3, '08:00', [(3, '08:00', '16:00', 'Astreinte')])
PARTIEL_B_ASTREINTE = remplacer(TEMPS_PARTIEL_B, 5, '09:00', [(5, '09:00', '15:00', 'Astreinte')])

# login -> (profil semaine courante, profil semaine suivante) : rotation matin / soir
PLANNINGS = {
    'e.renucci': (AVEC_REUNION, AVEC_REUNION),
    'c.morel':   (MATIN, MATIN),
    'l.martin':  (AVEC_REUNION, COUPEE),
    'h.bernard': (SOIR, MATIN),
    'c.petit':   (PARTIEL_ASTREINTE, TEMPS_PARTIEL_A),
    'l.dubois':  (TOT_MATIN, SOIR),
    'm.leroy':   (NUIT, QUATRE_JOURS),
    'n.moreau':  (AVEC_SAMEDI, AVEC_SAMEDI),
    'i.laurent': (AVEC_FORMATION, COUPEE),
    't.simon':   (SOIR, MATIN),
    's.michel':  (PARTIEL_B_ASTREINTE, TEMPS_PARTIEL_B),
}


def email_de(login, prenom, nom):
    if login == 'e.renucci':
        return 'renucci.ethan0@gmail.com'
    return f"{normaliser(prenom)}.{normaliser(nom)}@planizi.fr"


def main():
    if '--oui' not in sys.argv:
        reponse = input("Cette opération SUPPRIME tous les utilisateurs, équipes et shifts. Taper « oui » pour continuer : ")
        if reponse.strip().lower() != 'oui':
            print("Annulé.")
            return

    migrer()  # schéma à jour (colonne user_team.responsable)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Vidage dans l'ordre des clés étrangères
        for table in ('shift', 'user_team', 'team', 'user'):
            cursor.execute(f'DELETE FROM "{table}";')

        # 2. Utilisateurs (un seul hachage : même mot de passe de démo pour tous)
        hash_mdp = generate_password_hash(MOT_DE_PASSE)
        ids = {}
        for login, nom, prenom, poste, manager, superviseur, contrat, valide in UTILISATEURS:
            cursor.execute(
                '''
                INSERT INTO "user" (nom, prenom, email, poste, login, password_hash, manager, supervisor, contrat, valid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                ''',
                (nom, prenom, email_de(login, prenom, nom), poste, login, hash_mdp, manager, superviseur, contrat, valide)
            )
            ids[login] = cursor.fetchone()[0]

        # 3. Équipes : le manager en est responsable (il la gère), les autres en sont membres (planifiés)
        managers_de = {}
        for nom_equipe, (manager, membres) in EQUIPES.items():
            cursor.execute('INSERT INTO team (nom) VALUES (%s) RETURNING id;', (nom_equipe,))
            team_id = cursor.fetchone()[0]
            for login in [manager] + membres:
                cursor.execute('INSERT INTO user_team (user_id, team_id, responsable) VALUES (%s, %s, %s);',
                               (ids[login], team_id, int(login == manager)))
                managers_de.setdefault(login, manager)

        # 4. Shifts de la semaine courante et de la suivante
        lundi = date.today() - timedelta(days=date.today().weekday())
        nb_shifts = 0
        for login, profils in PLANNINGS.items():
            assigneur = ids[managers_de.get(login, login)]
            for numero_semaine, profil in enumerate(profils):
                debut_semaine = lundi + timedelta(weeks=numero_semaine)
                for jour, debut, fin, categorie in profil:
                    jour_date = debut_semaine + timedelta(days=jour)
                    debut_dt = datetime.combine(jour_date, time.fromisoformat(debut))
                    fin_dt = datetime.combine(jour_date, time.fromisoformat(fin))
                    if fin_dt < debut_dt:
                        fin_dt += timedelta(days=1)  # shift de nuit
                    cursor.execute(
                        'INSERT INTO shift (categorie, debut, fin, effectueur_id, assigneur_id) VALUES (%s, %s, %s, %s, %s);',
                        (categorie, debut_dt, fin_dt, ids[login], assigneur)
                    )
                    nb_shifts += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    print(f"Base réinitialisée : {len(UTILISATEURS)} utilisateurs, {len(EQUIPES)} équipes, {nb_shifts} shifts.")
    print(f"Mot de passe de tous les comptes : {MOT_DE_PASSE}\n")
    print("  Superviseur (écran 6, /valider-compte) : admin.planizi")
    print("  Managers (écrans 4 et 5)               : e.renucci (Accueil, Support client), c.morel (Logistique)")
    print("  Employés (écran 3)                     : l.martin, h.bernard, c.petit, l.dubois, m.leroy,")
    print("                                           n.moreau, i.laurent, t.simon, s.michel")
    print("  En attente de validation               : g.morillon, j.fontaine, k.benali")


if __name__ == '__main__':
    main()
