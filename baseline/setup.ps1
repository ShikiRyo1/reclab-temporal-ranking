param(
    [string]$Workspace = 'H:\Career_AI_Portfolio',
    [string]$Python = 'C:\Users\13191\AppData\Local\Programs\Python\Python312\python.exe'
)
$ErrorActionPreference = 'Stop'
$Commit = 'aa8332189cd495be6ffaa7e1c8054f1c180b5ef3'
$SourcePath = Join-Path $Workspace 'external\recommenders'
$EnvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$env:UV_CACHE_DIR = Join-Path $Workspace 'cache\uv'
$env:PIP_CACHE_DIR = Join-Path $Workspace 'cache\pip'
$env:P1_WORKSPACE = $Workspace
$env:PYTHONIOENCODING = 'utf-8'
if (-not (Test-Path -LiteralPath $SourcePath)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $SourcePath -Parent) | Out-Null
    & git clone --filter=blob:none --no-checkout 'https://github.com/recommenders-team/recommenders.git' $SourcePath
    if ($LASTEXITCODE -ne 0) { throw 'Git clone failed.' }
    & git -C $SourcePath sparse-checkout init --cone
    if ($LASTEXITCODE -ne 0) { throw 'Sparse checkout initialization failed.' }
    & git -C $SourcePath sparse-checkout set recommenders examples/00_quick_start examples/02_model_collaborative_filtering
    if ($LASTEXITCODE -ne 0) { throw 'Sparse checkout selection failed.' }
    & git -C $SourcePath checkout $Commit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned checkout failed.' }
}
$ActualCommit = & git -C $SourcePath rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $ActualCommit -ne $Commit) {
    throw 'Existing upstream checkout differs; preserve it and choose a separate workspace.'
}
if (-not (Test-Path -LiteralPath $EnvPython)) {
    & $Python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
& $EnvPython -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"
if ($LASTEXITCODE -ne 0) { throw 'Use Python 3.12 for this environment.' }
if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv pip install --python $EnvPython -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
} else {
    & $EnvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $EnvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
Write-Output "Ready: $EnvPython"
Write-Output "Pinned source: $ActualCommit"
