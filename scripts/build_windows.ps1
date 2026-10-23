$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed' }
npm ci --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'frontend build failed' }
$schema = Get-ChildItem (Join-Path $root 'docs/spec') -Filter '*.sql' | Select-Object -First 1
if (-not $schema) { throw 'Schema SQL not found' }
pyinstaller --noconfirm --clean --onedir --name CET4StudyOS --exclude-module torch --exclude-module pandas --exclude-module scipy --exclude-module numpy --exclude-module pytest --exclude-module matplotlib --exclude-module IPython --add-data 'frontend/dist;frontend/dist' --add-data "$($schema.FullName);docs/spec" launcher/windows_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
& (Join-Path $root 'dist/CET4StudyOS/CET4StudyOS.exe') --self-test
if ($LASTEXITCODE -ne 0) { throw 'Bundle self-test failed' }
$compiler = @(
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe',
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) { throw 'Inno Setup compiler not found' }
& $compiler 'installer/cet4.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
Get-FileHash 'artifacts/CET4-Study-OS-0.1.0-Setup.exe' -Algorithm SHA256 | Format-List
