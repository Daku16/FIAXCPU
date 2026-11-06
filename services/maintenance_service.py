import fnmatch
import gc
import os
import shutil
import subprocess
import sys
import tempfile
import time

import psutil
from flask import current_app, has_app_context

from domain.enums import EstadoIncidenciaEnum, TipoIncidenciaEnum
from domain.models import db, IncidenciaDetectada, AccionCorrectiva, get_utc_now
from services.audit_service import AuditService
from services.comparison_service import ComparisonService
from services.diagnostic_service import (
    CPU_ALTA_PCT, DISCO_BAJO_GB, DNS_ENTRADAS_ALTAS, DiagnosticService, RAM_MEDIA_PCT, TEMP_ALTO_ARCHIVOS, TEMP_ALTO_MB,
)

# Elementos de otros programas o del sistema que nunca se tocan al purgar.
TEMP_PROTEGIDOS = ("_MEI*", "systemd-private-*", "snap-private-tmp", ".X11-unix", ".ICE-unix", ".XIM-unix", ".font-unix")

_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}

PROCEDIMIENTOS = {
    "temporales": ("LIMPIEZA_TEMPORALES", "Limpieza de archivos temporales"),
    "dns": ("VACIADO_CACHE_DNS", "Vaciado de caché DNS"),
    "memoria": ("OPTIMIZACION_MEMORIA", "Optimización de memoria RAM"),
    "global": ("OPTIMIZACION_INTEGRAL", "Mantenimiento rápido integral"),
}


