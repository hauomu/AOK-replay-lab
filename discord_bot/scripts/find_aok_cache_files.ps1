$OutDir = "$env:USERPROFILE\Desktop\aok_local_cache_candidates"

$TargetFiles = @(
    @{ Label = "AoK assets 2021 rev.SC2Mod"; Size = 16484526 },
    @{ Label = "Age of Knights Replayable v20 PubFix.SC2Map"; Size = 5682671 }
)

$SearchRoots = @(
    "$env:USERPROFILE\Documents\StarCraft II",
    "$env:ProgramData\Blizzard Entertainment",
    "$env:ProgramData\Battle.net",
    "$env:ProgramFiles\StarCraft II",
    "${env:ProgramFiles(x86)}\StarCraft II"
) | Where-Object { Test-Path $_ }

if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$Found = @()
foreach ($root in $SearchRoots) {
    Write-Host "Scanning: $root"
    Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $TargetFiles.Size -contains $_.Length } |
        ForEach-Object {
            $file = $_
            $target = $TargetFiles | Where-Object { $_.Size -eq $file.Length } | Select-Object -First 1
            $safeLabel = $target.Label -replace '[\/:*?"<>|]', '_'
            $destPath = Join-Path $OutDir "$safeLabel - FOUND - $($file.Name)"
            Copy-Item -Path $file.FullName -Destination $destPath -Force
            $Found += [PSCustomObject]@{
                Expected = $target.Label
                Size = $file.Length
                Source = $file.FullName
                CopiedTo = $destPath
            }
            Write-Host "FOUND: $($target.Label)"
        }
}

$Found | Export-Csv -Path (Join-Path $OutDir "found_candidates.csv") -NoTypeInformation -Encoding UTF8
$ZipPath = "$env:USERPROFILE\Desktop\aok_local_cache_candidates.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$OutDir\*" -DestinationPath $ZipPath -Force
Write-Host "Done. ZIP created at: $ZipPath"
