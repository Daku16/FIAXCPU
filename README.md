# FIAX CPU

Diagnóstico y mantenimiento del equipo, con comparación del estado inicial y final de cada procedimiento.

## Instalar

| Sistema | Archivo | Cómo |
|---|---|---|
| Windows | `FIAX-CPU-<versión>.exe` | Doble clic. No requiere instalación. |
| Debian / Ubuntu | `fiax-cpu_<versión>_amd64.deb` | `sudo apt install ./fiax-cpu_<versión>_amd64.deb` |
| Fedora / RHEL | `fiax-cpu-<versión>-1.x86_64.rpm` | `sudo dnf install ./fiax-cpu-<versión>-1.x86_64.rpm` |

La aplicación abre el navegador y solo acepta conexiones desde el mismo equipo. La cuenta creada en la primera ejecución es la del Administrador. Los datos quedan en `%LOCALAPPDATA%\FIAXCPU` (Windows) o `~/.local/share/fiaxcpu` (Linux) y se conservan al actualizar.

## Publicar una versión

1. Cambie `APP_VERSION` en `config.py`.
2. Cree y suba una etiqueta: `git tag v1.2.0 && git push origin v1.2.0`.

GitHub Actions ejecuta las pruebas, genera el `.exe`, el `.deb` y el `.rpm`, prueba que arranquen y los publica en *Releases*. También se puede lanzar a mano desde la pestaña *Actions*, sin publicar.

Para generarlos localmente: `packaging/build_windows.ps1` en Windows o `packaging/build_linux.sh` en Linux (requiere `rpm` y `pip install -r requirements-build.txt`). Cada instalador debe construirse en su propio sistema.

## Desarrollo

```bash
pip install -r requirements.txt
python app.py                       # http://127.0.0.1:5000
python -m unittest tests.test_fiax
```

`python app.py` crea las cuentas de demostración `admin@fiax.com / admin123` y `tecnico@fiax.com / tecnico123`. La versión instalable no las incluye. Use `FLASK_DEBUG=1` para activar el depurador.

Las pruebas usan una base de datos en memoria y una carpeta temporal aislada.
