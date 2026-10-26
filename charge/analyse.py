"""
Planizi - analyse des campagnes de charge (étape 18)
====================================================

Lit les fichiers bruts de resultats/ et produit :
  ../docs/charge/debit.png, latence-p95.png, erreurs.png, cpu-<dep>.png   (courbes)
  ../docs/charge-mesures.md                                               (tableaux chiffrés)

Fichiers attendus dans resultats/ (noms produits par campagne.ps1) :
  dk-<N>-<serie>.csv / vm-<N>-<serie>.csv        résultats JMeter d'un palier
  dk-serveur-<serie>.csv / vm-serveur-<serie>.csv relevé côté hôte (releve-hote.ps1)
  vm-<role>-<serie>.csv                           relevé dans une VM (releve-vm.sh), facultatif
  etalonnage-<dep>-<N>[-<serie>].csv              étalonnage de l'injecteur

Usage (depuis charge/) :
  python analyse.py                       # montée 30 s, plateau 90 s
  python analyse.py --montee 30 --plateau 90 --charge-egale 25
Dépendances : Python 3 + matplotlib (fournis par Anaconda).
"""
import argparse
import csv
import glob
import os
import re
import statistics
from collections import defaultdict

NOMS = {'dk': 'Trois conteneurs', 'vm': 'Trois machines virtuelles'}
COULEURS = {'dk': '#1D4ED8', 'vm': '#B45309'}


# ---------------------------------------------------------------- utilitaires
def centile(valeurs, p):
    """Centile par interpolation linéaire (même définition que numpy, méthode 'linear')."""
    if not valeurs:
        return float('nan')
    v = sorted(valeurs)
    k = (len(v) - 1) * p / 100
    i = int(k)
    return v[i] if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * (k - i)


