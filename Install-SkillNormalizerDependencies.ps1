<#
.SYNOPSIS
    Installs dependencies for the SkillNormalizer Python script with logging and progress tracking.
.DESCRIPTION
    This script ensures Python is installed, checks for pip, installs required packages (pandas),
    and logs all actions to a file while displaying a progress bar.
.NOTES
    File Name      : Install-SkillNormalizerDependencies.ps1
    Prerequisite   : PowerShell 5.1 or later
#>

# Configuration
$LogPath = "$env:TEMP\SkillNormalizer_Install.log"
$RequiredPackages = @("pandas")

# Initialize log file
try {
    Start-Transcript -Path $LogPath -Append | Out-Null
    Write-Host "Logging installation progress to: $LogPath" -ForegroundColor Cyan

    # Progress bar function
    function Show-Progress {
        param (
            [int]$Step,
            [int]$TotalSteps,
            [string]$Message
        )
        $PercentComplete = ($Step / $TotalSteps) * 100
        Write-Progress -Activity "Installing Dependencies" -Status $Message -PercentComplete $PercentComplete
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message" -ForegroundColor Cyan
    }

    # Total steps for progress tracking
    $TotalSteps = 5 + $RequiredPackages.Count
    $CurrentStep = 1

    # Check Python installation
    Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Checking Python installation..."
    $CurrentStep++

    $PythonInstalled = $false

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonVersion = (python --version 2>&1)
        Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Python found: $PythonVersion"
        $PythonInstalled = $true
    }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        $PythonVersion = (python3 --version 2>&1)
        Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Python found: $PythonVersion"
        $PythonInstalled = $true
    }

    # Install Python if missing
    if (-not $PythonInstalled) {
        Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Python not found. Preparing to install..."
        $CurrentStep++

        $InstallPython = Read-Host "Do you want to install Python now? (Y/N)"

        if ($InstallPython -eq 'Y' -or $InstallPython -eq 'y') {
            Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Downloading Python installer..."
            $CurrentStep++

            $PythonUrl = "https://www.python.org/ftp/python/latest/python-3.x.x-amd64.exe"
            $InstallerPath = "$env:TEMP\python-installer.exe"

            try {
                Invoke-WebRequest -Uri $PythonUrl -OutFile $InstallerPath -ErrorAction Stop
                Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Installing Python..."
                $CurrentStep++

                Start-Process -FilePath $InstallerPath -Args "/quiet InstallAllUsers=1 PrependPath=1" -Wait
                Remove-Item $InstallerPath -Force

                # Refresh PATH
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

                if (Get-Command python -ErrorAction SilentlyContinue) {
                    Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Python installed successfully"
                    $PythonInstalled = $true
                } else {
                    throw "Python installation failed"
                }
            } catch {
                Write-Host "Error: $_" -ForegroundColor Red
                Stop-Transcript | Out-Null
                Add-Content -Path $LogPath -Value "ERROR: $_"
                exit 1
            }
        } else {
            Write-Host "Python is required. Exiting." -ForegroundColor Red
            Stop-Transcript | Out-Null
            Add-Content -Path $LogPath -Value "ERROR: Python installation aborted by user"
            exit 1
        }
    }

    # Check pip
    Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Checking pip installation..."
    $CurrentStep++

    try {
        $PipVersion = (python -m pip --version 2>&1)
        Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "pip found: $PipVersion"
    } catch {
        Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Installing pip..."
        $CurrentStep++

        python -m ensurepip --default-pip
        if (-not $?) {
            Write-Host "Failed to install pip." -ForegroundColor Red
            Stop-Transcript | Out-Null
            Add-Content -Path $LogPath -Value "ERROR: Failed to install pip"
            exit 1
        }
    }

    # Install packages
    foreach ($Package in $RequiredPackages) {
        Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "Installing $Package..."
        $CurrentStep++

        try {
            python -m pip install $Package --upgrade | Out-Null
            Show-Progress -Step $CurrentStep -TotalSteps $TotalSteps -Message "$Package installed successfully"
        } catch {
            Write-Host "Failed to install $Package." -ForegroundColor Red
            Stop-Transcript | Out-Null
            Add-Content -Path $LogPath -Value "ERROR: Failed to install $Package"
            exit 1
        }
    }

    # Completion
    Write-Progress -Completed -Activity "Installation Complete"
    Write-Host "`nAll dependencies installed successfully!" -ForegroundColor Green
}
finally {
    # Ensure transcript is stopped before trying to write to the log file again
    Stop-Transcript | Out-Null
    Add-Content -Path $LogPath -Value "SUCCESS: All dependencies installed at $(Get-Date)"
}

# Show log location
Write-Host "Detailed log available at: $LogPath" -ForegroundColor Cyan