<#
  Planizi - mesures du déploiement sur trois machines virtuelles
  --------------------------------------------------------------
  Même protocole que mesures.ps1 (conteneurs) : 3 exécutions, médiane retenue.
  À lancer depuis docker/, Docker ARRÊTÉ (docker compose down) :
      powershell -ExecutionPolicy Bypass -File .\mesures-vm.ps1

  ATTENTION : le script éteint puis redémarre les 3 VM (en arrière-plan, sans fenêtre),
  trois fois. Enregistrez votre travail dans les VM avant de le lancer.
  Rapport : ..\docs\mesures-vm-<date>.md
#>
param(
    [int]$Executions = 3,
    [int]$Requetes   = 50,
    [string]$Url     = 'http://localhost:8080/connexion',
    [string[]]$VMs   = @('vm-donnees', 'vm-metier', 'vm-proxy'),   # ordre de démarrage : base, métier, proxy
    [int]$DelaiMax   = 300
)
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$inv = [Globalization.CultureInfo]::InvariantCulture

$vbox = (Get-Command VBoxManage -ErrorAction SilentlyContinue).Source
if (-not $vbox) { $vbox = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe' }
if (-not (Test-Path $vbox)) { Write-Host 'VBoxManage introuvable.' -ForegroundColor Red; exit 1 }

if (docker compose ps -q 2>$null) { Write-Host 'Des conteneurs Planizi tournent : docker compose down d''abord (même port 8080).' -ForegroundColor Red; exit 1 }

function Mediane([double[]]$v) {
    $t = $v | Sort-Object; $n = $t.Count
    if ($n -eq 0) { return [double]::NaN }
    if ($n % 2) { return $t[[int][math]::Floor($n / 2)] }
    return ($t[$n / 2 - 1] + $t[$n / 2]) / 2
}
function Fmt($x, $d = 2) { if ([double]::IsNaN($x)) { 'n/d' } else { $x.ToString("F$d", $inv) } }
function En-Marche { (& $vbox list runningvms) -join "`n" }
function Attendre-Http([int]$max) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $max) {
        if ((& curl.exe -s -o NUL -w '%{http_code}' --max-time 2 $Url) -eq '200') { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}
function Eteindre-Tout {
    foreach ($vm in $VMs) { if ((En-Marche) -match [regex]::Escape("`"$vm`"")) { & $vbox controlvm $vm acpipowerbutton 2>$null | Out-Null } }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt 90) {
        if (-not ($VMs | Where-Object { (En-Marche) -match [regex]::Escape("`"$_`"") })) { return }
        Start-Sleep -Seconds 2
    }
    foreach ($vm in $VMs) { & $vbox controlvm $vm poweroff 2>$null | Out-Null }   # arrêt forcé si l'ACPI n'a pas suffi
    Start-Sleep -Seconds 5
}
function Memoire-VMs {
    # Mémoire réellement occupée sur l'hôte par chaque VM (processus VirtualBoxVM, nom lu dans --comment)
    $r = @{}
    # VirtualBoxVM.exe : VM avec fenêtre ; VBoxHeadless.exe : VM démarrée sans fenêtre
    Get-CimInstance Win32_Process -Filter "Name='VirtualBoxVM.exe' OR Name='VBoxHeadless.exe'" | ForEach-Object {
        $nom = if ($_.CommandLine -match '--comment\s+"?([^"]+?)"?\s+--') { $Matches[1] } else { "pid-$($_.ProcessId)" }
        $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        if ($p) { $r[$nom] = $p.WorkingSet64 / 1MB }
    }
    return $r
}

$res = [ordered]@{}

# ------------------------------------------------------------------ 1. Temps de démarrage
Write-Host "`n== Temps de démarrage ($Executions exécutions : VM éteintes -> HTTP 200 sur $Url) ==" -ForegroundColor Cyan
$demarrages = @()
for ($i = 1; $i -le $Executions; $i++) {
    Write-Host "  arrêt des VM..."
    Eteindre-Tout
    $sw = [Diagnostics.Stopwatch]::StartNew()
    foreach ($vm in $VMs) { & $vbox startvm $vm --type headless 2>&1 | Out-Null }
    $ok = Attendre-Http $DelaiMax
    $sw.Stop()
    if ($ok) { $demarrages += $sw.Elapsed.TotalSeconds }
    Write-Host ("  exécution {0} : {1:N1} s (ok={2})" -f $i, $sw.Elapsed.TotalSeconds, $ok)
    if (-not $ok) { Write-Host "  L'application ne répond pas après $DelaiMax s : les services démarrent-ils automatiquement au boot des VM (systemctl enable) ?" -ForegroundColor Yellow }
}
$res['Temps de démarrage (VM éteintes -> HTTP 200)'] = "$(Fmt (Mediane $demarrages) 1) s  (exécutions : $(($demarrages | ForEach-Object { Fmt $_ 1 }) -join ' ; '))"

# ------------------------------------------------------------------ 2. Mémoire au repos
Write-Host "`n== Mémoire au repos (30 s après le démarrage) ==" -ForegroundColor Cyan
Start-Sleep -Seconds 30
$parVM = @{}; $totaux = @()
for ($i = 1; $i -le $Executions; $i++) {
    $m = Memoire-VMs
    $totaux += ($m.Values | Measure-Object -Sum).Sum
    foreach ($k in $m.Keys) { if (-not $parVM[$k]) { $parVM[$k] = @() }; $parVM[$k] += $m[$k] }
    Write-Host ("  relevé {0} : {1} Mio au total" -f $i, (Fmt $totaux[-1] 0))
    Start-Sleep -Seconds 5
}
$res['Mémoire - somme des 3 VM vue de l''hôte (processus VirtualBoxVM)'] = "$(Fmt (Mediane $totaux) 0) Mio"
foreach ($k in ($parVM.Keys | Sort-Object)) { $res["Mémoire - $k (hôte)"] = "$(Fmt (Mediane $parVM[$k]) 0) Mio" }
$alloue = 0
foreach ($vm in $VMs) {
    $l = & $vbox showvminfo $vm --machinereadable | Where-Object { $_ -match '^memory=(\d+)' }
    if ($l -match '^memory=(\d+)') { $alloue += [int]$Matches[1] }
}
$res['Mémoire - RAM allouée aux 3 VM (configuration)'] = "$alloue Mio"

# ------------------------------------------------------------------ 3. Empreinte disque
Write-Host "`n== Empreinte disque ==" -ForegroundColor Cyan
$totalDisque = 0
foreach ($vm in $VMs) {
    $disques = & $vbox showvminfo $vm --machinereadable | ForEach-Object {
        if ($_ -match '^"[^"]+-\d+-\d+"="(.+\.(vdi|vmdk|vhd|vhdx))"$') { $Matches[1] }
    }
    $taille = 0
    foreach ($d in $disques) { if (Test-Path $d) { $taille += (Get-Item $d).Length } }
    $totalDisque += $taille
    $res["Disque - $vm"] = "$(Fmt ($taille / 1GB) 2) Gio"
    Write-Host ("  {0,-12} {1} Gio" -f $vm, (Fmt ($taille / 1GB) 2))
}
$res['Disque - total des 3 VM'] = "$(Fmt ($totalDisque / 1GB) 2) Gio"

# ------------------------------------------------------------------ 4. Latence applicative
Write-Host "`n== Latence ($Requetes requêtes x $Executions, $Url) ==" -ForegroundColor Cyan
if (-not (Attendre-Http 120)) { Write-Host "  L'application ne répond pas en 200 : latence non mesurée." -ForegroundColor Red }
1..5 | ForEach-Object { & curl.exe -s -o NUL $Url }
$latences = @(); $echecs = 0
for ($i = 1; $i -le $Executions; $i++) {
    $t = @()
    for ($j = 1; $j -le $Requetes; $j++) {
        $s = (& curl.exe -s -o NUL --max-time 10 -w '%{http_code} %{time_total}' $Url) -split ' '
        if ($s[0] -eq '200') { $t += [double]::Parse($s[1], $inv) * 1000 } else { $echecs++ }   # seules les réponses 200 comptent
    }
    $latences += (Mediane $t)
    Write-Host ("  exécution {0} : médiane {1:N2} ms ({2} réponses 200 sur {3})" -f $i, $latences[-1], $t.Count, $Requetes)
}
if ($echecs) { $res['Latence - réponses non 200 ignorées'] = "$echecs" }
$res['Latence applicative (médiane des médianes)'] = "$(Fmt (Mediane $latences)) ms"

# ------------------------------------------------------------------ Rapport
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
New-Item -ItemType Directory -Force -Path ..\docs | Out-Null
$fichier = "..\docs\mesures-vm-$(Get-Date -Format 'yyyyMMdd-HHmm').md"
$md = @('# Mesures — déploiement sur trois machines virtuelles', '', "Relevé du $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Protocole identique à mesures.ps1 : $Executions exécutions, médiane retenue.", '',
        '| Grandeur | Valeur |', '|---|---|')
foreach ($k in $res.Keys) { $md += "| $k | $($res[$k]) |" }
$md += @('', '## Configuration', '', "- Poste : $cpu, $ram Gio de RAM", "- VirtualBox : $(& $vbox --version)", "- VM (ordre de démarrage) : $($VMs -join ', '), démarrées sans interface (headless)", "- URL mesurée : $Url")
$md | Out-File -Encoding utf8 $fichier
Write-Host "`nRapport écrit dans $fichier" -ForegroundColor Green
$res.GetEnumerator() | ForEach-Object { Write-Host ("  {0,-62} {1}" -f $_.Key, $_.Value) }
