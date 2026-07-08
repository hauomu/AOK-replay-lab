$Root = "$env:USERPROFILE\Documents\StarCraft II"
$OutDir = "$env:USERPROFILE\Desktop\sherman_aok_replays"
$ZipPath = "$env:USERPROFILE\Desktop\sherman_aok_replays.zip"

$NamePatterns = @(
    "*Age of Knights*.SC2Replay",
    "*AOK*.SC2Replay",
    "*AoK*.SC2Replay"
)

if (Test-Path $OutDir) {
    Remove-Item $OutDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$Matches = Get-ChildItem -Path $Root -Recurse -File -Filter "*.SC2Replay" -ErrorAction SilentlyContinue |
    Where-Object {
        $fileName = $_.Name
        $NamePatterns | Where-Object { $fileName -like $_ }
    }

Write-Host "Found $($Matches.Count) replay(s)."

foreach ($file in $Matches) {
    $relativePath = $file.FullName.Substring($Root.Length).TrimStart("\")
    $destination = Join-Path $OutDir $relativePath
    $destinationFolder = Split-Path $destination -Parent
    New-Item -ItemType Directory -Path $destinationFolder -Force | Out-Null
    Copy-Item -Path $file.FullName -Destination $destination -Force
}

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path "$OutDir\*" -DestinationPath $ZipPath -Force

Write-Host "Done. ZIP created at: $ZipPath"
