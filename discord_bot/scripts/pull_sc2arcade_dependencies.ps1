$RegionId = 2
$MapId = 131901
$OutDir = "$env:USERPROFILE\Desktop\aok_sc2arcade_dependencies"
$ApiUrl = "https://sc2arcade.com/api/maps/$RegionId/$MapId/dependencies"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$data = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "User-Agent" = "AoKReplayAnalyzer/0.1" }

$regionCode = switch ($RegionId) {
    1 { "us" }
    2 { "eu" }
    3 { "kr" }
    5 { "cn" }
    default { throw "Unknown region id: $RegionId" }
}

$downloadable = $data.list | Where-Object { $_.mapHeader.archiveSize -ge 256 -and $_.mapHeader.archiveHash }
foreach ($item in $downloadable) {
    $name = $item.map.name
    $version = "v$($item.mapHeader.majorVersion).$($item.mapHeader.minorVersion)"
    $hash = $item.mapHeader.archiveHash
    $safeName = ($name -replace '[\/:*?"<>|]', '_')
    $fileName = "$safeName - $version - $hash.s2ma"
    $outFile = Join-Path $OutDir $fileName
    $url = if ($regionCode -eq "cn") { "http://cn-sc2.depot.battlenet.com.cn:1119/$hash.s2ma" } else { "https://$regionCode-s2-depot.classic.blizzard.com/$hash.s2ma" }
    if (-not (Test-Path $outFile)) {
        Invoke-WebRequest -Uri $url -OutFile $outFile -Headers @{ "User-Agent" = "AoKReplayAnalyzer/0.1" }
    }
}

$data | ConvertTo-Json -Depth 30 | Set-Content -Path (Join-Path $OutDir "manifest.json") -Encoding UTF8
$ZipPath = "$env:USERPROFILE\Desktop\aok_sc2arcade_dependencies.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$OutDir\*" -DestinationPath $ZipPath -Force
Write-Host "Done. ZIP created at: $ZipPath"
