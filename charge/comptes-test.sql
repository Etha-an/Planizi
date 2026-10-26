-- ---------------------------------------------------------------------------
-- Planizi - comptes de test pour l'injection de charge (étape 15)
--
-- 24 employés « charge.01 » à « charge.24 », mot de passe planizi123,
-- chacun avec un shift par jour ouvré sur la semaine EN COURS et la suivante :
-- « Mon planning » affiche donc toujours au moins un shift, quel que soit le
-- jour de la campagne.
--
-- À jouer APRÈS schema.sql et donnees.sql, à l'identique sur les deux déploiements.
-- Idempotent : peut être rejoué (les comptes charge.* sont recréés).
-- ---------------------------------------------------------------------------
BEGIN;

DELETE FROM "user" WHERE login LIKE 'charge.%';      -- shifts supprimés en cascade

INSERT INTO "user" (nom, prenom, email, poste, login, password_hash, manager, supervisor, contrat, valid)
SELECT 'Charge', 'Testeur ' || lpad(n::text, 2, '0'),
       'charge.' || lpad(n::text, 2, '0') || '@planizi.test',
       'Compte de test (charge)',
       'charge.' || lpad(n::text, 2, '0'),
       'scrypt:32768:8:1$EFK1dYq3PCG92ps1$8dfaa08561dd20d2d0803adc0fa111d8d89cf74a37ccf9350b2a99d6fb23191f9c511a029bc73ee68b8337ebd410f6758f95066ab39e72c7d1abe2d93a41fa73',            -- même empreinte que les comptes de démonstration : planizi123
       0, 0, 35, 1
FROM generate_series(1, 24) AS n;

-- Un shift de 9 h à 16 h par jour ouvré, semaine en cours + suivante (10 shifts par compte)
INSERT INTO shift (categorie, debut, fin, effectueur_id, assigneur_id)
SELECT CASE WHEN j % 5 = 2 THEN 'Formation' ELSE 'Travail' END,
       date_trunc('week', current_date) + (j * interval '1 day') + interval '9 hours',
       date_trunc('week', current_date) + (j * interval '1 day') + interval '16 hours',
       u.id,
       u.id
FROM "user" u
CROSS JOIN (SELECT unnest(ARRAY[0,1,2,3,4,7,8,9,10,11]) AS j) jours
WHERE u.login LIKE 'charge.%';

COMMIT;

SELECT count(*) AS comptes_de_test,
       (SELECT count(*) FROM shift s JOIN "user" u ON u.id = s.effectueur_id WHERE u.login LIKE 'charge.%') AS shifts_de_test
FROM "user" WHERE login LIKE 'charge.%';
