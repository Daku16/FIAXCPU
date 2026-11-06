import os
import re
import shutil
import stat
import subprocess
import tempfile
from domain.models import db, SesionDiagnostico, MetricaRendimiento, IncidenciaDetectada, AccionCorrectiva, get_utc_now
from domain.enums import SeveridadEnum, EstadoIncidenciaEnum, TipoIncidenciaEnum, EstadoDiagnosticoEnum
from services.telemetry_service import TelemetryService
from services.audit_service import AuditService

# Límites a partir de los cuales el diagnóstico abre incidencias.
RAM_ALTA_PCT = 80.0
RAM_MEDIA_PCT = 65.0
CPU_ALTA_PCT = 80.0
DISCO_BAJO_GB = 20.0
TEMP_ALTO_MB = 250.0
TEMP_ALTO_ARCHIVOS = 200
DNS_ENTRADAS_ALTAS = 100

_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}


class DiagnosticService:
    @staticmethod
    def inspect_temp_cache_size():
        """Calcula el tamaño y conteo de archivos residuales en el directorio temporal, con subcarpetas."""
        total_bytes = 0
        file_count = 0
        for root, dirs, files in os.walk(tempfile.gettempdir()):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for nombre in files:
                try:
                    info = os.lstat(os.path.join(root, nombre))
                except OSError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    total_bytes += info.st_size
                    file_count += 1
        return round(total_bytes / (1024 * 1024), 1), file_count

    @staticmethod
    def parse_windows_dns_cache(salida):
        """Cuenta registros de `ipconfig /displaydns`; el separador no depende del idioma."""
        return sum(1 for linea in salida.splitlines() if linea.strip() and set(linea.strip()) == {"-"})

    @classmethod
    def count_dns_cache_entries(cls):
        """Entradas reales en caché DNS, o None si el sistema no permite medirlas."""
        try:
            if os.name == "nt":
                res = subprocess.run(["ipconfig", "/displaydns"], capture_output=True, text=True,
                                     errors="replace", timeout=10, **_NO_WINDOW)
                return cls.parse_windows_dns_cache(res.stdout) if res.returncode == 0 else None
            if shutil.which("resolvectl"):
                res = subprocess.run(["resolvectl", "statistics"], capture_output=True, text=True,
                                     errors="replace", timeout=5)
                encontrado = re.search(r"Current Cache Size:\s*(\d+)", res.stdout)
                return int(encontrado.group(1)) if encontrado else None
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    @staticmethod
    def calculate_health_score(cpu_pct, ram_pct, disk_free_gb, temp_mb, incidents):
        """
        Algoritmo Heurístico de Puntuación de Salud del Sistema (0 - 100).
        Fórmula ponderada con penalizaciones por estrés de hardware y severidad de incidencias.
        """
        score = 100.0

        # Penalizaciones por CPU
        if cpu_pct >= 85.0:
            score -= 18.0
        elif cpu_pct >= 70.0:
            score -= 9.0

        # Penalizaciones por RAM
        if ram_pct >= 88.0:
            score -= 22.0
        elif ram_pct >= 75.0:
            score -= 12.0
        elif ram_pct >= 60.0:
            score -= 5.0

        # Penalizaciones por Disco Libre
        if disk_free_gb <= 15.0:
            score -= 25.0
        elif disk_free_gb <= 35.0:
            score -= 10.0

        # Penalizaciones por Basura Temporal
        if temp_mb >= 1000.0:
            score -= 10.0
        elif temp_mb >= 300.0:
            score -= 5.0

        # Penalizaciones por incidencias activas detectadas
        for inc in incidents:
            sev = inc.get('severidad')
            if sev == SeveridadEnum.CRITICO.value:
                score -= 15.0
            elif sev == SeveridadEnum.ALTO.value:
                score -= 10.0
            elif sev == SeveridadEnum.MEDIO.value:
                score -= 5.0
            elif sev == SeveridadEnum.BAJO.value:
                score -= 2.0

        score = max(15, min(100, int(round(score))))
        return score

    @classmethod
    def execute_complete_diagnosis(cls, user_id=None):
        """Ejecuta un análisis heurístico integral del sistema y lo persiste en la base de datos."""
        try:
            equipo = TelemetryService.get_or_register_host_equipo()
            metrics = TelemetryService.get_live_metrics(cpu_interval=0.5)
        except Exception as exc:
            # Sin mediciones reales no se registra ningún diagnóstico.
            db.session.rollback()
            return {"success": False, "error": f"No se pudieron leer las métricas del equipo: {exc}"}
        
        cpu_pct = metrics['cpu']['usage_percent']
        ram_pct = metrics['ram']['usage_percent']
        disk_free_gb = metrics['disk']['free_gb']
        temp_mb, temp_files = cls.inspect_temp_cache_size()

        detected_incidents = []

        # 1. Heurística de Memoria RAM
        if ram_pct >= RAM_ALTA_PCT:
            detected_incidents.append({
                "tipo": TipoIncidenciaEnum.SATURACION_RAM.value,
                "componente": f"Memoria RAM ({ram_pct}% en uso)",
                "descripcion": f"La memoria física presenta saturación ({metrics['ram']['used_gb']} GB de {metrics['ram']['total_gb']} GB). Alto riesgo de contención y uso excesivo de archivo de paginación.",
                "severidad": SeveridadEnum.ALTO.value if ram_pct < 90 else SeveridadEnum.CRITICO.value,
                "solucion": "Optimizar espacio de memoria activa y recortar el Working Set de subprocesos inactivos.",
                "tipo_accion": "OPTIMIZAR_RAM"
            })
        elif ram_pct >= RAM_MEDIA_PCT:
            detected_incidents.append({
                "tipo": TipoIncidenciaEnum.SATURACION_RAM.value,
                "componente": f"Memoria RAM ({ram_pct}% en uso)",
                "descripcion": f"Consumo moderado-alto de memoria ({ram_pct}%). Hay {metrics['procesos_activos']} procesos en segundo plano consumiendo recursos.",
                "severidad": SeveridadEnum.MEDIO.value,
                "solucion": "Optimizar memoria residente en segundo plano.",
                "tipo_accion": "OPTIMIZAR_RAM"
            })

        # 2. Heurística de CPU
        if cpu_pct >= CPU_ALTA_PCT:
            detected_incidents.append({
                "tipo": TipoIncidenciaEnum.ALTO_CONSUMO_CPU.value,
                "componente": f"Procesador ({cpu_pct}% de carga)",
                "descripcion": f"Uso sostenido elevado de los {metrics['cpu']['cores_logical']} núcleos lógicos. Puede provocar degradación térmica y throttling.",
                "severidad": SeveridadEnum.CRITICO.value,
                "solucion": "Revisar procesos dominantes en segundo plano y balancear afinidad de CPU.",
                "tipo_accion": "AUDITAR_PROCESOS"
            })

        # 3. Heurística de Espacio en Disco
        if disk_free_gb <= DISCO_BAJO_GB:
            detected_incidents.append({
                "tipo": TipoIncidenciaEnum.ESPACIO_DISCO_BAJO.value,
                "componente": f"Disco del Sistema {metrics['disk']['drive']}",
                "descripcion": f"Quedan solo {disk_free_gb} GB libres en la unidad principal. El mínimo recomendado es de {DISCO_BAJO_GB:.0f} GB.",
                "severidad": SeveridadEnum.ALTO.value,
                "solucion": "Depurar residuos del sistema y ejecutar vaciado de almacenamiento temporal.",
                "tipo_accion": "LIMPIEZA_TEMP"
            })

        # 4. Heurística de Archivos Temporales y Caché
        if temp_mb >= TEMP_ALTO_MB or temp_files >= TEMP_ALTO_ARCHIVOS:
            detected_incidents.append({
                "tipo": TipoIncidenciaEnum.CACHE_SOBREDIMENSIONADO.value,
                "componente": "Directorio de Archivos Temporales",
                "descripcion": f"Se identificaron {temp_files} archivos residuales ocupando aproximadamente {temp_mb} MB en el espacio temporal del usuario.",
                "severidad": SeveridadEnum.MEDIO.value,
                "solucion": "Purgar de manera segura archivos temporales obsoletos para liberar espacio y acelerar lecturas.",
                "tipo_accion": "LIMPIEZA_TEMP"
            })

        # 5. Caché DNS: solo se reporta cuando se pudo medir y está realmente alta
        dns_entradas = cls.count_dns_cache_entries()
        if dns_entradas is not None and dns_entradas >= DNS_ENTRADAS_ALTAS:
            detected_incidents.append({
                "tipo": TipoIncidenciaEnum.CACHE_DNS_SATURADA.value,
                "componente": "Sub-sistema de Resolución DNS y Conectividad",
                "descripcion": f"La caché DNS local contiene {dns_entradas} entradas, lo que puede incluir registros obsoletos.",
                "severidad": SeveridadEnum.BAJO.value,
                "solucion": "Vaciar y refrescar la caché del cliente DNS.",
                "tipo_accion": "FLUSH_DNS"
            })

        # Cálculo del Health Score con la fórmula ponderada
        health_score = cls.calculate_health_score(cpu_pct, ram_pct, disk_free_gb, temp_mb, detected_incidents)

        estado_diag = EstadoDiagnosticoEnum.COMPLETADO.value
        if health_score < 60:
            estado_diag = EstadoDiagnosticoEnum.CRITICO.value
        elif health_score < 80:
            estado_diag = EstadoDiagnosticoEnum.CON_ADVERTENCIAS.value

        # Persistencia en Base de Datos (Transacción Atómica)
        try:
            sesion_previa = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).first()
            score_previo = sesion_previa.score_actual if sesion_previa else None

            # Lo que siga vigente vuelve a registrarse en esta sesión; lo anterior queda como historial.
            IncidenciaDetectada.query.filter_by(estado=EstadoIncidenciaEnum.PENDIENTE.value).update(
                {"estado": EstadoIncidenciaEnum.REEMPLAZADA.value}
            )

            sesion = SesionDiagnostico(
                equipo_id=equipo.id,
                usuario_id=user_id,
                fecha_hora=get_utc_now(),
                estado=estado_diag,
                score_salud=health_score,
                resumen=f"Diagnóstico heurístico finalizado: Score {health_score}/100. {len(detected_incidents)} incidencias analizadas."
            )
            db.session.add(sesion)
            db.session.flush()

            # Guardar Métricas
            metrica = MetricaRendimiento(
                diagnostico_id=sesion.id,
                uso_cpu_porcentaje=cpu_pct,
                uso_ram_porcentaje=ram_pct,
                ram_usada_gb=metrics['ram']['used_gb'],
                ram_libre_gb=metrics['ram']['free_gb'],
                disco_libre_gb=disk_free_gb,
                disco_usado_porcentaje=metrics['disk']['usage_percent'],
                procesos_activos=metrics['procesos_activos']
            )
            db.session.add(metrica)

            # Guardar Incidencias y sus Acciones Sugeridas
            incidencias_creadas = []
            for inc in detected_incidents:
                nueva_inc = IncidenciaDetectada(
                    diagnostico_id=sesion.id,
                    tipo_incidencia=inc['tipo'],
                    componente_afectado=inc['componente'],
                    descripcion=inc['descripcion'],
                    nivel_severidad=inc['severidad'],
                    estado=EstadoIncidenciaEnum.PENDIENTE.value
                )
                db.session.add(nueva_inc)
                db.session.flush()

                accion = AccionCorrectiva(
                    incidencia_id=nueva_inc.id,
                    solucion_recomendada=inc['solucion'],
                    tipo_accion=inc['tipo_accion'],
                    autorizada_por_usuario=0,
                    ejecutada_con_exito=0
                )
                db.session.add(accion)
                incidencias_creadas.append(nueva_inc)

            db.session.commit()

            # Registrar en Auditoría
            AuditService.registrar(
                accion="EJECUTAR_DIAGNOSTICO",
                modulo="DIAGNOSTICO",
                detalles=f"Diagnóstico completado en equipo {equipo.nombre_equipo}. Score: {health_score}/100, Incidencias: {len(detected_incidents)}",
                nivel="INFO" if health_score >= 70 else "WARNING",
                usuario_id=user_id
            )

            return {
                "success": True,
                "sesion_id": sesion.id,
                "score_salud": health_score,
                "score_previo": score_previo,
                "estado": estado_diag,
                "metricas": metrica.to_dict(),
                "incidencias": [i.to_dict() for i in incidencias_creadas],
                "equipo": equipo.to_dict()
            }
        except Exception as e:
            db.session.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def get_latest_diagnostic_summary():
        """Recupera la última sesión de diagnóstico con métricas e incidencias activas."""
        sesion = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).first()
        if not sesion:
            return None
        return {
            "sesion": sesion.to_dict(),
            "metricas": sesion.metricas.to_dict() if sesion.metricas else None,
            "incidencias": [i.to_dict() for i in sesion.incidencias]
        }