class MaintenanceService:
    @staticmethod
    def _temp_min_age_seconds():
        horas = current_app.config.get("TEMP_MIN_AGE_HOURS", 1) if has_app_context() else 1
        return horas * 3600

    @staticmethod
    def _last_use(info):
        # Windows bloquea los archivos abiertos y actualiza el acceso de forma poco fiable;
        # en Linux se pueden borrar aunque estén abiertos, así que también se mira el último acceso.
        return info.st_mtime if os.name == "nt" else max(info.st_mtime, info.st_atime)

    @classmethod
    def clean_temporary_files(cls):
        """Borra temporales antiguos sin tocar lo reciente, lo protegido ni los enlaces simbólicos."""
        temp_dir = tempfile.gettempdir()
        limite = time.time() - cls._temp_min_age_seconds()
        eliminados = omitidos = bytes_liberados = 0

        for root, dirs, files in os.walk(temp_dir, topdown=True):
            dirs[:] = [
                d for d in dirs
                if not os.path.islink(os.path.join(root, d))
                and not any(fnmatch.fnmatch(d, patron) for patron in TEMP_PROTEGIDOS)
            ]
            for nombre in files:
                ruta = os.path.join(root, nombre)
                try:
                    info = os.lstat(ruta)
                    if not os.path.isfile(ruta) or os.path.islink(ruta) or cls._last_use(info) > limite:
                        omitidos += 1
                        continue
                    os.remove(ruta)
                    bytes_liberados += info.st_size
                    eliminados += 1
                except OSError:
                    # Archivos en uso o de otro usuario: se conservan.
                    omitidos += 1

        # Quita las carpetas antiguas que quedaron vacías.
        for root, dirs, _ in os.walk(temp_dir, topdown=False):
            for nombre in dirs:
                ruta = os.path.join(root, nombre)
                try:
                    if (not os.path.islink(ruta)
                            and not any(fnmatch.fnmatch(nombre, patron) for patron in TEMP_PROTEGIDOS)
                            and os.lstat(ruta).st_mtime <= limite):
                        os.rmdir(ruta)
                except OSError:
                    pass

        mb_liberados = round(bytes_liberados / (1024 * 1024), 2)
        return {
            "success": True,
            "mensaje": f"Temporales eliminados: {eliminados} ({mb_liberados} MB). Conservados por estar en uso o ser recientes: {omitidos}.",
            "mb_liberados": mb_liberados,
            "archivos_eliminados": eliminados,
            "archivos_omitidos": omitidos,
            "directorio": temp_dir,
        }

    @staticmethod
    def _dns_commands():
        if os.name == "nt":
            return [["ipconfig", "/flushdns"]]
        if sys.platform == "darwin":
            return [["dscacheutil", "-flushcache"]]
        return [["resolvectl", "flush-caches"], ["systemd-resolve", "--flush-caches"]]

    @classmethod
    def flush_dns_cache(cls):
        """Vacía la caché DNS con el comando del sistema; informa si no fue posible."""
        ultimo_error = "Este sistema no tiene un servicio de caché DNS administrable."
        for comando in cls._dns_commands():
            if not shutil.which(comando[0]):
                continue
            try:
                res = subprocess.run(comando, capture_output=True, text=True, errors="replace", timeout=10, **_NO_WINDOW)
            except (OSError, subprocess.SubprocessError) as exc:
                ultimo_error = f"No se pudo ejecutar {comando[0]}: {exc}"
                continue
            if res.returncode == 0:
                return {
                    "success": True,
                    "mensaje": res.stdout.strip() or "Caché DNS vaciada correctamente.",
                    "comando": " ".join(comando),
                }
            ultimo_error = (res.stderr or res.stdout).strip() or f"{comando[0]} terminó con código {res.returncode}."
        return {"success": False, "mensaje": ultimo_error, "comando": None}

    @staticmethod
    def _trim_windows_working_sets():
        """Recorta el Working Set de los procesos accesibles y devuelve cuántos fueron."""
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        psapi.EmptyWorkingSet.argtypes = (wintypes.HANDLE,)
        PROCESS_SET_QUOTA_AND_QUERY = 0x0100 | 0x0400

        recortados = 0
        for pid in psutil.pids():
            handle = kernel32.OpenProcess(PROCESS_SET_QUOTA_AND_QUERY, False, pid)
            if handle:
                if psapi.EmptyWorkingSet(handle):
                    recortados += 1
                kernel32.CloseHandle(handle)
        return recortados

    @classmethod
    def optimize_memory(cls):
        """Recorta Working Sets en Windows; en otros sistemas informa que no aplica."""
        mem_antes = psutil.virtual_memory().percent
        gc.collect()
        recortados = cls._trim_windows_working_sets() if os.name == "nt" else None
        mem_despues = psutil.virtual_memory().percent

        if recortados is None:
            mensaje = "Este sistema operativo administra la memoria automáticamente: no se recortó ningún proceso."
        else:
            mensaje = f"Working Set recortado en {recortados} procesos. RAM: {mem_antes}% antes, {mem_despues}% después."
        return {
            "success": True,
            "aplicado": recortados is not None,
            "mensaje": mensaje,
            "procesos_recortados": recortados,
            "ram_antes": mem_antes,
            "ram_despues": mem_despues,
            "reduccion_porcentaje": round(mem_antes - mem_despues, 1),
        }

    @staticmethod
    def audit_processes():
        """Mide qué procesos consumen más CPU. Es informativo: no modifica ninguno."""
        try:
            procesos = list(psutil.process_iter(["name"]))
        except (psutil.Error, OSError):
            return {"success": False, "mensaje": "No se pudo consultar la lista de procesos."}
        for proc in procesos:
            try:
                proc.cpu_percent(None)
            except psutil.Error:
                pass
        time.sleep(0.5)
        consumo = []
        for proc in procesos:
            try:
                consumo.append((proc.cpu_percent(None), proc.info.get("name") or str(proc.pid)))
            except psutil.Error:
                pass
        top = sorted(consumo, key=lambda item: item[0], reverse=True)[:5]
        detalle = ", ".join(f"{nombre} ({uso:.0f}%)" for uso, nombre in top)
        return {
            "success": True,
            "aplicado": False,
            "mensaje": f"Procesos con mayor consumo de CPU: {detalle}. Ciérrelos manualmente si no los necesita; FIAX no los modificó.",
        }

    @staticmethod
    def _condition_cleared(incidencia, accion, estado, ejecucion_ok):
        """Una incidencia se resuelve solo si la medición posterior confirma que desapareció."""
        if not ejecucion_ok:
            return False
        tipo = incidencia.tipo_incidencia
        if tipo == TipoIncidenciaEnum.SATURACION_RAM.value:
            return estado["ram_porcentaje"] < RAM_MEDIA_PCT
        if tipo == TipoIncidenciaEnum.ALTO_CONSUMO_CPU.value:
            return estado["cpu_porcentaje"] < CPU_ALTA_PCT
        if tipo == TipoIncidenciaEnum.ESPACIO_DISCO_BAJO.value:
            return estado["disco_libre_gb"] > DISCO_BAJO_GB
        if tipo == TipoIncidenciaEnum.CACHE_SOBREDIMENSIONADO.value:
            return estado["temp_mb"] < TEMP_ALTO_MB and estado["temp_archivos"] < TEMP_ALTO_ARCHIVOS
        if accion and accion.tipo_accion == "FLUSH_DNS":
            return estado["dns_entradas"] is None or estado["dns_entradas"] < DNS_ENTRADAS_ALTAS
        return False

    @classmethod
    def _reconcile_incidents(cls, resultados_por_accion, estado, incidencia_objetivo=None):
        """Registra lo ejecutado en las incidencias afectadas y cierra las verificadas."""
        incidencias = list(ComparisonService.pending_incidents())
        if incidencia_objetivo is not None and incidencia_objetivo not in incidencias:
            incidencias.append(incidencia_objetivo)

        resueltas = []
        for incidencia in incidencias:
            accion = AccionCorrectiva.query.filter_by(incidencia_id=incidencia.id).first()
            if not accion or accion.tipo_accion not in resultados_por_accion:
                continue
            resultado = resultados_por_accion[accion.tipo_accion]
            accion.autorizada_por_usuario = 1
            accion.ejecutada_con_exito = 1 if resultado.get("success") else 0
            accion.fecha_ejecucion = get_utc_now()
            accion.resultado_log = resultado.get("mensaje")
            if cls._condition_cleared(incidencia, accion, estado, resultado.get("success")):
                incidencia.estado = EstadoIncidenciaEnum.RESUELTA.value
                resueltas.append(incidencia.id)
        db.session.commit()
        return resueltas

    @classmethod
    def run_procedure(cls, tipo, user_id=None):
        """Ejecuta un procedimiento y guarda la comparación entre estado inicial y final."""
        if tipo not in PROCEDIMIENTOS:
            return {"success": False, "error": f"Procedimiento desconocido: {tipo}"}
        accion_audit, titulo = PROCEDIMIENTOS[tipo]

        inicial = ComparisonService.capture_state()
        resultados, por_accion = {}, {}
        if tipo in ("temporales", "global"):
            resultados["temporales"] = por_accion["LIMPIEZA_TEMP"] = cls.clean_temporary_files()
        if tipo in ("dns", "global"):
            resultados["dns"] = por_accion["FLUSH_DNS"] = cls.flush_dns_cache()
        if tipo in ("memoria", "global"):
            resultados["memoria"] = por_accion["OPTIMIZAR_RAM"] = cls.optimize_memory()

        final = ComparisonService.capture_state()
        resueltas = cls._reconcile_incidents(por_accion, final)
        ComparisonService.refresh_score(final)

        exito = all(r.get("success") for r in resultados.values())
        mensaje = " ".join(r.get("mensaje", "") for r in resultados.values())
        comparacion = ComparisonService.save(tipo, titulo, inicial, final, exito, mensaje, usuario_id=user_id)
        AuditService.registrar(
            accion=accion_audit,
            modulo="MANTENIMIENTO",
            detalles=f"{mensaje} Score: {inicial['score_salud']} -> {final['score_salud']}.",
            nivel="INFO" if exito else "WARNING",
            usuario_id=user_id,
        )
        return {
            "success": exito,
            "tipo": tipo,
            "mensaje": mensaje,
            "resultados": resultados,
            "incidencias_resueltas": resueltas,
            "nuevo_score": final["score_salud"],
            "comparacion": comparacion,
        }

    @classmethod
    def resolve_incident(cls, incidencia_id: int, user_id: int = None):
        """Aplica la acción de una incidencia y la cierra solo si la verificación lo confirma."""
        incidencia = db.session.get(IncidenciaDetectada, incidencia_id)
        if not incidencia:
            return {"success": False, "error": "Incidencia no encontrada."}
        if incidencia.estado == EstadoIncidenciaEnum.RESUELTA.value:
            return {"success": False, "error": "Esta incidencia ya ha sido resuelta previamente."}
        if incidencia.estado == EstadoIncidenciaEnum.REEMPLAZADA.value:
            return {"success": False, "error": "Esta incidencia pertenece a un diagnóstico anterior. Revise el más reciente."}

        accion = AccionCorrectiva.query.filter_by(incidencia_id=incidencia.id).first()
        tipo_accion = accion.tipo_accion if accion else None
        ejecutores = {
            "LIMPIEZA_TEMP": cls.clean_temporary_files,
            "FLUSH_DNS": cls.flush_dns_cache,
            "OPTIMIZAR_RAM": cls.optimize_memory,
            "AUDITAR_PROCESOS": cls.audit_processes,
        }
        if tipo_accion not in ejecutores:
            return {"success": False, "error": "Esta incidencia no tiene una acción automática disponible."}

        inicial = ComparisonService.capture_state()
        resultado = ejecutores[tipo_accion]()
        final = ComparisonService.capture_state()
        resueltas = cls._reconcile_incidents({tipo_accion: resultado}, final, incidencia_objetivo=incidencia)
        ComparisonService.refresh_score(final)

        resuelta = incidencia.id in resueltas
        mensaje = resultado.get("mensaje", "")
        if resultado.get("success") and not resuelta:
            mensaje += " La medición posterior indica que la condición persiste: la incidencia sigue pendiente."
        titulo = f"Incidencia #{incidencia.id}: {incidencia.tipo_incidencia.replace('_', ' ').title()}"
        comparacion = ComparisonService.save(
            "incidencia", titulo, inicial, final, resultado.get("success"), mensaje,
            usuario_id=user_id, incidencia_id=incidencia.id,
        )
        AuditService.registrar(
            accion="RESOLVER_INCIDENCIA" if resuelta else "INTENTO_RESOLVER_INCIDENCIA",
            modulo="MANTENIMIENTO",
            detalles=f"Incidencia #{incidencia.id} ({incidencia.tipo_incidencia}): {mensaje} Score: {inicial['score_salud']} -> {final['score_salud']}.",
            nivel="INFO" if resuelta else "WARNING",
            usuario_id=user_id,
        )
        return {
            "success": bool(resultado.get("success")),
            "resuelta": resuelta,
            "incidencia": incidencia.to_dict(),
            "accion": accion.to_dict(),
            "resultado": {**resultado, "mensaje": mensaje},
            "error": None if resultado.get("success") else mensaje,
            "incidencias_resueltas": resueltas,
            "nuevo_score": final["score_salud"],
            "incidencias_pendientes_count": final["incidencias_pendientes"],
            "comparacion": comparacion,
        }
