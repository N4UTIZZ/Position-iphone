# Lance en administrateur par start.bat : regle pare-feu (port 5000, profil Prive) + tunneld.
$Root = $PSScriptRoot
if (-not $Root) { $Root = Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location $Root

Write-Host ""
Write-Host "============================================"
Write-Host "  Position iPhone — pare-feu et tunneld"
Write-Host "============================================"
Write-Host ""
Write-Host "Pare-feu : ouverture du port 5000 (reseaux prives uniquement)..."

$shown = netsh advfirewall firewall show rule name="Position iPhone 5000" 2>&1 | Out-String
if ($shown -match "No rules match" -or $shown -match "Aucune r") {
    netsh advfirewall firewall add rule name="Position iPhone 5000" dir=in action=allow protocol=TCP localport=5000 profile=private | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[ERREUR] Impossible d'ajouter la regle pare-feu."
        Write-Host "1. Relance start.bat en tant qu'administrateur."
        Write-Host "2. Definis le Wi-Fi du PC comme reseau Prive :"
        Write-Host "   Parametres > Reseau et Internet > Wi-Fi > ton reseau > Prive."
        Write-Host "Sinon l'iPhone risque de ne pas joindre l'interface."
        Write-Host ""
    } else {
        Write-Host "[OK] Regle pare-feu ajoutee (profil Prive, port TCP 5000)."
    }
} else {
    Write-Host "[OK] La regle pare-feu existe deja."
}

Write-Host ""
$py = Join-Path $Root ".venv\Scripts\python.exe"
Write-Host "Lancement de tunneld. Laisse cette fenetre ouverte."
Write-Host "(Necessaire surtout sur iOS 17.0 a 17.3 ; facultatif ensuite.)"
Write-Host ""

if (-not (Test-Path $py)) {
    Write-Host "[ERREUR] Python du .venv introuvable : $py"
    Write-Host "Relance start.bat d'abord pour creer l'environnement."
    pause
    exit 1
}

& $py -m pymobiledevice3 remote tunneld
Write-Host ""
Write-Host "tunneld s'est arrete."
pause
