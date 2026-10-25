<#
  Planizi - Étape 14 : matrice de joignabilité
  -------------------------------------------
  À lancer depuis le dossier docker/, la pile démarrée (docker compose up -d) :
      powershell -ExecutionPolicy Bypass -File .\verifier-isolation.ps1

  Chaque test ouvre une connexion TCP depuis un terminal DANS le conteneur
  (bash + /dev/tcp, présents dans les trois images Debian). Le résultat est
  écrit dans ..\docs\matrice-joignabilite.md.
#>
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

function Get-Id($svc) { (docker compose ps -q $svc 2>$null | Select-Object -First 1) }

# --- 0. Tout doit tourner : un échec doit venir de l'absence de route, pas d'un arrêt
Write-Host "`n== Etat des services ==" -ForegroundColor Cyan
$services = 'proxy', 'metier', 'donnees'
foreach ($s in $services) {
    $id = Get-Id $s
    if (-not $id) { Write-Host "Le service $s n'est pas lancé : docker compose up -d" -ForegroundColor Red; exit 1 }
    $etat = docker inspect -f '{{.State.Status}} / {{if .State.Health}}{{.State.Health.Status}}{{end}}' $id
    Write-Host ("  {0,-8} {1}" -f $s, $etat)
    if ($etat -notmatch 'running / healthy') { Write-Host "  -> $s n'est pas 'healthy', attendez puis relancez." -ForegroundColor Red; exit 1 }
}

# --- Fonctions de test
function Test-Depuis($svc, $cible, $port) {
    $sortie = docker compose exec -T $svc timeout 3 bash -c "exec 3<>/dev/tcp/$cible/$port" 2>&1
    $code = $LASTEXITCODE
    $detail = ((($sortie | ForEach-Object { "$_" }) -join ' ').Trim() -replace '\s+', ' ')
    if ($code -eq 0)        { $detail = 'connexion établie' }
    elseif ($code -eq 124)  { $detail = 'délai dépassé (aucune route)' }
    elseif (-not $detail)   { $detail = "code $code" }
    [pscustomobject]@{ Ok = ($code -eq 0); Detail = $detail }
}

function Test-Hote($port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $ar = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        $fini = $ar.AsyncWaitHandle.WaitOne(2000)
        $ok = $fini -and $client.Connected
    } catch { $ok = $false } finally { $client.Close() }
    $detail = if ($ok) { 'connexion établie' } else { 'refusée / aucune écoute' }
    if ($ok) {
        # Qui écoute ? (utile si un PostgreSQL installé sur Windows occupe 5432)
        $l = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($l) { $detail += " (processus : $((Get-Process -Id $l.OwningProcess -ErrorAction SilentlyContinue).ProcessName))" }
    }
    [pscustomobject]@{ Ok = $ok; Detail = $detail }
}

# --- 1. Publications de ports déclarées
Write-Host "`n== Ports publiés par le projet ==" -ForegroundColor Cyan
$pub = docker ps --filter "label=com.docker.compose.project=planizi" --format '{{.Names}} -> {{.Ports}}'
$pub | ForEach-Object { Write-Host "  $_" }

# --- 2. La matrice (attendu tiré du sujet)
$tests = @(
    @{ De = "L'hôte";           Vers = 'proxy :80';      Attendu = $true;  F = { Test-Hote 8080 } ;  Note = 'via 8080' },
    @{ De = "L'hôte";           Vers = 'metier :8000';   Attendu = $false; F = { Test-Hote 8000 } },
    @{ De = "L'hôte";           Vers = 'donnees :5432';  Attendu = $false; F = { Test-Hote 5432 } },
    @{ De = 'conteneur proxy';   Vers = 'metier :8000';   Attendu = $true;  F = { Test-Depuis proxy metier 8000 } },
    @{ De = 'conteneur proxy';   Vers = 'donnees :5432';  Attendu = $false; F = { Test-Depuis proxy donnees 5432 } },
    @{ De = 'conteneur metier';  Vers = 'proxy :80';      Attendu = $true;  F = { Test-Depuis metier proxy 80 } },
    @{ De = 'conteneur metier';  Vers = 'donnees :5432';  Attendu = $true;  F = { Test-Depuis metier donnees 5432 } },
    @{ De = 'conteneur donnees'; Vers = 'proxy :80';      Attendu = $false; F = { Test-Depuis donnees proxy 80 } },
    @{ De = 'conteneur donnees'; Vers = 'metier :8000';   Attendu = $true;  F = { Test-Depuis donnees metier 8000 } }
)

# Contre-épreuve : même sans le DNS, l'adresse IP de la base n'est pas joignable depuis le proxy
$ipDonnees = (docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' (Get-Id donnees)).Trim().Split(' ')[0]
$ipProxy   = (docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' (Get-Id proxy)).Trim().Split(' ')[0]
$tests += @{ De = 'conteneur proxy';   Vers = "donnees par IP ($ipDonnees):5432"; Attendu = $false; F = { Test-Depuis proxy $ipDonnees 5432 } }
$tests += @{ De = 'conteneur donnees'; Vers = "proxy par IP ($ipProxy):80";       Attendu = $false; F = { Test-Depuis donnees $ipProxy 80 } }

Write-Host "`n== Matrice de joignabilité ==" -ForegroundColor Cyan
$lignes = @()
$conformes = 0
foreach ($t in $tests) {
    $r = & $t.F
    $conforme = ($r.Ok -eq $t.Attendu)
    if ($conforme) { $conformes++ }
    $attendu = if ($t.Attendu) { 'oui' } else { 'doit échouer' }
    $obtenu  = if ($r.Ok) { 'oui' } else { 'échec' }
    $couleur = if ($conforme) { 'Green' } else { 'Red' }
    Write-Host ("  {0,-18} -> {1,-32} attendu: {2,-13} obtenu: {3,-6} {4}" -f $t.De, $t.Vers, $attendu, $obtenu, $r.Detail) -ForegroundColor $couleur
    $lignes += "| $($t.De) | $($t.Vers) | $attendu | $obtenu | $($r.Detail) | $(if ($conforme) {'✅'} else {'❌'}) |"
}

Write-Host ("`n{0}/{1} cas conformes." -f $conformes, $tests.Count) -ForegroundColor $(if ($conformes -eq $tests.Count) {'Green'} else {'Red'})

# --- 3. Rapport Markdown
New-Item -ItemType Directory -Force -Path ..\docs | Out-Null
$md = @()
$md += '# Matrice de joignabilité — déploiement en conteneurs'
$md += ''
$md += "Relevé du $(Get-Date -Format 'yyyy-MM-dd HH:mm') — $conformes/$($tests.Count) cas conformes."
$md += ''
$md += 'Tests TCP lancés depuis un terminal ouvert dans chaque conteneur (`docker compose exec <service> bash -c "exec 3<>/dev/tcp/<cible>/<port>"`), et depuis Windows pour la ligne « hôte ».'
$md += ''
$md += '| Depuis | Vers | Attendu | Obtenu | Détail | |'
$md += '|---|---|---|---|---|---|'
$md += $lignes
$md += ''
$md += 'Ports publiés :'
$md += ''
$md += '```'
$md += $pub
$md += '```'
$md | Out-File -Encoding utf8 ..\docs\matrice-joignabilite.md
Write-Host "Rapport écrit dans docs\matrice-joignabilite.md"
