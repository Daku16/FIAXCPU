# Genera dist\FIAX-CPU-<versión>.exe. Ejecutar en Windows desde la raíz del proyecto.
$ErrorActionPreference = "Stop"
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/fiax.spec
$version = python -c "from config import Config; print(Config.APP_VERSION)"
Move-Item -Force dist\FIAX-CPU.exe "dist\FIAX-CPU-$version.exe"
Write-Host "Listo: dist\FIAX-CPU-$version.exe"
