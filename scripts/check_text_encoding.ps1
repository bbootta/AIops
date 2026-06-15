param(
    [string[]]$Paths = @(
        "quant_validation_team_agent",
        "team_agents",
        "tradingagents_team_agent.md"
    )
)

$ErrorActionPreference = "Stop"
$failed = $false

function Test-HasUtf8Bom {
    param([string]$Path)

    $bytes = Get-Content -LiteralPath $Path -Encoding Byte -TotalCount 3
    return $bytes.Count -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
}

foreach ($target in $Paths) {
    if (-not (Test-Path -LiteralPath $target)) {
        Write-Warning "Missing path: $target"
        continue
    }

    $item = Get-Item -LiteralPath $target
    $checkedExtensions = @(".md", ".ps1", ".psm1")
    $files = if ($item.PSIsContainer) {
        Get-ChildItem -LiteralPath $target -Recurse -File |
            Where-Object { $checkedExtensions -contains $_.Extension.ToLowerInvariant() }
    } elseif ($checkedExtensions -contains $item.Extension.ToLowerInvariant()) {
        @($item)
    } else {
        @()
    }

    foreach ($file in $files) {
        $text = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -Raw

        if (-not (Test-HasUtf8Bom -Path $file.FullName)) {
            Write-Host "Missing UTF-8 BOM: $($file.FullName)" -ForegroundColor Red
            $failed = $true
        }

        if ($text -match '<<<<<<<|=======|>>>>>>>') {
            Write-Host "Merge conflict marker found: $($file.FullName)" -ForegroundColor Red
            $failed = $true
        }

        if ($text -match [char]0xFFFD) {
            Write-Host "Unicode replacement character found: $($file.FullName)" -ForegroundColor Red
            $failed = $true
        }
    }
}

if ($failed) {
    exit 1
}

Write-Host "Text encoding check passed."
