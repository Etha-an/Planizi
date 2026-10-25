-- Preuve du peuplement de la base (livrable de l'etape 11)
-- Usage (PowerShell, depuis docker/) :
--   Get-Content preuve-donnees.sql | docker compose exec -T donnees psql -U planizi -d planizi

\echo '--- Version du serveur'
SELECT version();

\echo '--- Nombre de lignes par table (attendu : 15 / 3 / 14 / 145)'
SELECT (SELECT count(*) FROM "user")    AS utilisateurs,
       (SELECT count(*) FROM team)      AS equipes,
       (SELECT count(*) FROM user_team) AS appartenances,
       (SELECT count(*) FROM shift)     AS shifts;

\echo '--- Equipes et responsables'
SELECT t.nom AS equipe, u.prenom || ' ' || u.nom AS responsable
FROM team t
JOIN user_team ut ON ut.team_id = t.id AND ut.responsable = 1
JOIN "user" u     ON u.id = ut.user_id
ORDER BY t.nom;

\echo '--- Emplacement physique des donnees (= le volume pgdata)'
SHOW data_directory;
