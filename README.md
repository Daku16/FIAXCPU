# FIAX CPU

Diagnóstico y mantenimiento del equipo, con comparación del estado inicial y final de cada procedimiento.

## Instalar

| Sistema | Archivo | Cómo |
|---|---|---|
| Windows | `FIAX-CPU-<versión>.exe` | Doble clic. No requiere instalación. |
| Debian / Ubuntu | `fiax-cpu_<versión>_amd64.deb` | `sudo apt install ./fiax-cpu_<versión>_amd64.deb` |
| Fedora / RHEL | `fiax-cpu-<versión>-1.x86_64.rpm` | `sudo dnf install ./fiax-cpu-<versión>-1.x86_64.rpm` |

La aplicación abre el navegador y solo acepta conexiones desde el mismo equipo. La cuenta creada en la primera ejecución es la del Administrador. Los datos quedan en `%LOCALAPPDATA%\FIAXCPU` (Windows) o `~/.local/share/fiaxcpu` (Linux) y se conservan al actualizar.

## Mantenimiento automático y reportes

- **Reportes de Mantenimiento** (menú lateral): filtra los procedimientos por año, mes, tipo, origen (manual o programado) y resultado, con resumen por mes y por procedimiento. *Exportar a Excel (CSV)* descarga el detalle.
- **Mantenimiento Automático** (Administrador y Técnico): al elegir *Sí* se registra la tarea en el Programador de tareas de Windows (`\FIAX CPU\Mantenimiento automatico`) o en el crontab del usuario en Linux. La aplicación lo marca como **ACTIVO** solo después de consultar al sistema y confirmar que la tarea existe; al elegir *No* la elimina y vuelve a verificar.
- La tarea ejecuta `FIAX-CPU --run-maintenance <tipo>` sin abrir el navegador y guarda el resultado en la misma base de datos, con origen *Programado*.

## Accesibilidad (WCAG 2.1 AA)

- Navegable solo con teclado: enlace *Saltar al contenido*, foco visible, filas de tablas que se abren con Enter y modales que retienen el foco, se cierran con Escape y lo devuelven al botón de origen.
- Compatible con lectores de pantalla: regiones (`nav`, `main`, secciones con nombre), etiquetas en todos los campos, errores asociados al campo y avisos anunciados (`aria-live`).
- Botón **Accesibilidad** (pie del menú lateral; flotante en el inicio de sesión): tema oscuro, claro o del sistema, contraste alto y tamaño de texto de 100 % a 150 %. Se recuerda en el navegador.
- Implementado en `static/a11y.css` y `static/a11y.js`, compartidos por todas las pantallas. Verificado con axe-core en los temas claro, oscuro y de alto contraste.

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
