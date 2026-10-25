<#
  Planizi - Étape 14 : mesures du déploiement en conteneurs
  --------------------------------------------------------
  Même protocole qu'à l'étape 10 : 3 exécutions, médiane retenue, configuration consignée.

  Usage (depuis docker/, Docker Desktop démarré, VM VirtualBox ÉTEINTES) :
      powershell -ExecutionPolicy Bypass -File .\mesures.ps1
      powershell -ExecutionPolicy Bypass -File .\mesures.ps1 -Requetes 100 -Url http://localhost:8080/connexion
      powershell -ExecutionPolicy Bypass -File .\mesures.ps1 -MiseEnPlace     # repart de zéro (supprime images + volume)

  Le rapport est écrit dans ..\docs\mesures-conteneurs-<date>.md
  IMPORTANT : utilisez pour -Url et -Requetes les mêmes valeurs qu'à l'étape 10.
#>
param(
    [int]$Executions = 3,
    [int]$Requetes   = 50,
    [string]$Url     = 'http://localhost:8080/connexion',
    [switch]$MiseEnPlace
)
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$inv = [Globalization.CultureInfo]::InvariantCulture

function Mediane([double[]]$v) {
    $t = $v | Sort-Object; $n = $t.Count
    if ($n -eq 0) { return [double]::NaN }
    if ($n % 2) { return $t[[int][math]::Floor($n / 2)] }
    return ($t[$n / 2 - 1] + $t[$n / 2]) / 2
}
function Attendre-Http([int]$delaiMax = 180) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $delaiMax) {
        $code = & curl.exe -s -o NUL -w '%{http_code}' --max-time 2 $Url
        if ($code -eq '200') { return $true }
        Start-Sleep -Milliseconds 200
    }
    return $false
}
function EnMio([string]$s) {   # "45.2MiB" -> 45.2
    if ($s -notmatch '([\d\.]+)\s*([kKMG]?i?B)') { return 0 }
    $n = [double]::Parse($Matches[1], $inv)
    switch ($Matches[2]) { 'B' { $n / 1MB } 'KiB' { $n / 1KB } 'kB' { $n / 1000 / 1.048576 } 'MiB' { $n } 'MB' { $n / 1.048576 } 'GiB' { $n * 1024 } 'GB' { $n * 1000 / 1.048576 } default { $n } }
}
function Memoire-VM {          # mémoire de la VM Linux qui héberge le moteur Docker (WSL 2)
    $p = Get-Process -Name vmmemWSL, vmmem -ErrorAction SilentlyContinue
    if (-not $p) { return [double]::NaN }
    return (($p | Measure-Object WorkingSet64 -Sum).Sum / 1MB)
}
function Memoire-Conteneurs {
    $ids = docker compose ps -q
    if (-not $ids) { return 0 }
    $total = 0
    docker stats --no-stream --format '{{.MemUsage}}' $ids | ForEach-Object { $total += EnMio (($_ -split '/')[0].Trim()) }
    return $total
}
function Fmt($x, $d = 2) { if ([double]::IsNaN($x)) { 'n/d' } else { $x.ToString("F$d", $inv) } }

docker info --format '{{.ServerVersion}}' 1>$null 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host 'Le moteur Docker ne répond pas : lancez Docker Desktop.' -ForegroundColor Red; exit 1 }

$res = [ordered]@{}

# ------------------------------------------------------------------ 0. Mise en place depuis zéro
if ($MiseEnPlace) {
    Write-Host "`n== Mise en place depuis zéro ==" -ForegroundColor Cyan
    $r = Read-Host 'Cela supprime les conteneurs, le VOLUME (données) et les images du projet. Continuer ? (o/n)'
    if ($r -ne 'o') { exit 0 }
    docker compose down -v --rmi all 2>$null | Out-Null
    docker image rm python:3.12.8-slim-bookworm nginx:1.27.5-bookworm postgres:16.9-bookworm 2>$null | Out-Null
    docker builder prune -af 2>$null | Out-Null
    $sw = [Diagnostics.Stopwatch]::StartNew()
    docker compose up -d --build
    $ok = Attendre-Http 900
    $sw.Stop()
    $res['Mise en place (téléchargement + construction + 1er démarrage)'] = "$(Fmt $sw.Elapsed.TotalSeconds 1) s"
    Write-Host ("  -> {0:N1} s (ok={1})" -f $sw.Elapsed.TotalSeconds, $ok)
}

