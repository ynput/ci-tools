# Receive first positional argument
Param([Parameter(Position=0)]$FunctionName)
$current_dir = Get-Location

function defaultfunc {
    Write-Host ""
    Write-Host "Usage: manage.ps1 <function>"
    Write-Host ""
    Write-Host "Functions:"
    Write-Host "  install_poetry"
    Write-Host "  install_venv"
    Write-Host ""
}

function InstallPoetry {
    $poetry_path = "$current_dir/.poetry"

    if (Test-Path -Path $poetry_path) {
        Write-Host "Poetry already installed"
    } else {
        $env:POETRY_HOME=$poetry_path
        Write-Host "Installing poetry"
        (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
    }
}

function InstallVenv {
    $poetry_executable = "$current_dir/.poetry/bin/poetry.exe"

    if (!(Test-Path -Path $poetry_executable)) {
        Write-Host "Poetry not installed"
        InstallPoetry
    }

    Write-Host "Installing venv with poetry executable ""$poetry_executable"""
    & $poetry_executable install
}

function main {
      if ($FunctionName -eq "install_poetry") {
        InstallPoetry
    } elseif ($FunctionName -eq "install_venv") {
        InstallVenv
    } elseif ($null -eq $FunctionName) {
        defaultfunc
    } else {
        Write-Host "Unknown function ""$FunctionName"""
        defaultfunc
    }
}

main