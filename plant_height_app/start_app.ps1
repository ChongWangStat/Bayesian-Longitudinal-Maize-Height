$ErrorActionPreference = "Stop"
$AppDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryDirectory = Split-Path -Parent $AppDirectory
$EnvironmentDirectory = Join-Path $RepositoryDirectory ".venv-plant-height"
$PythonExecutable = Join-Path $EnvironmentDirectory "Scripts\python.exe"
$RequirementsFile = Join-Path $AppDirectory "requirements.txt"
$RequirementFiles = @(
    $RequirementsFile
    (Join-Path $RepositoryDirectory "requirements.txt")
    (Join-Path $RepositoryDirectory "requirements-core.txt")
)
$HashFile = Join-Path $EnvironmentDirectory ".requirements-sha256"

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    Write-Host "Creating the application environment..."
    $Created = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.13 -m venv $EnvironmentDirectory
        $Created = $LASTEXITCODE -eq 0
        if (-not $Created) {
            & py -3.12 -m venv $EnvironmentDirectory
            $Created = $LASTEXITCODE -eq 0
        }
    }
    if (-not $Created -and (Get-Command python -ErrorAction SilentlyContinue)) {
        & python -m venv $EnvironmentDirectory
        $Created = $LASTEXITCODE -eq 0
    }
    if (-not $Created) {
        Write-Host "Python 3.12 or 3.13 is required. Install 64-bit Python from python.org, then run this file again."
        exit 1
    }
}

$RequiredHash = ($RequirementFiles | ForEach-Object {
    (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash
}) -join ":"
$InstalledHash = if (Test-Path -LiteralPath $HashFile) {
    (Get-Content -LiteralPath $HashFile -Raw).Trim()
} else {
    ""
}
if ($InstalledHash -ne $RequiredHash) {
    Write-Host "Installing application components. The first installation can take several minutes..."
    & $PythonExecutable -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Could not update pip." }
    & $PythonExecutable -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) { throw "Could not install the application components." }
    Set-Content -LiteralPath $HashFile -Value $RequiredHash -NoNewline
}

Write-Host "Opening Bayesian Plant Height..."
& $PythonExecutable -m streamlit run (Join-Path $AppDirectory "app.py")
