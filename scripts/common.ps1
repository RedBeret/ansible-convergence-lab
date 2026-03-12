Set-StrictMode -Version Latest

function New-LogPath {
    param(
        [Parameter(Mandatory)]
        [string]$RepositoryRoot
    )

    $logDir = Join-Path $RepositoryRoot 'reports\logs'
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    }

    Join-Path $logDir 'windows-runner.jsonl'
}

function Write-StructuredLog {
    param(
        [Parameter(Mandatory)]
        [string]$RepositoryRoot,
        [Parameter(Mandatory)]
        [string]$Event,
        [hashtable]$Data = @{}
    )

    $record = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        event = $Event
    }
    foreach ($key in $Data.Keys) {
        $record[$key] = $Data[$key]
    }

    $json = $record | ConvertTo-Json -Compress -Depth 10
    Add-Content -Path (New-LogPath -RepositoryRoot $RepositoryRoot) -Value $json
}

function Assert-CommandAvailable {
    param(
        [Parameter(Mandatory)]
        [string]$CommandName
    )

    if (-not (Get-Command -Name $CommandName -ErrorAction SilentlyContinue)) {
        throw "Required command '$CommandName' is not available."
    }
}

function Initialize-DockerConfig {
    param(
        [Parameter(Mandatory)]
        [string]$RepositoryRoot
    )

    $dockerConfig = Join-Path $RepositoryRoot '.docker-config'
    if (-not (Test-Path -LiteralPath $dockerConfig)) {
        New-Item -ItemType Directory -Force -Path $dockerConfig | Out-Null
    }

    return $dockerConfig
}

function Convert-ToWslPath {
    param(
        [Parameter(Mandatory)]
        [string]$WindowsPath
    )

    $normalized = $WindowsPath -replace '\\', '/'
    if ($normalized -match '^([A-Za-z]):/(.*)$') {
        $drive = $Matches[1].ToLowerInvariant()
        $rest = $Matches[2]
        return "/mnt/$drive/$rest"
    }

    throw "Unable to convert path '$WindowsPath' to a WSL path."
}

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$ScriptBlock,
        [int]$MaxAttempts = 4,
        [int]$InitialDelaySeconds = 1,
        [int]$MaxDelaySeconds = 8
    )

    $delay = $InitialDelaySeconds
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return & $ScriptBlock
        }
        catch {
            if ($attempt -eq $MaxAttempts) {
                throw
            }
            Start-Sleep -Seconds $delay
            $delay = [Math]::Min($delay * 2, $MaxDelaySeconds)
        }
    }
}

function Invoke-Process {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory)]
        [string]$WorkingDirectory,
        [int]$TimeoutSeconds = 300,
        [hashtable]$Environment = @{}
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    foreach ($argument in $ArgumentList) {
        [void]$startInfo.ArgumentList.Add($argument)
    }

    foreach ($key in $Environment.Keys) {
        $startInfo.Environment[$key] = [string]$Environment[$key]
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo

    $stdoutHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)
        if ($null -ne $eventArgs.Data) {
            Write-Host $eventArgs.Data
        }
    }

    $stderrHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)
        if ($null -ne $eventArgs.Data) {
            Write-Host $eventArgs.Data
        }
    }

    $process.add_OutputDataReceived($stdoutHandler)
    $process.add_ErrorDataReceived($stderrHandler)

    [void]$process.Start()
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill($true)
        }
        catch {
        }
        throw "Command '$FilePath $($ArgumentList -join ' ')' timed out after $TimeoutSeconds seconds."
    }

    $process.WaitForExit()

    if ($process.ExitCode -ne 0) {
        throw "Command '$FilePath $($ArgumentList -join ' ')' failed with exit code $($process.ExitCode)."
    }
}

