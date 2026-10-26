<#
  Planizi - relevé côté serveur pendant une campagne (étape 17)
  ------------------------------------------------------------
  Échantillonne toutes les $Periode secondes, jusqu'à arrêt (Ctrl+C ou Stop-Job) :
    - hôte     : charge processeur totale du poste
    - jmeter   : processeur et mémoire de l'injecteur (java)  -> l'injecteur n'est-il pas limitant ?
    - mode dk  : chaque conteneur (docker stats : CPU, mémoire, E/S disque) + connexions ouvertes à la base
    - mode vm  : chaque VM vue depuis l'hôte (processus VirtualBoxVM : CPU, mémoire)
                 (E/S disque et connexions de la VM données : voir releve-vm.sh, lancé DANS la VM)

  Colonnes : horodatage_ms ; source ; cpu_pct_coeur (100 = un cœur plein) ; mem_mio ; io_lecture_mio ; io_ecriture_mio ; connexions_bd
  Normalement lancé par campagne.ps1 ; utilisable seul :
      powershell -ExecutionPolicy Bypass -File .\releve-hote.ps1 -Mode dk -Sortie resultats\dk-serveur-s1.csv
#>
param(
    [Parameter(Mandatory)][ValidateSet('dk', 'vm')][string]$Mode,
    [Parameter(Mandatory)][string]$Sortie,
    [int]$Periode = 5,
    [string]$ComposeFile = (Join-Path $PSScriptRoot '..\docker\compose.yaml'),
    [string]$DbUser = 'planizi',
    [string]$DbName = 'planizi'
)
$ErrorActionPreference = 'Continue'
$inv  = [Globalization.CultureInfo]::InvariantCulture
$ncpu = [Environment]::ProcessorCount
$prec = @{}

function EnMio([string]$s) {
    if ($s -notmatch '([\d\.]+)\s*([kKMGT]?i?B)') { return 0 }
    $n = [double]::Parse($Matches[1], $inv)
    switch -CaseSensitive ($Matches[2]) {
        'B' { $n / 1MB } 'kB' { $n * 1000 / 1MB } 'KiB' { $n / 1KB } 'MB' { $n * 1e6 / 1MB } 'MiB' { $n }
        'GB' { $n * 1e9 / 1MB } 'GiB' { $n * 1024 } default { $n }
    }
}
function Pct-Processus([string]$cle, $proc, [long]$t) {
    # % d'un cœur depuis l'échantillon précédent (100 = un cœur occupé à plein)
    $cpu = $proc.TotalProcessorTime.TotalMilliseconds
    $pct = ''
    if ($prec.ContainsKey($cle)) {
        $dt = $t - $prec[$cle].t
        if ($dt -gt 0) { $pct = (100 * ($cpu - $prec[$cle].cpu) / $dt).ToString('F1', $inv) }
    }
    $prec[$cle] = @{ cpu = $cpu; t = $t }
    return $pct
}
function F($x, $d = 1) { ([double]$x).ToString("F$d", $inv) }

$dossier = Split-Path -Parent $Sortie
if ($dossier) { New-Item -ItemType Directory -Force -Path $dossier | Out-Null }
# Fichier existant (paliers ajoutés à une série) : on complète, l'analyse trie par horodatage
if (-not (Test-Path $Sortie)) { 'horodatage_ms;source;cpu_pct_coeur;mem_mio;io_lecture_mio;io_ecriture_mio;connexions_bd' | Out-File -Encoding utf8 $Sortie }

while ($true) {
    $debut = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $t = $debut
    $lignes = New-Object System.Collections.Generic.List[string]

    # --- Hôte (toute la machine), exprimé lui aussi en % d'un cœur
    $total = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'").PercentProcessorTime
    $lignes.Add("$t;hote;$(F ($total * $ncpu));;;;")

    # --- Injecteur (JMeter tourne dans java.exe)
    $java = Get-Process -Name java -ErrorAction SilentlyContinue
    if ($java) {
        $cpuJ = 0; $memJ = 0
        foreach ($p in $java) { $c = Pct-Processus "java-$($p.Id)" $p $t; if ($c) { $cpuJ += [double]::Parse($c, $inv) }; $memJ += $p.WorkingSet64 / 1MB }
        $lignes.Add("$t;jmeter;$(F $cpuJ);$(F $memJ);;;")
    }

    if ($Mode -eq 'dk') {
        # --- Conteneurs du projet
        $ids = docker compose -f $ComposeFile ps -q 2>$null
        if ($ids) {
            docker stats --no-stream --format '{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.BlockIO}}' $ids 2>$null | ForEach-Object {
                $c = $_ -split ';'
                if ($c.Count -ge 4) {
                    $nom = ($c[0] -replace '^planizi-', '') -replace '-\d+$', ''
                    $cpu = $c[1].TrimEnd('%')
                    $mem = EnMio (($c[2] -split '/')[0].Trim())
                    $io  = $c[3] -split '/'
                    $lignes.Add("$t;$nom;$cpu;$(F $mem);$(F (EnMio $io[0].Trim()) 2);$(F (EnMio $io[1].Trim()) 2);")
                }
            }
            # --- Connexions ouvertes à la base (hors la session de mesure elle-même)
            $n = docker compose -f $ComposeFile exec -T donnees psql -U $DbUser -d $DbName -tAc "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();" 2>$null
            if ($n) { $lignes.Add("$t;donnees-connexions;;;;;$("$n".Trim())") }
        }
    }
    else {
        # --- Une ligne par VM : processus VirtualBoxVM.exe, nom de la VM lu dans « --comment »
        Get-CimInstance Win32_Process -Filter "Name='VirtualBoxVM.exe' OR Name='VBoxHeadless.exe'" | ForEach-Object {
            $nom = if ($_.CommandLine -match '--comment\s+"?([^"]+?)"?\s+--') { $Matches[1] } else { "vm-$($_.ProcessId)" }
            $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
            if ($p) {
                $cpu = Pct-Processus "vm-$($_.ProcessId)" $p $t
                $lignes.Add("$t;$nom;$cpu;$(F ($p.WorkingSet64 / 1MB));;;")
            }
        }
    }

    $lignes | Add-Content -Encoding utf8 $Sortie
    $reste = $Periode * 1000 - ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - $debut)
    if ($reste -gt 0) { Start-Sleep -Milliseconds $reste }
}
