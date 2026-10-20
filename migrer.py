"""Mise à jour du schéma de la base Planizi (idempotent : peut être relancé sans risque).

Usage : python migrer.py

- user_team.responsable : distingue les responsables d'une équipe (qui la gèrent)
  de ses simples membres (planifiés). Les managers déjà membres d'une équipe en
  deviennent responsables, ce qui conserve le fonctionnement précédent.
"""
from database import get_db_connection


def colonne_existe(cursor, table, colonne):
    cursor.execute(
        '''
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = current_schema() AND TABLE_NAME = %s AND COLUMN_NAME = %s;
        ''',
        (table, colonne)
    )
    return cursor.fetchone() is not None


def migrer():
    """Applique les migrations manquantes ; renvoie la liste des changements effectués."""
    conn = get_db_connection()
    cursor = conn.cursor()
    changements = []
    try:
        if not colonne_existe(cursor, 'user_team', 'responsable'):
            cursor.execute('ALTER TABLE user_team ADD COLUMN responsable SMALLINT NOT NULL DEFAULT 0;')
            cursor.execute(
                '''
                UPDATE user_team ut SET responsable = 1
                FROM "user" u WHERE u.id = ut.user_id AND u.manager = 1;
                '''
            )
            conn.commit()
            changements.append('user_team.responsable ajoutée (managers membres -> responsables)')
        return changements
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    faits = migrer()
    print('\n'.join(faits) if faits else 'Base déjà à jour.')
