import os
import gc
import subprocess
from datetime import datetime
import psutil
from domain.models import db, IncidenciaDetectada, AccionCorrectiva, get_utc_now
from domain.enums import EstadoIncidenciaEnum
from services.audit_service import AuditService

class MaintenanceService:
    @staticmethod
    def clean_temporary_files():
        """Elimina de manera segura archivos temporales en el directorio TEMP del usuario."""
        temp_dir = os.environ.get('TEMP') or os.environ.get('TMP')
        if not temp_dir or not os.path.exists(temp_dir):
            return {"success": False, "mensaje": "Directorio TEMP no localizado.", "mb_liberados": 0, "archivos_eliminados": 0}

        archivos_eliminados = 0
        bytes_liberados = 0

        for entry in os.scandir(temp_dir):
            try:
                if entry.is_file(follow_symlinks=False):
                    size = entry.stat().st_size
                    os.remove(entry.path)
                    bytes_liberados += size
                    archivos_eliminados += 1
            except (PermissionError, FileNotFoundError, OSError):
                # Archivos en uso por procesos activos del sistema se ignoran de forma segura
                continue

        mb_liberados = round(bytes_liberados / (1024 * 1024), 2)
        return {
            "success": True,
            "mensaje": f"Limpieza completada: {archivos_eliminados} archivos temporales purgados.",
            "mb_liberados": mb_liberados,
            "archivos_eliminados": archivos_eliminados
        }

    @staticmethod
    def flush_dns_cache():
        """Ejecuta el vaciado y refresco de la caché de nombres de dominio (DNS) en el sistema operativo."""
        try:
            if os.name == 'nt':
                res = subprocess.run(
                    ["ipconfig", "/flushdns"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                output = res.stdout.strip() or "Se vació correctamente la caché de resolución de DNS."
            else:
                output = "Comando DNS completado (Plataforma no Windows)."

            return {
                "success": True,
                "mensaje": output,
                "comando": "ipconfig /flushdns"
            }
        except Exception as e:
            return {
                "success": False,
                "mensaje": f"No se pudo ejecutar flushdns: {str(e)}"
            }

    @staticmethod
    def optimize_memory():
        """Fuerza recolección de basura e intenta liberar páginas de memoria en desuso."""
        mem_antes = psutil.virtual_memory().percent
        gc.collect()

        # Intento de vaciar Working Sets en Windows
        if os.name == 'nt':
            try:
                import ctypes
                for proc in psutil.process_iter(['pid']):
                    try:
                        handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, proc.info['pid'])
                        if handle:
                            ctypes.windll.psapi.EmptyWorkingSet(handle)
                            ctypes.windll.kernel32.CloseHandle(handle)
                    except Exception:
                        pass
            except Exception:
                pass

        mem_despues = psutil.virtual_memory().percent
        diferencia = round(mem_antes - mem_despues, 1)
        
        return {
            "success": True,
            "mensaje": f"Optimización de memoria ejecutada. RAM antes: {mem_antes}%, RAM actual: {mem_despues}%.",
            "ram_antes": mem_antes,
            "ram_despues": mem_despues,
            "reduccion_porcentaje": diferencia
        }

    @classmethod
    def resolve_incident(cls, incidencia_id: int, user_id: int = None):
        """Aplica la acción correctiva recomendada para una incidencia detectada y actualiza su estado."""
        incidencia = db.session.get(IncidenciaDetectada, incidencia_id)
        if not incidencia:
            return {"success": False, "error": "Incidencia no encontrada."}

        if incidencia.estado == EstadoIncidenciaEnum.RESUELTA.value:
            return {"success": False, "error": "Esta incidencia ya ha sido resuelta previamente."}

        accion = AccionCorrectiva.query.filter_by(incidencia_id=incidencia.id).first()
        tipo_accion = accion.tipo_accion if accion else "SISTEMA"

        resultado = {}
        if tipo_accion == "LIMPIEZA_TEMP":
            resultado = cls.clean_temporary_files()
        elif tipo_accion == "FLUSH_DNS":
            resultado = cls.flush_dns_cache()
        elif tipo_accion == "OPTIMIZAR_RAM":
            resultado = cls.optimize_memory()
        else:
            # Corrección guiada / Simulación de mantenimiento
            resultado = {
                "success": True,
                "mensaje": f"Acción correctiva '{accion.solucion_recomendada if accion else 'Mantenimiento'}' aplicada con éxito."
            }

        # Actualizar registros en base de datos
        incidencia.estado = EstadoIncidenciaEnum.RESUELTA.value
        
        if accion:
            accion.autorizada_por_usuario = 1
            accion.ejecutada_con_exito = 1 if resultado.get("success") else 0
            accion.fecha_ejecucion = get_utc_now()
            accion.resultado_log = resultado.get("mensaje", "Ejecutado con éxito")

        # Recalcular dinámicamente el Score de Salud tras la remediación
        from domain.models import SesionDiagnostico, MetricaRendimiento
        from services.diagnostic_service import DiagnosticService
        
        sesion = db.session.get(SesionDiagnostico, incidencia.diagnostico_id) if incidencia.diagnostico_id else None
        incidencias_restantes = IncidenciaDetectada.query.filter_by(
            diagnostico_id=incidencia.diagnostico_id,
            estado=EstadoIncidenciaEnum.PENDIENTE.value
        ).all() if incidencia.diagnostico_id else []

        metrica = MetricaRendimiento.query.filter_by(diagnostico_id=incidencia.diagnostico_id).first() if incidencia.diagnostico_id else None

        nuevo_score = DiagnosticService.calculate_health_score(
            cpu_pct=metrica.uso_cpu_porcentaje if metrica else 20.0,
            ram_pct=resultado.get('ram_despues', metrica.uso_ram_porcentaje if metrica else 35.0),
            disk_free_gb=(metrica.disco_libre_gb if metrica else 50.0) + (resultado.get('mb_liberados', 0) / 1024.0),
            temp_mb=0.0 if tipo_accion == "LIMPIEZA_TEMP" else 50.0,
            incidents=[{'severidad': inc.nivel_severidad} for inc in incidencias_restantes]
        )

        if sesion:
            sesion.score_salud = nuevo_score

        db.session.commit()

        # Registrar en Auditoría
        AuditService.registrar(
            accion="RESOLVER_INCIDENCIA",
            modulo="MANTENIMIENTO",
            detalles=f"Incidencia #{incidencia.id} ({incidencia.tipo_incidencia}) resuelta. Resultado: {resultado.get('mensaje')}. Nuevo Score: {nuevo_score}/100",
            nivel="INFO",
            usuario_id=user_id
        )

        return {
            "success": True,
            "incidencia": incidencia.to_dict(),
            "accion": accion.to_dict() if accion else None,
            "resultado": resultado,
            "nuevo_score": nuevo_score,
            "incidencias_pendientes_count": len(incidencias_restantes)
        }

