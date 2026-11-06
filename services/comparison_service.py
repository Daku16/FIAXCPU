"""Mide el estado del equipo y compara el antes y el después de cada procedimiento."""
import json

from domain.enums import EstadoIncidenciaEnum
from domain.models import db, EjecucionMantenimiento, IncidenciaDetectada, SesionDiagnostico, format_local
from services.diagnostic_service import DiagnosticService
from services.telemetry_service import TelemetryService

# clave, etiqueta, unidad, sentido favorable (+1 sube, -1 baja, 0 sin juicio), tolerancia, depende de otros procesos
METRICAS = (
    ("score_salud", "Score de salud", "/100", 1, 0, False),
    ("incidencias_pendientes", "Incidencias pendientes", "", -1, 0, False),
    ("temp_mb", "Archivos temporales", " MB", -1, 0.1, False),
    ("temp_archivos", "Cantidad de temporales", "", -1, 0, False),
    ("disco_libre_gb", "Disco libre", " GB", 1, 0.01, False),
    ("dns_entradas", "Entradas en caché DNS", "", -1, 0, False),
    ("ram_porcentaje", "RAM en uso", "%", -1, 0.5, True),
    ("ram_usada_gb", "RAM usada", " GB", -1, 0.05, True),
    ("cpu_porcentaje", "CPU en uso", "%", -1, 5, True),
    ("procesos_activos", "Procesos activos", "", 0, 0, True),
)


class ComparisonService:
    @staticmethod
    def pending_incidents():
        """Incidencias pendientes de la última sesión de diagnóstico."""
        sesion = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).first()
        if not sesion:
            return []
        return IncidenciaDetectada.query.filter_by(
            diagnostico_id=sesion.id, estado=EstadoIncidenciaEnum.PENDIENTE.value
        ).all()

    @classmethod
    def capture_state(cls):
        metrics = TelemetryService.get_live_metrics(cpu_interval=0.5)
        temp_mb, temp_archivos = DiagnosticService.inspect_temp_cache_size()
        state = {
            "cpu_porcentaje": metrics["cpu"]["usage_percent"],
            "ram_porcentaje": metrics["ram"]["usage_percent"],
            "ram_usada_gb": metrics["ram"]["used_gb"],
            "disco_libre_gb": metrics["disk"]["free_gb"],
            "procesos_activos": metrics["procesos_activos"],
            "temp_mb": temp_mb,
            "temp_archivos": temp_archivos,
            "dns_entradas": DiagnosticService.count_dns_cache_entries(),
        }
        return cls.refresh_score(state)

    @classmethod
    def refresh_score(cls, state):
        """Calcula score e incidencias con la misma fórmula para el antes y el después."""
        pendientes = cls.pending_incidents()
        state["incidencias_pendientes"] = len(pendientes)
        state["score_salud"] = DiagnosticService.calculate_health_score(
            cpu_pct=state["cpu_porcentaje"],
            ram_pct=state["ram_porcentaje"],
            disk_free_gb=state["disco_libre_gb"],
            temp_mb=state["temp_mb"],
            incidents=[{"severidad": i.nivel_severidad} for i in pendientes],
        )
        return state

    @staticmethod
    def build_rows(inicial, final):
        filas = []
        for clave, etiqueta, unidad, sentido, tolerancia, volatil in METRICAS:
            antes, despues = inicial.get(clave), final.get(clave)
            if antes is None or despues is None:
                continue
            delta = round(despues - antes, 2)
            if sentido == 0 or abs(delta) <= tolerancia:
                tendencia = "igual"
            else:
                tendencia = "mejora" if delta * sentido > 0 else "empeora"
            filas.append({
                "clave": clave,
                "etiqueta": etiqueta,
                "unidad": unidad,
                "inicial": antes,
                "final": despues,
                "cambio": delta,
                "tendencia": tendencia,
                "volatil": volatil,
            })
        return filas

    @classmethod
    def save(cls, tipo, titulo, inicial, final, exito, mensaje, usuario_id=None, incidencia_id=None):
        sesion = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).first()
        ejecucion = EjecucionMantenimiento(
            tipo=tipo,
            titulo=titulo,
            sesion_id=sesion.id if sesion else None,
            incidencia_id=incidencia_id,
            usuario_id=usuario_id,
            exito=1 if exito else 0,
            mensaje=mensaje,
            estado_inicial_json=json.dumps(inicial),
            estado_final_json=json.dumps(final),
        )
        db.session.add(ejecucion)
        db.session.commit()
        return cls.to_dict(ejecucion)

    @classmethod
    def to_dict(cls, ejecucion):
        return {
            "id": ejecucion.id,
            "tipo": ejecucion.tipo,
            "titulo": ejecucion.titulo,
            "fecha_hora": format_local(ejecucion.fecha_hora),
            "usuario_nombre": ejecucion.usuario.nombre_completo if ejecucion.usuario else "Sistema",
            "exito": bool(ejecucion.exito),
            "mensaje": ejecucion.mensaje,
            "filas": cls.build_rows(ejecucion.estado_inicial, ejecucion.estado_final),
        }

    @classmethod
    def history(cls, limite=20):
        ejecuciones = EjecucionMantenimiento.query.order_by(EjecucionMantenimiento.id.desc()).limit(limite).all()
        return [cls.to_dict(e) for e in ejecuciones]
