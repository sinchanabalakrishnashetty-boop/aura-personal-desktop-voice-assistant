$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

${mode} = "default"
if ($args.Count -ge 1 -and -not [string]::IsNullOrWhiteSpace($args[0])) {
    ${mode} = ($args[0].ToString().Trim().ToLower())
}

if (${mode} -notin @("default", "quiet-room", "noisy-room", "far-field")) {
    throw "Invalid mode '$mode'. Allowed values: default, quiet-room, noisy-room, far-field"
}

$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    New-Item -ItemType File -Path $envPath | Out-Null
}

function Set-Or-AddEnvLine {
    param(
        [string]$Key,
        [string]$Value
    )

    $escaped = [Regex]::Escape($Key)
    $lines = Get-Content $envPath -ErrorAction SilentlyContinue
    if (-not $lines) { $lines = @() }

    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$escaped\s*=") {
            $lines[$i] = "$Key=$Value"
            $found = $true
        }
    }

    if (-not $found) {
        $lines += "$Key=$Value"
    }

    $maxRetries = 5
    $retryDelay = 300  # ms
    for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
        try {
            [System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.Encoding]::UTF8)
            break
        } catch [System.IO.IOException] {
            if ($attempt -eq $maxRetries) { throw }
            Start-Sleep -Milliseconds $retryDelay
        }
    }
}

switch (${mode}) {
    "default" {
        $values = @{
            "AURA_WAKE_DYNAMIC_ENERGY" = "1"
            "AURA_WAKE_ENERGY_THRESHOLD" = "300"
            "AURA_WAKE_PAUSE_THRESHOLD" = "0.8"
            "AURA_WAKE_AMBIENT_SEC" = "1.0"
            "AURA_WAKE_TIMEOUT_SEC" = "5.0"
            "AURA_WAKE_PHRASE_LIMIT_SEC" = "3.0"
            "AURA_WAKE_TRIGGER_COOLDOWN_SEC" = "0.8"
        }
    }
    "quiet-room" {
        $values = @{
            "AURA_WAKE_DYNAMIC_ENERGY" = "1"
            "AURA_WAKE_ENERGY_THRESHOLD" = "220"
            "AURA_WAKE_PAUSE_THRESHOLD" = "0.75"
            "AURA_WAKE_AMBIENT_SEC" = "0.7"
            "AURA_WAKE_TIMEOUT_SEC" = "4.0"
            "AURA_WAKE_PHRASE_LIMIT_SEC" = "3.0"
            "AURA_WAKE_TRIGGER_COOLDOWN_SEC" = "0.7"
        }
    }
    "noisy-room" {
        $values = @{
            "AURA_WAKE_DYNAMIC_ENERGY" = "1"
            "AURA_WAKE_ENERGY_THRESHOLD" = "420"
            "AURA_WAKE_PAUSE_THRESHOLD" = "0.95"
            "AURA_WAKE_AMBIENT_SEC" = "1.3"
            "AURA_WAKE_TIMEOUT_SEC" = "6.0"
            "AURA_WAKE_PHRASE_LIMIT_SEC" = "3.5"
            "AURA_WAKE_TRIGGER_COOLDOWN_SEC" = "1.1"
        }
    }
    "far-field" {
        $values = @{
            "AURA_WAKE_DYNAMIC_ENERGY" = "1"
            "AURA_WAKE_ENERGY_THRESHOLD" = "260"
            "AURA_WAKE_PAUSE_THRESHOLD" = "1.0"
            "AURA_WAKE_AMBIENT_SEC" = "1.2"
            "AURA_WAKE_TIMEOUT_SEC" = "7.0"
            "AURA_WAKE_PHRASE_LIMIT_SEC" = "4.0"
            "AURA_WAKE_TRIGGER_COOLDOWN_SEC" = "1.0"
        }
    }
}

foreach ($k in $values.Keys) {
    Set-Or-AddEnvLine -Key $k -Value $values[$k]
}

Write-Host "[Aura] Wake-word preset applied: $mode"
Write-Host "[Aura] Updated .env at: $envPath"
Write-Host "[Aura] Optional mic pinning: add AURA_WAKE_MIC_INDEX=<device_index> in .env"