"""Rutas de recursos y datos, válidas tanto en desarrollo como en el ejecutable."""
import os
import secrets
import sys
from pathlib import Path

APP_DIR_NAME = "FIAXCPU"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts) -> str:
    """Ruta a recursos de solo lectura (plantillas y estáticos)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def user_data_dir() -> str:
    """Carpeta persistente por usuario: sobrevive a actualizaciones de la aplicación."""
    override = os.environ.get("FIAX_DATA_DIR")
    if override:
        path = Path(override)
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_DIR_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / APP_DIR_NAME.lower()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def load_or_create_secret(directory: str) -> str:
    """Devuelve la clave de sesión de esta instalación, creándola la primera vez."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "secret.key")
    try:
        with open(path, "r", encoding="ascii") as handle:
            value = handle.read().strip()
        if value:
            return value
    except FileNotFoundError:
        pass
    value = secrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(value)
    return value
