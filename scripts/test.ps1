[CmdletBinding()]
param(
    [ValidateSet('docker', 'wsl')]
    [string]$Runtime = 'docker',
    [switch]$Build,
    [switch]$ShutdownOnExit,
    [int]$TimeoutSeconds = 300
)

& (Join-Path $PSScriptRoot 'invoke-lab.ps1') -Task 'test' -Runtime $Runtime -Build:$Build -ShutdownOnExit:$ShutdownOnExit -TimeoutSeconds $TimeoutSeconds
