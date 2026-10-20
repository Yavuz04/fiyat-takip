# PC görevini kurar: ayrı bir klon + kendi sanal ortamı + Windows Görev Zamanlayıcı (25 dk'da bir).
# Görev sadece oturum açıkken çalışır (şifre gerekmez), pencere açmaz, kaçırılan çalışmayı PC açılınca yapar.
#
# Kullanım (PowerShell):  powershell -ExecutionPolicy Bypass -File tools\ev_gorevi_kur.ps1
# Kaldırmak için:         Unregister-ScheduledTask -TaskName FiyatTakipBot -Confirm:$false

$ErrorActionPreference = "Stop"
$Repo   = "https://github.com/Yavuz04/fiyat-takip"
$Target = Join-Path $env:USERPROFILE "fiyat-takip-ev"
$Source = Split-Path -Parent $PSScriptRoot          # bu betiğin bulunduğu geliştirme klasörü
$Task   = "FiyatTakipBot"

if (-not (Test-Path $Target)) { git clone -q $Repo $Target }
if (-not (Test-Path "$Target\.env")) { Copy-Item "$Source\.env" "$Target\.env" }

if (-not (Test-Path "$Target\.venv\Scripts\python.exe")) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { $py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe" }
    & $py -m venv "$Target\.venv"
}
& "$Target\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$Target\.venv\Scripts\python.exe" -m pip install -q -r "$Target\requirements.txt"

$action = New-ScheduledTaskAction -Execute "$Target\.venv\Scripts\pythonw.exe" `
    -Argument "`"$Target\tools\ev_gorevi.py`"" -WorkingDirectory $Target
$every = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 25)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $Task -Action $action -Trigger @($every, $logon) -Settings $settings `
    -Principal $principal -Force `
    -Description "Fiyat takip botu: GitHub'ı engelleyen siteleri (Trendyol, Akakçe, Cimri, PttAVM, Pazarama, epey) 25 dk'da bir tarar. Log: $Target\logs\ev-gorevi.log" | Out-Null

Write-Host "Görev kuruldu: $Task  (ilk çalışma ~1 dk sonra)"
Write-Host "Log: $Target\logs\ev-gorevi.log"
