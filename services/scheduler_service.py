"""Mantenimiento automático: registra la tarea en el programador del sistema operativo y la verifica.

Windows usa el Programador de tareas (schtasks con una definición XML) y Linux/macOS el crontab
del usuario. La aplicación solo considera activo el mantenimiento cuando el sistema operativo
confirma que la tarea quedó registrada.
"""
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

from flask import current_app

from domain.models import db, ProgramacionMantenimiento, get_utc_now
from services.audit_service import AuditService
from services.maintenance_service import MaintenanceService, PROCEDIMIENTOS

FRECUENCIAS = ("DIARIA", "SEMANAL", "MENSUAL")
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_DIAS_XML = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MESES_XML = ("January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December")
_HORA_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}

RUN_FLAG = "--run-maintenance"


class SchedulerError(Exception):
    pass


def _run(comando, **kwargs):
    try:
        return subprocess.run(comando, capture_output=True, text=True, errors="replace",
                              timeout=30, **_NO_WINDOW, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SchedulerError(f"No se pudo ejecutar {comando[0]}: {exc}") from exc


def _salida(res):
    return (res.stderr or res.stdout or "").strip() or f"código {res.returncode}"


class WindowsTaskBackend:
    nombre = "Programador de tareas de Windows"
    TASK = "\\FIAX CPU\\Mantenimiento automatico"

    @staticmethod
    def build_xml(spec, comando):
        hora = spec["hora"]
        inicio = f"{datetime.now():%Y-%m-%d}T{hora}:00"
        if spec["frecuencia"] == "DIARIA":
            horario = "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
        elif spec["frecuencia"] == "SEMANAL":
            horario = (f"<ScheduleByWeek><DaysOfWeek><{_DIAS_XML[spec['dia_semana']]} /></DaysOfWeek>"
                       "<WeeksInterval>1</WeeksInterval></ScheduleByWeek>")
        else:
            meses = "".join(f"<{m} />" for m in _MESES_XML)
            horario = (f"<ScheduleByMonth><DaysOfMonth><Day>{spec['dia_mes']}</Day></DaysOfMonth>"
                       f"<Months>{meses}</Months></ScheduleByMonth>")
        argumentos = subprocess.list2cmdline(comando[1:])
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>FIAX CPU</Author>
    <Description>Mantenimiento automático de FIAX CPU ({escape(PROCEDIMIENTOS[spec['tipo']][1])}).</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{inicio}</StartBoundary>
      <Enabled>true</Enabled>
      {horario}
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>{escape(comando[0])}</Command>
      <Arguments>{escape(argumentos)}</Arguments>
    </Exec>
  </Actions>
</Task>
"""

    def install(self, spec, comando):
        fd, ruta = tempfile.mkstemp(prefix="fiax-tarea-", suffix=".xml")
        try:
            with os.fdopen(fd, "w", encoding="utf-16") as handle:
                handle.write(self.build_xml(spec, comando))
            res = _run(["schtasks", "/Create", "/TN", self.TASK, "/XML", ruta, "/F"])
        finally:
            try:
                os.remove(ruta)
            except OSError:
                pass
        if res.returncode != 0:
            raise SchedulerError(f"El Programador de tareas rechazó la tarea: {_salida(res)}")

    def remove(self):
        if self.query()["registrada"]:
            res = _run(["schtasks", "/Delete", "/TN", self.TASK, "/F"])
            if res.returncode != 0:
                raise SchedulerError(f"No se pudo eliminar la tarea: {_salida(res)}")

    def _next_run_time(self):
        """Próxima ejecución según Windows (independiente del idioma del sistema)."""
        carpeta, nombre = self.TASK.rsplit("\\", 1)
        script = (f"(Get-ScheduledTaskInfo -TaskPath '{carpeta}\\' -TaskName '{nombre}')"
                  ".NextRunTime.ToString('yyyy-MM-dd HH:mm')")
        try:
            res = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
        except SchedulerError:
            return None
        valor = res.stdout.strip()
        return valor if res.returncode == 0 and re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", valor) else None

    def query(self):
        res = _run(["schtasks", "/Query", "/TN", self.TASK, "/XML"])
        registrada = res.returncode == 0 and RUN_FLAG in res.stdout
        return {
            "registrada": registrada,
            "identificador": self.TASK,
            "proxima_ejecucion": self._next_run_time() if registrada else None,
        }


class CronBackend:
    nombre = "cron (crontab del usuario)"
    MARCA = "# FIAX-CPU mantenimiento automatico"

    @staticmethod
    def build_line(spec, comando):
        hh, mm = (int(x) for x in spec["hora"].split(":"))
        if spec["frecuencia"] == "DIARIA":
            dia_mes, dia_semana = "*", "*"
        elif spec["frecuencia"] == "SEMANAL":
            dia_mes, dia_semana = "*", str((spec["dia_semana"] + 1) % 7)  # cron: 0 = domingo
        else:
            dia_mes, dia_semana = str(spec["dia_mes"]), "*"
        return f"{mm} {hh} {dia_mes} * {dia_semana} {shlex.join(comando)} >/dev/null 2>&1 {CronBackend.MARCA}"

    def _read(self):
        if not shutil.which("crontab"):
            raise SchedulerError("Este equipo no tiene el comando crontab instalado.")
        res = _run(["crontab", "-l"])
        if res.returncode != 0:
            if "no crontab" in (res.stderr or "").lower():
                return []
            raise SchedulerError(f"No se pudo leer el crontab: {_salida(res)}")
        return res.stdout.splitlines()

    def _write(self, lineas):
        contenido = "\n".join(lineas).strip("\n")
        res = _run(["crontab", "-"], input=(contenido + "\n") if contenido else "")
        if res.returncode != 0:
            raise SchedulerError(f"No se pudo guardar el crontab: {_salida(res)}")

    def install(self, spec, comando):
        lineas = [l for l in self._read() if self.MARCA not in l]
        lineas.append(self.build_line(spec, comando))
        self._write(lineas)

    def remove(self):
        lineas = self._read()
        restantes = [l for l in lineas if self.MARCA not in l]
        if len(restantes) != len(lineas):
            self._write(restantes)

    def query(self):
        linea = next((l for l in self._read() if self.MARCA in l and RUN_FLAG in l), None)
        return {"registrada": linea is not None, "identificador": linea, "proxima_ejecucion": None}


class MemoryBackend:
    """Programador simulado para pruebas: nunca toca el sistema operativo."""
    nombre = "Programador simulado (pruebas)"
    tareas = {}
    fallar_al_instalar = False

    def install(self, spec, comando):
        if self.fallar_al_instalar:
            raise SchedulerError("Acceso denegado (simulado).")
        MemoryBackend.tareas["fiax"] = {"spec": dict(spec), "comando": list(comando)}

    def remove(self):
        MemoryBackend.tareas.pop("fiax", None)

    def query(self):
        tarea = MemoryBackend.tareas.get("fiax")
        return {"registrada": tarea is not None, "identificador": "fiax" if tarea else None, "proxima_ejecucion": None}


class SchedulerService:
    @staticmethod
    def backend():
        eleccion = current_app.config.get("SCHEDULER_BACKEND", "auto")
        if eleccion == "memoria":
            return MemoryBackend()
        if eleccion == "windows" or (eleccion == "auto" and os.name == "nt"):
            return WindowsTaskBackend()
        return CronBackend()

    @staticmethod
    def get_config():
        config = db.session.get(ProgramacionMantenimiento, 1)
        if not config:
            config = ProgramacionMantenimiento(id=1)
            db.session.add(config)
            db.session.commit()
        return config

    @staticmethod
    def validate(data):
        tipo = data.get("tipo", "global")
        if tipo not in PROCEDIMIENTOS:
            raise ValueError(f"Procedimiento desconocido: {tipo}")
        frecuencia = str(data.get("frecuencia", "SEMANAL")).upper()
        if frecuencia not in FRECUENCIAS:
            raise ValueError("La frecuencia debe ser diaria, semanal o mensual.")
        hora = str(data.get("hora", "03:00")).strip()
        if not _HORA_RE.match(hora):
            raise ValueError("La hora debe tener el formato HH:MM (24 horas).")
        try:
            dia_semana = int(data.get("dia_semana", 0))
            dia_mes = int(data.get("dia_mes", 1))
        except (TypeError, ValueError):
            raise ValueError("Día inválido.")
        if not 0 <= dia_semana <= 6:
            raise ValueError("El día de la semana es inválido.")
        if not 1 <= dia_mes <= 28:
            raise ValueError("El día del mes debe estar entre 1 y 28 para que exista en todos los meses.")
        return {"tipo": tipo, "frecuencia": frecuencia, "hora": hora, "dia_semana": dia_semana, "dia_mes": dia_mes}

    @staticmethod
    def describe(spec):
        if spec["frecuencia"] == "DIARIA":
            cuando = "Todos los días"
        elif spec["frecuencia"] == "SEMANAL":
            cuando = f"Cada {DIAS[spec['dia_semana']]}"
        else:
            cuando = f"El día {spec['dia_mes']} de cada mes"
        return f"{cuando} a las {spec['hora']} · {PROCEDIMIENTOS[spec['tipo']][1]}"

    @staticmethod
    def next_run(spec, ahora=None):
        ahora = ahora or datetime.now()
        hh, mm = (int(x) for x in spec["hora"].split(":"))
        candidato = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if spec["frecuencia"] == "DIARIA":
            if candidato <= ahora:
                candidato += timedelta(days=1)
        elif spec["frecuencia"] == "SEMANAL":
            candidato += timedelta(days=(spec["dia_semana"] - candidato.weekday()) % 7)
            if candidato <= ahora:
                candidato += timedelta(days=7)
        else:
            candidato = candidato.replace(day=spec["dia_mes"])
            if candidato <= ahora:
                anio, mes = (candidato.year + 1, 1) if candidato.month == 12 else (candidato.year, candidato.month + 1)
                candidato = candidato.replace(year=anio, month=mes)
        return candidato

    @staticmethod
    def build_command(tipo):
        """Comando que el programador ejecutará: el mismo ejecutable y la misma base de datos."""
        if getattr(sys, "frozen", False):
            comando = [sys.executable]
        else:
            interprete = sys.executable
            if os.name == "nt":
                sin_consola = os.path.join(os.path.dirname(interprete), "pythonw.exe")
                interprete = sin_consola if os.path.exists(sin_consola) else interprete
            raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            comando = [interprete, os.path.join(raiz, "fiax_launcher.py")]
        return comando + [RUN_FLAG, tipo, "--env", current_app.config.get("CONFIG_NAME", "prod"),
                          "--instance", current_app.instance_path]

    @classmethod
    def status(cls):
        config = cls.get_config()
        spec = cls.validate(config.to_dict())
        backend = cls.backend()
        try:
            sistema = backend.query()
            error = None
        except SchedulerError as exc:
            sistema, error = {"registrada": False, "identificador": None, "proxima_ejecucion": None}, str(exc)
        activo = bool(config.activo)
        registrada = sistema["registrada"]
        proxima = sistema.get("proxima_ejecucion")
        if registrada and not proxima:
            proxima = f"{cls.next_run(spec):%Y-%m-%d %H:%M}"
        return {
            "success": True,
            "config": config.to_dict(),
            "descripcion": cls.describe(spec),
            "programador": backend.nombre,
            "registrada_en_sistema": registrada,
            "identificador": sistema.get("identificador"),
            "proxima_ejecucion": proxima if registrada else None,
            "confirmado": activo and registrada,
            # La configuración dice una cosa y el sistema operativo otra (p. ej. borraron la tarea a mano).
            "inconsistente": activo != registrada and error is None,
            "error": error,
        }

    @classmethod
    def configure(cls, data, user_id=None):
        """Activa o desactiva el mantenimiento automático y verifica el resultado en el sistema."""
        config = cls.get_config()
        activar = bool(data.get("activo"))
        spec = cls.validate({**config.to_dict(), **data}) if activar else cls.validate(config.to_dict())
        backend = cls.backend()

        try:
            if activar:
                backend.install(spec, cls.build_command(spec["tipo"]))
            else:
                backend.remove()
            registrada = backend.query()["registrada"]
        except SchedulerError as exc:
            AuditService.registrar(accion="ERROR_PROGRAMAR_MANTENIMIENTO", modulo="MANTENIMIENTO",
                                   detalles=str(exc), nivel="ERROR", usuario_id=user_id)
            return {**cls.status(), "success": False, "error": str(exc)}

        if registrada != activar:
            error = ("El programador no muestra la tarea después de crearla." if activar
                     else "La tarea sigue registrada en el programador después de eliminarla.")
            AuditService.registrar(accion="ERROR_PROGRAMAR_MANTENIMIENTO", modulo="MANTENIMIENTO",
                                   detalles=error, nivel="ERROR", usuario_id=user_id)
            return {**cls.status(), "success": False, "error": error}

        for campo, valor in spec.items():
            setattr(config, campo, valor)
        config.activo = 1 if activar else 0
        config.confirmado_en = get_utc_now() if activar else None
        config.actualizado_por = user_id
        db.session.commit()

        AuditService.registrar(
            accion="PROGRAMAR_MANTENIMIENTO_AUTOMATICO" if activar else "DESACTIVAR_MANTENIMIENTO_AUTOMATICO",
            modulo="MANTENIMIENTO",
            detalles=(f"{cls.describe(spec)}. Registrado y verificado en {backend.nombre}." if activar
                      else f"Tarea eliminada de {backend.nombre}."),
            usuario_id=user_id,
        )
        return cls.status()

    @classmethod
    def run_scheduled(cls, tipo):
        """Lo invoca el programador del sistema operativo, sin servidor web ni sesión."""
        resultado = MaintenanceService.run_procedure(tipo, user_id=None, origen="PROGRAMADO")
        config = cls.get_config()
        config.ultima_ejecucion = get_utc_now()
        config.ultimo_resultado = ("Exitoso. " if resultado.get("success") else "Con errores. ") + (
            resultado.get("mensaje") or resultado.get("error") or "")
        db.session.commit()
        return resultado
