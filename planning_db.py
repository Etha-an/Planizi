"""Requêtes et règles métier des plannings (écrans 3, 4 et 5)."""
import math
import re
import unicodedata
from datetime import date, datetime, time, timedelta

from database import get_db_connection

CATEGORIES = ['Travail', 'Formation', 'Réunion']
CLASSES_CSS = {'Travail': 'cat-travail', 'Formation': 'cat-formation', 'Réunion': 'cat-reunion'}
NB_TEINTES = 6           # teintes des types personnalisés (.cat-perso-0 à 5 dans app.css)
CATEGORIE_MAX = 40       # longueur maximale d'un nom de type
JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
HEURE_MIN = 7     # plage affichée par défaut (élargie si un shift en sort)
HEURE_MAX = 21
# Couleur de chaque utilisateur (rond des initiales, planning par type) : la même sur toutes les pages
COULEURS_UTILISATEURS = ['#4E0B9A', '#0F766E', '#1D4ED8', '#B45309', '#BE185D', '#3F7D20',
                         '#B91C1C', '#7C4A1E', '#475569', '#86198F', '#0E7490', '#A16207']


def couleur_utilisateur(user_id):
    return COULEURS_UTILISATEURS[int(user_id) % len(COULEURS_UTILISATEURS)]


# ---------- Types de shift ----------

def classe_categorie(nom):
    """Classe CSS d'un type : fixe pour les types de base, teinte calculée depuis le nom sinon.

    Même calcul que classeCategorie() dans organisation.html : un type a la même couleur partout.
    """
    if nom in CLASSES_CSS:
        return CLASSES_CSS[nom]
    return f"cat-perso-{sum(ord(c) for c in nom) % NB_TEINTES}"


def cle_tri(nom):
    """Clé de tri alphabétique sans accents ni casse (« Réunion » entre « Repos » et « Rz »)."""
    sans_accents = ''.join(c for c in unicodedata.normalize('NFD', nom) if not unicodedata.combining(c))
    return sans_accents.casefold()