# ------------------------------------------------------------------ 1. Préparation (non chronométrée)
Write-Host "`n== Préparation : construction des images (non chronométrée) ==" -ForegroundColor Cyan
docker compose build -q
docker compose up -d --wait 2>$null | Out-Null
if (-not (Attendre-Http)) { Write-Host "L'application ne répond pas sur $Url" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------ 2. Temps de démarrage
Write-Host "`n== Temps de démarrage ($Executions exécutions) ==" -ForegroundColor Cyan
$demarrages = @(); $memBase = @()
for ($i = 1; $i -le $Executions; $i++) {
    docker compose down 2>$null | Out-Null          # conteneurs détruits, volume CONSERVÉ
    Start-Sleep -Seconds 5
    $memBase += Memoire-VM                           # VM Docker sans le projet
    $sw = [Diagnostics.Stopwatch]::StartNew()
    docker compose up -d 2>$null | Out-Null
    $ok = Attendre-Http
    $sw.Stop()
    $demarrages += $sw.Elapsed.TotalSeconds
    Write-Host ("  exécution {0} : {1:N2} s (ok={2})" -f $i, $sw.Elapsed.TotalSeconds, $ok)
}
$res['Temps de démarrage (up -> HTTP 200)'] = "$(Fmt (Mediane $demarrages)) s  (exécutions : $(($demarrages | ForEach-Object { Fmt $_ }) -join ' ; '))"

# ------------------------------------------------------------------ 3. Mémoire
Write-Host "`n== Mémoire (pile au repos) ==" -ForegroundColor Cyan
Start-Sleep -Seconds 15
$memC = @(); $memV = @()
for ($i = 1; $i -le $Executions; $i++) {
    $memC += Memoire-Conteneurs
    $memV += Memoire-VM
    Write-Host ("  relevé {0} : conteneurs {1:N1} Mio, VM Docker (vmmemWSL) {2} Mio" -f $i, $memC[-1], (Fmt $memV[-1] 0))
    Start-Sleep -Seconds 5
}
$res['Mémoire - somme des 3 conteneurs (docker stats)'] = "$(Fmt (Mediane $memC) 1) Mio"
$res['Mémoire - VM du moteur Docker, pile lancée'] = "$(Fmt (Mediane $memV) 0) Mio"
$res['Mémoire - VM du moteur Docker, sans la pile'] = "$(Fmt (Mediane $memBase) 0) Mio"
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' (docker compose ps -q) | Out-String | Write-Host

# ------------------------------------------------------------------ 4. Empreinte disque
Write-Host "`n== Empreinte disque ==" -ForegroundColor Cyan
foreach ($img in 'planizi-metier:1.0', 'planizi-proxy:1.0', 'postgres:16.9-bookworm') {
    $o = docker image inspect -f '{{.Size}}' $img 2>$null
    $taille = if ($o) { [double]$o / 1MB } else { [double]::NaN }
    $res["Image $img"] = "$(Fmt $taille 1) Mio"
    Write-Host ("  {0,-26} {1} Mio" -f $img, (Fmt $taille 1))
}
$vol = docker compose exec -T donnees du -sb /var/lib/postgresql/data 2>$null
$volMio = if ($vol) { [double](($vol -split '\s+')[0]) / 1MB } else { [double]::NaN }
$res['Volume pgdata (données)'] = "$(Fmt $volMio 1) Mio"
$vhdx = @("$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx", "$env:LOCALAPPDATA\Docker\wsl\data\ext4.vhdx", "$env:LOCALAPPDATA\Docker\wsl\main\ext4.vhdx") |
        Where-Object { Test-Path $_ } | ForEach-Object { Get-Item $_ }
foreach ($f in $vhdx) { $res["Disque virtuel Docker Desktop ($($f.Name))"] = "$(Fmt ($f.Length / 1GB) 2) Gio" }
$df = docker system df | Out-String
Write-Host $df

# ------------------------------------------------------------------ 5. Latence applicative
Write-Host "`n== Latence ($Requetes requêtes x $Executions, $Url) ==" -ForegroundColor Cyan
1..5 | ForEach-Object { & curl.exe -s -o NUL $Url }   # échauffement
$latences = @()
for ($i = 1; $i -le $Executions; $i++) {
    $t = @()
    for ($j = 1; $j -le $Requetes; $j++) {
        $s = & curl.exe -s -o NUL -w '%{time_total}' $Url
        $t += [double]::Parse($s, $inv) * 1000
    }
    $m = Mediane $t
    $latences += $m
    Write-Host ("  exécution {0} : médiane {1:N2} ms (min {2:N2}, max {3:N2})" -f $i, $m, ($t | Measure-Object -Minimum).Minimum, ($t | Measure-Object -Maximum).Maximum)
}
$res['Latence applicative (médiane des médianes)'] = "$(Fmt (Mediane $latences)) ms"

# ------------------------------------------------------------------ 6. Configuration consignée
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$dv  = docker version --format 'Client {{.Client.Version}} / Moteur {{.Server.Version}}'
$cv  = docker compose version --short
$dinfo = docker info --format 'CPU alloués : {{.NCPU}} ; mémoire allouée : {{.MemTotal}} octets ; noyau : {{.KernelVersion}} ; OS moteur : {{.OperatingSystem}}'
$wslcfg = if (Test-Path "$env:USERPROFILE\.wslconfig") { (Get-Content "$env:USERPROFILE\.wslconfig") -join ' | ' } else { 'absent (valeurs par défaut de WSL 2)' }

New-Item -ItemType Directory -Force -Path ..\docs | Out-Null
$fichier = "..\docs\mesures-conteneurs-$(Get-Date -Format 'yyyyMMdd-HHmm').md"
$md = @('# Mesures — déploiement sur trois conteneurs', '', "Relevé du $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Protocole : $Executions exécutions, médiane retenue.", '')
$md += '| Grandeur | Valeur |'
$md += '|---|---|'
foreach ($k in $res.Keys) { $md += "| $k | $($res[$k]) |" }
$md += ''
$md += '## Configuration'
$md += ''
$md += "- Poste : $cpu, $ram Gio de RAM, $($os.Caption) $($os.Version)"
$md += "- Docker : $dv ; Compose $cv"
$md += "- Moteur : $dinfo"
$md += "- .wslconfig : $wslcfg"
$md += "- URL mesurée : $Url ($Requetes requêtes par exécution)"
$md += ''
$md += '## docker system df'
$md += ''
$md += '```'
$md += $df.Trim()
$md += '```'
$md | Out-File -Encoding utf8 $fichier
Write-Host "`nRapport écrit dans $fichier" -ForegroundColor Green
$res.GetEnumerator() | ForEach-Object { Write-Host ("  {0,-55} {1}" -f $_.Key, $_.Value) }
