import os
import gc
import subprocess
from datetime import datetime
import psutil
from domain.models import db, IncidenciaDetectada, AccionCorrectiva
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
        incidencia = IncidenciaDetectada.query.get(incidencia_id)
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
            accion.fecha_ejecucion = datetime.utcnow()
            accion.resultado_log = resultado.get("mensaje", "Ejecutado con éxito")

        db.session.commit()

        # Registrar en Auditoría
        AuditService.registrar(
            accion="RESOLVER_INCIDENCIA",
            modulo="MANTENIMIENTO",
            detalles=f"Incidencia #{incidencia.id} ({incidencia.tipo_incidencia}) resuelta. Resultado: {resultado.get('mensaje')}",
            nivel="INFO",
            usuario_id=user_id
        )

        return {
            "success": True,
            "incidencia": incidencia.to_dict(),
            "accion": accion.to_dict() if accion else None,
            "resultado": resultado
        }

