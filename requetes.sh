# Requête sans jeton (devrait te retourner une erreur 401)
curl -X GET http://localhost:5000/cours/1/notes

# Requête avec un jeton valide (devrait te retourner les notes avec le code 200)
curl -X GET http://localhost:5000/cours/1/notes -H "Authorization: mon_super_jeton_secret"