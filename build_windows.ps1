[CmdletBinding()]
param(
    [string]$Python = '',
    [string]$InnoCompiler = '',
    [switch]$SkipInstall
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Push-Location $PSScriptRoot
try {
    if (-not $Python) { $Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Create a Python 3.12 virtual environment first; see README.md.' }
    & $Python -c 'import sys; sys.exit(0 if sys.version_info[:2]==(3,12) and sys.maxsize>2**32 else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Wrong Python version or architecture.' }
    if (-not $SkipInstall) {
        & $Python -m pip install --disable-pip-version-check -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
    & $Python -m pytest -q --junitxml=docs/qa/tests.xml
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Release not built.' }
    Copy-Item -LiteralPath USER_GUIDE.md -Destination resources\USER_GUIDE.md -Force
    & $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller installer/MobileDesk.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    & $Python tools\release.py prepare
    if ($LASTEXITCODE -ne 0) { throw 'Release preparation failed.' }
    if (-not $InnoCompiler) {
        $candidates = @(
            (Join-Path $PSScriptRoot 'build\toolchain\inno\ISCC.exe'),
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
        )
        $found = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($found) { $candidates += $found.Source }
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate) { $InnoCompiler = $candidate; break }
        }
    }
    if ($InnoCompiler) {
        & $InnoCompiler installer\MobileDesk.iss
        if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
    } else {
        Write-Warning 'Inno Setup compiler not found. Portable release is available; installer recipe is in installer/MobileDesk.iss.'
    }
    & $Python tools\release.py archive
    if ($LASTEXITCODE -ne 0) { throw 'Release archive failed.' }
    Write-Output 'Built Mobile Desk. Run dist\MobileDesk\MobileDesk.exe. See dist\SHA256SUMS.txt.'
} finally {
    Pop-Location
}
