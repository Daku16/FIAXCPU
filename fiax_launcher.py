"""Punto de entrada de la versión de escritorio: sirve la aplicación solo en este equipo."""
import argparse
import json
import logging
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

HOST = "127.0.0.1"
DEFAULT_PORT = 5000


def _state_path(data_dir):
    return os.path.join(data_dir, "instancia.json")


def _running_url(data_dir):
    """URL de una instancia que ya esté en ejecución, si existe."""
    try:
        with open(_state_path(data_dir), encoding="utf-8") as handle:
            url = json.load(handle)["url"]
        with urllib.request.urlopen(f"{url}/healthz", timeout=2) as res:
            return url if json.load(res).get("app") == "fiax-cpu" else None
    except (OSError, ValueError, KeyError):
        return None


def _pick_port(preferred):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(prog="fiax-cpu", description="FIAX CPU - Mantenimiento del equipo")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="puerto local preferido")
    parser.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    parser.add_argument("--version", action="store_true", help="mostrar la versión y salir")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    os.environ["FIAX_ENV"] = "prod"
    from config import Config
    if args.version:
        print(Config.APP_VERSION)
        return 0

    from runtime_paths import user_data_dir
    data_dir = user_data_dir()
    logging.basicConfig(filename=os.path.join(data_dir, "fiax.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    existing = _running_url(data_dir)
    if existing:
        print(f"FIAX CPU ya está en ejecución: {existing}")
        if not args.no_browser:
            webbrowser.open(existing)
        return 0

    from waitress import serve
    import app as fiax

    fiax.app.config["ALLOW_SHUTDOWN"] = True
    fiax.setup_initial_data()

    port = _pick_port(args.port)
    url = f"http://{HOST}:{port}"
    with open(_state_path(data_dir), "w", encoding="utf-8") as handle:
        json.dump({"url": url, "pid": os.getpid()}, handle)

    print(f"FIAX CPU {Config.APP_VERSION} en {url}")
    print(f"Datos: {data_dir}")
    print("Para salir use 'Cerrar aplicación' en el menú o cierre esta ventana.")
    if not args.no_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    serve(fiax.app, host=HOST, port=port, threads=8, ident="FIAX CPU")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.exception("Fallo al iniciar FIAX CPU")
        raise
