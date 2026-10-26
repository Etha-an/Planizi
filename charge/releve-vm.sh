#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Planizi - relevé côté serveur DANS une machine virtuelle (étape 17, série vm)
#
# À lancer dans chaque VM pendant toute la campagne (s'arrête avec Ctrl+C) :
#     sudo bash releve-vm.sh donnees > vm-donnees-s1.csv   (sudo : pour interroger PostgreSQL)
#     bash releve-vm.sh metier   > vm-metier-s1.csv
#     bash releve-vm.sh proxy    > vm-proxy-s1.csv
# puis copier les fichiers dans charge/resultats/ sur l'hôte.
#
# Colonnes : horodatage_ms ; source ; cpu_pct (user+system, 100 = tous les cœurs de la VM) ;
#            mem_utilisee_mio ; io_lecture_ko_s ; io_ecriture_ko_s ; connexions_bd
# L'horloge de la VM doit être synchronisée avec l'hôte (Additions invité) :
# comparer `date` dans la VM et l'heure de Windows avant de commencer.
# ---------------------------------------------------------------------------
ROLE="${1:-vm}"
PERIODE="${2:-5}"
echo "horodatage_ms;source;cpu_pct;mem_utilisee_mio;io_lecture_ko_s;io_ecriture_ko_s;connexions_bd"

# « vmstat P 2 » : la 2e ligne est la moyenne sur les P dernières secondes
while true; do
    read -r r b swpd free buff cache si so bi bo inn cs us sy id wa st < <(vmstat "$PERIODE" 2 | tail -n 1)
    t=$(date +%s%3N)
    mem=$(free -m | awk '/^Mem:/ {print $3}')
    cnx=""
    if [ "$ROLE" = "donnees" ] && command -v psql >/dev/null; then
        cnx=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_stat_activity WHERE datname='planizi' AND pid <> pg_backend_pid();" 2>/dev/null)
    fi
    # bi/bo de vmstat : blocs de 1 Kio par seconde
    echo "$t;$ROLE;$((us + sy));$mem;$bi;$bo;$cnx"
done