def categories_connues():
    """Types de base et types personnalisés déjà utilisés, dans l'ordre alphabétique."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT DISTINCT categorie FROM shift;')
        utilises = {ligne[0] for ligne in cursor.fetchall()}
        return sorted(set(CATEGORIES) | utilises, key=cle_tri)
    finally:
        cursor.close()
        conn.close()


def index_categories(noms):
    """{nom en minuscules: orthographe de référence}, pour éviter les doublons de casse."""
    index = {}
    for nom in noms:
        index.setdefault(nom.casefold(), nom)
    return index


def nettoyer_categorie(nom, index):
    """Nom de type normalisé, ou None s'il est invalide.

    Un nom déjà connu à la casse près reprend l'orthographe existante (« réunion » -> « Réunion ») ;
    un nouveau nom est ajouté à l'index pour que les shifts suivants le réutilisent.
    """
    if not isinstance(nom, str) or any(ord(c) < 32 or ord(c) == 127 for c in nom):
        return None
    nom = re.sub(r'\s+', ' ', nom).strip()
    if not 1 <= len(nom) <= CATEGORIE_MAX:
        return None
    return index.setdefault(nom.casefold(), nom)


# ---------- Semaines ----------

def lundi_de(texte=None):
    """Lundi de la semaine contenant la date 'AAAA-MM-JJ' (aujourd'hui par défaut ou si invalide)."""
    try:
        jour = datetime.strptime(texte, '%Y-%m-%d').date() if texte else date.today()
    except ValueError:
        jour = date.today()
    return jour - timedelta(days=jour.weekday())


def infos_semaine(lundi):
    """Données d'affichage d'une semaine : jours, libellé, liens précédente/suivante."""
    dimanche = lundi + timedelta(days=6)
    return {
        'lundi': lundi.isoformat(),
        'precedente': (lundi - timedelta(days=7)).isoformat(),
        'suivante': (lundi + timedelta(days=7)).isoformat(),
        'courante': lundi == lundi_de(),
        'libelle': f"{lundi.strftime('%d/%m')} – {dimanche.strftime('%d/%m/%Y')}",
        'jours': [
            {'nom': JOURS[i], 'court': JOURS[i][:3], 'date': (lundi + timedelta(days=i)).strftime('%d/%m'),
             'aujourdhui': lundi + timedelta(days=i) == date.today()}
            for i in range(7)
        ],
    }


def formater_shift(ligne):
    """Ligne SQL -> dict prêt pour le HTML / JSON (jour 0-6, heures 'HH:MM', durée en heures)."""
    debut, fin = ligne['debut'], ligne['fin']
    return {
        'id': ligne['id'],
        'employe_id': ligne.get('effectueur_id'),
        'categorie': ligne['categorie'],
        'classe': classe_categorie(ligne['categorie']),
        'jour': debut.weekday(),
        'debut': debut.strftime('%H:%M'),
        'fin': fin.strftime('%H:%M'),
        'lendemain': fin.date() > debut.date(),  # shift de nuit qui passe minuit
        'duree': (fin - debut).total_seconds() / 3600,
    }


def decouper_par_jour(lignes, lundi):
    """Découpe les shifts en segments d'une journée, limités à la semaine (pour la grille horaire).

    Un shift de nuit 22:00 -> 06:00 donne deux segments : 22h-24h le jour J et 0h-6h le jour J+1.
    """
    debut_semaine = datetime.combine(lundi, time())
    fin_semaine = debut_semaine + timedelta(days=7)
    segments = []
    for ligne in lignes:
        shift = formater_shift(ligne)
        curseur = max(ligne['debut'], debut_semaine)
        fin = min(ligne['fin'], fin_semaine)
        while curseur < fin:
            minuit = datetime.combine(curseur.date() + timedelta(days=1), time())
            fin_segment = min(fin, minuit)
            debut_jour = datetime.combine(curseur.date(), time())
            segments.append(dict(
                shift,
                jour=(curseur.date() - lundi).days,
                debut_h=(curseur - debut_jour).total_seconds() / 3600,
                fin_h=(fin_segment - debut_jour).total_seconds() / 3600,
                suite=curseur > ligne['debut'],   # commencé la veille
            ))
            curseur = fin_segment
    return segments


def plage_horaire(segments):
    """Heures affichées : 7h-21h par défaut, élargies pour contenir tous les segments."""
    debut = min([HEURE_MIN] + [math.floor(s['debut_h']) for s in segments])
    fin = max([HEURE_MAX] + [math.ceil(s['fin_h']) for s in segments])
    return debut, fin


def format_heures(heures):
    """35.5 -> '35h30', 35.0 -> '35h'."""
    h = int(heures)
    m = round((heures - h) * 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


# ---------- Lectures ----------

def shifts_utilisateur_semaine(user_id, lundi):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT id, categorie, debut, fin, effectueur_id FROM shift
            WHERE effectueur_id = %s AND debut >= %s AND debut < %s
            ORDER BY debut;
            ''',
            (user_id, lundi, lundi + timedelta(days=7))
        )
        return [formater_shift(ligne) for ligne in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def shifts_visibles_semaine(user_id, lundi):
    """Lignes brutes des shifts qui chevauchent la semaine (y compris une nuit commencée le dimanche d'avant)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT id, categorie, debut, fin, effectueur_id FROM shift
            WHERE effectueur_id = %s AND debut < %s AND fin > %s
            ORDER BY debut;
            ''',
            (user_id, lundi + timedelta(days=7), lundi)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def shifts_voisins(employe_id, lundi):
    """Shifts commencés hors de la semaine mais proches de ses bords (nuits à cheval sur deux semaines)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT debut, fin FROM shift
            WHERE effectueur_id = %s AND (debut < %s OR debut >= %s)
              AND debut < %s AND fin > %s;
            ''',
            (employe_id, lundi, lundi + timedelta(days=7), lundi + timedelta(days=8), lundi - timedelta(days=1))
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def recuperer_utilisateur(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT id, nom, prenom, poste, contrat FROM user WHERE id = %s;', (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def equipes_du_manager(user_id, lundi):
    """Équipes dont l'utilisateur est responsable, avec effectif, heures planifiées et heures de contrat.

    Tous les membres validés comptent (responsables et managers membres compris) ;
    membres_ids ne liste que les membres non responsables (ceux qu'on coche dans la fenêtre).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT t.id, t.nom,
                   COUNT(u.id) AS nb_membres,
                   COALESCE(SUM(u.contrat), 0) AS heures_contrat,
                   COALESCE(SUM(h.minutes), 0) / 60 AS heures_planifiees,
                   GROUP_CONCAT(CONCAT(u.id, ':', LEFT(u.prenom, 1), LEFT(u.nom, 1)) ORDER BY u.prenom SEPARATOR ',') AS membres,
                   GROUP_CONCAT(CASE WHEN ut.responsable = 0 THEN u.id END) AS membres_ids
            FROM team t
            JOIN user_team moi ON moi.team_id = t.id AND moi.user_id = %s AND moi.responsable = 1
            LEFT JOIN user_team ut ON ut.team_id = t.id
            LEFT JOIN user u ON u.id = ut.user_id AND u.valid = 1
            LEFT JOIN (
                SELECT effectueur_id, SUM(TIMESTAMPDIFF(MINUTE, debut, fin)) AS minutes FROM shift
                WHERE debut >= %s AND debut < %s
                GROUP BY effectueur_id
            ) h ON h.effectueur_id = u.id
            GROUP BY t.id, t.nom
            ORDER BY t.nom;
            ''',
            (user_id, lundi, lundi + timedelta(days=7))
        )
        equipes = cursor.fetchall()
        for equipe in equipes:
            equipe['heures_planifiees'] = float(equipe['heures_planifiees'])
            equipe['heures_contrat'] = float(equipe['heures_contrat'])
            equipe['membres'] = [{'id': int(i), 'initiales': ini} for i, ini in
                                 (m.split(':') for m in equipe['membres'].split(','))] if equipe['membres'] else []
            equipe['membres_ids'] = [int(i) for i in equipe['membres_ids'].split(',')] if equipe['membres_ids'] else []
        return equipes
    finally:
        cursor.close()
        conn.close()


# ---------- Gestion des équipes (écran 4) ----------

def membres_disponibles(exclure_id):
    """Utilisateurs actifs pouvant être ajoutés à une équipe : employés et managers (pas les superviseurs).

    exclure_id : le manager qui gère la fenêtre, déjà responsable de ses équipes.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT u.id, u.nom, u.prenom, u.poste, u.manager, COUNT(ut.team_id) AS nb_equipes
            FROM user u
            LEFT JOIN user_team ut ON ut.user_id = u.id
            WHERE u.valid = 1 AND u.supervisor = 0 AND u.id <> %s
            GROUP BY u.id
            ORDER BY u.prenom, u.nom;
            ''',
            (exclure_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def creer_equipe(nom, manager_id, membres_ids):
    """Crée l'équipe ; le manager qui la crée en est responsable (c'est ce qui lui en donne la gestion)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        cursor.execute('INSERT INTO team (nom) VALUES (%s);', (nom,))
        team_id = cursor.lastrowid
        cursor.execute('INSERT INTO user_team (user_id, team_id, responsable) VALUES (%s, %s, 1);', (manager_id, team_id))
        for user_id in membres_ids:
            if user_id != manager_id:
                cursor.execute('INSERT INTO user_team (user_id, team_id, responsable) VALUES (%s, %s, 0);', (user_id, team_id))
        conn.commit()
        return team_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def modifier_equipe(team_id, nom, membres_ids):
    """Renomme l'équipe et remplace ses membres simples ; les responsables sont conservés tels quels."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        cursor.execute('UPDATE team SET nom = %s WHERE id = %s;', (nom, team_id))
        cursor.execute('DELETE FROM user_team WHERE team_id = %s AND responsable = 0;', (team_id,))
        for user_id in membres_ids:
            # IGNORE : un responsable coché reste responsable (clé primaire user_id, team_id)
            cursor.execute('INSERT IGNORE INTO user_team (user_id, team_id, responsable) VALUES (%s, %s, 0);',
                           (user_id, team_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def supprimer_equipe(team_id):
    """Supprime l'équipe (user_team suit par ON DELETE CASCADE). Les shifts, liés aux employés, sont conservés."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM team WHERE id = %s;', (team_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def equipe_geree(team_id, user_id):
    """Renvoie l'équipe si user_id en est responsable, sinon None (contrôle d'accès)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT t.id, t.nom FROM team t
            JOIN user_team ut ON ut.team_id = t.id
            WHERE t.id = %s AND ut.user_id = %s AND ut.responsable = 1;
            ''',
            (team_id, user_id)
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def membres_equipe(team_id):
    """Membres validés de l'équipe, responsables et managers compris (tous sont planifiables)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT u.id, u.nom, u.prenom, u.poste, u.contrat, ut.responsable FROM user u
            JOIN user_team ut ON ut.user_id = u.id
            WHERE ut.team_id = %s AND u.valid = 1
            ORDER BY u.prenom, u.nom;
            ''',
            (team_id,)
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def shifts_equipe_semaine(team_id, lundi):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            '''
            SELECT s.id, s.categorie, s.debut, s.fin, s.effectueur_id FROM shift s
            JOIN user_team ut ON ut.user_id = s.effectueur_id AND ut.team_id = %s
            JOIN user u ON u.id = s.effectueur_id AND u.valid = 1
            WHERE s.debut >= %s AND s.debut < %s
            ORDER BY s.debut;
            ''',
            (team_id, lundi, lundi + timedelta(days=7))
        )
        return [formater_shift(ligne) for ligne in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ---------- Écriture (bouton « Appliquer ») ----------

def preparer_shifts(shifts_bruts, lundi, nom_employe, voisins=(), categories=None):
    """Valide les shifts envoyés par le formulaire et les convertit en datetimes.

    Une fin antérieure au début désigne un shift de nuit qui se termine le lendemain.
    voisins : shifts de l'employé hors de la semaine, pris en compte pour les chevauchements.
    categories : index des types connus (index_categories), complété par les nouveaux types.
    Renvoie (liste, None) si tout est correct, sinon (None, message d'erreur).
    """
    if not isinstance(shifts_bruts, list):
        return None, "Données de planning invalides."
    if categories is None:
        categories = index_categories(categories_connues())

    shifts = []
    for brut in shifts_bruts:
        try:
            jour = int(brut['jour'])
            h_debut = datetime.strptime(brut['debut'], '%H:%M').time()
            h_fin = datetime.strptime(brut['fin'], '%H:%M').time()
            categorie = brut['categorie']
            shift_id = int(brut['id']) if brut.get('id') else None
        except (KeyError, TypeError, ValueError):
            return None, f"{nom_employe} : un shift est incomplet ou mal formaté."

        nom_jour = JOURS[jour] if 0 <= jour < 7 else '?'
        if not 0 <= jour < 7:
            return None, f"{nom_employe} : jour invalide."
        categorie = nettoyer_categorie(categorie, categories)
        if categorie is None:
            return None, f"{nom_employe}, {nom_jour} : nom de type invalide (1 à {CATEGORIE_MAX} caractères)."
        if h_fin == h_debut:
            return None, f"{nom_employe}, {nom_jour} : un shift ne peut pas avoir une durée nulle."

        jour_date = lundi + timedelta(days=jour)
        debut = datetime.combine(jour_date, h_debut)
        fin = datetime.combine(jour_date, h_fin)
        if fin < debut:
            fin += timedelta(days=1)  # shift de nuit : se termine le lendemain

        shifts.append({'id': shift_id, 'categorie': categorie, 'debut': debut, 'fin': fin})

    # Pas de chevauchement (y compris avec les nuits à cheval sur la semaine voisine) :
    # une fois triés, chaque shift doit commencer après la fin du précédent
    tous = sorted(
        [dict(s, voisin=False) for s in shifts] + [dict(v, voisin=True) for v in voisins],
        key=lambda s: s['debut']
    )
    for precedent, suivant in zip(tous, tous[1:]):
        if suivant['debut'] < precedent['fin']:
            if precedent['voisin'] or suivant['voisin']:
                return None, (f"{nom_employe} : un shift chevauche un shift d'une semaine voisine "
                              f"({precedent['debut']:%d/%m %H:%M}–{precedent['fin']:%H:%M} et "
                              f"{suivant['debut']:%d/%m %H:%M}–{suivant['fin']:%H:%M}).")
            return None, (f"{nom_employe}, {JOURS[suivant['debut'].weekday()]} : deux shifts se chevauchent "
                          f"({precedent['debut']:%H:%M}–{precedent['fin']:%H:%M} et "
                          f"{suivant['debut']:%H:%M}–{suivant['fin']:%H:%M}).")
    shifts.sort(key=lambda s: s['debut'])
    return shifts, None


def appliquer_planning(modifications, assigneur_id, lundi):
    """Applique en une seule transaction le planning complet de la semaine de chaque employé modifié.

    modifications : {employe_id: [shifts préparés]}. Pour chaque employé, les shifts existants
    de la semaine absents de la liste sont supprimés, ceux présents sont mis à jour, les nouveaux insérés.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        for employe_id, shifts in modifications.items():
            cursor.execute(
                'SELECT id FROM shift WHERE effectueur_id = %s AND debut >= %s AND debut < %s;',
                (employe_id, lundi, lundi + timedelta(days=7))
            )
            existants = {ligne[0] for ligne in cursor.fetchall()}
            conserves = {s['id'] for s in shifts if s['id'] in existants}

            for shift_id in existants - conserves:
                cursor.execute('DELETE FROM shift WHERE id = %s;', (shift_id,))

            for s in shifts:
                if s['id'] in existants:
                    cursor.execute(
                        'UPDATE shift SET categorie = %s, debut = %s, fin = %s, assigneur_id = %s WHERE id = %s;',
                        (s['categorie'], s['debut'], s['fin'], assigneur_id, s['id'])
                    )
                else:
                    # id inconnu ou absent : nouveau shift (on n'accepte jamais l'id d'un autre employé)
                    cursor.execute(
                        'INSERT INTO shift (categorie, debut, fin, effectueur_id, assigneur_id) VALUES (%s, %s, %s, %s, %s);',
                        (s['categorie'], s['debut'], s['fin'], employe_id, assigneur_id)
                    )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
