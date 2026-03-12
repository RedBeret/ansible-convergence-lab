[CmdletBinding()]
param(
    [ValidateSet('demo', 'precheck', 'backup', 'deploy', 'verify', 'drift-check', 'rollback', 'inject-drift', 'reset', 'test', 'down')]
    [string]$Task = 'demo',
    [ValidateSet('docker', 'wsl')]
    [string]$Runtime = 'docker',
    [switch]$Build,
    [switch]$ShutdownOnExit,
    [int]$TimeoutSeconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Write-StructuredLog -RepositoryRoot $repositoryRoot -Event 'lab.invoke.start' -Data @{
    task = $Task
    runtime = $Runtime
    timeout_seconds = $TimeoutSeconds
}

try {
    switch ($Runtime) {
        'docker' {
            Assert-CommandAvailable -CommandName 'docker'
            $dockerConfig = Initialize-DockerConfig -RepositoryRoot $repositoryRoot
            $environment = @{
                DOCKER_CONFIG = $dockerConfig
            }

            if ($Task -eq 'down') {
                Write-Host "Stopping the local containers..."
                Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'down', '--remove-orphans') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
                break
            }

            if ($Build.IsPresent) {
                Write-Host "Building the simulator and ansible images..."
                Invoke-WithRetry -ScriptBlock {
                    Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'build', 'simulator', 'ansible') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
                }
            }

            Write-Host "Starting the local simulator container..."
            Invoke-WithRetry -ScriptBlock {
                Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'up', '-d', 'simulator') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
            }

            Write-Host "Running make $Task inside the Linux ansible container..."
            Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'run', '--rm', 'ansible', 'make', $Task) -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment

            if ($ShutdownOnExit.IsPresent) {
                Write-Host "Stopping the local containers..."
                Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'down', '--remove-orphans') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
            }
        }
        'wsl' {
            Assert-CommandAvailable -CommandName 'wsl.exe'
            Assert-CommandAvailable -CommandName 'docker'
            $dockerConfig = Initialize-DockerConfig -RepositoryRoot $repositoryRoot
            $environment = @{
                DOCKER_CONFIG = $dockerConfig
            }

            if ($Task -eq 'down') {
                Write-Host "Stopping the local containers..."
                Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'down', '--remove-orphans') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
                break
            }

            if ($Build.IsPresent) {
                Write-Host "Building the simulator image for the WSL path..."
                Invoke-WithRetry -ScriptBlock {
                    Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'build', 'simulator') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
                }
            }

            Write-Host "Starting the local simulator container for the WSL path..."
            Invoke-WithRetry -ScriptBlock {
                Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'up', '-d', 'simulator') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
            }

            $wslPath = Convert-ToWslPath -WindowsPath $repositoryRoot
            $bashCommand = "cd '$wslPath' && export LAB_WORKSPACE='$wslPath' LAB_SIMULATOR_URL='http://host.docker.internal:18080' && make $Task"
            Write-Host "Running make $Task inside WSL Ubuntu..."
            Invoke-Process -FilePath 'wsl.exe' -ArgumentList @('-d', 'Ubuntu', '--', 'bash', '-lc', $bashCommand) -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds

            if ($ShutdownOnExit.IsPresent) {
                Write-Host "Stopping the local containers..."
                Invoke-Process -FilePath 'docker' -ArgumentList @('compose', 'down', '--remove-orphans') -WorkingDirectory $repositoryRoot -TimeoutSeconds $TimeoutSeconds -Environment $environment
            }
        }
    }

    Write-StructuredLog -RepositoryRoot $repositoryRoot -Event 'lab.invoke.success' -Data @{
        task = $Task
        runtime = $Runtime
    }
}
catch {
    Write-StructuredLog -RepositoryRoot $repositoryRoot -Event 'lab.invoke.failure' -Data @{
        task = $Task
        runtime = $Runtime
        error = $_.Exception.Message
    }
    throw
}
