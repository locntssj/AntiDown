$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$downloads = Join-Path $root ".ffmpeg-downloads"
$targetRoot = Join-Path $root "bin/android"
New-Item -ItemType Directory -Force -Path $downloads, $targetRoot | Out-Null

$assets = @(
    @{
        Abi = "arm64-v8a"
        Url = "https://github.com/husen-hn/ffmpeg-android-binary/releases/download/v2.0.0/arm64-v8a.zip"
    },
    @{
        Abi = "armeabi-v7a"
        Url = "https://github.com/husen-hn/ffmpeg-android-binary/releases/download/v2.0.0/armeabi-v7a.zip"
    },
    @{
        Abi = "x86_64"
        Url = "https://github.com/husen-hn/ffmpeg-android-binary/releases/download/v2.0.0/x86_64.zip"
    }
)

foreach ($asset in $assets) {
    $abi = $asset.Abi
    $zipPath = Join-Path $downloads "$abi.zip"
    $extractDir = Join-Path $downloads $abi
    $targetDir = Join-Path $targetRoot $abi

    Write-Host "Downloading $abi..."
    Invoke-WebRequest -Uri $asset.Url -OutFile $zipPath

    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $extractDir
    New-Item -ItemType Directory -Force -Path $extractDir, $targetDir | Out-Null
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    $ffmpeg = Get-ChildItem -Path $extractDir -Recurse -File -Filter "ffmpeg" | Select-Object -First 1
    $ffprobe = Get-ChildItem -Path $extractDir -Recurse -File -Filter "ffprobe" | Select-Object -First 1

    if (-not $ffmpeg -or -not $ffprobe) {
        throw "Could not find ffmpeg/ffprobe in $zipPath"
    }

    Copy-Item -LiteralPath $ffmpeg.FullName -Destination (Join-Path $targetDir "ffmpeg") -Force
    Copy-Item -LiteralPath $ffprobe.FullName -Destination (Join-Path $targetDir "ffprobe") -Force

    $libSource = Get-ChildItem -Path $extractDir -Recurse -Directory -Filter "lib" | Select-Object -First 1
    if ($libSource) {
        $libTarget = Join-Path $targetDir "lib"
        New-Item -ItemType Directory -Force -Path $libTarget | Out-Null
        Get-ChildItem -LiteralPath $libSource.FullName -File -Filter "*.so" | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $libTarget -Force
        }
    }
}

Write-Host "Done. Binaries are in bin/android/<abi>/"