def nombre(x):
    try:
        return float(str(x).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def fmt(x, d=1):
    return '—' if x is None or x != x else f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')


def lire_jtl(chemin):
    with open(chemin, newline='', encoding='utf-8', errors='replace') as f:
        lignes = list(csv.DictReader(f))
    for l in lignes:
        l['timeStamp'] = int(l['timeStamp'])
        l['elapsed'] = int(l['elapsed'])
        l['ok'] = l.get('success', '').strip().lower() == 'true'
        l['allThreads'] = int(l.get('allThreads') or 0)
    return lignes


# ---------------------------------------------------------------- un palier
def analyser_palier(chemin, montee, plateau):
    lignes = lire_jtl(chemin)
    if not lignes:
        return None
    t0 = min(l['timeStamp'] for l in lignes)
    debut, fin = t0 + montee * 1000, t0 + (montee + plateau) * 1000
    fenetre = [l for l in lignes if debut <= l['timeStamp'] < fin]
    if not fenetre:
        return None
    duree = (min(fin, max(l['timeStamp'] for l in fenetre) + 1) - debut) / 1000
    duree = max(duree, 1e-9)
    lat = [l['elapsed'] for l in fenetre]
    lat_ok = [l['elapsed'] for l in fenetre if l['ok']]
    par_label = defaultdict(list)
    for l in fenetre:
        par_label[l['label']].append(l)
    labels = {}
    for nom, ls in sorted(par_label.items()):
        labels[nom] = {
            'n': len(ls),
            'erreurs_pct': 100 * sum(not l['ok'] for l in ls) / len(ls),
            'p50': centile([l['elapsed'] for l in ls], 50),
            'p95': centile([l['elapsed'] for l in ls], 95),
            'messages': sorted({l.get('failureMessage', '') or l.get('responseMessage', '') for l in ls if not l['ok']})[:3],
        }
    connexions_ok = sum(1 for l in fenetre if l['ok'] and l['label'].startswith('1'))
    return {
        'debut': debut, 'fin': fin, 'duree': duree,
        'n': len(fenetre),
        'debit': len(fenetre) / duree,
        'debit_ok': sum(l['ok'] for l in fenetre) / duree,
        'parcours': connexions_ok / duree,
        'erreurs_pct': 100 * sum(not l['ok'] for l in fenetre) / len(fenetre),
        'p50': centile(lat, 50), 'p90': centile(lat, 90), 'p95': centile(lat, 95), 'p99': centile(lat, 99),
        'p95_ok': centile(lat_ok, 95),
        'moyenne': statistics.fmean(lat),
        'utilisateurs_effectifs': statistics.median(l['allThreads'] for l in fenetre),
        'labels': labels,
    }


# ---------------------------------------------------------------- relevés serveur
def lire_releve(chemin):
    """Relevé « ; » : horodatage_ms;source;cpu;mem;io_l;io_e;connexions."""
    ech = []
    with open(chemin, encoding='utf-8-sig', errors='replace') as f:
        en_tete = f.readline().strip().split(';')
        for ligne in f:
            c = ligne.strip().split(';')
            if len(c) < 2 or not c[0].isdigit():
                continue
            c += [''] * (len(en_tete) - len(c))
            ech.append({'t': int(c[0]), 'source': c[1], 'cpu': nombre(c[2]), 'mem': nombre(c[3]),
                        'io_l': nombre(c[4]), 'io_e': nombre(c[5]), 'cnx': nombre(c[6])})
    return ech


def metriques_serveur(releves, debut, fin, unite_io):
    """Moyennes par source sur la fenêtre de mesure."""
    par_source = defaultdict(list)
    for chemin, ech, dans_vm in releves:
        for e in ech:
            if debut <= e['t'] < fin:
                cle = e['source'] + (' (dans la VM)' if dans_vm else '')
                par_source[cle].append(e)
    res = {}
    for src, es in sorted(par_source.items()):
        def moy(k):
            v = [e[k] for e in es if e[k] is not None]
            return statistics.fmean(v) if v else None
        def maxi(k):
            v = [e[k] for e in es if e[k] is not None]
            return max(v) if v else None
        io_l = io_e = None
        if unite_io == 'cumul':               # docker stats : compteurs cumulés en Mio -> Mio/s
            v = [e for e in es if e['io_l'] is not None]
            if len(v) >= 2 and v[-1]['t'] > v[0]['t']:
                dt = (v[-1]['t'] - v[0]['t']) / 1000
                io_l = (v[-1]['io_l'] - v[0]['io_l']) / dt
                io_e = (v[-1]['io_e'] - v[0]['io_e']) / dt
        else:                                  # vmstat : déjà en Kio/s -> Mio/s
            io_l = (moy('io_l') or 0) / 1024 if moy('io_l') is not None else None
            io_e = (moy('io_e') or 0) / 1024 if moy('io_e') is not None else None
        res[src] = {'cpu': moy('cpu'), 'cpu_max': maxi('cpu'), 'mem': moy('mem'),
                    'io_l': io_l, 'io_e': io_e, 'cnx': moy('cnx'), 'cnx_max': maxi('cnx'), 'n': len(es)}
    return res


# ---------------------------------------------------------------- saturation
def saturation(points):
    """Saturation : le débit ne suit plus la charge offerte.
    Débit attendu par utilisateur = médiane de (débit / N) sur les paliers <= 10 (régime non saturé).
    Un palier est saturé si son efficacité (débit mesuré / débit attendu) tombe sous 90 %
    ou si son taux d'erreur dépasse 5 %.
    Renvoie (dernier palier non saturé, premier palier saturé, débit maximal soutenu, efficacités)."""
    pts = sorted(points, key=lambda p: p[0])
    debit_max = max((p[1]['debit_ok'] for p in pts), default=None)
    bas = [r['debit_ok'] / n for n, r in pts if n <= 10 and n > 0] or [pts[0][1]['debit_ok'] / max(pts[0][0], 1)]
    par_util = statistics.median(bas)
    eff = {n: r['debit_ok'] / (n * par_util) if par_util else float('nan') for n, r in pts}
    precedent = None
    for n, r in pts:
        if eff[n] < 0.9 or r['erreurs_pct'] > 5:
            return precedent, n, debit_max, eff
        precedent = n
    return None, None, debit_max, eff


def goulot_candidat(r):
    """Service applicatif le plus chargé en processeur sur ce palier."""
    srv = {s: v for s, v in r.get('serveur', {}).items()
           if v.get('cpu') is not None and not s.startswith(('hote', 'jmeter', 'donnees-connexions')) and 'dans la VM' not in s}
    if not srv:
        return None
    s, v = max(srv.items(), key=lambda kv: kv[1]['cpu'])
    return f"candidat : {s} (CPU {fmt(v['cpu'], 0)} % d'un cœur)"


# ---------------------------------------------------------------- programme
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dossier', default='resultats')
    ap.add_argument('--sortie', default=os.path.join('..', 'docs'))
    ap.add_argument('--montee', type=int, default=30)
    ap.add_argument('--plateau', type=int, default=90)
    ap.add_argument('--montee-etalonnage', type=int, default=10)
    ap.add_argument('--plateau-etalonnage', type=int, default=60)
    ap.add_argument('--charge-egale', type=int, default=None, help='palier pour « latence p95 à charge égale »')
    a = ap.parse_args()

    # --- paliers
    series = defaultdict(dict)          # (dep, serie) -> {N: resultat}
    for chemin in glob.glob(os.path.join(a.dossier, '*.csv')):
        m = re.fullmatch(r'(dk|vm)-(\d+)-(s\d+)\.csv', os.path.basename(chemin))
        if m:
            r = analyser_palier(chemin, a.montee, a.plateau)
            if r:
                series[(m[1], m[3])][int(m[2])] = r
    # --- relevés serveur, associés aux paliers par horodatage
    for (dep, serie), paliers in series.items():
        releves = []
        p = os.path.join(a.dossier, f'{dep}-serveur-{serie}.csv')
        if os.path.exists(p):
            releves.append((p, lire_releve(p), False))
        for p in glob.glob(os.path.join(a.dossier, f'vm-*-{serie}.csv')):
            if dep == 'vm' and re.fullmatch(rf'vm-(proxy|metier|donnees)-{serie}\.csv', os.path.basename(p)):
                releves.append((p, lire_releve(p), True))
        for n, r in paliers.items():
            r['serveur'] = metriques_serveur(releves, r['debut'], r['fin'], 'cumul' if dep == 'dk' else 'vmstat')
            # les relevés dans la VM ont des débits d'E/S en Kio/s : traités à part
            if dep == 'vm':
                for src, v in r['serveur'].items():
                    if src.endswith('(dans la VM)'):
                        ech = [e for _, es, dv in releves if dv for e in es
                               if e['source'] + ' (dans la VM)' == src and r['debut'] <= e['t'] < r['fin']]
                        il = [e['io_l'] for e in ech if e['io_l'] is not None]
                        ie = [e['io_e'] for e in ech if e['io_e'] is not None]
                        v['io_l'] = statistics.fmean(il) / 1024 if il else None
                        v['io_e'] = statistics.fmean(ie) / 1024 if ie else None
                    else:
                        v['io_l'] = v['io_e'] = None
    # --- étalonnage
    etal = []
    for chemin in sorted(glob.glob(os.path.join(a.dossier, 'etalonnage-*.csv'))):
        m = re.fullmatch(r'etalonnage-(dk|vm)-(\d+)(?:-(s\d+))?\.csv', os.path.basename(chemin))
        if m:
            r = analyser_palier(chemin, a.montee_etalonnage, a.plateau_etalonnage)
            if r:
                etal.append((m[1], int(m[2]), m[3] or 's1', r))
    etal.sort(key=lambda e: (e[0], e[1], e[2]))

    if not series and not etal:
        print(f'Aucun fichier de résultats dans {a.dossier}/')
        return

    os.makedirs(os.path.join(a.sortie, 'charge'), exist_ok=True)
    md = ['# Charge — mesures (générées par charge/analyse.py)', '',
          f'Fenêtre de mesure : plateau de {a.plateau} s après {a.montee} s de montée, montée exclue. '
          'Latences en millisecondes, débits en requêtes par seconde (deux requêtes par parcours).', '']

    # --- étalonnage
    if etal:
        md += ['## Étalonnage de l\'injecteur (ressource statique servie par le proxy, sans temps de réflexion)', '',
               '| Déploiement | Utilisateurs | Série | Débit (req/s) | p95 (ms) | Erreurs |', '|---|---|---|---|---|---|']
        for dep, n, s, r in etal:
            md.append(f"| {dep} | {n} | {s} | {fmt(r['debit'])} | {fmt(r['p95'], 0)} | {fmt(r['erreurs_pct'], 2)} % |")
        md.append('')

    # --- tableaux par série
    for (dep, serie), paliers in sorted(series.items()):
        md += [f'## {NOMS[dep]} — série {serie}', '',
               '| Utilisateurs | effectifs | Débit (req/s) | dont réussies | Parcours/s | p50 | p90 | p95 | p99 | Erreurs | Erreurs connexion | Erreurs planning |',
               '|---|---|---|---|---|---|---|---|---|---|---|---|']
        for n, r in sorted(paliers.items()):
            e = {k[0]: v['erreurs_pct'] for k, v in r['labels'].items()}
            md.append(f"| {n} | {fmt(r['utilisateurs_effectifs'], 0)} | {fmt(r['debit'])} | {fmt(r['debit_ok'])} | {fmt(r['parcours'])} | "
                      f"{fmt(r['p50'], 0)} | {fmt(r['p90'], 0)} | {fmt(r['p95'], 0)} | {fmt(r['p99'], 0)} | {fmt(r['erreurs_pct'], 2)} % | "
                      f"{fmt(e.get('1'), 2)} % | {fmt(e.get('2'), 2)} % |")
        md.append('')
        md += ['Latence p95 par requête (ms) :', '', '| Utilisateurs | 1 - Connexion | 2 - Mon planning |', '|---|---|---|']
        for n, r in sorted(paliers.items()):
            l = {k[0]: v for k, v in r['labels'].items()}
            md.append(f"| {n} | {fmt(l.get('1', {}).get('p95'), 0)} | {fmt(l.get('2', {}).get('p95'), 0)} |")
        md.append('')
        msgs = sorted({m for r in paliers.values() for v in r['labels'].values() for m in v['messages'] if m})
        if msgs:
            md += ['Messages d\'erreur rencontrés : ' + ' ; '.join(f'`{m[:120]}`' for m in msgs[:6]), '']
        # serveur
        sources = sorted({s for r in paliers.values() for s in r.get('serveur', {})})
        if sources:
            md += ['Côté serveur, moyenne sur le plateau (CPU en % d\'un cœur, sauf « dans la VM » : % de la VM) :', '',
                   '| Utilisateurs | ' + ' | '.join(sources) + ' |', '|---|' + '---|' * len(sources)]
            for n, r in sorted(paliers.items()):
                cel = []
                for s in sources:
                    v = r['serveur'].get(s)
                    if not v:
                        cel.append('—'); continue
                    t = []
                    if v['cpu'] is not None: t.append(f"CPU {fmt(v['cpu'], 0)} %")
                    if v['mem'] is not None: t.append(f"{fmt(v['mem'], 0)} Mio")
                    if v['io_e'] is not None: t.append(f"E/S {fmt(v['io_l'], 2)}/{fmt(v['io_e'], 2)} Mio/s")
                    if v['cnx'] is not None: t.append(f"{fmt(v['cnx'], 1)} cnx (max {fmt(v['cnx_max'], 0)})")
                    cel.append(' · '.join(t) or '—')
                md.append(f'| {n} | ' + ' | '.join(cel) + ' |')
            md.append('')

    # --- répétabilité (même déploiement, même palier, deux séries)
    rep = []
    for dep in ('dk', 'vm'):
        ss = sorted(s for d, s in series if d == dep)
        for s1, s2 in zip(ss, ss[1:]):
            for n in sorted(set(series[(dep, s1)]) & set(series[(dep, s2)])):
                a1, a2 = series[(dep, s1)][n], series[(dep, s2)][n]
                ecart = 100 * abs(a2['debit_ok'] - a1['debit_ok']) / max(a1['debit_ok'], 1e-9)
                ecart95 = 100 * abs(a2['p95'] - a1['p95']) / max(a1['p95'], 1e-9)
                rep.append(f"| {dep} | {n} | {s1} / {s2} | {fmt(a1['debit_ok'])} / {fmt(a2['debit_ok'])} | {fmt(ecart)} % | "
                           f"{fmt(a1['p95'], 0)} / {fmt(a2['p95'], 0)} | {fmt(ecart95)} % | {'ok' if ecart <= 10 else '⚠ > 10 %'} |")
    if rep:
        md += ['## Répétabilité', '', '| Déploiement | Utilisateurs | Séries | Débit réussi (req/s) | Écart | p95 (ms) | Écart | |',
               '|---|---|---|---|---|---|---|---|'] + rep + ['']

    # --- synthèse
    md += ['## Synthèse (série s1)', '', '| Grandeur | Trois machines virtuelles | Trois conteneurs |', '|---|---|---|']
    syn = {}
    for dep in ('vm', 'dk'):
        p = series.get((dep, 's1'), {})
        syn[dep] = (p, *(saturation(list(p.items())) if p else (None, None, None, {})))
    def charge_sat(dep):
        p, ok, ko, dmax, eff = syn[dep]
        if not p:
            return '—'
        if ko is None:
            return 'non atteinte (monter plus haut)'
        return f"entre {ok} et {ko} (efficacité à {ko} : {fmt(100 * eff[ko], 0)} %)" if ok else f"dès {ko}"
    def goulot(dep):
        p, ok, ko, dmax, eff = syn[dep]
        return (goulot_candidat(p[ko]) if ko else None) or 'à nommer'
    md.append(f"| Débit maximal soutenu (req/s réussies) | {fmt(syn['vm'][3])} | {fmt(syn['dk'][3])} |")
    md.append(f"| Charge au point de saturation (utilisateurs) | {charge_sat('vm')} | {charge_sat('dk')} |")
    communs = sorted(set(syn['vm'][0]) & set(syn['dk'][0]))
    ce = a.charge_egale or (communs[len(communs) // 2] if communs else None)
    if ce and ce in syn['vm'][0] and ce in syn['dk'][0]:
        md.append(f"| Latence p95 à charge égale ({ce} utilisateurs) | {fmt(syn['vm'][0][ce]['p95'], 0)} ms | {fmt(syn['dk'][0][ce]['p95'], 0)} ms |")
    md.append(f"| Goulot d'étranglement identifié | {goulot('vm')} | {goulot('dk')} |")
    md += ['', 'Efficacité = débit mesuré / débit attendu si chaque utilisateur était servi aussi vite qu\'à faible charge. '
           'Un palier est saturé sous 90 % d\'efficacité ou au-delà de 5 % d\'erreurs. À confirmer sur les courbes.', '']
    for dep in ('vm', 'dk'):
        p, ok, ko, dmax, eff = syn[dep]
        if p:
            md.append(f"Efficacité par palier ({NOMS[dep]}) : " + ' · '.join(f"{n} → {fmt(100 * e, 0)} %" for n, e in sorted(eff.items())))
    md.append('')

    with open(os.path.join(a.sortie, 'charge-mesures.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print('\n'.join(md))

    # --- courbes
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('\nmatplotlib absent : pip install matplotlib  (courbes non générées)')
        return

    def courbe(fichier, cle, titre, axe_y, log_y=False):
        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
        for (dep, serie), p in sorted(series.items()):
            xs = sorted(p)
            ax.plot(xs, [p[n][cle] for n in xs], marker='o', color=COULEURS[dep],
                    linestyle='-' if serie == 's1' else '--', label=f'{NOMS[dep]} ({serie})')
        ax.set_xlabel('Utilisateurs simultanés')
        ax.set_ylabel(axe_y)
        ax.set_title(titre)
        ax.set_xscale('log')
        xs_all = sorted({n for p in series.values() for n in p})
        ax.set_xticks(xs_all)
        ax.set_xticklabels([str(x) for x in xs_all])
        if log_y:
            from matplotlib.ticker import ScalarFormatter
            ax.set_yscale('log')
            for axe in (ax.yaxis,):
                axe.set_major_formatter(ScalarFormatter()); axe.set_minor_formatter(ScalarFormatter())
        ax.grid(True, alpha=.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(a.sortie, 'charge', fichier))
        plt.close(fig)

    if series:
        courbe('debit.png', 'debit_ok', 'Débit (requêtes réussies par seconde)', 'req/s')
        courbe('latence-p95.png', 'p95', 'Latence au 95e centile', 'ms', log_y=True)
        courbe('erreurs.png', 'erreurs_pct', "Taux d'erreur", '%')
        # CPU par service, par déploiement
        for (dep, serie), p in sorted(series.items()):
            srcs = sorted({s for r in p.values() for s, v in r.get('serveur', {}).items()
                           if v['cpu'] is not None and 'dans la VM' not in s and s != 'donnees-connexions'})
            if not srcs:
                continue
            fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
            xs = sorted(p)
            for s in srcs:
                ax.plot(xs, [p[n].get('serveur', {}).get(s, {}).get('cpu') or float('nan') for n in xs], marker='o', label=s)
            ax.set_xscale('log'); ax.set_xticks(xs); ax.set_xticklabels([str(x) for x in xs])
            ax.set_xlabel('Utilisateurs simultanés'); ax.set_ylabel("% d'un cœur")
            ax.set_title(f'Processeur par service — {NOMS[dep]} ({serie})')
            ax.grid(True, alpha=.3); ax.legend(); fig.tight_layout()
            fig.savefig(os.path.join(a.sortie, 'charge', f'cpu-{dep}-{serie}.png'))
            plt.close(fig)
        print(f"\nCourbes écrites dans {os.path.join(a.sortie, 'charge')}")


if __name__ == '__main__':
    main()
