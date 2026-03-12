[CmdletBinding()]
param(
    [ValidateSet('docker', 'wsl')]
    [string]$Runtime = 'docker',
    [int]$TimeoutSeconds = 120
)

& (Join-Path $PSScriptRoot 'invoke-lab.ps1') -Task 'down' -Runtime $Runtime -TimeoutSeconds $TimeoutSeconds

