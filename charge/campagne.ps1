<#
  Planizi - campagne de charge par paliers (étape 17)
  ---------------------------------------------------
  Lance plan.jmx en ligne de commande, palier par palier, sur UN déploiement,
  en conservant les fichiers bruts et un relevé serveur continu.

  Conteneurs (VM éteintes) :
      powershell -ExecutionPolicy Bypass -File .\campagne.ps1 -Deploiement dk
  Machines virtuelles (conteneurs arrêtés : docker compose down) :
      powershell -ExecutionPolicy Bypass -File .\campagne.ps1 -Deploiement vm -Hote 192.168.56.10 -Port 80
  Seconde série, ordre inversé (vm puis dk) :
      ... -Serie s2

  Fichiers produits dans resultats\ :
      <dep>-<N>-<serie>.csv     résultats bruts JMeter (un par palier)
      <dep>-<N>-<serie>.log     journal JMeter du palier
      <dep>-serveur-<serie>.csv relevé serveur de toute la campagne
      <dep>-<serie>-config.txt  configuration qui a produit les chiffres
#>
param(
    [Parameter(Mandatory)][ValidateSet('dk', 'vm')][string]$Deploiement,
    [string]$Serie    = 's1',
    [string]$Paliers  = '1,5,10,25,50,100',   # liste séparée par des virgules
    [string]$Hote     = 'localhost',
    [int]$Port        = 8080,
    [int]$Montee      = 30,      # gelé à l'étape 16
    [int]$Plateau     = 90,      # >= 60 s hors montée (contrainte du sujet)
    [int]$Pause       = 20,      # repos entre deux paliers
    [string]$JMeter   = '',
    [switch]$SansReinit
)
$ErrorActionPreference = 'Continue'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false   # SQL envoyé à psql en UTF-8
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path resultats | Out-Null

# --- Paliers : « 75,150,200 » -> 75, 150, 200 (et garde-fou contre une valeur aberrante)
$ListePaliers = [int[]]@($Paliers -split '[,; ]+' | Where-Object { $_ } | ForEach-Object { [int]$_ })
if (-not $ListePaliers -or ($ListePaliers | Where-Object { $_ -lt 1 -or $_ -gt 1000 })) { Write-Host "Paliers invalides : $($ListePaliers -join ', ') (attendu : 1 à 1000 utilisateurs)" -ForegroundColor Red; exit 1 }
Write-Host "Paliers : $($ListePaliers -join ', ')"

# --- JMeter
if (-not $JMeter) {
    $cmd = Get-Command jmeter.bat -ErrorAction SilentlyContinue
    if ($cmd) { $JMeter = $cmd.Source }
    else { $JMeter = (Get-ChildItem 'C:\apache-jmeter-*\bin\jmeter.bat' -ErrorAction SilentlyContinue | Select-Object -Last 1).FullName }
}
if (-not $JMeter -or -not (Test-Path $JMeter)) { Write-Host 'jmeter.bat introuvable : passez -JMeter C:\chemin\apache-jmeter-5.6.3\bin\jmeter.bat' -ForegroundColor Red; exit 1 }

$compose = Join-Path $PSScriptRoot '..\docker\compose.yaml'
$url = "http://${Hote}:$Port/connexion"

# --- Un seul déploiement en marche
Write-Host "`n== Contrôle : un seul déploiement en marche ==" -ForegroundColor Cyan
$conteneurs = docker compose -f $compose ps -q 2>$null
$vbox = Get-Command VBoxManage -ErrorAction SilentlyContinue
if (-not $vbox -and (Test-Path 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe')) { $vbox = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe' }
$vms = if ($vbox) { & $vbox list runningvms } else { @() }
if ($Deploiement -eq 'dk' -and $vms) { Write-Host "VM en marche :`n$($vms -join "`n")`nÉteignez-les avant la campagne conteneurs." -ForegroundColor Red; exit 1 }
if ($Deploiement -eq 'vm' -and $conteneurs) { Write-Host "Des conteneurs Planizi tournent : docker compose down (dans docker\) avant la campagne VM." -ForegroundColor Red; exit 1 }
Write-Host '  ok'

# --- Base réinitialisée depuis les scripts de peuplement
if (-not $SansReinit) {
    Write-Host "`n== Réinitialisation de la base ==" -ForegroundColor Cyan
    if ($Deploiement -eq 'dk') {
        docker compose -f $compose down -v 2>$null | Out-Null
        docker compose -f $compose up -d --wait 2>$null | Out-Null
        Get-Content -Raw -Encoding utf8 .\comptes-test.sql | docker compose -f $compose exec -T donnees psql -q -U planizi -d planizi
    } else {
        Write-Host '  Sur la VM données, rejouez les trois scripts (voir PROCEDURE.md, section 3) :'
        Write-Host '    psql -d planizi -f schema.sql -f donnees.sql -f comptes-test.sql' -ForegroundColor Yellow
        Write-Host '  et lancez releve-vm.sh dans la VM données.'
        if ((Read-Host '  Base réinitialisée et relevé lancé ? (o/n)') -ne 'o') { exit 0 }
    }
}

# --- L'application répond-elle ?
$code = & curl.exe -s -o NUL -w '%{http_code}' --max-time 5 $url
if ($code -ne '200') { Write-Host "L'application ne répond pas sur $url (code $code)." -ForegroundColor Red; exit 1 }

# --- Configuration consignée
$cfg = "resultats\$Deploiement-$Serie-config.txt"
@(
    "Campagne $Deploiement / série $Serie — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Cible : $url ; paliers : $($ListePaliers -join ', ') ; montée $Montee s ; plateau $Plateau s ; pause $Pause s",
    "JMeter : $JMeter",
    "Java : $((& java -version 2>&1 | Select-Object -First 1) -join '')",
    "Poste : $((Get-CimInstance Win32_Processor | Select-Object -First 1).Name) ; $([math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)) Gio ; $([Environment]::ProcessorCount) cœurs logiques",
    "Docker : $(docker version --format '{{.Server.Version}}' 2>$null) ; VM en marche : $($vms -join ' | ')"
) | Out-File -Encoding utf8 $cfg

# --- Relevé serveur en arrière-plan pendant toute la campagne
$releve = Join-Path $PSScriptRoot "resultats\$Deploiement-serveur-$Serie.csv"
$job = Start-Job -FilePath (Join-Path $PSScriptRoot 'releve-hote.ps1') -ArgumentList $Deploiement, $releve, 5, (Resolve-Path $compose).Path
Write-Host "`nRelevé serveur : $releve (job $($job.Id))"
Start-Sleep -Seconds 10       # quelques échantillons au repos avant le premier palier

try {
    foreach ($n in $ListePaliers) {
        $nom = "resultats\$Deploiement-$n-$Serie"
        Write-Host "`n== Palier $n utilisateurs ($Montee s de montée + $Plateau s de plateau) ==" -ForegroundColor Cyan
        & $JMeter -n -t plan.jmx -l "$nom.csv" -j "$nom.log" `
            "-Jhote=$Hote" "-Jport=$Port" "-Jutilisateurs=$n" '-Jiterations=-1' `
            "-Jmontee=$Montee" "-Jduree=$($Montee + $Plateau)" `
            '-Jjmeter.save.saveservice.output_format=csv' '-Jjmeter.save.saveservice.thread_counts=true' `
            '-Jjmeter.save.saveservice.assertion_results_failure_message=true'
        Start-Sleep -Seconds $Pause
    }
}
finally {
    Stop-Job $job; Remove-Job $job
    Write-Host "`nCampagne terminée. Analyse : python analyse.py" -ForegroundColor Green
}
